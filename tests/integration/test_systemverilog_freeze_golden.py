from pathlib import Path

import pytest

from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"
GOLDENS = Path(__file__).parents[1] / "golden"


@pytest.mark.parametrize(
    "stem",
    ["sv_reset_polarities", "sv_signed_parameters"],
)
def test_freeze_supported_systemverilog_matches_new_golden(stem: str) -> None:
    result = convert_file(
        FIXTURES / f"{stem}.sv",
        source_language="systemverilog",
        options=ConversionOptions(strict=True),
    )

    assert result.text.encode("utf-8") == (GOLDENS / f"{stem}.v").read_bytes()
