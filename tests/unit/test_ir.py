"""Canonical RTL IR 的结构与语义约束测试。"""

import pytest
from pydantic import ValidationError

from hdl_x.ir import (
    ActiveLevel,
    AssignmentKind,
    BinaryExpr,
    BinaryOperator,
    CombinationalProcess,
    Comment,
    CommentKind,
    CommentPlacement,
    ContinuousAssignment,
    Design,
    EdgeKind,
    ForGenerate,
    Identifier,
    IfGenerate,
    Instance,
    Literal,
    LiteralKind,
    Module,
    NullStatement,
    ParameterBinding,
    Port,
    PortBinding,
    PortDirection,
    ProceduralAssignment,
    RangeDirection,
    ResetKind,
    ResetSpec,
    ScalarType,
    SequentialProcess,
    Signal,
    SourceLocation,
    SourceSpan,
    VectorRange,
    VectorType,
)


def test_model_construction_and_round_trip() -> None:
    span = SourceSpan(
        start=SourceLocation(file="logic.vhd", line=3, column=1, offset=20),
        end=SourceLocation(file="logic.vhd", line=3, column=12, offset=31),
    )
    assignment = ContinuousAssignment(
        target=Identifier(name="y"),
        value=BinaryExpr(
            left=Identifier(name="a"),
            operator=BinaryOperator.BITWISE_AND,
            right=Identifier(name="b"),
        ),
        source_span=span,
    )
    module = Module(
        name="and_gate",
        ports=[
            Port(name="a", direction=PortDirection.INPUT, rtl_type=ScalarType()),
            Port(name="b", direction=PortDirection.INPUT, rtl_type=ScalarType()),
            Port(name="y", direction=PortDirection.OUTPUT, rtl_type=ScalarType()),
        ],
        items=[assignment],
    )
    design = Design(name="example", modules=[module], top="and_gate")

    restored = Design.model_validate_json(design.model_dump_json())

    assert restored == design
    assert isinstance(restored.modules[0].items[0], ContinuousAssignment)
    assert restored.modules[0].continuous_assignments[0].source_span == span


def test_ir_nodes_preserve_leading_and_trailing_comments() -> None:
    span = SourceSpan(
        start=SourceLocation(file="logic.vhd", line=1, column=1),
        end=SourceLocation(file="logic.vhd", line=1, column=18),
    )
    leading = Comment(
        text="output data path",
        kind=CommentKind.DOC,
        placement=CommentPlacement.LEADING,
        source_span=span,
    )
    trailing = Comment(
        text="registered value",
        kind=CommentKind.LINE,
        placement=CommentPlacement.TRAILING,
    )
    signal = Signal(
        name="data_q",
        rtl_type=ScalarType(),
        leading_comments=[leading],
        trailing_comments=[trailing],
    )

    assert signal.leading_comments[0].source_span == span
    assert signal.trailing_comments[0].placement is CommentPlacement.TRAILING


def test_invalid_models_are_rejected() -> None:
    with pytest.raises(ValidationError, match="source span end precedes start"):
        SourceSpan(
            start=SourceLocation(line=2, column=1),
            end=SourceLocation(line=1, column=1),
        )

    with pytest.raises(ValidationError):
        ScalarType(unknown_field=True)

    with pytest.raises(ValidationError, match="reset_body requires reset semantics"):
        SequentialProcess(
            clock=Identifier(name="clk"),
            edge=EdgeKind.POSITIVE,
            reset_body=[NullStatement()],
        )

    with pytest.raises(ValidationError, match="design top"):
        Design(modules=[Module(name="child")], top="missing")


def test_source_span_checks_offsets_and_line_columns_independently() -> None:
    with pytest.raises(ValidationError, match="source span end precedes start"):
        SourceSpan(
            start=SourceLocation(line=5, column=4, offset=10),
            end=SourceLocation(line=4, column=20, offset=30),
        )

    with pytest.raises(ValidationError, match="source span end precedes start"):
        SourceSpan(
            start=SourceLocation(line=4, column=4, offset=30),
            end=SourceLocation(line=5, column=1, offset=10),
        )


def test_numeric_ir_fields_do_not_coerce_booleans_or_strings() -> None:
    with pytest.raises(ValidationError):
        SourceLocation(line=True, column=1)

    with pytest.raises(ValidationError):
        VectorRange(
            left=True,
            right=0,
            direction=RangeDirection.DESCENDING,
        )

    with pytest.raises(ValidationError):
        Literal(value=1, bit_width="8")


