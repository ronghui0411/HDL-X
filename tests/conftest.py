from __future__ import annotations

from typing import Any

import pytest

from hdl_x.parser.ghdl.runtime import PyGhdlRuntimeStatus, inspect_pyghdl_runtime
from hdl_x.parser.slang.runtime import PySlangRuntimeStatus, inspect_pyslang_runtime
from hdl_x.verification import VerificationToolchain, detect_verification_toolchain

_GHDL_MARKER = "ghdl_integration"
_SLANG_MARKER = "slang_integration"
_EQUIVALENCE_MARKER = "semantic_equivalence"
_SV_EQUIVALENCE_MARKER = "systemverilog_equivalence"
_V2V_EQUIVALENCE_MARKER = "verilog_to_vhdl_equivalence"
_SELECTED_KEY = pytest.StashKey[frozenset[str]]()
_STATUS_KEY = pytest.StashKey[PyGhdlRuntimeStatus]()
_SLANG_SELECTED_KEY = pytest.StashKey[frozenset[str]]()
_SLANG_STATUS_KEY = pytest.StashKey[PySlangRuntimeStatus]()
_EQUIVALENCE_SELECTED_KEY = pytest.StashKey[frozenset[str]]()
_SV_EQUIVALENCE_SELECTED_KEY = pytest.StashKey[frozenset[str]]()
_V2V_EQUIVALENCE_SELECTED_KEY = pytest.StashKey[frozenset[str]]()
_TOOLCHAIN_KEY = pytest.StashKey[VerificationToolchain]()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-ghdl-integration",
        action="store_true",
        default=False,
        help="要求本次选择至少一个真实 GHDL integration test。",
    )
    parser.addoption(
        "--require-slang-integration",
        action="store_true",
        default=False,
        help="要求本次选择至少一个真实 pyslang/Slang integration test。",
    )
    parser.addoption(
        "--require-semantic-equivalence",
        action="store_true",
        default=False,
        help="要求选择并实际具备 GHDL+Icarus 差分仿真工具链。",
    )
    parser.addoption(
        "--require-systemverilog-equivalence",
        action="store_true",
        default=False,
        help="要求选择并实际具备 Icarus SystemVerilog/Verilog 差分工具链。",
    )
    parser.addoption(
        "--require-verilog-to-vhdl-equivalence",
        action="store_true",
        default=False,
        help="要求选择并实际具备 Icarus/GHDL Verilog 到 VHDL 差分工具链。",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "ghdl_integration: 使用真实 pyGHDL/libghdl frontend 的集成测试",
    )
    config.addinivalue_line(
        "markers",
        "slang_integration: 使用真实 pyslang/Slang frontend 的集成测试",
    )
    config.addinivalue_line(
        "markers",
        "semantic_equivalence: 使用独立 VHDL/Verilog simulator 比较 trace",
    )
    config.addinivalue_line(
        "markers",
        "systemverilog_equivalence: 使用 Icarus 比较 SystemVerilog/Verilog trace",
    )
    config.addinivalue_line(
        "markers",
        "verilog_to_vhdl_equivalence: 使用 Icarus/GHDL 比较 Verilog 与生成 VHDL trace",
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    selected = frozenset(
        item.nodeid for item in items if item.get_closest_marker(_GHDL_MARKER) is not None
    )
    config.stash[_SELECTED_KEY] = selected
    slang_selected = frozenset(
        item.nodeid for item in items if item.get_closest_marker(_SLANG_MARKER) is not None
    )
    config.stash[_SLANG_SELECTED_KEY] = slang_selected
    equivalence_selected = frozenset(
        item.nodeid for item in items if item.get_closest_marker(_EQUIVALENCE_MARKER) is not None
    )
    config.stash[_EQUIVALENCE_SELECTED_KEY] = equivalence_selected
    systemverilog_equivalence_selected = frozenset(
        item.nodeid for item in items if item.get_closest_marker(_SV_EQUIVALENCE_MARKER) is not None
    )
    config.stash[_SV_EQUIVALENCE_SELECTED_KEY] = systemverilog_equivalence_selected
    verilog_to_vhdl_equivalence_selected = frozenset(
        item.nodeid
        for item in items
        if item.get_closest_marker(_V2V_EQUIVALENCE_MARKER) is not None
    )
    config.stash[_V2V_EQUIVALENCE_SELECTED_KEY] = verilog_to_vhdl_equivalence_selected
    toolchain = detect_verification_toolchain()
    config.stash[_TOOLCHAIN_KEY] = toolchain

    if config.getoption("--require-ghdl-integration") and not selected:
        raise pytest.UsageError("--require-ghdl-integration selected 0 real GHDL tests")
    if config.getoption("--require-slang-integration") and not slang_selected:
        raise pytest.UsageError("--require-slang-integration selected 0 real Slang tests")

    if config.getoption("--require-semantic-equivalence"):
        if not equivalence_selected:
            raise pytest.UsageError("--require-semantic-equivalence selected 0 equivalence tests")
        if not toolchain.differential_available:
            raise pytest.UsageError(
                "semantic equivalence required but external tools are missing: "
                + ", ".join(toolchain.missing_differential)
            )

    if config.getoption("--require-systemverilog-equivalence"):
        if not systemverilog_equivalence_selected:
            raise pytest.UsageError(
                "--require-systemverilog-equivalence selected 0 equivalence tests"
            )
        if not toolchain.systemverilog_differential_available:
            raise pytest.UsageError(
                "SystemVerilog equivalence required but external tools are missing: "
                + ", ".join(toolchain.missing_systemverilog_differential)
            )

    if config.getoption("--require-verilog-to-vhdl-equivalence"):
        if not verilog_to_vhdl_equivalence_selected:
            raise pytest.UsageError(
                "--require-verilog-to-vhdl-equivalence selected 0 equivalence tests"
            )
        if not toolchain.differential_available:
            raise pytest.UsageError(
                "Verilog to VHDL equivalence required but external tools are missing: "
                + ", ".join(toolchain.missing_differential)
            )

    if selected:
        status = inspect_pyghdl_runtime()
        config.stash[_STATUS_KEY] = status
        if not status.available:
            raise pytest.UsageError(
                f"GHDL integration selected but pyGHDL runtime is unavailable: {status.detail}"
            )

    if slang_selected:
        slang_status = inspect_pyslang_runtime()
        config.stash[_SLANG_STATUS_KEY] = slang_status
        if not slang_status.available:
            raise pytest.UsageError(
                "Slang integration selected but pyslang runtime is unavailable: "
                f"{slang_status.detail}"
            )


def pytest_terminal_summary(
    terminalreporter: Any,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    del exitstatus
    selected = config.stash.get(_SELECTED_KEY, frozenset())
    if not selected:
        terminalreporter.write_line("GHDL integration: NOT SELECTED (0 tests)")
    else:
        reports = _call_reports(terminalreporter, selected)
        passed = sum(report.passed for report in reports)
        failed = sum(report.failed for report in reports)
        skipped = sum(report.skipped for report in reports)
        status = config.stash.get(_STATUS_KEY, None)
        version = status.installed_version if status is not None else "unknown"
        terminalreporter.write_line(
            "GHDL integration: "
            f"EXECUTED {len(reports)}/{len(selected)} (passed={passed}, failed={failed}, "
            f"skipped={skipped}, pyGHDL={version})"
        )

    slang_selected = config.stash.get(_SLANG_SELECTED_KEY, frozenset())
    if not slang_selected:
        terminalreporter.write_line("Slang integration: NOT SELECTED (0 tests)")
    else:
        reports = _call_reports(terminalreporter, slang_selected)
        passed = sum(report.passed for report in reports)
        failed = sum(report.failed for report in reports)
        skipped = sum(report.skipped for report in reports)
        status = config.stash.get(_SLANG_STATUS_KEY, None)
        version = status.installed_version if status is not None else "unknown"
        terminalreporter.write_line(
            "Slang integration: "
            f"EXECUTED {len(reports)}/{len(slang_selected)} "
            f"(passed={passed}, failed={failed}, skipped={skipped}, pyslang={version})"
        )

    equivalence_selected = config.stash.get(_EQUIVALENCE_SELECTED_KEY, frozenset())
    if not equivalence_selected:
        terminalreporter.write_line("Semantic equivalence: NOT SELECTED (0 tests)")
    else:
        reports = _call_reports(terminalreporter, equivalence_selected)
        passed = sum(report.passed for report in reports)
        failed = sum(report.failed for report in reports)
        skipped = sum(report.skipped for report in reports)
        toolchain = config.stash[_TOOLCHAIN_KEY]
        missing = ", ".join(toolchain.missing_differential) or "none"
        terminalreporter.write_line(
            "Semantic equivalence: "
            f"EXECUTED {len(reports)}/{len(equivalence_selected)} "
            f"(passed={passed}, failed={failed}, skipped={skipped}, missing={missing})"
        )

    verilog_to_vhdl_selected = config.stash.get(
        _V2V_EQUIVALENCE_SELECTED_KEY, frozenset()
    )
    if not verilog_to_vhdl_selected:
        terminalreporter.write_line("Verilog to VHDL equivalence: NOT SELECTED (0 tests)")
    else:
        reports = _call_reports(terminalreporter, verilog_to_vhdl_selected)
        passed = sum(report.passed for report in reports)
        failed = sum(report.failed for report in reports)
        skipped = sum(report.skipped for report in reports)
        toolchain = config.stash[_TOOLCHAIN_KEY]
        missing = ", ".join(toolchain.missing_differential) or "none"
        terminalreporter.write_line(
            "Verilog to VHDL equivalence: "
            f"EXECUTED {len(reports)}/{len(verilog_to_vhdl_selected)} "
            f"(passed={passed}, failed={failed}, skipped={skipped}, missing={missing})"
        )

    systemverilog_selected = config.stash.get(_SV_EQUIVALENCE_SELECTED_KEY, frozenset())
    if not systemverilog_selected:
        terminalreporter.write_line("SystemVerilog equivalence: NOT SELECTED (0 tests)")
        return
    reports = _call_reports(terminalreporter, systemverilog_selected)
    passed = sum(report.passed for report in reports)
    failed = sum(report.failed for report in reports)
    skipped = sum(report.skipped for report in reports)
    toolchain = config.stash[_TOOLCHAIN_KEY]
    missing = ", ".join(toolchain.missing_systemverilog_differential) or "none"
    terminalreporter.write_line(
        "SystemVerilog equivalence: "
        f"EXECUTED {len(reports)}/{len(systemverilog_selected)} "
        f"(passed={passed}, failed={failed}, skipped={skipped}, missing={missing})"
    )


def _call_reports(terminalreporter: Any, selected: frozenset[str]) -> list[Any]:
    """提取指定测试的 call 阶段结果，避免 collection 数量冒充执行数量。"""

    return [
        report
        for outcome in ("passed", "failed", "skipped")
        for report in terminalreporter.stats.get(outcome, ())
        if getattr(report, "when", None) == "call" and report.nodeid in selected
    ]
