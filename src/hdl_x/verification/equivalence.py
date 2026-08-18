"""基于独立 HDL 模拟器的 trace 差分验证。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hdl_x.diagnostics import ValidationError
from hdl_x.utils.subprocess import CommandResult, find_executable, run_command

_TRACE_MARKER = "HDLX-TRACE"


@dataclass(frozen=True, slots=True)
class VerificationToolchain:
    """语义验证相关外部程序的绝对路径快照。"""

    ghdl: Path | None
    iverilog: Path | None
    vvp: Path | None
    verilator: Path | None
    yosys: Path | None
    sby: Path | None

    @property
    def differential_available(self) -> bool:
        """当前 GHDL+Icarus 差分后端是否完整。"""

        return self.ghdl is not None and self.iverilog is not None and self.vvp is not None

    @property
    def missing_differential(self) -> tuple[str, ...]:
        """返回当前差分后端缺少的工具名。"""

        return tuple(
            name
            for name, executable in (
                ("ghdl", self.ghdl),
                ("iverilog", self.iverilog),
                ("vvp", self.vvp),
            )
            if executable is None
        )

    @property
    def missing_formal(self) -> tuple[str, ...]:
        """返回 Yosys/SymbiYosys 形式验证路径缺少的工具名。"""

        return tuple(
            name
            for name, executable in (("yosys", self.yosys), ("sby", self.sby))
            if executable is None
        )


@dataclass(frozen=True, slots=True)
class DifferentialSimulationCase:
    """一组 VHDL/Verilog DUT 与各自 testbench。"""

    vhdl_sources: tuple[Path, ...]
    vhdl_testbench: Path
    vhdl_top: str
    verilog_sources: tuple[Path, ...]
    verilog_testbench: Path
    verilog_top: str
    timeout: float = 60.0


@dataclass(frozen=True, slots=True)
class DifferentialSimulationResult:
    """两侧归一化 trace 及比较结果。"""

    vhdl_trace: tuple[str, ...]
    verilog_trace: tuple[str, ...]

    @property
    def matched(self) -> bool:
        """两侧 trace 是否逐项完全一致。"""

        return self.vhdl_trace == self.verilog_trace


def detect_verification_toolchain() -> VerificationToolchain:
    """一次性探测差分、lint/synthesis 与形式工具。"""

    return VerificationToolchain(
        ghdl=find_executable("ghdl"),
        iverilog=find_executable("iverilog"),
        vvp=find_executable("vvp"),
        verilator=find_executable("verilator"),
        yosys=find_executable("yosys"),
        sby=find_executable("sby"),
    )


def run_differential_simulation(
    case: DifferentialSimulationCase,
    work_directory: Path,
    *,
    toolchain: VerificationToolchain | None = None,
) -> DifferentialSimulationResult:
    """分别运行 GHDL 与 Icarus，并比较带固定 marker 的 trace。"""

    tools = toolchain or detect_verification_toolchain()
    if not tools.differential_available:
        raise ValidationError(
            "差分仿真工具链不完整：" + ", ".join(tools.missing_differential),
            code="HDLX-EQUIV-TOOLS",
        )
    assert tools.ghdl is not None
    assert tools.iverilog is not None
    assert tools.vvp is not None

    root = Path(work_directory).resolve()
    vhdl_work = root / "ghdl-work"
    verilog_work = root / "iverilog-work"
    vhdl_work.mkdir(parents=True, exist_ok=True)
    verilog_work.mkdir(parents=True, exist_ok=True)

    vhdl_analysis = _run_checked(
        [
            tools.ghdl,
            "-a",
            "--std=08",
            *(path.resolve() for path in case.vhdl_sources),
            case.vhdl_testbench.resolve(),
        ],
        cwd=vhdl_work,
        timeout=case.timeout,
        stage="GHDL analyze",
    )
    del vhdl_analysis
    _run_checked(
        [tools.ghdl, "-e", "--std=08", case.vhdl_top],
        cwd=vhdl_work,
        timeout=case.timeout,
        stage="GHDL elaborate",
    )
    vhdl_run = _run_checked(
        [tools.ghdl, "-r", "--std=08", case.vhdl_top, "--assert-level=error"],
        cwd=vhdl_work,
        timeout=case.timeout,
        stage="GHDL run",
    )

    simulation_image = verilog_work / "simulation.vvp"
    _run_checked(
        [
            tools.iverilog,
            "-g2001",
            "-s",
            case.verilog_top,
            "-o",
            simulation_image,
            *(path.resolve() for path in case.verilog_sources),
            case.verilog_testbench.resolve(),
        ],
        cwd=verilog_work,
        timeout=case.timeout,
        stage="Icarus compile",
    )
    verilog_run = _run_checked(
        [tools.vvp, simulation_image],
        cwd=verilog_work,
        timeout=case.timeout,
        stage="Icarus run",
    )

    result = DifferentialSimulationResult(
        vhdl_trace=_extract_trace(vhdl_run),
        verilog_trace=_extract_trace(verilog_run),
    )
    if not result.matched:
        raise ValidationError(
            "VHDL/Verilog trace 不一致："
            f"VHDL={result.vhdl_trace!r}；Verilog={result.verilog_trace!r}",
            code="HDLX-EQUIV-MISMATCH",
        )
    if not result.vhdl_trace:
        raise ValidationError(
            f"两侧模拟均未输出 {_TRACE_MARKER} trace，不能宣称等价。",
            code="HDLX-EQUIV-NO-TRACE",
        )
    return result


def _run_checked(
    args: list[object],
    *,
    cwd: Path,
    timeout: float,
    stage: str,
) -> CommandResult:
    result = run_command(args, cwd=cwd, timeout=timeout)
    if result.succeeded:
        return result
    details = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
    raise ValidationError(
        f"{stage} 失败：{details}",
        code="HDLX-EQUIV-COMMAND",
    )


def _extract_trace(result: CommandResult) -> tuple[str, ...]:
    trace: list[str] = []
    for line in (*result.stdout.splitlines(), *result.stderr.splitlines()):
        marker = line.find(_TRACE_MARKER)
        if marker >= 0:
            trace.append(line[marker + len(_TRACE_MARKER) :].strip())
    return tuple(trace)


__all__ = [
    "DifferentialSimulationCase",
    "DifferentialSimulationResult",
    "VerificationToolchain",
    "detect_verification_toolchain",
    "run_differential_simulation",
]
