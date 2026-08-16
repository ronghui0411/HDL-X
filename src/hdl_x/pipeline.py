"""HDL-X VHDL 到 Verilog-2001 转换编排。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from hdl_x.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    UnsupportedConstructError,
    ValidationError,
)
from hdl_x.frontend.vhdl import VhdlFrontend
from hdl_x.generator.verilog import VerilogGenerator
from hdl_x.ir import Design
from hdl_x.transformer import NameStyle
from hdl_x.transformer.identifier_resolver import DesignIdentifierResolver
from hdl_x.transformer.type_lowering import DriverAnalysis
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
    frontend: VhdlFrontend | None = None,
    generator: VerilogGenerator | None = None,
) -> ConversionResult:
    """执行当前声明支持的真实 VHDL → Verilog-2001 pipeline。"""

    normalized_source = source_language.casefold()
    normalized_target = target_language.casefold()
    if normalized_source != "vhdl" or normalized_target != "verilog":
        raise UnsupportedConstructError(
            f"当前 MVP 不支持 {source_language} → {target_language}；"
            "仅支持 vhdl → verilog。",
            code="HDLX-CONVERSION-PATH",
        )

    active_options = options or ConversionOptions()
    active_frontend = frontend or VhdlFrontend()
    active_generator = generator or VerilogGenerator(name_style=active_options.name_style)

    design = active_frontend.parse_design(Path(source_path))
    if generator is None:
        name_resolver = DesignIdentifierResolver(active_options.name_style)
        lowered_design = DriverAnalysis().lower(name_resolver.lower(design))
        text = active_generator.generate_lowered(lowered_design)
    else:
        # 自定义 generator 仍通过其公共契约自行执行需要的 lowering。
        lowered_design = design
        text = active_generator.generate(design)
    diagnostics: list[Diagnostic] = []
    if active_frontend.unassociated_comments:
        if active_options.strict:
            first = active_frontend.unassociated_comments[0]
            raise UnsupportedConstructError(
                f"{len(active_frontend.unassociated_comments)} 条源码注释无法安全关联；"
                "strict 模式拒绝静默省略。",
                code="HDLX-COMMENT-UNASSOCIATED",
                source_span=first.source_span,
                suggestion="改用 --best-effort 允许省略非语义注释，或调整注释位置。",
            )
        diagnostics.append(
            Diagnostic(
                code="HDLX-COMMENT-UNASSOCIATED",
                message=(
                    f"{len(active_frontend.unassociated_comments)} 条源码注释无法安全关联，"
                    "已在 best-effort 模式省略。"
                ),
                severity=DiagnosticSeverity.WARNING,
            )
        )
    if active_options.validate:
        diagnostics.extend(_validate_generated_verilog(text))
    return ConversionResult(
        text=text,
        design=lowered_design,
        diagnostics=tuple(diagnostics),
    )


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
