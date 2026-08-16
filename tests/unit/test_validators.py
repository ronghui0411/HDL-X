from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hdl_x.utils.subprocess import CommandResult
from hdl_x.validator import (
    GhdlValidator,
    SlangValidator,
    ValidationStatus,
    YosysValidator,
)


def test_optional_validator_unavailable_does_not_block_translation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "generated.v"
    source.write_text("module generated; endmodule\n", encoding="utf-8")
    monkeypatch.setattr("hdl_x.validator.base.find_executable", lambda _name: None)

    validator = SlangValidator()
    availability = validator.availability()
    result = validator.validate(source)

    assert availability.available is False
    assert availability.optional is True
    assert availability.blocks_translation is False
    assert result.status is ValidationStatus.UNAVAILABLE
    assert result.unavailable is True
    assert result.blocks_translation is False
    assert "可选验证器" in result.message


def test_required_validator_unavailable_is_reported_as_blocking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.vhd"
    source.write_text("entity source is end entity;\n", encoding="utf-8")
    monkeypatch.setattr("hdl_x.validator.base.find_executable", lambda _name: None)

    result = GhdlValidator().validate(source)

    assert result.status is ValidationStatus.UNAVAILABLE
    assert result.blocks_translation is True
    assert "ghdl" in result.message


@pytest.mark.parametrize(
    ("validator", "expected_arguments", "version_line"),
    [
        (GhdlValidator(), ("--version",), "GHDL 5.0.1"),
        (SlangValidator(), ("--version",), "slang version 9.1"),
        (YosysValidator(), ("-V",), "Yosys 0.50"),
    ],
)
def test_version_uses_tool_specific_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    validator: GhdlValidator | SlangValidator | YosysValidator,
    expected_arguments: tuple[str, ...],
    version_line: str,
) -> None:
    executable = tmp_path / f"{validator.executable_name}.exe"
    seen: list[tuple[tuple[Any, ...], float]] = []
    monkeypatch.setattr(
        "hdl_x.validator.base.find_executable",
        lambda _name: executable,
    )

    def fake_run(args: tuple[Any, ...] | list[Any], *, timeout: float) -> CommandResult:
        seen.append((tuple(args), timeout))
        return CommandResult(
            args=tuple(str(argument) for argument in args),
            returncode=0,
            stdout=f"\n{version_line}\nmore details\n",
            stderr="",
        )

    monkeypatch.setattr("hdl_x.validator.base.run_command", fake_run)

    assert validator.version(timeout=7.5) == version_line
    assert seen == [((executable, *expected_arguments), 7.5)]


@pytest.mark.parametrize(
    ("validator", "suffix", "expected_tail"),
    [
        (GhdlValidator(), ".vhd", ("-s", "--std=08")),
        (SlangValidator(), ".v", ("--lint-only",)),
    ],
)
def test_file_validator_builds_argument_array_without_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    validator: GhdlValidator | SlangValidator,
    suffix: str,
    expected_tail: tuple[str, ...],
) -> None:
    source = tmp_path / f"source with space{suffix}"
    source.write_text("-- fixture\n" if suffix == ".vhd" else "// fixture\n", encoding="utf-8")
    executable = tmp_path / f"{validator.executable_name}.exe"
    seen: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "hdl_x.validator.base.find_executable",
        lambda _name: executable,
    )

    def fake_run(args: tuple[Any, ...], *, timeout: float) -> CommandResult:
        del timeout
        seen.append(args)
        return CommandResult(
            args=tuple(str(argument) for argument in args),
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("hdl_x.validator.base.run_command", fake_run)

    result = validator.validate(source)

    assert result.status is ValidationStatus.PASSED
    assert seen == [
        (
            str(executable),
            *expected_tail,
            str(source.resolve()),
        )
    ]


def test_yosys_validator_runs_recommended_smoke_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source with space.v"
    source.write_text("module source; endmodule\n", encoding="utf-8")
    executable = tmp_path / "yosys.exe"
    seen: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "hdl_x.validator.base.find_executable",
        lambda _name: executable,
    )

    def fake_run(args: tuple[Any, ...], *, timeout: float) -> CommandResult:
        del timeout
        seen.append(args)
        return CommandResult(
            args=tuple(str(argument) for argument in args),
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("hdl_x.validator.base.run_command", fake_run)

    result = YosysValidator().validate(source)

    expected_script = (
        f'read_verilog "{source.resolve().as_posix()}"; '
        "hierarchy -check; proc; check"
    )
    assert result.passed is True
    assert seen == [(str(executable), "-q", "-p", expected_script)]


def test_validator_preserves_failed_command_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "bad.v"
    source.write_text("module bad(\n", encoding="utf-8")
    executable = tmp_path / "slang.exe"
    monkeypatch.setattr(
        "hdl_x.validator.base.find_executable",
        lambda _name: executable,
    )

    def fake_run(args: tuple[Any, ...], *, timeout: float) -> CommandResult:
        del timeout
        return CommandResult(
            args=tuple(str(argument) for argument in args),
            returncode=2,
            stdout="standard output",
            stderr="syntax error",
        )

    monkeypatch.setattr("hdl_x.validator.base.run_command", fake_run)

    result = SlangValidator().validate(source)

    assert result.status is ValidationStatus.FAILED
    assert result.returncode == 2
    assert result.stdout == "standard output"
    assert result.stderr == "syntax error"
    assert result.blocks_translation is True


def test_missing_source_fails_without_trying_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool_lookup_called = False

    def fake_find(_name: str) -> None:
        nonlocal tool_lookup_called
        tool_lookup_called = True
        return None

    monkeypatch.setattr("hdl_x.validator.base.find_executable", fake_find)

    result = YosysValidator().validate(tmp_path / "missing.v")

    assert result.status is ValidationStatus.FAILED
    assert result.blocks_translation is True
    assert "不存在" in result.message
    assert tool_lookup_called is False


def test_ghdl_rejects_unknown_standard() -> None:
    with pytest.raises(ValueError, match="VHDL 标准"):
        GhdlValidator(standard="invalid")
