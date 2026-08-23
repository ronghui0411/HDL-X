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
        ("unsupported_generate.sv", "HDLX-SV-GENERATE"),
        ("unsupported_include.sv", "HDLX-SV-COMPILATION-UNIT"),
        ("unsupported_macro_include.sv", "HDLX-SV-COMPILATION-UNIT"),
        ("unsupported_implicit_generate_local.sv", "HDLX-SV-GENERATE"),
        ("unsupported_unsigned_parameter.sv", "HDLX-SV-PARAMETER-SIGNEDNESS"),
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
