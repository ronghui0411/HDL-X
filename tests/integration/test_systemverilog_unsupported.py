from pathlib import Path

import pytest

from hdl_x.diagnostics import UnsupportedConstructError
from hdl_x.frontend import SystemVerilogFrontend

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"


@pytest.mark.parametrize(
    ("fixture", "code"),
    [
        ("unsupported_program.sv", "HDLX-SV-PROGRAM"),
        ("unsupported_typedef.sv", "HDLX-SV-TYPEDEF"),
        ("unsupported_always.sv", "HDLX-SV-ALWAYS"),
        ("unsupported_assertion.sv", "HDLX-SV-ASSERTION"),
    ],
)
def test_real_slang_frontend_structurally_rejects_more_unsupported_families(
    fixture: str,
    code: str,
) -> None:
    with pytest.raises(UnsupportedConstructError) as raised:
        SystemVerilogFrontend().parse_design(FIXTURES / fixture)

    assert raised.value.code == code
    assert raised.value.diagnostic.line is not None
    assert raised.value.diagnostic.column is not None
    assert raised.value.diagnostic.source_span is not None

    if fixture == "unsupported_program.sv":
        for extra_fixture, extra_code in (
            ("unsupported_generate.sv", "HDLX-SV-GENERATE"),
            ("unsupported_include.sv", "HDLX-SV-COMPILATION-UNIT"),
        ):
            with pytest.raises(UnsupportedConstructError) as extra:
                SystemVerilogFrontend().parse_design(FIXTURES / extra_fixture)
            assert extra.value.code == extra_code
            assert extra.value.diagnostic.source_span is not None
