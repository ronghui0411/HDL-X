"""真实 GHDL 与 Icarus 的组合/时序差分仿真。"""

from pathlib import Path

import pytest

from hdl_x.pipeline import ConversionOptions, convert_file
from hdl_x.verification import (
    DifferentialSimulationCase,
    detect_verification_toolchain,
    run_differential_simulation,
)

pytestmark = pytest.mark.semantic_equivalence

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"
TOOLS = detect_verification_toolchain()


def test_combinational_random_vectors_match_vhdl(tmp_path: Path) -> None:
    _require_differential_tools()
    source = FIXTURES / "m2_simple_and.vhd"
    generated = tmp_path / "m2_simple_and.v"
    generated.write_text(
        convert_file(source, options=ConversionOptions(strict=True)).text,
        encoding="utf-8",
    )
    vhdl_tb = tmp_path / "tb_comb.vhd"
    verilog_tb = tmp_path / "tb_comb.v"
    vhdl_tb.write_text(_COMBINATIONAL_VHDL_TB, encoding="utf-8")
    verilog_tb.write_text(_COMBINATIONAL_VERILOG_TB, encoding="utf-8")

    result = run_differential_simulation(
        DifferentialSimulationCase(
            vhdl_sources=(source,),
            vhdl_testbench=vhdl_tb,
            vhdl_top="tb_comb",
            verilog_sources=(generated,),
            verilog_testbench=verilog_tb,
            verilog_top="tb_comb",
        ),
        tmp_path,
        toolchain=TOOLS,
    )

    assert result.matched
    assert len(result.vhdl_trace) == 32


def test_sequential_clock_reset_enable_trace_matches_vhdl(tmp_path: Path) -> None:
    _require_differential_tools()
    source = FIXTURES / "v01_seq_reset_enable.vhd"
    generated = tmp_path / "v01_seq_reset_enable.v"
    generated.write_text(
        convert_file(source, options=ConversionOptions(strict=True)).text,
        encoding="utf-8",
    )
    vhdl_tb = tmp_path / "tb_seq.vhd"
    verilog_tb = tmp_path / "tb_seq.v"
    vhdl_tb.write_text(_SEQUENTIAL_VHDL_TB, encoding="utf-8")
    verilog_tb.write_text(_SEQUENTIAL_VERILOG_TB, encoding="utf-8")

    result = run_differential_simulation(
        DifferentialSimulationCase(
            vhdl_sources=(source,),
            vhdl_testbench=vhdl_tb,
            vhdl_top="tb_seq",
            verilog_sources=(generated,),
            verilog_testbench=verilog_tb,
            verilog_top="tb_seq",
        ),
        tmp_path,
        toolchain=TOOLS,
    )

    assert result.matched
    assert result.vhdl_trace == ("reset '0'", "load '1'", "hold '1'", "clear '0'")


def _require_differential_tools() -> None:
    if TOOLS.differential_available:
        return
    pytest.skip(
        "semantic equivalence not run; missing external tools: "
        + ", ".join(TOOLS.missing_differential)
    )


_COMBINATIONAL_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;

entity tb_comb is end entity;
architecture sim of tb_comb is
  signal a, b, y : std_logic := '0';
begin
  dut : entity work.M2SimpleAnd port map (a => a, b => b, y => y);
  stimulus : process
    variable seed : natural := 1;
  begin
    for i in 0 to 31 loop
      seed := (seed * 25173 + 13849) mod 65536;
      if (seed mod 2) = 0 then a <= '0'; else a <= '1'; end if;
      seed := (seed * 25173 + 13849) mod 65536;
      if (seed mod 2) = 0 then b <= '0'; else b <= '1'; end if;
      wait for 1 ns;
      report "HDLX-TRACE " & integer'image(i) & " " & std_logic'image(a) &
        " " & std_logic'image(b) & " " & std_logic'image(y);
    end loop;
    wait;
  end process;
end architecture;
"""

_COMBINATIONAL_VERILOG_TB = """`timescale 1ns/1ps
module tb_comb;
    reg a;
    reg b;
    wire y;
    integer i;
    integer seed;
    M2SimpleAnd dut (.a(a), .b(b), .y(y));
    initial begin
        a = 0;
        b = 0;
        seed = 1;
        for (i = 0; i < 32; i = i + 1) begin
            seed = (seed * 25173 + 13849) % 65536;
            a = seed % 2;
            seed = (seed * 25173 + 13849) % 65536;
            b = seed % 2;
            #1;
            $display("HDLX-TRACE %0d '%b' '%b' '%b'", i, a, b, y);
        end
        $finish;
    end
endmodule
"""

_SEQUENTIAL_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;

entity tb_seq is end entity;
architecture sim of tb_seq is
  signal clk : std_logic := '0';
  signal reset_n : std_logic := '1';
  signal enable : std_logic := '0';
  signal d : std_logic := '0';
  signal q : std_logic;
begin
  dut : entity work.V01SeqResetEnable
    port map (clk => clk, reset_n => reset_n, enable => enable, d => d, q => q);
  stimulus : process
  begin
    wait for 1 ns; reset_n <= '0'; wait for 1 ns;
    report "HDLX-TRACE reset " & std_logic'image(q);
    reset_n <= '1'; enable <= '1'; d <= '1';
    wait for 1 ns; clk <= '1'; wait for 1 ns;
    report "HDLX-TRACE load " & std_logic'image(q);
    clk <= '0'; enable <= '0'; d <= '0'; wait for 1 ns;
    clk <= '1'; wait for 1 ns;
    report "HDLX-TRACE hold " & std_logic'image(q);
    clk <= '0'; enable <= '1'; wait for 1 ns;
    clk <= '1'; wait for 1 ns;
    report "HDLX-TRACE clear " & std_logic'image(q);
    wait;
  end process;
end architecture;
"""

_SEQUENTIAL_VERILOG_TB = """`timescale 1ns/1ps
module tb_seq;
    reg clk;
    reg reset_n;
    reg enable;
    reg d;
    wire q;
    V01SeqResetEnable dut (
        .clk(clk), .reset_n(reset_n), .enable(enable), .d(d), .q(q)
    );
    initial begin
        clk = 0; reset_n = 1; enable = 0; d = 0;
        #1 reset_n = 0; #1;
        $display("HDLX-TRACE reset '%b'", q);
        reset_n = 1; enable = 1; d = 1;
        #1 clk = 1; #1;
        $display("HDLX-TRACE load '%b'", q);
        clk = 0; enable = 0; d = 0; #1;
        clk = 1; #1;
        $display("HDLX-TRACE hold '%b'", q);
        clk = 0; enable = 1; #1;
        clk = 1; #1;
        $display("HDLX-TRACE clear '%b'", q);
        $finish;
    end
endmodule
"""
