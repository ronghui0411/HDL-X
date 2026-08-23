from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hdl_x.cli.main import app

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"
runner = CliRunner()


@pytest.mark.parametrize("source_language", ["systemverilog", "sv"])
def test_cli_converts_real_systemverilog_file(
    tmp_path: Path,
    source_language: str,
) -> None:
    output = tmp_path / f"{source_language}.v"

    result = runner.invoke(
        app,
        [
            "convert",
            str(FIXTURES / "sv_comb_logic.sv"),
            "--from",
            source_language,
            "--to",
            "verilog",
            "-o",
            str(output),
            "--strict",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.is_file()
    assert "always @(*) begin : comb_p" in output.read_text(encoding="utf-8")
