from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from hdl_x import environment
from hdl_x.diagnostics import FrontendError
from hdl_x.parser.slang import runtime

ROOT = Path(__file__).parents[2]


def test_pyslang_runtime_requires_the_exact_backend_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_distribution_version", lambda: "11.0.1")

    status = runtime.inspect_pyslang_runtime()

    assert not status.available
    assert status.installed_version == "11.0.1"
    assert status.code == "HDLX-SV-FRONTEND-VERSION"
    with pytest.raises(FrontendError) as raised:
        runtime.require_pyslang_runtime()
    assert raised.value.code == "HDLX-SV-FRONTEND-VERSION"


def test_pyslang_runtime_reports_backend_load_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime,
        "_distribution_version",
        lambda: runtime.SUPPORTED_PYSLANG_VERSION,
    )
    monkeypatch.setattr(
        runtime,
        "_load_required_module",
        lambda: (_ for _ in ()).throw(OSError("missing slang runtime")),
    )

    status = runtime.inspect_pyslang_runtime()

    assert not status.available
    assert status.code == "HDLX-SV-FRONTEND-LOAD"
    assert "missing slang runtime" in status.detail


def test_environment_reports_pyslang_as_optional_frontend() -> None:
    items = {item.name: item for item in environment.inspect_environment()}

    frontend = items["SystemVerilog frontend (pyslang/Slang)"]
    assert frontend.version == runtime.SUPPORTED_PYSLANG_VERSION
    assert frontend.available
    assert not frontend.required


def test_real_slang_collection_fails_instead_of_skipping_when_runtime_is_unavailable(
    tmp_path: Path,
) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "pyslang.py").write_text("__version__ = 'broken'\n", encoding="utf-8")
    process_environment = os.environ.copy()
    process_environment["PYTHONPATH"] = os.pathsep.join((str(shadow), str(ROOT / "src")))

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/integration/test_systemverilog_frontend.py",
        ],
        cwd=ROOT,
        env=process_environment,
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "Slang integration selected but pyslang runtime is unavailable" in output


def test_slang_gate_rejects_a_selection_without_real_slang_tests() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--require-slang-integration",
            "tests/unit/test_environment.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "--require-slang-integration selected 0 real Slang tests" in output
