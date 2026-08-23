from pathlib import Path

import pytest

from hdl_x.diagnostics import UnsupportedConstructError
from hdl_x.frontend import SystemVerilogFrontend
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"


def test_systemverilog_frontend_preserves_module_comment_and_reports_internal() -> None:
    frontend = SystemVerilogFrontend()

    design = frontend.parse_design(FIXTURES / "sv_comments.sv")

    assert [comment.text for comment in design.modules[0].leading_comments] == [
        "SystemVerilog module comment"
    ]
    assert [comment.text for comment in frontend.unassociated_comments] == [
        "This internal comment cannot yet be associated safely."
    ]


def test_strict_systemverilog_conversion_rejects_unassociated_comment() -> None:
    with pytest.raises(UnsupportedConstructError) as captured:
        convert_file(
            FIXTURES / "sv_comments.sv",
            source_language="systemverilog",
            options=ConversionOptions(strict=True),
        )

    assert captured.value.code == "HDLX-COMMENT-UNASSOCIATED"
    assert captured.value.diagnostic.source_span is not None
    assert captured.value.diagnostic.source_span.start.line == 7
    assert captured.value.diagnostic.source_span.start.column == 5


def test_best_effort_systemverilog_conversion_warns_and_preserves_safe_comment() -> None:
    result = convert_file(
        FIXTURES / "sv_comments.sv",
        source_language="systemverilog",
        options=ConversionOptions(strict=False, best_effort=True),
    )

    assert result.text.startswith("/// SystemVerilog module comment\nmodule SvComments")
    assert [diagnostic.code for diagnostic in result.diagnostics].count(
        "HDLX-COMMENT-UNASSOCIATED"
    ) == 1
    diagnostic = next(
        item for item in result.diagnostics if item.code == "HDLX-COMMENT-UNASSOCIATED"
    )
    assert diagnostic.source_span is not None
    assert diagnostic.source_span.start.line == 7
    assert "This internal comment cannot yet be associated safely." in diagnostic.message
