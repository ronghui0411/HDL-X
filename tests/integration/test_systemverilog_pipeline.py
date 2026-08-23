from __future__ import annotations

from pathlib import Path

import pytest

from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"
GOLDENS = Path(__file__).parents[1] / "golden"


@pytest.mark.parametrize(
    ("fixture", "golden"),
    [
        ("sv_comb_logic.sv", "sv_comb_logic.v"),
        ("sv_sequential.sv", "sv_sequential.v"),
        ("sv_hierarchy.sv", "sv_hierarchy.v"),
        ("sv_case_sensitive.sv", "sv_case_sensitive.v"),
    ],
)
def test_real_systemverilog_pipeline_matches_new_golden(
    fixture: str,
    golden: str,
) -> None:
    result = convert_file(
        FIXTURES / fixture,
        source_language="systemverilog",
        options=ConversionOptions(strict=True),
    )

    assert result.text.encode("utf-8") == (GOLDENS / golden).read_bytes()
    if fixture == "sv_comb_logic.sv":
        assert "HDLX-SV-ALWAYS-COMB-TIME-ZERO" in {
            diagnostic.code for diagnostic in result.diagnostics
        }
    if fixture == "sv_sequential.sv":
        assert [diagnostic.code for diagnostic in result.diagnostics] == [
            "HDLX-SV-EDGE-XZ",
            "HDLX-SV-EDGE-XZ",
        ]


def test_sv_alias_uses_same_real_frontend_and_output() -> None:
    source = FIXTURES / "sv_comb_logic.sv"

    long_name = convert_file(
        source,
        source_language="systemverilog",
        options=ConversionOptions(strict=True),
    )
    alias = convert_file(
        source,
        source_language="sv",
        options=ConversionOptions(strict=True),
    )

    assert alias.text == long_name.text
    assert alias.design == long_name.design


def test_systemverilog_case_sensitive_identifiers_remain_distinct() -> None:
    result = convert_file(
        FIXTURES / "sv_case_sensitive.sv",
        source_language="systemverilog",
        options=ConversionOptions(strict=True),
    )

    assert "input wire data" in result.text
    assert "input wire Data" in result.text
    assert "assign y = data ^ Data;" in result.text
