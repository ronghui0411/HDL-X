"""Verilog-2001 generator 与 driver lowering 测试。"""

import pytest

from hdl_x.diagnostics import GenerationError, SemanticError
from hdl_x.generator import VerilogGenerator
from hdl_x.ir import (
    ActiveLevel,
    AssignmentKind,
    BinaryExpr,
    BinaryOperator,
    BlockStatement,
    CaseAlternative,
    CaseStatement,
    CombinationalProcess,
    Comment,
    CommentKind,
    CommentPlacement,
    Concatenation,
    ContinuousAssignment,
    Design,
    DriverKind,
    EdgeKind,
    ForGenerate,
    ForStatement,
    FunctionCall,
    Identifier,
    IfGenerate,
    IfStatement,
    Index,
    Instance,
    IntegerType,
    Literal,
    LiteralKind,
    Module,
    NullStatement,
    Parameter,
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
    Slice,
    TernaryExpr,
    UnaryExpr,
    UnaryOperator,
    Variable,
    VectorRange,
    VectorType,
)
from hdl_x.transformer import NameStyle


def _generator() -> VerilogGenerator:
    return VerilogGenerator()


def _scalar_port(name: str, direction: PortDirection) -> Port:
    return Port(name=name, direction=direction, rtl_type=ScalarType())


def _nonblocking(target: str, value: object) -> ProceduralAssignment:
    return ProceduralAssignment(
        target=Identifier(name=target),
        value=value,
        assignment_kind=AssignmentKind.NON_BLOCKING,
    )


@pytest.mark.parametrize("direction", list(PortDirection))
def test_integer_ports_are_rejected_by_generator_defensively(
    direction: PortDirection,
) -> None:
    design = Design(
        modules=[
            Module(
                name="IntegerPort",
                ports=[
                    Port(
                        name="value",
                        direction=direction,
                        rtl_type=IntegerType(),
                    )
                ],
            )
        ]
    )

    with pytest.raises(GenerationError) as raised:
        _generator().generate(design)

    assert raised.value.code == "HDLX-GEN-PORT-TYPE"


def test_module_parameters_types_comments_and_expressions() -> None:
    width = Parameter(
        name="WIDTH",
        rtl_type=IntegerType(minimum=1),
        default=Literal(value=8),
        leading_comments=[Comment(text="data width", kind=CommentKind.DOC)],
    )
    vector_type = VectorType(
        range=VectorRange(
            left=BinaryExpr(
                left=Identifier(name="WIDTH"),
                operator=BinaryOperator.SUBTRACT,
                right=Literal(value=1),
            ),
            right=0,
            direction=RangeDirection.DESCENDING,
        ),
        signed=True,
    )
    expression = TernaryExpr(
        condition=UnaryExpr(
            operator=UnaryOperator.LOGICAL_NOT,
            operand=Identifier(name="sel_n"),
        ),
        when_true=Concatenation(
            parts=[
                BinaryExpr(
                    left=Identifier(name="a"),
                    operator=BinaryOperator.BITWISE_AND,
                    right=Identifier(name="b"),
                ),
                Identifier(name="b"),
            ]
        ),
        when_false=Slice(
            value=Identifier(name="a"),
            left=Literal(value=7),
            right=Literal(value=0),
            direction=RangeDirection.DESCENDING,
        ),
    )
    module = Module(
        name="data_path",
        parameters=[width],
        ports=[
            Port(name="a", direction=PortDirection.INPUT, rtl_type=vector_type),
            Port(name="b", direction=PortDirection.INPUT, rtl_type=vector_type),
            _scalar_port("sel_n", PortDirection.INPUT),
            Port(
                name="y",
                direction=PortDirection.OUTPUT,
                rtl_type=vector_type,
                trailing_comments=[
                    Comment(
                        text="translated output",
                        placement=CommentPlacement.TRAILING,
                    )
                ],
            ),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="y"),
                value=expression,
                leading_comments=[Comment(text="select the result")],
            )
        ],
        leading_comments=[Comment(text="data path unit", kind=CommentKind.BLOCK)],
    )

    output = _generator().generate(Design(modules=[module], top="data_path"))

    assert "/* data path unit */" in output
    assert "parameter integer WIDTH = 8" in output
    assert "input wire signed [WIDTH - 1:0] a" in output
    assert "output wire signed [WIDTH - 1:0] y" in output
    assert "/// data width" in output
    assert "// translated output" in output
    assert "assign y = !sel_n ? {a & b, b} : a[7:0];" in output
    assert output.endswith("endmodule\n")


