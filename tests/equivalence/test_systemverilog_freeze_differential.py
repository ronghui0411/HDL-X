"""冻结候选新增 signed 参数与 reset 极性的真实 Icarus 证据。"""

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


def test_generated_signed_parameter_verilog_compiles_as_verilog_2001(
    tmp_path: Path,
) -> None:
    _require_iverilog()
    generated = _convert(FIXTURES / "sv_signed_parameters.sv", tmp_path)
    testbench = tmp_path / "tb_sv_signed.v"
    testbench.write_text(_SIGNED_TB, encoding="utf-8")

    result = compile_iverilog(
        IcarusCompilationCase(
            sources=(generated, testbench),
            top="tb_sv_signed",
            standard="2001",
        ),
        tmp_path / "compile-signed",
        toolchain=TOOLS,
    )

    assert result.succeeded


def test_signed_parameter_trace_matches_original_systemverilog(tmp_path: Path) -> None:
    _require_differential_tools()
    source = FIXTURES / "sv_signed_parameters.sv"
    generated = _convert(source, tmp_path)
    reference_tb = tmp_path / "tb_sv_signed_reference.v"
    generated_tb = tmp_path / "tb_sv_signed_generated.v"
    reference_tb.write_text(_SIGNED_TB, encoding="utf-8")
    generated_tb.write_text(_SIGNED_TB, encoding="utf-8")

    result = run_systemverilog_differential_simulation(
        SystemVerilogDifferentialSimulationCase(
            systemverilog_sources=(source,),
            systemverilog_testbench=reference_tb,
            systemverilog_top="tb_sv_signed",
            verilog_sources=(generated,),
            verilog_testbench=generated_tb,
            verilog_top="tb_sv_signed",
        ),
        tmp_path / "diff-signed",
        toolchain=TOOLS,
    )

    assert result.matched
    assert result.systemverilog_trace == (
        "signed-negative -2 1",
        "signed-positive 5 0",
        "signed-zero 0 0",
    )


def test_generated_reset_polarity_verilog_compiles_as_verilog_2001(
    tmp_path: Path,
) -> None:
    _require_iverilog()
    generated = _convert(FIXTURES / "sv_reset_polarities.sv", tmp_path)
    testbench = tmp_path / "tb_sv_reset_polarities.v"
    testbench.write_text(_RESET_POLARITY_TB, encoding="utf-8")

    result = compile_iverilog(
        IcarusCompilationCase(
            sources=(generated, testbench),
            top="tb_sv_reset_polarities",
            standard="2001",
        ),
        tmp_path / "compile-reset-polarities",
        toolchain=TOOLS,
    )

    assert result.succeeded


def test_reset_polarity_trace_matches_original_systemverilog(tmp_path: Path) -> None:
    _require_differential_tools()
    source = FIXTURES / "sv_reset_polarities.sv"
    generated = _convert(source, tmp_path)
    reference_tb = tmp_path / "tb_sv_reset_reference.v"
    generated_tb = tmp_path / "tb_sv_reset_generated.v"
    reference_tb.write_text(_RESET_POLARITY_TB, encoding="utf-8")
    generated_tb.write_text(_RESET_POLARITY_TB, encoding="utf-8")

    result = run_systemverilog_differential_simulation(
        SystemVerilogDifferentialSimulationCase(
            systemverilog_sources=(source,),
            systemverilog_testbench=reference_tb,
            systemverilog_top="tb_sv_reset_polarities",
            verilog_sources=(generated,),
            verilog_testbench=generated_tb,
            verilog_top="tb_sv_reset_polarities",
        ),
        tmp_path / "diff-reset-polarities",
        toolchain=TOOLS,
    )

    assert result.matched
    assert result.systemverilog_trace == (
        "async-high-reset 0",
        "async-high-load a",
        "async-high-hold a",
        "sync-low-reset 0",
        "sync-low-load 3",
        "sync-low-hold 3",
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


_SIGNED_TB = """`timescale 1ns/1ps
module tb_sv_signed;
    reg signed [3:0] a;
    reg signed [3:0] b;
    wire signed [4:0] y;
    wire negative;

    SvSignedParams #(.WIDTH(4), .OUT_WIDTH(5)) dut (
        .a(a), .b(b), .y(y), .negative(negative)
    );

    initial begin
        a = -3;
        b = 1;
        #1;
        $display("HDLX-TRACE signed-negative %0d %b", y, negative);

        a = 3;
        b = 2;
        #1;
        $display("HDLX-TRACE signed-positive %0d %b", y, negative);

        a = 0;
        b = 0;
        #1;
        $display("HDLX-TRACE signed-zero %0d %b", y, negative);
        $finish;
    end
endmodule
"""

_RESET_POLARITY_TB = """`timescale 1ns/1ps
module tb_sv_reset_polarities;
    reg clk;
    reg rst;
    reg rst_n;
    reg en;
    reg [3:0] d;
    wire [3:0] q_async;
    wire [3:0] q_sync;

    SvAsyncHighReg #(.WIDTH(4)) async_dut (
        .clk(clk), .rst(rst), .en(en), .d(d), .q(q_async)
    );
    SvSyncLowReg #(.WIDTH(4)) sync_dut (
        .clk(clk), .rst_n(rst_n), .en(en), .d(d), .q(q_sync)
    );

    initial begin
        clk = 0;
        rst = 0;
        rst_n = 1;
        en = 0;
        d = 0;

        #1 rst = 1;
        #1;
        $display("HDLX-TRACE async-high-reset %h", q_async);

        rst = 0;
        en = 1;
        d = 4'ha;
        #1 clk = 1;
        #1;
        $display("HDLX-TRACE async-high-load %h", q_async);

        en = 0;
        d = 4'h5;
        #1 clk = 0;
        #1 clk = 1;
        #1;
        $display("HDLX-TRACE async-high-hold %h", q_async);

        rst_n = 0;
        #1 clk = 0;
        #1 clk = 1;
        #1;
        $display("HDLX-TRACE sync-low-reset %h", q_sync);

        rst_n = 1;
        en = 1;
        d = 4'h3;
        #1 clk = 0;
        #1 clk = 1;
        #1;
        $display("HDLX-TRACE sync-low-load %h", q_sync);

        en = 0;
        d = 4'hf;
        #1 clk = 0;
        #1 clk = 1;
        #1;
        $display("HDLX-TRACE sync-low-hold %h", q_sync);
        $finish;
    end
endmodule
"""
