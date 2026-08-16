"""VHDL Raw 表示到 canonical IR 的单元测试。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import SemanticError
from hdl_x.ir import (
    AssignmentKind,
    BinaryExpr,
    BinaryOperator,
    CombinationalProcess,
    ContinuousAssignment,
    IfStatement,
    ProceduralAssignment,
    RangeDirection,
    TernaryExpr,
    UnaryExpr,
    UnaryOperator,
    VectorType,
)
from hdl_x.parser.ghdl import (
    RawArchitecture,
    RawBinaryExpression,
    RawBinaryOperator,
    RawCombinationalProcess,
    RawConcurrentAssignment,
    RawConditionalExpression,
    RawDesign,
    RawEntity,
    RawIdentifier,
    RawIfStatement,
    RawIndexExpression,
    RawLiteral,
    RawLiteralKind,
    RawPort,
    RawPortDirection,
    RawProceduralAssignment,
    RawRange,
    RawRangeDirection,
    RawSignal,
    RawType,
    RawTypeKind,
    RawUnaryExpression,
    RawUnaryOperator,
)
from hdl_x.parser.vhdl_adapter import VhdlAdapter


def test_adapter_maps_ports_ranges_and_logic_operators() -> None:
    width = RawLiteral(value=8, kind=RawLiteralKind.INTEGER)
    vector = RawType(
        kind=RawTypeKind.VECTOR,
        source_name="std_logic_vector",
        four_state=True,
        range=RawRange(
            left=RawBinaryExpression(
                left=width,
                operator=RawBinaryOperator.SUBTRACT,
                right=RawLiteral(value=1, kind=RawLiteralKind.INTEGER),
            ),
            right=RawLiteral(value=0, kind=RawLiteralKind.INTEGER),
            direction=RawRangeDirection.DOWNTO,
        ),
    )
    entity = RawEntity(
        name="Logic",
        ports=(
            RawPort("a", RawPortDirection.IN, vector),
            RawPort("b", RawPortDirection.IN, vector),
            RawPort("y", RawPortDirection.OUT, vector),
        ),
    )
    value = RawBinaryExpression(
        left=RawUnaryExpression(
            operator=RawUnaryOperator.NOT,
            operand=RawIdentifier("a"),
        ),
        operator=RawBinaryOperator.AND,
        right=RawIdentifier("b"),
    )
    architecture = RawArchitecture(
        name="rtl",
        entity_name="logic",
        items=(RawConcurrentAssignment(RawIdentifier("y"), value),),
    )

    design = VhdlAdapter().adapt(RawDesign(Path("logic.vhd"), (entity,), (architecture,)))

    module = design.modules[0]
    assert design.top == "Logic"
    assert isinstance(module.ports[0].rtl_type, VectorType)
    assert module.ports[0].rtl_type.range.direction is RangeDirection.DESCENDING
    assignment = module.items[0]
    assert isinstance(assignment, ContinuousAssignment)
    assert isinstance(assignment.value, BinaryExpr)
    assert assignment.value.operator is BinaryOperator.BITWISE_AND
    assert isinstance(assignment.value.left, UnaryExpr)
    assert assignment.value.left.operator is UnaryOperator.BITWISE_NOT


def test_adapter_uses_logical_operators_for_boolean_values() -> None:
    boolean = RawType(kind=RawTypeKind.BOOLEAN, source_name="boolean")
    entity = RawEntity(
        name="BoolLogic",
        ports=(
            RawPort("a", RawPortDirection.IN, boolean),
            RawPort("b", RawPortDirection.IN, boolean),
            RawPort("y", RawPortDirection.OUT, boolean),
        ),
    )
    value = RawBinaryExpression(
        left=RawUnaryExpression(RawUnaryOperator.NOT, RawIdentifier("a")),
        operator=RawBinaryOperator.OR,
        right=RawIdentifier("b"),
    )
    raw = RawDesign(
        Path("boolean.vhd"),
        (entity,),
        (
            RawArchitecture(
                "rtl",
                "BOOLLOGIC",
                (RawConcurrentAssignment(RawIdentifier("y"), value),),
            ),
        ),
    )

    expression = VhdlAdapter().adapt(raw).modules[0].continuous_assignments[0].value

    assert isinstance(expression, BinaryExpr)
    assert expression.operator is BinaryOperator.LOGICAL_OR
    assert isinstance(expression.left, UnaryExpr)
    assert expression.left.operator is UnaryOperator.LOGICAL_NOT


def test_adapter_maps_conditional_expression_to_ternary() -> None:
    scalar = RawType(
        kind=RawTypeKind.SCALAR,
        source_name="std_logic",
        four_state=True,
    )
    entity = RawEntity(
        name="Mux",
        ports=(
            RawPort("a", RawPortDirection.IN, scalar),
            RawPort("b", RawPortDirection.IN, scalar),
            RawPort("sel", RawPortDirection.IN, scalar),
            RawPort("y", RawPortDirection.OUT, scalar),
        ),
    )
    condition = RawBinaryExpression(
        RawIdentifier("sel"),
        RawBinaryOperator.EQUAL,
        RawLiteral("1", RawLiteralKind.BIT),
    )
    raw = RawDesign(
        Path("mux.vhd"),
        (entity,),
        (
            RawArchitecture(
                "rtl",
                "Mux",
                (
                    RawConcurrentAssignment(
                        RawIdentifier("y"),
                        RawConditionalExpression(condition, RawIdentifier("a"), RawIdentifier("b")),
                    ),
                ),
            ),
        ),
    )

    value = VhdlAdapter().adapt(raw).modules[0].continuous_assignments[0].value

    assert isinstance(value, TernaryExpr)
    assert value.when_true.name == "a"
    assert value.when_false.name == "b"


def test_adapter_maps_combinational_process_and_preserves_latch_shape() -> None:
    scalar = RawType(
        kind=RawTypeKind.SCALAR,
        source_name="std_logic",
        four_state=True,
    )
    entity = RawEntity(
        name="Latch",
        ports=(
            RawPort("d", RawPortDirection.IN, scalar),
            RawPort("en", RawPortDirection.IN, scalar),
            RawPort("q", RawPortDirection.OUT, scalar),
        ),
    )
    condition = RawBinaryExpression(
        RawIdentifier("en"),
        RawBinaryOperator.EQUAL,
        RawLiteral("1", RawLiteralKind.BIT),
    )
    process = RawCombinationalProcess(
        "latch_p",
        (RawIdentifier("d"), RawIdentifier("en")),
        (
            RawIfStatement(
                condition,
                (RawProceduralAssignment(RawIdentifier("q"), RawIdentifier("d")),),
            ),
        ),
    )
    raw = RawDesign(
        Path("latch.vhd"),
        (entity,),
        (RawArchitecture("rtl", "Latch", (process,)),),
    )

    canonical = VhdlAdapter().adapt(raw).modules[0].processes[0]

    assert isinstance(canonical, CombinationalProcess)
    assert canonical.label == "latch_p"
    assert [item.name for item in canonical.sensitivity] == ["d", "en"]
    statement = canonical.body[0]
    assert isinstance(statement, IfStatement)
    assert statement.else_body == []
    assignment = statement.then_body[0]
    assert isinstance(assignment, ProceduralAssignment)
    assert assignment.assignment_kind is AssignmentKind.BLOCKING


def test_adapter_rejects_combinational_signal_dependency_across_nested_paths() -> None:
    scalar = RawType(kind=RawTypeKind.SCALAR, source_name="bit")
    entity = RawEntity(
        name="NestedDependency",
        ports=(
            RawPort("a", RawPortDirection.IN, scalar),
            RawPort("sel", RawPortDirection.IN, scalar),
            RawPort("y", RawPortDirection.OUT, scalar),
        ),
    )
    process = RawCombinationalProcess(
        label="dependency_p",
        sensitivity=(RawIdentifier("a"), RawIdentifier("sel")),
        body=(
            RawIfStatement(
                condition=RawIdentifier("sel"),
                then_body=(RawProceduralAssignment(RawIdentifier("x"), RawIdentifier("a")),),
                else_body=(
                    RawIfStatement(
                        condition=RawIdentifier("a"),
                        then_body=(
                            RawProceduralAssignment(RawIdentifier("y"), RawIdentifier("x")),
                        ),
                    ),
                ),
            ),
        ),
    )
    raw = RawDesign(
        Path("nested_dependency.vhd"),
        (entity,),
        (
            RawArchitecture(
                "rtl",
                "NestedDependency",
                items=(process,),
                signals=(RawSignal("x", scalar),),
            ),
        ),
    )

    with pytest.raises(SemanticError) as raised:
        VhdlAdapter().adapt(raw)

    assert raised.value.code == "HDLX-VHDL-PROCESS-SIGNAL-DEPENDENCY"


def test_adapter_counts_indexed_target_index_as_process_read() -> None:
    scalar = RawType(kind=RawTypeKind.SCALAR, source_name="bit")
    vector = RawType(
        kind=RawTypeKind.VECTOR,
        source_name="bit_vector",
        range=RawRange(
            RawLiteral(1, RawLiteralKind.INTEGER),
            RawLiteral(0, RawLiteralKind.INTEGER),
            RawRangeDirection.DOWNTO,
        ),
    )
    entity = RawEntity(
        name="IndexedDependency",
        ports=(
            RawPort("a", RawPortDirection.IN, scalar),
            RawPort("idx", RawPortDirection.OUT, scalar),
            RawPort("x", RawPortDirection.OUT, vector),
        ),
    )
    process = RawCombinationalProcess(
        label=None,
        sensitivity=(RawIdentifier("a"),),
        body=(
            RawProceduralAssignment(
                RawIndexExpression(RawIdentifier("x"), RawIdentifier("idx")),
                RawIdentifier("a"),
            ),
            RawProceduralAssignment(RawIdentifier("idx"), RawIdentifier("a")),
        ),
    )
    raw = RawDesign(
        Path("indexed_dependency.vhd"),
        (entity,),
        (RawArchitecture("rtl", "IndexedDependency", items=(process,)),),
    )

    with pytest.raises(SemanticError) as raised:
        VhdlAdapter().adapt(raw)

    assert raised.value.code == "HDLX-VHDL-PROCESS-SIGNAL-DEPENDENCY"
