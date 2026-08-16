"""可独立测试的 HDL-X GUI 业务编排。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from hdl_x.diagnostics import HDLXError
from hdl_x.environment import EnvironmentItem, inspect_environment
from hdl_x.pipeline import ConversionOptions, ConversionResult, convert_file
from hdl_x.transformer import NameStyle


class GuiInputError(ValueError):
    """GUI 输入路径或选项无效。"""


@dataclass(frozen=True, slots=True)
class ConversionRequest:
    """一次桌面界面转换请求。"""

    source_path: Path
    output_path: Path
    strict: bool = True
    name_style: NameStyle = NameStyle.PRESERVE
    validate: bool = False


@dataclass(frozen=True, slots=True)
class ConversionReport:
    """转换结果与实际写入路径。"""

    result: ConversionResult
    output_path: Path


@dataclass(frozen=True, slots=True)
class EnvironmentReport:
    """doctor 信息及必需能力是否完整。"""

    text: str
    required_available: bool


Converter = Callable[..., ConversionResult]


def suggest_output_path(source_path: Path) -> Path:
    """按输入文件名建议同目录 Verilog 输出路径。"""

    return Path(source_path).with_suffix(".v")


def execute_conversion(
    request: ConversionRequest,
    *,
    converter: Converter = convert_file,
) -> ConversionReport:
    """验证请求、执行转换，并仅在成功后写入目标文件。"""

    request = validate_conversion_request(request)
    source_path = request.source_path
    output_path = request.output_path

    options = ConversionOptions(
        strict=request.strict,
        best_effort=not request.strict,
        name_style=request.name_style,
        validate=request.validate,
        verbose=False,
    )
    result = converter(
        source_path,
        source_language="vhdl",
        target_language="verilog",
        options=options,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.text, encoding="utf-8", newline="\n")
    return ConversionReport(result=result, output_path=output_path)


def validate_conversion_request(request: ConversionRequest) -> ConversionRequest:
    """规范化路径，并在启动耗时转换前拒绝危险输入。"""

    source_path = request.source_path.expanduser().resolve()
    output_path = request.output_path.expanduser().resolve()
    if not source_path.is_file():
        raise GuiInputError(f"输入 VHDL 文件不存在或不可读：{source_path}")
    if output_path == source_path:
        raise GuiInputError("输出文件不能覆盖输入 VHDL 源文件。")
    if output_path.exists() and output_path.is_dir():
        raise GuiInputError(f"输出路径是目录而不是文件：{output_path}")
    return ConversionRequest(
        source_path=source_path,
        output_path=output_path,
        strict=request.strict,
        name_style=request.name_style,
        validate=request.validate,
    )


def inspect_environment_report(
    *,
    inspector: Callable[[], Iterable[EnvironmentItem]] = inspect_environment,
) -> EnvironmentReport:
    """生成适合 GUI 日志窗显示的环境检查结果。"""

    lines: list[str] = []
    required_available = True
    for item in inspector():
        state = "可用" if item.available else "不可用"
        requirement = "必需" if item.required else "可选"
        version = f" {item.version}" if item.version else ""
        lines.append(f"{item.name}: {state}{version}（{requirement}）")
        lines.append(f"  {item.detail}")
        required_available &= item.available or not item.required
    return EnvironmentReport(
        text="\n".join(lines),
        required_available=required_available,
    )


def format_gui_error(error: Exception) -> str:
    """将异常转换为用户可读且保留结构化诊断的信息。"""

    if isinstance(error, HDLXError):
        diagnostic = error.diagnostic
        lines = [diagnostic.format()]
        if diagnostic.suggestion:
            lines.append(f"建议：{diagnostic.suggestion}")
        return "\n".join(lines)
    return f"{type(error).__name__}: {error}"


__all__ = [
    "ConversionReport",
    "ConversionRequest",
    "EnvironmentReport",
    "GuiInputError",
    "execute_conversion",
    "format_gui_error",
    "inspect_environment_report",
    "suggest_output_path",
    "validate_conversion_request",
]
