from pathlib import Path

import pytest

from hdl_x.gui import ConversionRequest, execute_conversion
from hdl_x.transformer import NameStyle

pytestmark = pytest.mark.ghdl_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"


def test_gui_controller_converts_real_vhdl_file(tmp_path: Path) -> None:
    output = tmp_path / "simple_logic.v"

    report = execute_conversion(
        ConversionRequest(
            source_path=FIXTURES / "simple_logic.vhd",
            output_path=output,
            strict=True,
            name_style=NameStyle.PRESERVE,
        )
    )

    assert report.output_path == output.resolve()
    assert "module SimpleLogic" in report.result.text
    assert "assign y = ~a & b ^ a;" in output.read_text(encoding="utf-8")
