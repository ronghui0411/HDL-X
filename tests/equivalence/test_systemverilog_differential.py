"""真实 SystemVerilog frontend 输出的 Icarus 编译与组合/时序差分。"""

from pathlib import Path

import pytest

from hdl_x.pipeline import ConversionOptions, convert_file
from hdl_x.verification import (
    IcarusCompilationCase,
    SystemVerilogDifferentialSimulationCase,
    compile_iverilog,
    detect_verification_toolchain,
    run_systemverilog_differential_simulation,
)

pytestmark = [
    pytest.mark.slang_integration,
    pytest.mark.systemverilog_equivalence,
]

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"
TOOLS = detect_verification_toolchain()


def test_generated_combinational_verilog_compiles_as_verilog_2001(
    tmp_path: Path,
) -> None:
    _require_iverilog()
    generated = _convert(FIXTURES / "sv_comb_logic.sv", tmp_path)
    testbench = tmp_path / "tb_sv_comb.v"
    testbench.write_text(_COMBINATIONAL_TB, encoding="utf-8")

    result = compile_iverilog(
        IcarusCompilationCase(
            sources=(generated, testbench),
            top="tb_sv_comb",
            standard="2001",
        ),
        tmp_path / "compile-comb",
        toolchain=TOOLS,
    )

    assert result.succeeded


def test_generated_sequential_verilog_compiles_as_verilog_2001(
    tmp_path: Path,
) -> None:
    _require_iverilog()
    generated = _convert(FIXTURES / "sv_sequential.sv", tmp_path)
    testbench = tmp_path / "tb_sv_seq.v"
    testbench.write_text(_SEQUENTIAL_TB, encoding="utf-8")

    result = compile_iverilog(
        IcarusCompilationCase(
            sources=(generated, testbench),
            top="tb_sv_seq",
            standard="2001",
        ),
        tmp_path / "compile-seq",
        toolchain=TOOLS,
    )

    assert result.succeeded


def test_combinational_trace_matches_original_systemverilog(tmp_path: Path) -> None:
    _require_differential_tools()
    source = FIXTURES / "sv_comb_logic.sv"
    generated = _convert(source, tmp_path)
    reference_tb = tmp_path / "tb_sv_comb_reference.v"
    generated_tb = tmp_path / "tb_sv_comb_generated.v"
    reference_tb.write_text(_COMBINATIONAL_TB, encoding="utf-8")
    generated_tb.write_text(_COMBINATIONAL_TB, encoding="utf-8")

    result = run_systemverilog_differential_simulation(
        SystemVerilogDifferentialSimulationCase(
            systemverilog_sources=(source,),
            systemverilog_testbench=reference_tb,
            systemverilog_top="tb_sv_comb",
            verilog_sources=(generated,),
            verilog_testbench=generated_tb,
            verilog_top="tb_sv_comb",
        ),
        tmp_path / "diff-comb",
        toolchain=TOOLS,
    )

    assert result.matched
    assert len(result.systemverilog_trace) == 32


def test_clock_reset_enable_trace_matches_original_systemverilog(
    tmp_path: Path,
) -> None:
    _require_differential_tools()
    source = FIXTURES / "sv_sequential.sv"
    generated = _convert(source, tmp_path)
    reference_tb = tmp_path / "tb_sv_seq_reference.v"
    generated_tb = tmp_path / "tb_sv_seq_generated.v"
    reference_tb.write_text(_SEQUENTIAL_TB, encoding="utf-8")
    generated_tb.write_text(_SEQUENTIAL_TB, encoding="utf-8")

    result = run_systemverilog_differential_simulation(
        SystemVerilogDifferentialSimulationCase(
            systemverilog_sources=(source,),
            systemverilog_testbench=reference_tb,
            systemverilog_top="tb_sv_seq",
            verilog_sources=(generated,),
            verilog_testbench=generated_tb,
            verilog_top="tb_sv_seq",
        ),
        tmp_path / "diff-seq",
        toolchain=TOOLS,
    )

    assert result.matched
    assert result.systemverilog_trace == (
        "async-reset 0",
        "async-load a",
        "async-hold a",
        "sync-reset 0",
        "sync-load 3",
        "sync-hold 3",
    )


