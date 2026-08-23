from hdl_x.frontend import SystemVerilogCommentScanner
from hdl_x.ir import CommentKind, CommentPlacement


def test_systemverilog_comment_scanner_ignores_strings_and_escaped_identifiers() -> None:
    source = (
        'string value = "not // a comment and not /* a block */";\n'
        "wire \\name//part ; // trailing\n"
        "/* block\ncomment */\n"
    )

    comments = SystemVerilogCommentScanner(file="comments.sv").scan(source)

    assert [(comment.text, comment.kind, comment.placement) for comment in comments] == [
        ("trailing", CommentKind.LINE, CommentPlacement.TRAILING),
        ("block\ncomment", CommentKind.BLOCK, CommentPlacement.LEADING),
    ]
    assert comments[0].source_span is not None
    assert comments[0].source_span.start.line == 2
    assert comments[0].source_span.start.column == 20
    assert comments[1].source_span is not None
    assert comments[1].source_span.start.line == 3
    assert comments[1].source_span.end.line == 4
