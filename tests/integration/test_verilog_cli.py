from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hdl_x.cli.main import app
from hdl_x.utils import run_command

pytestmark = [pytest.mark.slang_integration, pytest.mark.ghdl_integration]

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parents[1] / "fixtures" / "verilog"
GOLDENS = Path(__file__).parents[1] / "golden_vhdl"
runner = CliRunner()


@pytest.mark.parametrize("source_language", ["verilog", "v"])
def test_cli_converts_real_verilog_to_vhdl(
    source_language: str,
    tmp_path: Path,
) -> None:
    output = tmp_path / f"{source_language}.vhd"

    result = runner.invoke(
        app,
        [
            "convert",
            str(FIXTURES / "v3_simple_assign.v"),
            "--from",
            source_language,
            "--to",
            "vhdl",
            "-o",
            str(output),
            "--strict",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.read_text(encoding="utf-8") == (
        GOLDENS / "v3_simple_assign.vhd"
    ).read_text(encoding="utf-8")


def test_cli_validate_uses_real_pyghdl_for_vhdl_target(tmp_path: Path) -> None:
    output = tmp_path / "validated.vhd"

    completed = run_command(
        [
            sys.executable,
            "-m",
            "hdl_x.cli.main",
            "convert",
            str(FIXTURES / "v3_generate_for.v"),
            "--from",
            "verilog",
            "--to",
            "vhdl",
            "-o",
            str(output),
            "--strict",
            "--validate",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        timeout=60.0,
    )

    assert completed.succeeded, completed.stdout + completed.stderr
    assert output.read_text(encoding="utf-8") == (
        GOLDENS / "v3_generate_for.vhd"
    ).read_text(encoding="utf-8")
