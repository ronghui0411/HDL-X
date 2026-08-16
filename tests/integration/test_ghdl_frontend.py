"""真实 pyGHDL/libghdl frontend 集成测试。"""

from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

pytest.importorskip("pyGHDL", reason="真实 GHDL integration 需要 pyGHDL wheel")

from hdl_x.diagnostics import FrontendError, UnsupportedConstructError
from hdl_x.frontend import VhdlFrontend
from hdl_x.generator import VerilogGenerator
from hdl_x.ir import (
    AssignmentKind,
    BinaryExpr,
    BinaryOperator,
    CaseStatement,
    CombinationalProcess,
    IfStatement,
    ProceduralAssignment,
    RangeDirection,
    TernaryExpr,
    UnaryExpr,
    UnaryOperator,
    VectorType,
)
from hdl_x.parser.ghdl import (
    PyGhdlBackend,
    RawBinaryExpression,
    RawCombinationalProcess,
    RawDesign,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"


def _walk_dataclasses(value: object):
    yield value
    if is_dataclass(value) and not isinstance(value, type):
        for item in fields(value):
            yield from _walk_dataclasses(getattr(value, item.name))
    elif isinstance(value, tuple | list):
        for item in value:
            yield from _walk_dataclasses(item)


def test_real_ghdl_parses_simple_logic_without_frontend_node_leaks() -> None:
    raw = PyGhdlBackend().parse(FIXTURES / "simple_logic.vhd")

    assert isinstance(raw, RawDesign)
    assert raw.entities[0].name == "SimpleLogic"
    assert [port.name for port in raw.entities[0].ports] == ["a", "b", "y"]
    assert isinstance(raw.architectures[0].items[0].value, RawBinaryExpression)
    assert all(
        not type(item).__module__.startswith(("pyGHDL", "pyVHDLModel"))
        for item in _walk_dataclasses(raw)
    )


def test_real_ghdl_preserves_vector_direction_generic_and_expression_tree() -> None:
    design = VhdlFrontend().parse_design(FIXTURES / "vector_logic.vhd")

    module = design.modules[0]
    assert module.name == "VectorLogic"
    assert module.parameters[0].name == "WIDTH"
    assert module.parameters[0].default.value == 8
    assert isinstance(module.ports[0].rtl_type, VectorType)
    assert module.ports[0].rtl_type.range.direction is RangeDirection.DESCENDING
    assert isinstance(module.ports[1].rtl_type, VectorType)
    assert module.ports[1].rtl_type.range.direction is RangeDirection.ASCENDING
    expression = module.continuous_assignments[0].value
    assert isinstance(expression, BinaryExpr)
    assert expression.operator is BinaryOperator.BITWISE_XOR
    assert expression.source_span is not None
    assert expression.source_span.start.line == 17


def test_real_ghdl_maps_conditional_concurrent_assignment_to_ternary() -> None:
    design = VhdlFrontend().parse_design(FIXTURES / "conditional_assignment.vhd")

    assignment = design.modules[0].continuous_assignments[0]
    assert isinstance(assignment.value, TernaryExpr)
    assert isinstance(assignment.value.condition, BinaryExpr)
    assert assignment.value.condition.operator is BinaryOperator.CASE_EQUAL
    assert assignment.value.when_true.name == "a"
    assert assignment.value.when_false.name == "b"


def test_real_ghdl_maps_if_else_process_and_blocking_assignments() -> None:
    raw = PyGhdlBackend().parse(FIXTURES / "if_else_mux.vhd")
    raw_process = raw.architectures[0].items[0]
    assert isinstance(raw_process, RawCombinationalProcess)
    assert raw_process.label == "mux_p"
    assert [item.name for item in raw_process.sensitivity] == ["a", "b", "sel"]

    process = VhdlFrontend().parse_design(FIXTURES / "if_else_mux.vhd").modules[0].processes[0]
    assert isinstance(process, CombinationalProcess)
    statement = process.body[0]
    assert isinstance(statement, IfStatement)
    assert len(statement.then_body) == 1
    assert len(statement.else_body) == 1
    assert all(
        isinstance(item, ProceduralAssignment)
        and item.assignment_kind is AssignmentKind.BLOCKING
        for item in (*statement.then_body, *statement.else_body)
    )


def test_real_ghdl_preserves_nested_if_and_elsif_structure() -> None:
    process = VhdlFrontend().parse_design(FIXTURES / "nested_if.vhd").modules[0].processes[0]

    outer = process.body[0]
    assert isinstance(outer, IfStatement)
    assert isinstance(outer.then_body[0], IfStatement)
    assert len(outer.else_body) == 1
    assert isinstance(outer.else_body[0], IfStatement)
    assert len(outer.else_body[0].else_body) == 1


def test_real_ghdl_maps_vector_process_and_marks_output_reg_downstream() -> None:
    design = VhdlFrontend().parse_design(FIXTURES / "vector_process.vhd")

    process = design.modules[0].processes[0]
    assert [item.name for item in process.sensitivity] == ["a", "b"]
    assignment = process.body[0]
    assert isinstance(assignment, ProceduralAssignment)
    assert isinstance(assignment.value, BinaryExpr)
    assert assignment.value.operator is BinaryOperator.BITWISE_XOR
    assert isinstance(assignment.value.right, UnaryExpr)
    assert assignment.value.right.operator is UnaryOperator.BITWISE_NOT

    output = VerilogGenerator().generate(
        VhdlFrontend().parse_design(FIXTURES / "output_reg.vhd")
    )
    assert "output reg y" in output
    assert "y = a | b;" in output


def test_real_ghdl_maps_basic_case_statement() -> None:
    process = VhdlFrontend().parse_design(FIXTURES / "case_logic.vhd").modules[0].processes[0]

    statement = process.body[0]
    assert isinstance(statement, CaseStatement)
    assert [item.selectors[0].value for item in statement.alternatives] == ["00", "01"]
    assert [item.selectors[0].bit_width for item in statement.alternatives] == [2, 2]
    assert len(statement.default_body) == 1


def test_real_ghdl_preserves_intentional_latch_without_inventing_else() -> None:
    design = VhdlFrontend().parse_design(FIXTURES / "latch.vhd")

    statement = design.modules[0].processes[0].body[0]
    assert isinstance(statement, IfStatement)
    assert statement.else_body == []
    output = VerilogGenerator().generate(design)
    assert "output reg q" in output
    assert "if (en === 1'b1) begin" in output
    assert "end else begin" not in output


@pytest.mark.parametrize(
    ("fixture", "code", "line"),
    [
        ("unsupported_wait.vhd", "HDLX-VHDL-WAIT", 12),
        ("unsupported_process_delay.vhd", "HDLX-VHDL-DELAY", 12),
        ("unsupported_assert.vhd", "HDLX-VHDL-SEQUENTIAL-CONSTRUCT", 12),
    ],
)
def test_real_ghdl_reports_unsupported_sequential_constructs(
    fixture: str, code: str, line: int
) -> None:
    source = (FIXTURES / fixture).resolve()

    with pytest.raises(UnsupportedConstructError) as raised:
        PyGhdlBackend().parse(source)

    assert raised.value.code == code
    assert raised.value.diagnostic.file == str(source)
    assert raised.value.diagnostic.line == line


def test_real_ghdl_syntax_error_is_structured(tmp_path: Path) -> None:
    source = tmp_path / "broken.vhd"
    source.write_text("entity Broken is this is not VHDL;", encoding="utf-8")

    with pytest.raises(FrontendError) as raised:
        PyGhdlBackend().parse(source)

    assert raised.value.code == "HDLX-GHDL-ANALYZE"
    assert raised.value.diagnostic.file == str(source.resolve())