def _convert(source: Path, tmp_path: Path) -> Path:
    generated = tmp_path / f"{source.stem}.v"
    generated.write_text(
        convert_file(
            source,
            source_language="systemverilog",
            options=ConversionOptions(strict=True),
        ).text,
        encoding="utf-8",
    )
    return generated


def _require_iverilog() -> None:
    if TOOLS.iverilog is not None:
        return
    pytest.skip("SystemVerilog generated Verilog compile not run; missing external tool: iverilog")


def _require_differential_tools() -> None:
    if TOOLS.systemverilog_differential_available:
        return
    pytest.skip(
        "SystemVerilog/Verilog differential simulation not run; missing external tools: "
        + ", ".join(TOOLS.missing_systemverilog_differential)
    )


_COMBINATIONAL_TB = """`timescale 1ns/1ps
module tb_sv_comb;
    reg [3:0] a;
    reg [3:0] b;
    reg sel;
    reg [1:0] opcode;
    wire [3:0] y;
    wire parity;
    integer i;
    integer seed;

    SvComb #(.WIDTH(4)) dut (
        .a(a), .b(b), .sel(sel), .opcode(opcode), .y(y), .parity(parity)
    );

    initial begin
        a = 0;
        b = 0;
        sel = 0;
        opcode = 0;
        seed = 1;
        for (i = 0; i < 32; i = i + 1) begin
            seed = (seed * 25173 + 13849) % 65536;
            a = seed % 16;
            seed = (seed * 25173 + 13849) % 65536;
            b = seed % 16;
            seed = (seed * 25173 + 13849) % 65536;
            sel = seed % 2;
            seed = (seed * 25173 + 13849) % 65536;
            opcode = seed % 4;
            #1;
            $display(
                "HDLX-TRACE %0d %h %h %b %b %h %b",
                i, a, b, sel, opcode, y, parity
            );
        end
        $finish;
    end
endmodule
"""

_SEQUENTIAL_TB = """`timescale 1ns/1ps
module tb_sv_seq;
    reg clk;
    reg rst_n;
    reg rst;
    reg en;
    reg [3:0] d;
    wire [3:0] q_async;
    wire [3:0] q_sync;

    SvAsyncReg #(.WIDTH(4)) async_dut (
        .clk(clk), .rst_n(rst_n), .en(en), .d(d), .q(q_async)
    );
    SvSyncReg #(.WIDTH(4)) sync_dut (
        .clk(clk), .rst(rst), .en(en), .d(d), .q(q_sync)
    );

    initial begin
        clk = 0;
        rst_n = 1;
        rst = 0;
        en = 0;
        d = 0;

        #1 rst_n = 0;
        #1;
        $display("HDLX-TRACE async-reset %h", q_async);

        rst_n = 1;
        en = 1;
        d = 4'ha;
        #1 clk = 1;
        #1;
        $display("HDLX-TRACE async-load %h", q_async);

        en = 0;
        d = 4'h5;
        #1 clk = 0;
        #1;
        #1 clk = 1;
        #1;
        $display("HDLX-TRACE async-hold %h", q_async);

        rst = 1;
        #1 clk = 0;
        #1;
        $display("HDLX-TRACE sync-reset %h", q_sync);

        rst = 0;
        en = 1;
        d = 4'h3;
        #1 clk = 1;
        #1;
        #1 clk = 0;
        #1;
        $display("HDLX-TRACE sync-load %h", q_sync);

        en = 0;
        d = 4'hf;
        #1 clk = 1;
        #1;
        #1 clk = 0;
        #1;
        $display("HDLX-TRACE sync-hold %h", q_sync);
        $finish;
    end
endmodule
"""