def test_ascending_symbolic_ranges_preserve_index_orientation() -> None:
    ascending = VectorType(
        range=VectorRange(
            left=0,
            right=BinaryExpr(
                left=Identifier(name="WIDTH"),
                operator=BinaryOperator.SUBTRACT,
                right=Literal(value=1),
            ),
            direction=RangeDirection.ASCENDING,
        )
    )
    module = Module(
        name="ascending_bus",
        parameters=[Parameter(name="WIDTH", rtl_type=IntegerType(), default=Literal(value=8))],
        ports=[
            Port(name="a", direction=PortDirection.INPUT, rtl_type=ascending),
            Port(name="y", direction=PortDirection.OUTPUT, rtl_type=ascending),
        ],
        items=[ContinuousAssignment(target=Identifier(name="y"), value=Identifier(name="a"))],
    )

    output = _generator().generate(Design(modules=[module]))

    assert "input wire [0:WIDTH - 1] a" in output
    assert "output wire [0:WIDTH - 1] y" in output


def test_combinational_process_statements_and_driver_analysis() -> None:
    temporary = Signal(name="next_y", rtl_type=ScalarType())
    loop_variable = Variable(name="i", rtl_type=IntegerType())
    process = CombinationalProcess(
        label="comb_logic",
        sensitivity=[Identifier(name="a"), Identifier(name="b")],
        body=[
            ProceduralAssignment(
                target=Identifier(name="next_y"),
                value=Literal(value=False),
                assignment_kind=AssignmentKind.BLOCKING,
            ),
            IfStatement(
                condition=Identifier(name="sel"),
                then_body=[
                    ProceduralAssignment(
                        target=Identifier(name="next_y"),
                        value=Identifier(name="a"),
                        assignment_kind=AssignmentKind.BLOCKING,
                    )
                ],
                else_body=[
                    CaseStatement(
                        expression=Identifier(name="mode"),
                        alternatives=[
                            CaseAlternative(
                                selectors=[Literal(value=0), Literal(value=1)],
                                body=[
                                    ProceduralAssignment(
                                        target=Identifier(name="next_y"),
                                        value=Identifier(name="b"),
                                        assignment_kind=AssignmentKind.BLOCKING,
                                    )
                                ],
                            )
                        ],
                        default_body=[NullStatement()],
                    )
                ],
            ),
            ForStatement(
                index_name="i",
                range=VectorRange(
                    left=0,
                    right=3,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    BlockStatement(
                        label="loop_body",
                        statements=[
                            ProceduralAssignment(
                                target=Identifier(name="y"),
                                value=Index(
                                    value=Identifier(name="bus"),
                                    index=Identifier(name="i"),
                                ),
                                assignment_kind=AssignmentKind.BLOCKING,
                            )
                        ],
                    )
                ],
            ),
            ProceduralAssignment(
                target=Identifier(name="y"),
                value=FunctionCall(
                    function="choose",
                    arguments=[Identifier(name="next_y")],
                ),
                assignment_kind=AssignmentKind.BLOCKING,
            ),
        ],
    )
    module = Module(
        name="comb",
        ports=[
            _scalar_port("a", PortDirection.INPUT),
            _scalar_port("b", PortDirection.INPUT),
            _scalar_port("sel", PortDirection.INPUT),
            Port(
                name="mode",
                direction=PortDirection.INPUT,
                rtl_type=VectorType(
                    range=VectorRange(
                        left=1,
                        right=0,
                        direction=RangeDirection.DESCENDING,
                    )
                ),
            ),
            Port(
                name="bus",
                direction=PortDirection.INPUT,
                rtl_type=VectorType(
                    range=VectorRange(
                        left=3,
                        right=0,
                        direction=RangeDirection.DESCENDING,
                    )
                ),
            ),
            _scalar_port("y", PortDirection.OUTPUT),
        ],
        signals=[temporary],
        variables=[loop_variable],
        items=[process],
    )
    design = Design(modules=[module])

    output = _generator().generate(design)

    assert "output reg y" in output
    assert "reg next_y;" in output
    assert "integer i;" in output
    assert "always @(a or b) begin : comb_logic" in output
    assert "next_y = 1'b0;" in output
    assert "if (sel) begin" in output
    assert "case (mode)" in output
    assert "0, 1: begin" in output
    assert "default: begin" in output
    assert "for (i = 0; i <= 3; i = i + 1) begin" in output
    assert "begin : loop_body" in output
    assert "y = bus[i];" in output
    assert "y = choose(next_y);" in output
    # lowering 必须在深拷贝上工作，调用者的 IR 保持不变。
    assert module.ports[-1].driver_kind is None
    assert temporary.driver_kind is None


