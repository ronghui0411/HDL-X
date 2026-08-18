"""VHDL 与 Verilog 仿真语义边界的真实 frontend 回归。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import DiagnosticSeverity, UnsupportedConstructError
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.ghdl_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"


@pytest.mark.parametrize(
    "options",
    (
        ConversionOptions(strict=True),
        ConversionOptions(strict=False, best_effort=True),
    ),
)
def test_no_reset_std_logic_register_reports_initial_state_boundary(
    options: ConversionOptions,
) -> None:
    result = convert_file(FIXTURES / "m4_posedge.vhd", options=options)

    diagnostic = next(
        item for item in result.diagnostics if item.code == "HDLX-VHDL-INITIAL-STATE"
    )
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.file == str(FIXTURES / "m4_posedge.vhd")
    assert diagnostic.line == 14
    assert "std_logic" in diagnostic.message
    assert "q" in diagnostic.message


def test_no_reset_bit_register_reports_zero_vs_unknown_boundary(tmp_path: Path) -> None:
    source = tmp_path / "bit_register.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;

entity BitRegister is
  port (clk : in std_logic; d : in bit; q : out bit);
end entity;

architecture rtl of BitRegister is
begin
  p : process (clk)
  begin
    if rising_edge(clk) then
      q <= d;
    end if;
  end process;
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    diagnostic = next(
        item for item in result.diagnostics if item.code == "HDLX-VHDL-INITIAL-STATE"
    )
    assert diagnostic.line == 10
    assert "bit" in diagnostic.message
    assert "'0'" in diagnostic.message
    assert "X" in diagnostic.message


def test_reset_register_does_not_report_no_reset_boundary() -> None:
    result = convert_file(
        FIXTURES / "m4_async_low_reset.vhd",
        options=ConversionOptions(strict=True),
    )

    assert all(item.code != "HDLX-VHDL-INITIAL-STATE" for item in result.diagnostics)


def test_explicit_signal_initializer_is_rejected_with_location(tmp_path: Path) -> None:
    source = tmp_path / "signal_initializer.vhd"
    source.write_text(
        """entity SignalInitializer is
  port (y : out bit);
end entity;

architecture rtl of SignalInitializer is
  signal state : bit := '0';
begin
  y <= state;
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedConstructError) as captured:
        convert_file(source, options=ConversionOptions(strict=True))

    diagnostic = captured.value.diagnostic
    assert diagnostic.code == "HDLX-VHDL-SIGNAL-INITIALIZER"
    assert diagnostic.file == str(source)
    assert diagnostic.line == 6
    assert diagnostic.column == 10
