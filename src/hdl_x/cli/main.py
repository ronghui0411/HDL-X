"""HDL-X Typer 命令入口。"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from hdl_x.environment import inspect_environment
from hdl_x.transformer import NameStyle


class SourceLanguage(str, Enum):
    """当前声明支持的输入语言。"""

    VHDL = "vhdl"
    SYSTEMVERILOG = "systemverilog"
    SV = "sv"


class TargetLanguage(str, Enum):
    """当前声明支持的目标语言。"""

    VERILOG = "verilog"


app = typer.Typer(
    name="hdl-x",
    no_args_is_help=True,
    help="保持 RTL 语义与层次的离线 HDL 源码转换器。",
)


@app.command()
def doctor() -> None:
    """报告 frontend 与可选验证工具的真实状态。"""

    required_failure = False
    for item in inspect_environment():
        state = "available" if item.available else "unavailable"
        requirement = "required" if item.required else "optional"
        version = f" {item.version}" if item.version else ""
        typer.echo(f"{item.name}: {state}{version} ({requirement})")
        typer.echo(f"  {item.detail}")
        required_failure |= item.required and not item.available

    if required_failure:
        raise typer.Exit(code=1)


@app.command()
def convert(
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, resolve_path=True),
    ],
    source_language: Annotated[
        SourceLanguage,
        typer.Option("--from", help="输入 HDL 语言。"),
    ] = SourceLanguage.VHDL,
    target_language: Annotated[
        TargetLanguage,
        typer.Option("--to", help="输出 HDL 语言。"),
    ] = TargetLanguage.VERILOG,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="输出 Verilog 文件。"),
    ] = Path("output.v"),
    strict: Annotated[
        bool,
        typer.Option("--strict", help="遇到任何不支持构造时失败。"),
    ] = False,
    best_effort: Annotated[
        bool,
        typer.Option("--best-effort", help="仅允许跳过确认安全的非语义信息。"),
    ] = False,
    name_style: Annotated[
        NameStyle,
        typer.Option("--name-style", help="目标标识符样式。"),
    ] = NameStyle.PRESERVE,
    validate: Annotated[
        bool,
        typer.Option("--validate/--no-validate", help="调用可用验证器检查输出。"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="显示转换阶段信息。"),
    ] = False,
) -> None:
    """将受支持的 VHDL/SystemVerilog 子集转换为 Verilog-2001。"""

    if strict and best_effort:
        raise typer.BadParameter("--strict 与 --best-effort 不能同时启用")
    if not strict and not best_effort:
        strict = True

    # 延迟导入可让 doctor 在 frontend 不可用时仍报告完整环境。
    from hdl_x.pipeline import ConversionOptions, convert_file

    options = ConversionOptions(
        strict=strict,
        best_effort=best_effort,
        name_style=name_style,
        validate=validate,
        verbose=verbose,
    )
    try:
        result = convert_file(
            input_path,
            source_language=source_language.value,
            target_language=target_language.value,
            options=options,
        )
    except Exception as error:
        from hdl_x.diagnostics import HDLXError

        if isinstance(error, HDLXError):
            typer.echo(error.diagnostic.format(), err=True)
            raise typer.Exit(code=1) from error
        raise

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.text, encoding="utf-8", newline="\n")
    for diagnostic in result.diagnostics:
        typer.echo(diagnostic.format(), err=True)
    if verbose:
        typer.echo(f"generated: {output}")


if __name__ == "__main__":
    app()