@pytest.mark.parametrize(
    ("reset_kind", "active_level", "edge", "expected_header", "condition"),
    [
        (
            ResetKind.ASYNCHRONOUS,
            ActiveLevel.LOW,
            EdgeKind.POSITIVE,
            "always @(posedge clk or negedge reset_n)",
            "if (!reset_n)",
        ),
        (
            ResetKind.SYNCHRONOUS,
            ActiveLevel.HIGH,
            EdgeKind.NEGATIVE,
            "always @(negedge clk)",
            "if (reset)",
        ),
    ],
)
def test_sequential_process_reset_semantics(
    reset_kind: ResetKind,
    active_level: ActiveLevel,
    edge: EdgeKind,
    expected_header: str,
    condition: str,
) -> None:
    reset_name = "reset_n" if active_level is ActiveLevel.LOW else "reset"
    module = Module(
        name="register_bank",
        ports=[
            _scalar_port("clk", PortDirection.INPUT),
            _scalar_port(reset_name, PortDirection.INPUT),
            _scalar_port("d", PortDirection.INPUT),
            _scalar_port("q", PortDirection.OUTPUT),
        ],
        items=[
            SequentialProcess(
                clock=Identifier(name="clk"),
                edge=edge,
                reset=ResetSpec(
                    signal=Identifier(name=reset_name),
                    kind=reset_kind,
                    active_level=active_level,
                ),
                reset_body=[_nonblocking("q", Literal(value=0, bit_width=1))],
                body=[_nonblocking("q", Identifier(name="d"))],
            )
        ],
    )

    output = _generator().generate(Design(modules=[module]))

    assert "output reg q" in output
    assert expected_header in output
    assert condition in output
    assert "q <= 1'd0;" in output
    assert "q <= d;" in output


def test_named_and_positional_instances_render_without_flattening() -> None:
    child = Module(
        name="child",
        parameters=[Parameter(name="WIDTH", rtl_type=IntegerType(), default=Literal(value=1))],
        ports=[
            _scalar_port("a", PortDirection.INPUT),
            _scalar_port("y", PortDirection.OUTPUT),
        ],
        items=[ContinuousAssignment(target=Identifier(name="y"), value=Identifier(name="a"))],
    )
    top = Module(
        name="top",
        ports=[_scalar_port("a", PortDirection.INPUT)],
        signals=[
            Signal(name="named_y", rtl_type=ScalarType()),
            Signal(name="positional_y", rtl_type=ScalarType()),
        ],
        items=[
            Instance(
                referenced_unit="child",
                name="u_named",
                parameter_bindings=[ParameterBinding(formal="WIDTH", value=Literal(value=4))],
                port_bindings=[
                    PortBinding(formal="a", value=Identifier(name="a")),
                    PortBinding(formal="y", value=Identifier(name="named_y")),
                ],
            ),
            Instance(
                referenced_unit="child",
                name="u_positional",
                parameter_bindings=[ParameterBinding(position=0, value=Literal(value=2))],
                port_bindings=[
                    PortBinding(position=0, value=Identifier(name="a")),
                    PortBinding(position=1, value=Identifier(name="positional_y")),
                ],
            ),
        ],
    )

    output = _generator().generate(Design(modules=[child, top], top="top"))

    assert "child #(\n    .WIDTH(4)\n) u_named (" in output
    assert ".a(a)," in output
    assert ".y(named_y)" in output
    assert "child #(\n    2\n) u_positional (" in output
    assert "    a," in output
    assert "    positional_y" in output
    assert output.count("module ") == 2


