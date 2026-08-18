from pathlib import Path

import pytest

from hdl_x.diagnostics import SemanticError, UnsupportedConstructError
from hdl_x.generator import VerilogGenerator
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.ghdl_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"


def test_real_vhdl_to_verilog_pipeline_simple_logic() -> None:
    result = convert_file(
        FIXTURES / "simple_logic.vhd",
        options=ConversionOptions(strict=True),
    )

    assert result.design.top == "SimpleLogic"
    assert "module SimpleLogic (" in result.text
    assert "input wire a" in result.text
    assert "input wire b" in result.text
    assert "output wire y" in result.text
    assert "assign y = ~a & b ^ a;" in result.text


def test_default_pipeline_does_not_use_legacy_generate_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_legacy_generate(self: VerilogGenerator, design: object) -> str:
        raise AssertionError("pipeline must own Verilog lowering")

    monkeypatch.setattr(VerilogGenerator, "generate", reject_legacy_generate)

    result = convert_file(
        FIXTURES / "simple_logic.vhd",
        options=ConversionOptions(strict=True),
    )

    assert "assign y = ~a & b ^ a;" in result.text
    assert result.text.endswith("\n")


def test_real_vhdl_to_verilog_pipeline_vector_and_generic() -> None:
    result = convert_file(
        FIXTURES / "vector_logic.vhd",
        options=ConversionOptions(strict=True),
    )

    assert "parameter integer WIDTH = 8" in result.text
    assert "input wire [WIDTH - 1:0] a" in result.text
    assert "input wire [0:WIDTH - 1] b" in result.text
    assert "assign y = a ^ ~b;" in result.text


def test_requested_validation_reports_missing_optional_tools() -> None:
    result = convert_file(
        FIXTURES / "simple_logic.vhd",
        options=ConversionOptions(strict=True, validate=True),
    )

    assert {item.code for item in result.diagnostics} <= {"HDLX-VALIDATOR-UNAVAILABLE"}


def test_pipeline_supports_combinational_process() -> None:
    result = convert_file(
        FIXTURES / "if_else_mux.vhd",
        options=ConversionOptions(strict=True),
    )

    assert "output reg y" in result.text
    assert "always @(a or b or sel) begin : mux_p" in result.text
    assert "y = a;" in result.text
    assert "y = b;" in result.text


def test_strict_rejects_vhdl_signal_delta_dependency_in_process(
    tmp_path: Path,
) -> None:
    source = tmp_path / "process_signal_dependency.vhd"
    source.write_text(
        """entity ProcessSignalDependency is
    port (a : in bit; y : out bit);
end entity;
architecture rtl of ProcessSignalDependency is
    signal x : bit;
begin
    process(a)
    begin
        x <= a;
        y <= x;
    end process;
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-PROCESS-SIGNAL-DEPENDENCY"


def test_best_effort_never_skips_unsafe_wait(tmp_path: Path) -> None:
    source = tmp_path / "unsupported_wait.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity UnsupportedWait is
    port (a : in std_logic; y : out std_logic);
end entity;
architecture rtl of UnsupportedWait is
begin
    process
    begin
        wait on a;
    end process;
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedConstructError) as raised:
        convert_file(
            source,
            options=ConversionOptions(strict=False, best_effort=True),
        )

    assert raised.value.code == "HDLX-VHDL-WAIT"


def test_best_effort_reports_safe_unassociated_comment_omission(tmp_path: Path) -> None:
    source = tmp_path / "unassociated_comment.vhd"
    source.write_text(
        """-- file context comment
library ieee;
use ieee.std_logic_1164.all;
entity Commented is port (a : in bit; y : out bit); end entity;
architecture rtl of Commented is begin y <= a; end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(
        source,
        options=ConversionOptions(strict=False, best_effort=True),
    )

    assert {item.code for item in result.diagnostics} == {"HDLX-COMMENT-UNASSOCIATED"}
    diagnostic = result.diagnostics[0]
    assert diagnostic.source_span is not None
    assert diagnostic.line == 1
    assert diagnostic.column == 1
    assert "file context comment" in diagnostic.message
    assert diagnostic.source_snippet == "-- file context comment"


def test_strict_rejects_unassociated_comment_omission(tmp_path: Path) -> None:
    source = tmp_path / "strict_comment.vhd"
    source.write_text(
        """-- file context comment
library ieee;
use ieee.std_logic_1164.all;
entity StrictComment is port (a : in bit; y : out bit); end entity;
architecture rtl of StrictComment is begin y <= a; end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedConstructError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-COMMENT-UNASSOCIATED"
