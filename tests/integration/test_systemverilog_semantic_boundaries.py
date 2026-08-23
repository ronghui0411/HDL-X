from pathlib import Path

import pytest

from hdl_x.diagnostics import UnsupportedConstructError
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"
GOLDENS = Path(__file__).parents[1] / "golden"


def test_no_reset_logic_register_does_not_receive_vhdl_initial_state_diagnostic() -> None:
    result = convert_file(
        FIXTURES / "sv_no_reset.sv",
        source_language="systemverilog",
        options=ConversionOptions(strict=True),
    )

    assert result.text.encode("utf-8") == (GOLDENS / "sv_no_reset.v").read_bytes()
    assert not any(diagnostic.code.startswith("HDLX-VHDL-") for diagnostic in result.diagnostics)
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["HDLX-SV-EDGE-XZ"]

    ambiguous = convert_file(
        FIXTURES / "sv_ambiguous_reset.sv",
        source_language="systemverilog",
        options=ConversionOptions(best_effort=True, strict=False),
    )
    assert [diagnostic.code for diagnostic in ambiguous.diagnostics] == [
        "HDLX-SV-EDGE-XZ",
        "HDLX-SV-RESET-UNCLASSIFIED",
    ]


@pytest.mark.parametrize(
    ("fixture", "code"),
    [
        ("unsupported_bit.sv", "HDLX-SV-TWO-STATE"),
        ("unsupported_data_int.sv", "HDLX-SV-DATA-INTEGER"),
    ],
)
def test_two_state_or_data_integer_types_fail_with_structured_diagnostic(
    fixture: str,
    code: str,
) -> None:
    with pytest.raises(UnsupportedConstructError) as captured:
        convert_file(
            FIXTURES / fixture,
            source_language="systemverilog",
            options=ConversionOptions(strict=True),
        )

    assert captured.value.code == code
    assert captured.value.diagnostic.source_span is not None
    assert captured.value.diagnostic.line == 1
    assert captured.value.diagnostic.column == 1

    if fixture == "unsupported_data_int.sv":
        with pytest.raises(UnsupportedConstructError) as signed_mixed:
            convert_file(
                FIXTURES / "unsupported_signed_mixed.sv",
                source_language="systemverilog",
                options=ConversionOptions(best_effort=True, strict=False),
            )
        assert signed_mixed.value.code == "HDLX-SV-SIGNED-SIZING"
        assert signed_mixed.value.diagnostic.source_span is not None