def test_for_and_if_generate_preserve_hierarchy_and_comments() -> None:
    bus_type = VectorType(
        range=VectorRange(
            left=3,
            right=0,
            direction=RangeDirection.DESCENDING,
        )
    )
    for_generate = ForGenerate(
        label="g_bits",
        index_name="i",
        range=VectorRange(
            left=0,
            right=3,
            direction=RangeDirection.ASCENDING,
        ),
        body=[
            IfGenerate(
                label="g_enabled",
                condition=Identifier(name="ENABLE"),
                then_body=[
                    ContinuousAssignment(
                        target=Index(
                            value=Identifier(name="y"),
                            index=Identifier(name="i"),
                        ),
                        value=Index(
                            value=Identifier(name="a"),
                            index=Identifier(name="i"),
                        ),
                    )
                ],
                else_body=[
                    ContinuousAssignment(
                        target=Index(
                            value=Identifier(name="y"),
                            index=Identifier(name="i"),
                        ),
                        value=Literal(value="0", literal_kind=LiteralKind.BIT),
                    )
                ],
            )
        ],
        leading_comments=[Comment(text="one cell per bit")],
    )
    module = Module(
        name="generated",
        parameters=[Parameter(name="ENABLE", rtl_type=IntegerType(), default=Literal(value=1))],
        ports=[
            Port(name="a", direction=PortDirection.INPUT, rtl_type=bus_type),
            Port(name="y", direction=PortDirection.OUTPUT, rtl_type=bus_type),
        ],
        items=[for_generate],
    )

    output = _generator().generate(Design(modules=[module]))

    assert "genvar i;" in output
    assert "generate" in output and "endgenerate" in output
    assert "// one cell per bit" in output
    assert "for (i = 0; i <= 3; i = i + 1) begin : g_bits" in output
    assert "if (ENABLE) begin : g_enabled" in output
    assert "end else begin : g_enabled" in output
    assert "assign y[i] = a[i];" in output
    assert "assign y[i] = 1'b0;" in output


def test_generator_rejects_unsafe_or_incomplete_ir() -> None:
    mixed = Module(
        name="mixed",
        ports=[
            _scalar_port("a", PortDirection.INPUT),
            _scalar_port("y", PortDirection.OUTPUT),
        ],
        items=[
            ContinuousAssignment(target=Identifier(name="y"), value=Identifier(name="a")),
            CombinationalProcess(
                body=[
                    ProceduralAssignment(
                        target=Identifier(name="y"),
                        value=Identifier(name="a"),
                        assignment_kind=AssignmentKind.BLOCKING,
                    )
                ]
            ),
        ],
    )
    with pytest.raises(SemanticError, match="mixed continuous and procedural"):
        _generator().generate(Design(modules=[mixed]))

    missing_loop_index = Module(
        name="bad_loop",
        ports=[_scalar_port("y", PortDirection.OUTPUT)],
        items=[
            CombinationalProcess(
                body=[
                    ForStatement(
                        index_name="i",
                        range=VectorRange(
                            left=0,
                            right=1,
                            direction=RangeDirection.ASCENDING,
                        ),
                        body=[],
                    )
                ]
            )
        ],
    )
    with pytest.raises(SemanticError, match="explicit IntegerType Variable"):
        _generator().generate(Design(modules=[missing_loop_index]))

    parameter_without_default = Module(
        name="bad_parameter",
        parameters=[Parameter(name="WIDTH", rtl_type=IntegerType())],
    )
    with pytest.raises(GenerationError, match="has no default value"):
        _generator().generate(Design(modules=[parameter_without_default]))

    initialized_signal = Module(
        name="bad_initializer",
        signals=[Signal(name="state", rtl_type=ScalarType(), initial_value=Literal(value=0))],
    )
    with pytest.raises(GenerationError, match="initializer"):
        _generator().generate(Design(modules=[initialized_signal]))

    compound_select = Module(
        name="bad_select",
        ports=[
            _scalar_port("a", PortDirection.INPUT),
            _scalar_port("b", PortDirection.INPUT),
            _scalar_port("y", PortDirection.OUTPUT),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="y"),
                value=Index(
                    value=Concatenation(parts=[Identifier(name="a"), Identifier(name="b")]),
                    index=Literal(value=0),
                ),
            )
        ],
    )
    with pytest.raises(GenerationError, match="compound expression"):
        _generator().generate(Design(modules=[compound_select]))