@pytest.mark.parametrize(
    "literal",
    [
        {"value": True, "literal_kind": LiteralKind.INTEGER},
        {"value": 1, "literal_kind": LiteralKind.BOOLEAN},
        {"value": 1, "literal_kind": LiteralKind.BIT},
        {"value": "10", "literal_kind": LiteralKind.BIT},
        {"value": "1010", "literal_kind": LiteralKind.BIT_VECTOR, "bit_width": 3},
        {"value": "text", "literal_kind": LiteralKind.STRING, "bit_width": 8},
        {"value": True, "bit_width": 2},
        {"value": "101", "bit_width": 2},
    ],
)
def test_literal_rejects_inconsistent_kind_value_and_width(
    literal: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        Literal(**literal)


def test_literal_accepts_consistent_kinds_and_widths() -> None:
    assert Literal(value=7, literal_kind=LiteralKind.INTEGER, bit_width=4).bit_width == 4
    assert Literal(value=False, literal_kind=LiteralKind.BOOLEAN).value is False
    assert Literal(value="'x'", literal_kind=LiteralKind.BIT).bit_width is None
    assert (
        Literal(value='"10xz"', literal_kind=LiteralKind.BIT_VECTOR, bit_width=4).bit_width
        == 4
    )


def test_vector_ranges_preserve_direction_and_width() -> None:
    descending = VectorRange(
        left=7,
        right=0,
        direction=RangeDirection.DESCENDING,
    )
    ascending = VectorRange(
        left=0,
        right=7,
        direction=RangeDirection.ASCENDING,
    )

    assert descending != ascending
    assert descending.width == ascending.width == 8
    assert VectorType(range=descending, signed=True).width == 8

    symbolic = VectorRange(
        left=BinaryExpr(
            left=Identifier(name="WIDTH"),
            operator=BinaryOperator.SUBTRACT,
            right=Literal(value=1),
        ),
        right=0,
        direction=RangeDirection.DESCENDING,
    )
    assert symbolic.width is None


def test_assignment_and_process_semantics_are_explicit() -> None:
    combinational_assignment = ProceduralAssignment(
        target=Identifier(name="next_q"),
        value=Identifier(name="d"),
        assignment_kind=AssignmentKind.BLOCKING,
    )
    sequential_assignment = ProceduralAssignment(
        target=Identifier(name="q"),
        value=Identifier(name="d"),
        assignment_kind=AssignmentKind.NON_BLOCKING,
    )
    combinational = CombinationalProcess(body=[combinational_assignment])
    sequential = SequentialProcess(
        clock=Identifier(name="clk"),
        edge=EdgeKind.NEGATIVE,
        reset=ResetSpec(
            signal=Identifier(name="reset_n"),
            kind=ResetKind.ASYNCHRONOUS,
            active_level=ActiveLevel.LOW,
        ),
        reset_body=[
            ProceduralAssignment(
                target=Identifier(name="q"),
                value=Literal(value=0),
                assignment_kind=AssignmentKind.NON_BLOCKING,
            )
        ],
        body=[sequential_assignment],
    )

    assert combinational.body[0].assignment_kind is AssignmentKind.BLOCKING
    assert sequential.edge is EdgeKind.NEGATIVE
    assert sequential.reset is not None
    assert sequential.reset.kind is ResetKind.ASYNCHRONOUS
    assert sequential.reset.active_level is ActiveLevel.LOW
    assert sequential.body[0].assignment_kind is AssignmentKind.NON_BLOCKING


def test_instance_supports_named_and_positional_bindings() -> None:
    named = Instance(
        referenced_unit="child",
        name="u_child",
        parameter_bindings=[
            ParameterBinding(formal="WIDTH", value=Literal(value=8))
        ],
        port_bindings=[
            PortBinding(formal="clk", value=Identifier(name="clk")),
            PortBinding(formal="unused", value=None),
        ],
    )
    positional = Instance(
        referenced_unit="child",
        name="u_child_positional",
        port_bindings=[
            PortBinding(position=0, value=Identifier(name="clk")),
            PortBinding(position=1, value=Identifier(name="q")),
        ],
    )

    assert named.parameter_bindings[0].formal == "WIDTH"
    assert named.port_bindings[1].value is None
    assert [binding.position for binding in positional.port_bindings] == [0, 1]

    with pytest.raises(ValidationError, match="exactly one"):
        PortBinding(formal="a", position=0, value=Identifier(name="a"))
    with pytest.raises(ValidationError, match="cannot mix"):
        Instance(
            referenced_unit="child",
            name="mixed",
            port_bindings=[
                PortBinding(formal="a", value=Identifier(name="a")),
                PortBinding(position=1, value=Identifier(name="b")),
            ],
        )


def test_generate_nodes_preserve_nested_hierarchy() -> None:
    instance = Instance(referenced_unit="bit_cell", name="u_bit")
    conditional = IfGenerate(
        label="g_optional",
        condition=Identifier(name="ENABLE"),
        then_body=[instance],
    )
    generated = ForGenerate(
        label="g_bits",
        index_name="i",
        range=VectorRange(
            left=0,
            right=7,
            direction=RangeDirection.ASCENDING,
        ),
        body=[Signal(name="local", rtl_type=ScalarType()), conditional],
    )
    module = Module(name="top", items=[generated])

    restored = Module.model_validate_json(module.model_dump_json())

    assert restored.generates[0].label == "g_bits"
    assert isinstance(restored.generates[0].body[1], IfGenerate)
    assert restored.generates[0].body[1].then_body[0].name == "u_bit"
