"""SystemVerilog/Verilog Icarus 编译与 trace 差分编排回归。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import ValidationError
from hdl_x.utils.subprocess import CommandResult
from hdl_x.verification import (
    IcarusCompilationCase,
    SystemVerilogDifferentialSimulationCase,
    VerificationToolchain,
    compile_iverilog,
    run_systemverilog_differential_simulation,
)


def test_systemverilog_toolchain_requires_only_icarus_and_vvp() -> None:
    tools = _available_tools()

    assert not tools.differential_available
    assert tools.systemverilog_differential_available
    assert tools.missing_systemverilog_differential == ()


def test_iverilog_compile_uses_requested_language_standard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "dut.v"
    source.write_text("module dut; endmodule\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def fake_run(args: object, **kwargs: object) -> CommandResult:
        del kwargs
        command = tuple(str(item) for item in args)  # type: ignore[arg-type]
        commands.append(command)
        return CommandResult(command, 0, "", "")

    monkeypatch.setattr("hdl_x.verification.equivalence.run_command", fake_run)

    result = compile_iverilog(
        IcarusCompilationCase(sources=(source,), top="dut", standard="2001"),
        tmp_path / "compile",
        toolchain=_available_tools(),
    )

    assert result.succeeded
    assert commands[0][1:4] == ("-g2001", "-s", "dut")


def test_systemverilog_differential_harness_compares_traces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    results = iter(
        (
            CommandResult(("iverilog",), 0, "", ""),
            CommandResult(("vvp",), 0, "HDLX-TRACE 0 a 5 f\n", ""),
            CommandResult(("iverilog",), 0, "", ""),
            CommandResult(("vvp",), 0, "HDLX-TRACE 0 a 5 f\n", ""),
        )
    )

    def fake_run(args: object, **kwargs: object) -> CommandResult:
        del kwargs
        commands.append(tuple(str(item) for item in args))  # type: ignore[arg-type]
        return next(results)

    monkeypatch.setattr("hdl_x.verification.equivalence.run_command", fake_run)

    result = run_systemverilog_differential_simulation(
        _case(tmp_path),
        tmp_path / "work",
        toolchain=_available_tools(),
    )

    assert result.matched
    assert result.systemverilog_trace == ("0 a 5 f",)
    assert result.verilog_trace == result.systemverilog_trace
    assert commands[0][1] == "-g2012"
    assert commands[2][1] == "-g2001"


def test_systemverilog_differential_harness_raises_structured_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = iter(
        (
            CommandResult(("iverilog",), 0, "", ""),
            CommandResult(("vvp",), 0, "HDLX-TRACE expected\n", ""),
            CommandResult(("iverilog",), 0, "", ""),
            CommandResult(("vvp",), 0, "HDLX-TRACE actual\n", ""),
        )
    )
    monkeypatch.setattr(
        "hdl_x.verification.equivalence.run_command",
        lambda *args, **kwargs: next(results),
    )

    with pytest.raises(ValidationError) as captured:
        run_systemverilog_differential_simulation(
            _case(tmp_path),
            tmp_path / "work",
            toolchain=_available_tools(),
        )

    assert captured.value.code == "HDLX-SV-EQUIV-MISMATCH"
    assert "expected" in captured.value.diagnostic.message
    assert "actual" in captured.value.diagnostic.message


def _available_tools() -> VerificationToolchain:
    return VerificationToolchain(
        ghdl=None,
        iverilog=Path("C:/iverilog.exe"),
        vvp=Path("C:/vvp.exe"),
        verilator=None,
        yosys=None,
        sby=None,
    )


def _case(tmp_path: Path) -> SystemVerilogDifferentialSimulationCase:
    paths = [tmp_path / name for name in ("dut.sv", "tb.sv", "dut.v", "tb.v")]
    for path in paths:
        path.write_text("module placeholder; endmodule\n", encoding="utf-8")
    return SystemVerilogDifferentialSimulationCase(
        systemverilog_sources=(paths[0],),
        systemverilog_testbench=paths[1],
        systemverilog_top="tb_systemverilog",
        verilog_sources=(paths[2],),
        verilog_testbench=paths[3],
        verilog_top="tb_verilog",
    )
