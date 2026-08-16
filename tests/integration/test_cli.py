from pathlib import Path

from typer.testing import CliRunner

from hdl_x.cli.main import app

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"
runner = CliRunner()


def test_cli_converts_real_vhdl_file(tmp_path: Path) -> None:
    output = tmp_path / "simple_logic.v"

    result = runner.invoke(
        app,
        [
            "convert",
            str(FIXTURES / "simple_logic.vhd"),
            "--from",
            "vhdl",
            "--to",
            "verilog",
            "-o",
            str(output),
            "--strict",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.is_file()
    assert "assign y = ~a & b ^ a;" in output.read_text(encoding="utf-8")


def test_cli_best_effort_is_reachable(tmp_path: Path) -> None:
    output = tmp_path / "best_effort.v"

    result = runner.invoke(
        app,
        [
            "convert",
            str(FIXTURES / "simple_logic.vhd"),
            "-o",
            str(output),
            "--best-effort",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.is_file()


def test_cli_rejects_conflicting_modes(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "convert",
            str(FIXTURES / "simple_logic.vhd"),
            "-o",
            str(tmp_path / "never.v"),
            "--strict",
            "--best-effort",
        ],
    )

    assert result.exit_code == 2
    assert "不能同时启用" in result.output
