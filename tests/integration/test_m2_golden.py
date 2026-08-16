"""Milestone 2 真实 VHDL frontend 到完整 Verilog golden 的回归。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import DiagnosticSeverity, UnsupportedConstructError
from hdl_x.frontend.comments import (
    associate_comments_by_source_span,
    scan_vhdl_comments,
)
from hdl_x.ir import CommentKind, CommentPlacement
from hdl_x.pipeline import ConversionOptions, convert_file

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"
GOLDEN = Path(__file__).parents[1] / "golden"


@pytest.mark.parametrize(
    "case_name",
    [
        "simple_and",
        "simple_or",
        "simple_xor",
        "simple_not",
        "vector_assignment",
        "simple_expression",
    ],
)
def test_m2_real_pipeline_matches_complete_golden(case_name: str) -> None:
    source_path = FIXTURES / f"m2_{case_name}.vhd"
    expected = (GOLDEN / f"m2_{case_name}.v").read_text(encoding="utf-8")

    result = convert_file(
        source_path,
        options=ConversionOptions(strict=True),
    )

    assert result.text == expected
    assert result.design.top == result.design.modules[0].name
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("m2_unsupported_delay.vhd", "HDLX-VHDL-DELAY"),
        ("unsupported_wait.vhd", "HDLX-VHDL-WAIT"),
    ],
)
@pytest.mark.parametrize(
    "options",
    [
        ConversionOptions(strict=True),
        ConversionOptions(strict=False, best_effort=True),
    ],
    ids=["strict", "best-effort"],
)
def test_m2_unsafe_constructs_fail_with_structured_diagnostics(
    fixture_name: str,
    expected_code: str,
    options: ConversionOptions,
) -> None:
    source_path = (FIXTURES / fixture_name).resolve()

    with pytest.raises(UnsupportedConstructError) as raised:
        convert_file(source_path, options=options)

    diagnostic = raised.value.diagnostic
    assert diagnostic.code == expected_code
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.file == str(source_path)
    assert diagnostic.line is not None
    assert diagnostic.line > 0
    assert diagnostic.message


def test_m2_comments_associate_to_real_module_port_and_assignment_spans() -> None:
    source_path = (FIXTURES / "m2_simple_and.vhd").resolve()
    source = source_path.read_text(encoding="utf-8")
    result = convert_file(source_path, options=ConversionOptions(strict=True))
    module = result.design.modules[0]
    nodes = [module, *module.ports, *module.items]
    before_association = [node.model_dump_json() for node in nodes]

    comments = scan_vhdl_comments(source, file=source_path)
    association = associate_comments_by_source_span(comments, nodes)

    assert association.unassociated_comments == ()
    assert [comment.text for comment in association.associations[0].leading_comments] == [
        "Simple AND gate"
    ]
    assert association.associations[0].leading_comments[0].kind is CommentKind.DOC
    assert [comment.text for comment in association.associations[1].trailing_comments] == [
        "left operand"
    ]
    assert (
        association.associations[1].trailing_comments[0].placement
        is CommentPlacement.TRAILING
    )
    assert [comment.text for comment in association.associations[-1].leading_comments] == [
        "drive the result"
    ]
    # 独立关联函数保持纯函数语义，frontend 则已完成同一安全附着。
    assert [node.model_dump_json() for node in nodes] == before_association
    assert [comment.text for comment in module.leading_comments] == ["Simple AND gate"]
    assert [comment.text for comment in module.ports[0].trailing_comments] == [
        "left operand"
    ]
    assert [comment.text for comment in module.items[0].leading_comments] == [
        "drive the result"
    ]
