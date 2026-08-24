from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

from hdl_x.frontend import VerilogFrontend
from hdl_x.ir import (
    ContinuousAssignment,
    ForGenerate,
    IfGenerate,
    IfStatement,
    ProceduralAssignment,
    ScalarType,
    Signal,
    VectorType,
)

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "verilog"


def test_real_slang_verilog_frontend_produces_pure_canonical_ir() -> None:
    frontend = VerilogFrontend()

    raw = frontend.parse(FIXTURES / "v3_simple_assign.v")
    design = frontend.adapter.adapt(raw)

    assert design.top == "V3SimpleAssign"
    assert [module.name for module in design.modules] == ["V3SimpleAssign"]
    module = design.modules[0]
    assert [(port.name, port.direction.value) for port in module.ports] == [
        ("a", "input"),
        ("b", "input"),
        ("y", "output"),
    ]
    assert all(isinstance(port.rtl_type, ScalarType) for port in module.ports)
    assert len(module.items) == 1
    assert isinstance(module.items[0], ContinuousAssignment)
    assert module.source_span is not None
    assert module.source_span.start.line == 1
    assert module.source_span.start.column == 1
    _assert_no_pyslang_objects(raw)
    _assert_no_pyslang_objects(design)


def test_real_slang_generate_preserves_hierarchy_range_and_local_signal() -> None:
    design = VerilogFrontend().parse_design(FIXTURES / "v3_generate_for.v")

    generate = design.modules[0].generates[0]
    assert isinstance(generate, ForGenerate)
    assert generate.label == "g_bit"
    assert generate.index_name == "i"
    assert generate.range.direction.value == "ascending"
    assert [type(item) for item in generate.body] == [
        Signal,
        ContinuousAssignment,
        ContinuousAssignment,
    ]
    assert [comment.text for comment in generate.leading_comments] == [
        "per-bit hierarchy"
    ]
    assert [comment.text for comment in generate.body[0].leading_comments] == [
        "local generated signal"
    ]

    conditional = VerilogFrontend().parse_design(
        FIXTURES / "v3_generate_if.v"
    ).modules[0].generates[0]
    assert isinstance(conditional, IfGenerate)
    assert conditional.label == "g_enabled"
    assert conditional.else_body == []


def test_verilog_integer_is_preserved_as_signed_32_bit_four_state_vector() -> None:
    design = VerilogFrontend().parse_design(FIXTURES / "v3_integer_counter.v")

    count_type = design.modules[0].ports[-1].rtl_type
    assert isinstance(count_type, VectorType)
    assert count_type.width == 32
    assert count_type.signed is True
    assert count_type.four_state is True


def test_real_slang_preserves_nested_spans_and_comment_association() -> None:
    frontend = VerilogFrontend()

    design = frontend.parse_design(FIXTURES / "v3_comments.v")

    assert frontend.unassociated_comments == ()
    module = design.modules[0]
    assert (module.source_span.start.line, module.source_span.end.line) == (2, 18)
    assert [
        (port.name, port.source_span.start.line, port.source_span.end.line)
        for port in module.ports
    ] == [("a", 4, 4), ("b", 5, 5), ("y", 6, 6)]
    assert [comment.text for comment in module.leading_comments] == [
        "commented module"
    ]
    assert [comment.text for comment in module.ports[0].leading_comments] == [
        "input a docs"
    ]
    assert [comment.text for comment in module.ports[0].trailing_comments] == [
        "input a trailing"
    ]

    process = module.processes[0]
    assert (process.source_span.start.line, process.source_span.end.line) == (9, 17)
    assert [comment.text for comment in process.leading_comments] == [
        "combinational process"
    ]
    statement = process.body[0]
    assert isinstance(statement, IfStatement)
    assert (statement.source_span.start.line, statement.source_span.end.line) == (11, 16)
    assert [comment.text for comment in statement.leading_comments] == ["branch docs"]
    true_assignment = statement.then_body[0]
    false_assignment = statement.else_body[0]
    assert isinstance(true_assignment, ProceduralAssignment)
    assert isinstance(false_assignment, ProceduralAssignment)
    assert true_assignment.source_span.start.line == 12
    assert false_assignment.source_span.start.line == 15
    assert [comment.text for comment in true_assignment.trailing_comments] == [
        "true assignment"
    ]
    assert [comment.text for comment in false_assignment.leading_comments] == [
        "false assignment"
    ]


def _assert_no_pyslang_objects(value: object, seen: set[int] | None = None) -> None:
    if seen is None:
        seen = set()
    if value is None or isinstance(value, str | bytes | int | float | bool | Path):
        return
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)
    assert not type(value).__module__.startswith("pyslang")

    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_pyslang_objects(key, seen)
            _assert_no_pyslang_objects(item, seen)
    elif isinstance(value, list | tuple | set | frozenset):
        for item in value:
            _assert_no_pyslang_objects(item, seen)
    elif is_dataclass(value) and not isinstance(value, type):
        for item in fields(value):
            _assert_no_pyslang_objects(getattr(value, item.name), seen)
    elif hasattr(type(value), "model_fields"):
        for field_name in type(value).model_fields:
            _assert_no_pyslang_objects(getattr(value, field_name), seen)
