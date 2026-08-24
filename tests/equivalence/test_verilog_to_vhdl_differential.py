"""真实 Icarus 与 GHDL 的 Verilog-2001 到 VHDL-2008 差分仿真。"""

from __future__ import annotations

from pathlib import Path

import pytest

from hdl_x.pipeline import ConversionOptions, convert_file
from hdl_x.verification import (
    DifferentialSimulationCase,
    detect_verification_toolchain,
    run_differential_simulation,
)

pytestmark = [
    pytest.mark.slang_integration,
    pytest.mark.verilog_to_vhdl_equivalence,
]

FIXTURES = Path(__file__).parents[1] / "fixtures" / "verilog"
TOOLS = detect_verification_toolchain()


_COMBINATIONAL_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_v2v is end entity;
architecture sim of tb_v2v is
    signal a : std_logic := '0';
    signal b : std_logic := '0';
    signal enable : std_logic := '0';
    signal opcode : unsigned(1 downto 0) := (others => '0');
    signal y : std_logic;
begin
    dut : entity work.V3CombCase
        port map (a => a, b => b, enable => enable, opcode => opcode, y => y);

    stimulus : process
    begin
        for i in 0 to 15 loop
            if ((i / 8) mod 2) = 0 then enable <= '0'; else enable <= '1'; end if;
            if ((i / 4) mod 2) = 0 then a <= '0'; else a <= '1'; end if;
            if ((i / 2) mod 2) = 0 then b <= '0'; else b <= '1'; end if;
            opcode <= to_unsigned(i mod 4, opcode'length);
            wait for 1 ns;
            report "HDLX-TRACE " & integer'image(i) & " " & std_logic'image(y);
        end loop;
        wait;
    end process;
end architecture;
"""

_COMBINATIONAL_VERILOG_TB = """module tb_v2v;
    reg a;
    reg b;
    reg enable;
    reg [1:0] opcode;
    wire y;
    integer i;

    V3CombCase dut (.a(a), .b(b), .enable(enable), .opcode(opcode), .y(y));

    initial begin
        a = 0;
        b = 0;
        enable = 0;
        opcode = 0;
        for (i = 0; i < 16; i = i + 1) begin
            enable = (i / 8) % 2;
            a = (i / 4) % 2;
            b = (i / 2) % 2;
            opcode = i % 4;
            #1;
            $display("HDLX-TRACE %0d '%b'", i, y);
        end
        $finish;
    end
endmodule
"""

_RESET_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;

entity tb_v2v is end entity;
architecture sim of tb_v2v is
    signal clk : std_logic := '0';
    signal rst_n : std_logic := '1';
    signal rst : std_logic := '0';
    signal enable : std_logic := '0';
    signal d : std_logic := '0';
    signal q_async : std_logic;
    signal q_sync : std_logic;
begin
    async_dut : entity work.V3AsyncReset
        port map (clk => clk, rst_n => rst_n, enable => enable, d => d, q => q_async);
    sync_dut : entity work.V3SyncReset
        port map (clk => clk, rst => rst, d => d, q => q_sync);

    stimulus : process
    begin
        wait for 1 ns;
        rst_n <= '0';
        wait for 1 ns;
        report "HDLX-TRACE async-reset " & std_logic'image(q_async);

        rst_n <= '1';
        enable <= '1';
        d <= '1';
        wait for 1 ns;
        clk <= '1';
        wait for 1 ns;
        report "HDLX-TRACE async-load " & std_logic'image(q_async);

        enable <= '0';
        d <= '0';
        clk <= '0';
        wait for 1 ns;
        clk <= '1';
        wait for 1 ns;
        report "HDLX-TRACE async-hold " & std_logic'image(q_async);

        rst <= '1';
        wait for 1 ns;
        clk <= '0';
        wait for 1 ns;
        report "HDLX-TRACE sync-reset " & std_logic'image(q_sync);

        rst <= '0';
        d <= '1';
        wait for 1 ns;
        clk <= '1';
        wait for 1 ns;
        clk <= '0';
        wait for 1 ns;
        report "HDLX-TRACE sync-load " & std_logic'image(q_sync);
        wait;
    end process;
end architecture;
"""

_RESET_VERILOG_TB = """module tb_v2v;
    reg clk;
    reg rst_n;
    reg rst;
    reg enable;
    reg d;
    wire q_async;
    wire q_sync;

    V3AsyncReset async_dut (
        .clk(clk), .rst_n(rst_n), .enable(enable), .d(d), .q(q_async)
    );
    V3SyncReset sync_dut (.clk(clk), .rst(rst), .d(d), .q(q_sync));

    initial begin
        clk = 0;
        rst_n = 1;
        rst = 0;
        enable = 0;
        d = 0;

        #1;
        rst_n = 0;
        #1;
        $display("HDLX-TRACE async-reset '%b'", q_async);

        rst_n = 1;
        enable = 1;
        d = 1;
        #1;
        clk = 1;
        #1;
        $display("HDLX-TRACE async-load '%b'", q_async);

        enable = 0;
        d = 0;
        clk = 0;
        #1;
        clk = 1;
        #1;
        $display("HDLX-TRACE async-hold '%b'", q_async);

        rst = 1;
        #1;
        clk = 0;
        #1;
        $display("HDLX-TRACE sync-reset '%b'", q_sync);

        rst = 0;
        d = 1;
        #1;
        clk = 1;
        #1;
        clk = 0;
        #1;
        $display("HDLX-TRACE sync-load '%b'", q_sync);
        $finish;
    end
endmodule
"""

_SIGNED_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_v2v is end entity;
architecture sim of tb_v2v is
    signal a : signed(3 downto 0) := (others => '0');
    signal b : signed(3 downto 0) := (others => '0');
    signal y : signed(3 downto 0);
begin
    dut : entity work.V3SignedParameter
        generic map (WIDTH => 4)
        port map (a => a, b => b, y => y);

    stimulus : process
    begin
        for i in 0 to 15 loop
            a <= to_signed(i - 8, a'length);
            b <= to_signed(((i * 5) mod 16) - 8, b'length);
            wait for 1 ns;
            report "HDLX-TRACE " & integer'image(to_integer(a)) & " " &
                integer'image(to_integer(b)) & " " & integer'image(to_integer(y));
        end loop;
        wait;
    end process;
end architecture;
"""

_SIGNED_VERILOG_TB = """module tb_v2v;
    reg signed [3:0] a;
    reg signed [3:0] b;
    wire signed [3:0] y;
    integer i;

    V3SignedParameter #(.WIDTH(4)) dut (.a(a), .b(b), .y(y));

    initial begin
        a = 0;
        b = 0;
        for (i = 0; i < 16; i = i + 1) begin
            a = i - 8;
            b = ((i * 5) % 16) - 8;
            #1;
            $display("HDLX-TRACE %0d %0d %0d", a, b, y);
        end
        $finish;
    end
endmodule
"""

_HIERARCHY_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_v2v is end entity;
architecture sim of tb_v2v is
    signal a : unsigned(3 downto 0) := (others => '0');
    signal y : unsigned(3 downto 0);
begin
    dut : entity work.V3Hierarchy
        generic map (WIDTH => 4)
        port map (a => a, y => y);

    stimulus : process
    begin
        for i in 0 to 15 loop
            a <= to_unsigned(i, a'length);
            wait for 1 ns;
            report "HDLX-TRACE " & integer'image(i) & " " & integer'image(to_integer(y));
        end loop;
        wait;
    end process;
end architecture;
"""

_HIERARCHY_VERILOG_TB = """module tb_v2v;
    reg [3:0] a;
    wire [3:0] y;
    integer i;

    V3Hierarchy #(.WIDTH(4)) dut (.a(a), .y(y));

    initial begin
        a = 0;
        for (i = 0; i < 16; i = i + 1) begin
            a = i;
            #1;
            $display("HDLX-TRACE %0d %0d", i, y);
        end
        $finish;
    end
endmodule
"""

_FOR_GENERATE_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_v2v is end entity;
architecture sim of tb_v2v is
    signal a : unsigned(3 downto 0) := (others => '0');
    signal y : unsigned(3 downto 0);
begin
    dut : entity work.V3Generate
        generic map (WIDTH => 4)
        port map (a => a, y => y);

    stimulus : process
    begin
        for i in 0 to 15 loop
            a <= to_unsigned(i, a'length);
            wait for 1 ns;
            report "HDLX-TRACE " & integer'image(i) & " " & integer'image(to_integer(y));
        end loop;
        wait;
    end process;
end architecture;
"""

_FOR_GENERATE_VERILOG_TB = """module tb_v2v;
    reg [3:0] a;
    wire [3:0] y;
    integer i;

    V3Generate #(.WIDTH(4)) dut (.a(a), .y(y));

    initial begin
        a = 0;
        for (i = 0; i < 16; i = i + 1) begin
            a = i;
            #1;
            $display("HDLX-TRACE %0d %0d", i, y);
        end
        $finish;
    end
endmodule
"""

_IF_GENERATE_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;

entity tb_v2v is end entity;
architecture sim of tb_v2v is
    signal a : std_logic := '0';
    signal y : std_logic;
begin
    dut : entity work.V3IfGenerate
        generic map (ENABLE => 1)
        port map (a => a, y => y);

    stimulus : process
    begin
        for i in 0 to 7 loop
            if (i mod 2) = 0 then a <= '0'; else a <= '1'; end if;
            wait for 1 ns;
            report "HDLX-TRACE " & integer'image(i) & " " & std_logic'image(y);
        end loop;
        wait;
    end process;
end architecture;
"""

_IF_GENERATE_VERILOG_TB = """module tb_v2v;
    reg a;
    wire y;
    integer i;

    V3IfGenerate #(.ENABLE(1)) dut (.a(a), .y(y));

    initial begin
        a = 0;
        for (i = 0; i < 8; i = i + 1) begin
            a = i % 2;
            #1;
            $display("HDLX-TRACE %0d '%b'", i, y);
        end
        $finish;
    end
endmodule
"""

_INTEGER_VHDL_TB = """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_v2v is end entity;
architecture sim of tb_v2v is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal count : signed(31 downto 0);
begin
    dut : entity work.V3IntegerCounter
        port map (clk => clk, rst => rst, count => count);

    stimulus : process
    begin
        wait for 1 ns;
        clk <= '1';
        wait for 1 ns;
        report "HDLX-TRACE reset " & integer'image(to_integer(count));
        rst <= '0';
        for i in 1 to 4 loop
            clk <= '0';
            wait for 1 ns;
            clk <= '1';
            wait for 1 ns;
            report "HDLX-TRACE count " & integer'image(to_integer(count));
        end loop;
        wait;
    end process;
end architecture;
"""

_INTEGER_VERILOG_TB = """module tb_v2v;
    reg clk;
    reg rst;
    wire signed [31:0] count;
    integer i;

    V3IntegerCounter dut (.clk(clk), .rst(rst), .count(count));

    initial begin
        clk = 0;
        rst = 1;
        #1;
        clk = 1;
        #1;
        $display("HDLX-TRACE reset %0d", count);
        rst = 0;
        for (i = 1; i <= 4; i = i + 1) begin
            clk = 0;
            #1;
            clk = 1;
            #1;
            $display("HDLX-TRACE count %0d", count);
        end
        $finish;
    end
endmodule
"""

@pytest.mark.parametrize(
    ("fixture_name", "vhdl_testbench", "verilog_testbench", "trace_count"),
    [
        pytest.param(
            "v3_comb_case.v",
            _COMBINATIONAL_VHDL_TB,
            _COMBINATIONAL_VERILOG_TB,
            16,
            id="combinational-if-case",
        ),
        pytest.param(
            "v3_resets.v",
            _RESET_VHDL_TB,
            _RESET_VERILOG_TB,
            5,
            id="clock-reset-enable",
        ),
        pytest.param(
            "v3_signed_parameter.v",
            _SIGNED_VHDL_TB,
            _SIGNED_VERILOG_TB,
            16,
            id="signed-arithmetic-parameter",
        ),
        pytest.param(
            "v3_hierarchy.v",
            _HIERARCHY_VHDL_TB,
            _HIERARCHY_VERILOG_TB,
            16,
            id="named-positional-instances",
        ),
        pytest.param(
            "v3_generate_for.v",
            _FOR_GENERATE_VHDL_TB,
            _FOR_GENERATE_VERILOG_TB,
            16,
            id="for-generate-local-signal",
        ),
        pytest.param(
            "v3_generate_if.v",
            _IF_GENERATE_VHDL_TB,
            _IF_GENERATE_VERILOG_TB,
            8,
            id="if-generate",
        ),
        pytest.param(
            "v3_integer_counter.v",
            _INTEGER_VHDL_TB,
            _INTEGER_VERILOG_TB,
            5,
            id="integer-register",
        ),
    ],
)
def test_verilog_to_vhdl_trace_matches(
    fixture_name: str,
    vhdl_testbench: str,
    verilog_testbench: str,
    trace_count: int,
    tmp_path: Path,
) -> None:
    _require_differential_tools()
    source = FIXTURES / fixture_name
    generated = tmp_path / f"{source.stem}.vhd"
    generated.write_text(
        convert_file(
            source,
            source_language="verilog",
            target_language="vhdl",
            options=ConversionOptions(strict=True, validate=True),
        ).text,
        encoding="utf-8",
        newline="\n",
    )
    vhdl_tb = tmp_path / "tb_v2v.vhd"
    verilog_tb = tmp_path / "tb_v2v.v"
    vhdl_tb.write_text(vhdl_testbench, encoding="utf-8", newline="\n")
    verilog_tb.write_text(verilog_testbench, encoding="utf-8", newline="\n")

    result = run_differential_simulation(
        DifferentialSimulationCase(
            vhdl_sources=(generated,),
            vhdl_testbench=vhdl_tb,
            vhdl_top="tb_v2v",
            verilog_sources=(source,),
            verilog_testbench=verilog_tb,
            verilog_top="tb_v2v",
        ),
        tmp_path / "simulation",
        toolchain=TOOLS,
    )

    assert result.matched
    assert len(result.vhdl_trace) == trace_count


def _require_differential_tools() -> None:
    if TOOLS.differential_available:
        return
    pytest.skip(
        "Verilog to VHDL equivalence not run; missing external tools: "
        + ", ".join(TOOLS.missing_differential)
    )
