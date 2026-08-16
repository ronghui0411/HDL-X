from pathlib import Path

import pytest

from hdl_x.diagnostics import Diagnostic, DiagnosticSeverity, UnsupportedConstructError
from hdl_x.environment import EnvironmentItem
from hdl_x.gui.controller import (
    ConversionRequest,
    GuiInputError,
    execute_conversion,
    format_gui_error,
    inspect_environment_report,
    suggest_output_path,
)
from hdl_x.ir import Design, Module
from hdl_x.pipeline import ConversionResult
from hdl_x.transformer import NameStyle


def _conversion_result(text: str = "module Demo;\nendmodule\n") -> ConversionResult:
    return ConversionResult(
        text=text,
        design=Design(name="demo", modules=[Module(name="Demo")], top="Demo"),
    )


def test_suggest_output_path_replaces_vhdl_suffix() -> None:
    assert suggest_output_path(Path("rtl/core.vhd")) == Path("rtl/core.v")
    assert suggest_output_path(Path("rtl/core.vhdl")) == Path("rtl/core.v")


@pytest.mark.parametrize("strict", [True, False])
def test_execute_conversion_writes_only_successful_result(
    tmp_path: Path,
    strict: bool,
) -> None:
    source = tmp_path / "demo.vhd"
    source.write_text("entity Demo is end entity;", encoding="utf-8")
    output = tmp_path / "generated" / "demo.v"
    captured: dict[str, object] = {}

    def converter(source_path: Path, **kwargs: object) -> ConversionResult:
        captured["source_path"] = source_path
        captured.update(kwargs)
        return _conversion_result()

    report = execute_conversion(
        ConversionRequest(
            source_path=source,
            output_path=output,
            strict=strict,
            name_style=NameStyle.SNAKE_CASE,
            validate=True,
        ),
        converter=converter,
    )

    assert report.output_path == output.resolve()
    assert output.read_text(encoding="utf-8") == "module Demo;\nendmodule\n"
    assert captured["source_path"] == source.resolve()
    assert captured["source_language"] == "vhdl"
    assert captured["target_language"] == "verilog"
    options = captured["options"]
    assert options.strict is strict
    assert options.best_effort is not strict
    assert options.name_style is NameStyle.SNAKE_CASE
    assert options.validate is True


def test_execute_conversion_never_overwrites_source(tmp_path: Path) -> None:
    source = tmp_path / "danger.vhd"
    source.write_text("keep me", encoding="utf-8")

    with pytest.raises(GuiInputError, match="不能覆盖"):
        execute_conversion(
            ConversionRequest(source_path=source, output_path=source),
            converter=lambda *_args, **_kwargs: _conversion_result(),
        )

    assert source.read_text(encoding="utf-8") == "keep me"


def test_failed_conversion_does_not_create_output(tmp_path: Path) -> None:
    source = tmp_path / "unsupported.vhd"
    source.write_text("unsupported", encoding="utf-8")
    output = tmp_path / "unsupported.v"

    def converter(*_args: object, **_kwargs: object) -> ConversionResult:
        raise UnsupportedConstructError("不支持", code="HDLX-TEST")

    with pytest.raises(UnsupportedConstructError):
        execute_conversion(
            ConversionRequest(source_path=source, output_path=output),
            converter=converter,
        )

    assert not output.exists()


def test_execute_conversion_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(GuiInputError, match="不存在"):
        execute_conversion(
            ConversionRequest(
                source_path=tmp_path / "missing.vhd",
                output_path=tmp_path / "missing.v",
            )
        )


def test_environment_report_distinguishes_required_and_optional_tools() -> None:
    items = [
        EnvironmentItem("Python", True, "3.13", "python.exe", required=True),
        EnvironmentItem("GHDL frontend", False, None, "missing", required=True),
        EnvironmentItem("Yosys", False, None, "missing", required=False),
    ]

    report = inspect_environment_report(inspector=lambda: items)

    assert report.required_available is False
    assert "Python: 可用 3.13（必需）" in report.text
    assert "GHDL frontend: 不可用（必需）" in report.text
    assert "Yosys: 不可用（可选）" in report.text


def test_format_gui_error_preserves_diagnostic_and_suggestion() -> None:
    error = UnsupportedConstructError(
        diagnostic=Diagnostic(
            code="HDLX-GUI-TEST",
            message="无法转换",
            severity=DiagnosticSeverity.ERROR,
            file="demo.vhd",
            line=3,
            suggestion="修改输入",
        )
    )

    rendered = format_gui_error(error)

    assert "demo.vhd:3: error [HDLX-GUI-TEST]: 无法转换" in rendered
    assert "建议：修改输入" in rendered
