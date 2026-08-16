"""真实 VHDL frontend 到 Verilog 的 common comment preservation 回归。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import FrontendError
from hdl_x.frontend import VhdlFrontend
from hdl_x.frontend.comments import associate_comments_by_source_span, scan_vhdl_comments
from hdl_x.ir import (
    CommentPlacement,
    ContinuousAssignment,
    ForGenerate,
    Identifier,
    Module,
    SourceLocation,
    SourceSpan,
)
from hdl_x.pipeline import ConversionOptions, convert_file

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"
GOLDEN = Path(__file__).parents[1] / "golden"


def _span(file: Path, line: int, column: int) -> SourceSpan:
    location = SourceLocation(file=str(file), line=line, column=column)
    return SourceSpan(start=location, end=location)


def test_real_pipeline_preserves_common_comments_and_complete_golden() -> None:
    source_path = FIXTURES / "m7_comments.vhd"
    expected = (GOLDEN / "m7_comments.v").read_text(encoding="utf-8")
    frontend = VhdlFrontend()

    result = convert_file(
        source_path,
        options=ConversionOptions(strict=False, best_effort=True),
        frontend=frontend,
    )
    module = result.design.modules[0]
    process = module.processes[0]

    assert result.text == expected
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "HDLX-COMMENT-UNASSOCIATED"
    ]
    assert [comment.text for comment in module.leading_comments] == [
        "Commented datapath"
    ]
    assert [comment.text for comment in module.ports[0].leading_comments] == [
        "source port"
    ]
    assert [comment.text for comment in module.ports[0].trailing_comments] == [
        "sampled input"
    ]
    assert [comment.text for comment in module.signals[0].leading_comments] == [
        "intermediate signal"
    ]
    assert [
        comment.text
        for item in module.items
        if isinstance(item, ContinuousAssignment)
        for comment in item.leading_comments
    ] == ["internal connection", "concurrent output"]
    assert [comment.text for comment in process.leading_comments] == [
        "combinational output process"
    ]
    assert [comment.text for comment in process.body[0].leading_comments] == [
        "process assignment"
    ]
    assert [comment.text for comment in frontend.unassociated_comments] == [
        "context header must remain unassociated",
        "library context must not attach to the entity",
        "context import must remain unassociated",
        "architecture heading must remain unassociated",
    ]

    attached = [
        *module.leading_comments,
        *module.trailing_comments,
        *(
            comment
            for node in [*module.parameters, *module.ports, *module.signals, *module.items]
            for comment in [*node.leading_comments, *node.trailing_comments]
        ),
        *(
            comment
            for statement in process.body
            for comment in [*statement.leading_comments, *statement.trailing_comments]
        ),
    ]
    spans = [comment.source_span for comment in attached]
    assert all(span is not None for span in spans)
    assert len(spans) == len({span.model_dump_json() for span in spans if span is not None})


def test_source_aware_association_does_not_cross_context_or_architecture_tokens() -> None:
    source_path = Path("safe_comments.vhd").resolve()
    source = """-- header
library ieee;
-- import note
use ieee.std_logic_1164.all;
--! module docs
entity SafeComments is
end entity;
-- architecture note
architecture rtl of SafeComments is
begin
-- assignment docs
y <= a;
end architecture;
"""
    module = Module(name="SafeComments", source_span=_span(source_path, 6, 8))
    assignment = ContinuousAssignment(
        target=Identifier(name="y"),
        value=Identifier(name="a"),
        source_span=_span(source_path, 12, 1),
    )
    comments = scan_vhdl_comments(source, file=source_path)

    association = associate_comments_by_source_span(
        comments,
        [module, assignment],
        source=source,
    )

    assert [comment.text for comment in association.associations[0].leading_comments] == [
        "module docs"
    ]
    assert [comment.text for comment in association.associations[1].leading_comments] == [
        "assignment docs"
    ]
    assert [comment.text for comment in association.unassociated_comments] == [
        "header",
        "import note",
        "architecture note",
    ]
    assert all(
        comment.placement is CommentPlacement.LEADING
        for comment in association.unassociated_comments
    )


def test_unassociated_comment_state_resets_between_parse_attempts() -> None:
    source_path = FIXTURES / "m7_comments.vhd"
    frontend = VhdlFrontend()

    frontend.parse_design(source_path)
    assert frontend.unassociated_comments

    with pytest.raises(FrontendError):
        frontend.parse_design(FIXTURES / "does_not_exist.vhd")

    assert frontend.unassociated_comments == ()


def test_real_generate_label_comment_attaches_and_renders() -> None:
    result = convert_file(
        FIXTURES / "m7_generate_for.vhd",
        options=ConversionOptions(strict=True),
    )
    generate = result.design.modules[0].generates[0]

    assert isinstance(generate, ForGenerate)
    assert generate.label == "g_lane"
    assert [comment.text for comment in generate.leading_comments] == [
        "one generated cell per lane"
    ]
    assert "// one generated cell per lane" in result.text
    assert "begin : g_lane" in result.text
