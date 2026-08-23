from pathlib import Path

import pytest

from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"
GOLDEN = Path(__file__).parents[1] / "golden" / "sv_declarations.v"


def test_real_systemverilog_logic_wire_reg_signed_and_ternary_match_golden() -> None:
    result = convert_file(
        FIXTURES / "sv_declarations.sv",
        source_language="systemverilog",
        options=ConversionOptions(strict=True),
    )

    assert result.text.encode("utf-8") == GOLDEN.read_bytes()
    assert "reg selected;" in result.text
    assert "wire combined;" in result.text
    assert "input wire signed [WIDTH - 1:0] signed_a" in result.text
    assert "output reg signed [WIDTH - 1:0] signed_y" in result.text
    assert "reg signed [WIDTH - 1:0] signed_sum;" in result.text