def test_driver_annotations_can_be_supplied_explicitly() -> None:
    module = Module(
        name="annotated",
        ports=[
            Port(
                name="y",
                direction=PortDirection.OUTPUT,
                rtl_type=ScalarType(),
                driver_kind=DriverKind.PROCEDURAL,
            )
        ],
    )

    output = _generator().generate(Design(modules=[module]))

    assert "output reg y" in output


def test_name_resolution_covers_declarations_references_instances_and_generates() -> None:
    child = Module(
        name="module",
        parameters=[Parameter(name="DataWidth", rtl_type=IntegerType(), default=Literal(value=1))],
        ports=[
            _scalar_port("1-input", PortDirection.INPUT),
            _scalar_port("Result-Out", PortDirection.OUTPUT),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="RESULT-OUT"),
                value=Identifier(name="1-INPUT"),
            )
        ],
    )
    top = Module(
        name="TopLevel",
        ports=[
            _scalar_port("SourceValue", PortDirection.INPUT),
            _scalar_port("FinalResult", PortDirection.OUTPUT),
        ],
        items=[
            Instance(
                referenced_unit="MODULE",
                name="child instance",
                parameter_bindings=[ParameterBinding(formal="DATAWIDTH", value=Literal(value=1))],
                port_bindings=[
                    PortBinding(formal="1-INPUT", value=Identifier(name="sourcevalue")),
                    PortBinding(formal="result-out", value=Identifier(name="finalresult")),
                ],
            ),
            IfGenerate(
                label="optional block",
                condition=Literal(value=True),
                then_body=[],
            ),
        ],
    )
    generator = VerilogGenerator(name_style=NameStyle.SNAKE_CASE)

    output = generator.generate(Design(modules=[child, top], top="TopLevel"))

    assert "module module_hdl_x #(\n    parameter integer data_width = 1" in output
    assert "input wire hdl_x_1_input" in output
    assert "output wire result_out" in output
    assert "assign result_out = hdl_x_1_input;" in output
    assert "module top_level" in output
    assert "module_hdl_x #(\n    .data_width(1)" in output
    assert ".hdl_x_1_input(source_value)" in output
    assert ".result_out(final_result)" in output
    assert "child_instance" in output
    assert "begin : optional_block" in output
    assert generator.name_mappings["module::module"] == "module_hdl_x"


