from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_systemverilog_equivalence_gate_rejects_zero_selected_tests() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--require-systemverilog-equivalence",
            "tests/unit/test_environment.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "--require-systemverilog-equivalence selected 0 equivalence tests" in output


def test_systemverilog_equivalence_gate_rejects_missing_tools() -> None:
    process_environment = os.environ.copy()
    process_environment["PATH"] = ""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--require-systemverilog-equivalence",
            "tests/equivalence/test_systemverilog_differential.py",
        ],
        cwd=ROOT,
        env=process_environment,
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "SystemVerilog equivalence required but external tools are missing" in output
    assert "iverilog, vvp" in output
