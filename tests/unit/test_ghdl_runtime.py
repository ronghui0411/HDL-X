from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from hdl_x.diagnostics import FrontendError
from hdl_x.parser.ghdl import runtime

ROOT = Path(__file__).parents[2]


def test_pyghdl_runtime_requires_the_exact_backend_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_distribution_version", lambda: "6.0.1")

    status = runtime.inspect_pyghdl_runtime()

    assert not status.available
    assert status.installed_version == "6.0.1"
    assert status.code == "HDLX-GHDL-VERSION"
    with pytest.raises(FrontendError) as raised:
        runtime.require_pyghdl_runtime()
    assert raised.value.code == "HDLX-GHDL-VERSION"


def test_pyghdl_runtime_reports_backend_load_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_distribution_version", lambda: runtime.SUPPORTED_PYGHDL_VERSION)
    monkeypatch.setattr(
        runtime,
        "_load_required_modules",
        lambda: (_ for _ in ()).throw(OSError("missing libghdl")),
    )

    status = runtime.inspect_pyghdl_runtime()

    assert not status.available
    assert status.code == "HDLX-GHDL-LOAD"
    assert "missing libghdl" in status.detail


def test_real_ghdl_collection_fails_instead_of_skipping_when_runtime_is_unavailable(
    tmp_path: Path,
) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "pyGHDL.py").write_text("__version__ = 'broken'\n", encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(shadow), str(ROOT / "src")))

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/integration/test_ghdl_frontend.py",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "GHDL integration selected but pyGHDL runtime is unavailable" in output


def test_release_gate_rejects_a_test_selection_without_real_ghdl_tests() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--require-ghdl-integration",
            "tests/unit/test_environment.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "--require-ghdl-integration selected 0 real GHDL tests" in output


def test_equivalence_gate_rejects_a_selection_without_equivalence_tests() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--require-semantic-equivalence",
            "tests/unit/test_environment.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "--require-semantic-equivalence selected 0 equivalence tests" in output
