from pathlib import Path

import pytest

from hdl_x.frontend import SystemVerilogFrontend
from hdl_x.ir import BinaryExpr, SequentialProcess, VectorType
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"


def test_real_slang_preserves_async_high_and_sync_low_reset_semantics() -> None:
    design = SystemVerilogFrontend().parse_design(FIXTURES / "sv_reset_polarities.sv")
    async_process = next(
        item for item in design.modules[0].items if isinstance(item, SequentialProcess)
    )
    sync_process = next(
        item for item in design.modules[1].items if isinstance(item, SequentialProcess)
    )

    assert async_process.reset is not None
    assert async_process.reset.kind.value == "asynchronous"
    assert async_process.reset.active_level.value == "high"
    assert sync_process.reset is not None
    assert sync_process.reset.kind.value == "synchronous"
    assert sync_process.reset.active_level.value == "low"

    result = convert_file(
        FIXTURES / "sv_reset_polarities.sv",
        source_language="systemverilog",
        options=ConversionOptions(strict=True),
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "HDLX-SV-EDGE-XZ",
        "HDLX-SV-EDGE-XZ",
    ]
    assert "always @(posedge clk or posedge rst)" in result.text
    assert "always @(posedge clk)" in result.text
    assert "if (!rst_n)" in result.text


def test_real_slang_preserves_supported_signed_parameter_expressions() -> None:
    source = FIXTURES / "sv_signed_parameters.sv"
    design = SystemVerilogFrontend().parse_design(source)
    module = design.modules[0]

    assert [parameter.name for parameter in module.parameters] == ["WIDTH", "OUT_WIDTH"]
    assert isinstance(module.parameters[1].default, BinaryExpr)
    assert all(
        isinstance(port.rtl_type, VectorType) and port.rtl_type.signed
        for port in module.ports[:3]
    )

    result = convert_file(
        source,
        source_language="systemverilog",
        options=ConversionOptions(strict=True),
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "HDLX-SV-ALWAYS-COMB-TIME-ZERO"
    ]
    assert "parameter integer OUT_WIDTH = WIDTH + 1" in result.text
    assert "input wire signed [WIDTH - 1:0] a" in result.text
    assert "output reg signed [OUT_WIDTH - 1:0] y" in result.text
    assert "negative = a < 0;" in result.text
