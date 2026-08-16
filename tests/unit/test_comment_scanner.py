from __future__ import annotations

from hdl_x.frontend.comments import VhdlCommentScanner, scan_vhdl_comments
from hdl_x.ir import CommentKind, CommentPlacement


def test_scans_leading_and_trailing_comments_with_source_spans() -> None:
    source = "-- entity docs\nentity demo is -- public interface\nend entity;\n"

    comments = scan_vhdl_comments(source, file="demo.vhd")

    assert [(comment.text, comment.placement) for comment in comments] == [
        ("entity docs", CommentPlacement.LEADING),
        ("public interface", CommentPlacement.TRAILING),
    ]
    first_span = comments[0].source_span
    second_span = comments[1].source_span
    assert first_span is not None
    assert second_span is not None
    assert first_span.start.model_dump() == {
        "file": "demo.vhd",
        "line": 1,
        "column": 1,
        "offset": 0,
    }
    assert first_span.end.column == len("-- entity docs") + 1
    assert first_span.end.offset == len("-- entity docs")
    assert second_span.start.line == 2
    assert second_span.start.column == len("entity demo is ") + 1
    assert second_span.start.offset == source.index("-- public")
    assert second_span.end.offset == source.index("\n", source.index("-- public"))


def test_ignores_comment_markers_inside_vhdl_strings_and_escaped_quotes() -> None:
    source = (
        'plain <= "-- not a comment";\n'
        'quoted <= "say ""--"" here"; -- real comment\n'
        'mixed <= "escaped ""quote"""; -- second comment\n'
    )

    comments = scan_vhdl_comments(source)

    assert [comment.text for comment in comments] == ["real comment", "second comment"]
    assert all(comment.placement is CommentPlacement.TRAILING for comment in comments)


def test_preserves_consecutive_document_and_common_comments_in_order() -> None:
    source = (
        "--! First documentation line\n"
        "--! Second documentation line\n"
        "-- ordinary line\n"
        "--  deliberately aligned line\n"
        "signal ready : std_logic;\n"
    )

    comments = VhdlCommentScanner(file="comments.vhd").scan(source)

    assert [comment.text for comment in comments] == [
        "First documentation line",
        "Second documentation line",
        "ordinary line",
        " deliberately aligned line",
    ]
    assert [comment.kind for comment in comments] == [
        CommentKind.DOC,
        CommentKind.DOC,
        CommentKind.LINE,
        CommentKind.LINE,
    ]
    assert [comment.source_span.start.line for comment in comments if comment.source_span] == [
        1,
        2,
        3,
        4,
    ]


def test_crlf_offsets_include_original_line_endings() -> None:
    source = "signal a : bit;\r\n  -- next line\r\nsignal b : bit; -- tail\r\n"

    comments = scan_vhdl_comments(source)

    first_span = comments[0].source_span
    second_span = comments[1].source_span
    assert first_span is not None
    assert second_span is not None
    assert first_span.start.offset == source.index("-- next")
    assert first_span.start.line == 2
    assert first_span.start.column == 3
    assert first_span.end.offset == source.index("\r\n", first_span.start.offset)
    assert second_span.start.offset == source.index("-- tail")
    assert second_span.start.line == 3


def test_empty_comment_is_preserved_as_canonical_comment() -> None:
    comments = scan_vhdl_comments("--\n")

    assert len(comments) == 1
    assert comments[0].text == " "
    assert comments[0].kind is CommentKind.LINE
    assert comments[0].placement is CommentPlacement.LEADING


def test_source_without_final_newline_is_scanned() -> None:
    comments = scan_vhdl_comments("signal y : bit; -- output")

    assert len(comments) == 1
    assert comments[0].text == "output"
    assert comments[0].source_span is not None
    assert comments[0].source_span.end.offset == len("signal y : bit; -- output")


def test_lines_without_real_comments_produce_no_trivia() -> None:
    source = 'constant text : string := "doubled ""--"" marker";\n'

    assert scan_vhdl_comments(source) == []
