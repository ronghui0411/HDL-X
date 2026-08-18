"""差分仿真工具发现、命令编排与 trace 比较回归。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import ValidationError
from hdl_x.utils.subprocess import CommandResult
from hdl_x.verification.equivalence import (
    DifferentialSimulationCase,
    VerificationToolchain,
    detect_verification_toolchain,
    run_differential_simulation,
)


def test_toolchain_detection_reports_every_missing_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "hdl_x.verification.equivalence.find_executable",
        lambda name: Path(f"C:/{name}.exe") if name == "verilator" else None,
    )

    tools = detect_verification_toolchain()

    assert not tools.differential_available
    assert tools.missing_differential == ("ghdl", "iverilog", "vvp")
    assert tools.verilator == Path("C:/verilator.exe")
    assert tools.missing_formal == ("yosys", "sby")


def test_differential_harness_compares_normalized_traces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    results = iter(
        (
            CommandResult(("ghdl", "-a"), 0, "", ""),
            CommandResult(("ghdl", "-e"), 0, "", ""),
            CommandResult(
                ("ghdl", "-r"),
                0,
                "",
                "tb.vhd:8:5:@1ns:(report note):HDLX-TRACE 0 0 1 0\n",
            ),
            CommandResult(("iverilog",), 0, "", ""),
            CommandResult(("vvp",), 0, "HDLX-TRACE 0 0 1 0\n", ""),
        )
    )

    def fake_run(args: object, **kwargs: object) -> CommandResult:
        commands.append(tuple(str(item) for item in args))  # type: ignore[arg-type]
        return next(results)

    monkeypatch.setattr("hdl_x.verification.equivalence.run_command", fake_run)
    case = _case(tmp_path)

    result = run_differential_simulation(case, tmp_path, toolchain=_available_tools())

    assert result.matched
    assert result.vhdl_trace == ("0 0 1 0",)
    assert result.verilog_trace == result.vhdl_trace
    assert [command[1] for command in commands[:3]] == ["-a", "-e", "-r"]
    assert commands[3][0].endswith("iverilog.exe")
    assert commands[4][0].endswith("vvp.exe")


def test_differential_harness_raises_structured_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = iter(
        (
            CommandResult(("ghdl",), 0, "", ""),
            CommandResult(("ghdl",), 0, "", ""),
            CommandResult(("ghdl",), 0, "HDLX-TRACE expected\n", ""),
            CommandResult(("iverilog",), 0, "", ""),
            CommandResult(("vvp",), 0, "HDLX-TRACE actual\n", ""),
        )
    )
    monkeypatch.setattr(
        "hdl_x.verification.equivalence.run_command",
        lambda *args, **kwargs: next(results),
    )

    with pytest.raises(ValidationError) as captured:
        run_differential_simulation(_case(tmp_path), tmp_path, toolchain=_available_tools())

    assert captured.value.code == "HDLX-EQUIV-MISMATCH"
    assert "expected" in captured.value.diagnostic.message
    assert "actual" in captured.value.diagnostic.message


def _available_tools() -> VerificationToolchain:
    return VerificationToolchain(
        ghdl=Path("C:/ghdl.exe"),
        iverilog=Path("C:/iverilog.exe"),
        vvp=Path("C:/vvp.exe"),
        verilator=None,
        yosys=None,
        sby=None,
    )


def _case(tmp_path: Path) -> DifferentialSimulationCase:
    paths = [tmp_path / name for name in ("dut.vhd", "tb.vhd", "dut.v", "tb.v")]
    for path in paths:
        path.write_text("-- placeholder\n", encoding="utf-8")
    return DifferentialSimulationCase(
        vhdl_sources=(paths[0],),
        vhdl_testbench=paths[1],
        vhdl_top="tb_vhdl",
        verilog_sources=(paths[2],),
        verilog_testbench=paths[3],
        verilog_top="tb_verilog",
    )
