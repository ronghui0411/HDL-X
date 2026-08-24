"""HDL-X 已支持语言路径的 frontend、lowering 与 renderer 编排。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from hdl_x.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    HDLXError,
    UnsupportedConstructError,
    ValidationError,
)
from hdl_x.frontend import SystemVerilogFrontend, VerilogFrontend, VhdlFrontend
from hdl_x.generator import (
    VerilogGenerator,
    VerilogLowering,
    VerilogRenderer,
    VhdlGenerator,
    VhdlLowering,
    VhdlRenderer,
)
from hdl_x.ir import Comment, Design
from hdl_x.parser.ghdl import PyGhdlBackend
from hdl_x.transformer import (
    NameStyle,
    SemanticBoundaryAnalysis,
    SystemVerilogSemanticBoundaryAnalysis,
    VerilogToVhdlSemanticBoundaryAnalysis,
)
from hdl_x.validator import SlangValidator, ValidationStatus, YosysValidator


@dataclass(frozen=True, slots=True)
class ConversionOptions:
    """一次转换的用户可控策略。"""

    strict: bool = True
    best_effort: bool = False
    name_style: NameStyle = NameStyle.PRESERVE
    validate: bool = False
    verbose: bool = False

    def __post_init__(self) -> None:
        if self.strict == self.best_effort:
            raise ValueError("必须且只能选择 strict 或 best-effort 模式")


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """转换源码、canonical IR 与非致命诊断。"""

    text: str
    design: Design
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)


def convert_file(
    source_path: Path,
    *,
    source_language: str = "vhdl",
    target_language: str = "verilog",
    options: ConversionOptions | None = None,
    frontend: VhdlFrontend | SystemVerilogFrontend | VerilogFrontend | None = None,
    generator: VerilogGenerator | VhdlGenerator | None = None,
) -> ConversionResult:
    """执行已声明支持的真实 frontend → target HDL pipeline。"""

    normalized_source = source_language.casefold()
    normalized_target = target_language.casefold()
    to_verilog = (
        normalized_source in {"vhdl", "systemverilog", "sv"}
        and normalized_target == "verilog"
    )
    to_vhdl = (
        normalized_source in {"verilog", "v"}
        and normalized_target == "vhdl"
    )
    if not (to_verilog or to_vhdl):
        raise UnsupportedConstructError(
            f"当前 MVP 不支持 {source_language} → {target_language}；"
            "支持 vhdl/systemverilog → verilog 及 verilog → vhdl。",
            code="HDLX-CONVERSION-PATH",
        )

    active_options = options or ConversionOptions()
    if frontend is not None:
        active_frontend = frontend
    elif normalized_source == "vhdl":
        active_frontend = VhdlFrontend()
    elif normalized_source in {"systemverilog", "sv"}:
        active_frontend = SystemVerilogFrontend()
    else:
        active_frontend = VerilogFrontend()
    design = active_frontend.parse_design(Path(source_path))
    if normalized_source == "vhdl":
        boundary_analysis = SemanticBoundaryAnalysis()
    elif normalized_source in {"systemverilog", "sv"}:
        boundary_analysis = SystemVerilogSemanticBoundaryAnalysis()
    else:
        boundary_analysis = VerilogToVhdlSemanticBoundaryAnalysis()
    diagnostics: list[Diagnostic] = list(boundary_analysis.analyze(design))
    if generator is None:
        if to_verilog:
            render_ir = VerilogLowering(
                name_style=active_options.name_style,
                source_case_sensitive=normalized_source != "vhdl",
            ).lower(design)
            text = VerilogRenderer().render(render_ir)
        else:
            render_ir = VhdlLowering(name_style=active_options.name_style).lower(design)
            text = VhdlRenderer().render(render_ir)
        lowered_design = render_ir.design
    else:
        # 自定义 generator 仍通过其公共契约自行执行需要的 lowering。
        lowered_design = design
        text = generator.generate(design)
    if active_frontend.unassociated_comments:
        summary, snippet = _describe_omitted_comments(active_frontend.unassociated_comments)
        if active_options.strict:
            first = active_frontend.unassociated_comments[0]
            raise UnsupportedConstructError(
                f"{len(active_frontend.unassociated_comments)} 条源码注释无法安全关联；"
                f"strict 模式拒绝静默省略：{summary}。",
                code="HDLX-COMMENT-UNASSOCIATED",
                source_span=first.source_span,
                source_snippet=snippet,
                suggestion="改用 --best-effort 允许省略非语义注释，或调整注释位置。",
            )
        diagnostics.append(
            Diagnostic(
                code="HDLX-COMMENT-UNASSOCIATED",
                message=(
                    f"{len(active_frontend.unassociated_comments)} 条源码注释无法安全关联，"
                    f"已在 best-effort 模式省略：{summary}。"
                ),
                severity=DiagnosticSeverity.WARNING,
                source_span=active_frontend.unassociated_comments[0].source_span,
                source_snippet=snippet,
            )
        )
    if active_options.validate:
        diagnostics.extend(
            _validate_generated_verilog(text)
            if to_verilog
            else _validate_generated_vhdl(text)
        )
    return ConversionResult(
        text=text,
        design=lowered_design,
        diagnostics=tuple(diagnostics),
    )


def _describe_omitted_comments(comments: tuple[Comment, ...]) -> tuple[str, str]:
    """生成有限且稳定的省略注释位置摘要。"""

    entries: list[str] = []
    snippets: list[str] = []
    for comment in comments[:3]:
        if comment.source_span is None:
            location = "未知位置"
        else:
            start = comment.source_span.start
            location = f"{start.line}:{start.column}"
        text = comment.text.replace("\r", " ").replace("\n", " ")
        entries.append(f"{location} {text!r}")
        snippets.append(f"-- {text}")
    if len(comments) > 3:
        entries.append(f"另有 {len(comments) - 3} 条")
    return "; ".join(entries), "\n".join(snippets)


def _validate_generated_vhdl(text: str) -> list[Diagnostic]:
    """使用项目固定的 pyGHDL/libghdl 6.0.0 验证 VHDL-2008 输出。"""

    with TemporaryDirectory(prefix="hdl-x-validation-") as directory:
        output_path = Path(directory) / "generated.vhd"
        output_path.write_text(text, encoding="utf-8", newline="\n")
        try:
            PyGhdlBackend().validate(output_path)
        except HDLXError as error:
            raise ValidationError(
                f"pyGHDL/libghdl 拒绝生成的 VHDL：{error.diagnostic.message}",
                code="HDLX-VHDL-VALIDATION",
                source_span=error.diagnostic.source_span,
            ) from error
    return []


def _validate_generated_verilog(text: str) -> list[Diagnostic]:
    """使用可用目标工具验证临时 Verilog，不让 unavailable 冒充通过。"""

    diagnostics: list[Diagnostic] = []
    with TemporaryDirectory(prefix="hdl-x-validation-") as directory:
        output_path = Path(directory) / "generated.v"
        output_path.write_text(text, encoding="utf-8", newline="\n")
        for validator in (SlangValidator(), YosysValidator()):
            result = validator.validate(output_path)
            if result.status is ValidationStatus.UNAVAILABLE:
                diagnostics.append(
                    Diagnostic(
                        code="HDLX-VALIDATOR-UNAVAILABLE",
                        message=result.message,
                        severity=DiagnosticSeverity.WARNING,
                    )
                )
                continue
            if result.status is ValidationStatus.FAILED:
                details = result.stderr.strip() or result.stdout.strip() or result.message
                raise ValidationError(
                    f"{result.validator} 拒绝生成的 Verilog：{details}",
                    code="HDLX-VERILOG-VALIDATION",
                )
    return diagnostics


__all__ = ["ConversionOptions", "ConversionResult", "convert_file"]