def test_driver_analysis_rejects_coexisting_multiple_driver_sites() -> None:
    multiple_continuous = Module(
        name="multiple_continuous",
        ports=[
            _scalar_port("a", PortDirection.INPUT),
            _scalar_port("b", PortDirection.INPUT),
            _scalar_port("y", PortDirection.OUTPUT),
        ],
        items=[
            ContinuousAssignment(target=Identifier(name="y"), value=Identifier(name="a")),
            ContinuousAssignment(target=Identifier(name="y"), value=Identifier(name="b")),
        ],
    )
    with pytest.raises(SemanticError, match="multiple continuous driver sites"):
        _generator().generate(Design(modules=[multiple_continuous]))

    multiple_processes = Module(
        name="multiple_processes",
        ports=[
            _scalar_port("a", PortDirection.INPUT),
            _scalar_port("b", PortDirection.INPUT),
            _scalar_port("y", PortDirection.OUTPUT),
        ],
        items=[
            CombinationalProcess(
                body=[
                    ProceduralAssignment(
                        target=Identifier(name="y"),
                        value=Identifier(name="a"),
                        assignment_kind=AssignmentKind.BLOCKING,
                    ),
                    ProceduralAssignment(
                        target=Identifier(name="y"),
                        value=Identifier(name="b"),
                        assignment_kind=AssignmentKind.BLOCKING,
                    ),
                ]
            ),
            CombinationalProcess(
                body=[
                    ProceduralAssignment(
                        target=Identifier(name="y"),
                        value=Identifier(name="a"),
                        assignment_kind=AssignmentKind.BLOCKING,
                    )
                ]
            ),
        ],
    )
    with pytest.raises(SemanticError, match="multiple independent processes"):
        _generator().generate(Design(modules=[multiple_processes]))


def test_assignment_kind_is_checked_against_process_and_object_semantics() -> None:
    combinational_nonblocking = Module(
        name="comb_nb",
        ports=[_scalar_port("y", PortDirection.OUTPUT)],
        items=[
            CombinationalProcess(
                body=[
                    ProceduralAssignment(
                        target=Identifier(name="y"),
                        value=Literal(value=0),
                        assignment_kind=AssignmentKind.NON_BLOCKING,
                    )
                ]
            )
        ],
    )
    with pytest.raises(SemanticError, match="blocking semantics"):
        _generator().generate(Design(modules=[combinational_nonblocking]))

    sequential_signal_blocking = Module(
        name="seq_signal_blocking",
        ports=[
            _scalar_port("clk", PortDirection.INPUT),
            _scalar_port("q", PortDirection.OUTPUT),
        ],
        items=[
            SequentialProcess(
                clock=Identifier(name="clk"),
                edge=EdgeKind.POSITIVE,
                body=[
                    ProceduralAssignment(
                        target=Identifier(name="q"),
                        value=Literal(value=0),
                        assignment_kind=AssignmentKind.BLOCKING,
                    )
                ],
            )
        ],
    )
    with pytest.raises(SemanticError, match="non-blocking semantics"):
        _generator().generate(Design(modules=[sequential_signal_blocking]))

    variable = Variable(name="temporary", rtl_type=ScalarType())
    sequential_variable_nonblocking = Module(
        name="seq_variable_nonblocking",
        ports=[_scalar_port("clk", PortDirection.INPUT)],
        variables=[variable],
        items=[
            SequentialProcess(
                clock=Identifier(name="clk"),
                edge=EdgeKind.POSITIVE,
                body=[
                    ProceduralAssignment(
                        target=Identifier(name="temporary"),
                        value=Literal(value=0),
                        assignment_kind=AssignmentKind.NON_BLOCKING,
                    )
                ],
            )
        ],
    )
    with pytest.raises(SemanticError, match="variable .* blocking semantics"):
        _generator().generate(Design(modules=[sequential_variable_nonblocking]))

    sequential_variable_blocking = sequential_variable_nonblocking.model_copy(deep=True)
    process = sequential_variable_blocking.items[0]
    assert isinstance(process, SequentialProcess)
    assignment = process.body[0]
    assert isinstance(assignment, ProceduralAssignment)
    assignment.assignment_kind = AssignmentKind.BLOCKING
    output = _generator().generate(Design(modules=[sequential_variable_blocking]))
    assert "temporary = 0;" in output


def test_modulo_is_rejected_until_operand_semantics_are_explicit() -> None:
    module = Module(
        name="unsafe_modulo",
        ports=[
            _scalar_port("a", PortDirection.INPUT),
            _scalar_port("b", PortDirection.INPUT),
            _scalar_port("y", PortDirection.OUTPUT),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="y"),
                value=BinaryExpr(
                    left=Identifier(name="a"),
                    operator=BinaryOperator.MODULO,
                    right=Identifier(name="b"),
                ),
            )
        ],
    )

    with pytest.raises(GenerationError, match="modulo semantics"):
        _generator().generate(Design(modules=[module]))


