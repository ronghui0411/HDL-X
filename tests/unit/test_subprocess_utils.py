from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from hdl_x.utils.subprocess import ExecutableNotFoundError, run_command


def test_run_command_captures_process_result() -> None:
    result = run_command([sys.executable, "-c", "print('hdl-x')"])

    assert result.succeeded
    assert result.stdout.strip() == "hdl-x"
    assert result.stderr == ""


def test_run_command_preserves_nonzero_exit() -> None:
    result = run_command([sys.executable, "-c", "raise SystemExit(7)"])

    assert not result.succeeded
    assert result.returncode == 7


def test_run_command_rejects_missing_executable() -> None:
    with pytest.raises(ExecutableNotFoundError):
        run_command(["hdl-x-definitely-missing-executable"])


def test_run_command_resolves_relative_executable_against_cwd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    working_directory = tmp_path / "working"
    executable = working_directory / "tools" / "mock-tool"
    executable.parent.mkdir(parents=True)
    executable.touch()
    seen: dict[str, object] = {}

    def fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["args"] = args
        seen["cwd"] = kwargs["cwd"]
        seen["shell"] = kwargs["shell"]
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_command(["tools/mock-tool", "--check"], cwd=working_directory)

    assert result.succeeded
    assert result.args == (str(executable.resolve()), "--check")
    assert seen == {
        "args": (str(executable.resolve()), "--check"),
        "cwd": str(working_directory),
        "shell": False,
    }