def test_undeclared_object_reference_is_rejected_before_verilog_rendering() -> None:
    module = Module(
        name="unresolved_reference",
        ports=[_scalar_port("y", PortDirection.OUTPUT)],
        items=[
            ContinuousAssignment(
                target=Identifier(name="y"),
                value=Identifier(name="missing_name"),
            )
        ],
    )

    with pytest.raises(SemanticError) as raised:
        _generator().generate(Design(modules=[module]))

    assert raised.value.code == "HDLX-NAME-UNRESOLVED"


def test_parallel_for_generates_receive_unique_module_scope_genvars() -> None:
    module = Module(
        name="parallel_generates",
        ports=[
            Port(
                name="a",
                direction=PortDirection.INPUT,
                rtl_type=VectorType(
                    range=VectorRange(
                        left=1,
                        right=0,
                        direction=RangeDirection.DESCENDING,
                    )
                ),
            ),
            Port(
                name="y",
                direction=PortDirection.OUTPUT,
                rtl_type=VectorType(
                    range=VectorRange(
                        left=1,
                        right=0,
                        direction=RangeDirection.DESCENDING,
                    )
                ),
            ),
            Port(
                name="z",
                direction=PortDirection.OUTPUT,
                rtl_type=VectorType(
                    range=VectorRange(
                        left=1,
                        right=0,
                        direction=RangeDirection.DESCENDING,
                    )
                ),
            ),
        ],
        items=[
            ForGenerate(
                label="first",
                index_name="i",
                range=VectorRange(
                    left=0,
                    right=1,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    ContinuousAssignment(
                        target=Index(
                            value=Identifier(name="y"),
                            index=Identifier(name="i"),
                        ),
                        value=Index(
                            value=Identifier(name="a"),
                            index=Identifier(name="i"),
                        ),
                    )
                ],
            ),
            ForGenerate(
                label="second",
                index_name="i",
                range=VectorRange(
                    left=0,
                    right=1,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    ContinuousAssignment(
                        target=Index(
                            value=Identifier(name="z"),
                            index=Identifier(name="i"),
                        ),
                        value=Index(
                            value=Identifier(name="a"),
                            index=Identifier(name="i"),
                        ),
                    )
                ],
            ),
        ],
    )

    output = _generator().generate(Design(modules=[module]))

    assert "genvar i;" in output
    assert "genvar i_2;" in output
    assert "for (i_2 = 0; i_2 <= 1; i_2 = i_2 + 1) begin : second" in output
    assert "assign z[i_2] = a[i_2];" in output


def test_for_generate_rejects_unpartitioned_replicated_driver() -> None:
    module = Module(
        name="unsafe_generated_driver",
        ports=[
            _scalar_port("a", PortDirection.INPUT),
            _scalar_port("y", PortDirection.OUTPUT),
        ],
        items=[
            ForGenerate(
                label="replicated",
                index_name="i",
                range=VectorRange(
                    left=0,
                    right=3,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    ContinuousAssignment(
                        target=Identifier(name="y"),
                        value=Identifier(name="a"),
                    )
                ],
            )
        ],
    )

    with pytest.raises(SemanticError, match="does not partition"):
        _generator().generate(Design(modules=[module]))


def test_for_generate_allows_each_iteration_to_drive_its_local_signal() -> None:
    module = Module(
        name="generated_local",
        ports=[_scalar_port("a", PortDirection.INPUT)],
        items=[
            ForGenerate(
                label="replicated",
                index_name="i",
                range=VectorRange(
                    left=0,
                    right=3,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    Signal(name="local_value", rtl_type=ScalarType()),
                    ContinuousAssignment(
                        target=Identifier(name="local_value"),
                        value=Identifier(name="a"),
                    ),
                ],
            )
        ],
    )

    output = _generator().generate(Design(modules=[module]))

    assert "wire local_value;" in output
    assert "assign local_value = a;" in output
