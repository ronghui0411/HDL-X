"""Milestone 7 canonical generate 与 comment generator 合约回归。"""

import pytest

from hdl_x.diagnostics import SemanticError
from hdl_x.generator import VerilogGenerator
from hdl_x.ir import (
    AssignmentKind,
    CombinationalProcess,
    Comment,
    CommentKind,
    ContinuousAssignment,
    Design,
    ForGenerate,
    Identifier,
    IfGenerate,
    Index,
    Instance,
    IntegerType,
    Literal,
    LiteralKind,
    Module,
    Parameter,
    Port,
    PortBinding,
    PortDirection,
    ProceduralAssignment,
    RangeDirection,
    ScalarType,
    Signal,
    VectorRange,
    VectorType,
)


def _scalar_port(name: str, direction: PortDirection) -> Port:
    return Port(name=name, direction=direction, rtl_type=ScalarType())


def _vector_port(name: str, direction: PortDirection, width: int = 4) -> Port:
    return Port(
        name=name,
        direction=direction,
        rtl_type=VectorType(
            range=VectorRange(
                left=width - 1,
                right=0,
                direction=RangeDirection.DESCENDING,
            )
        ),
    )


def _bit_cell() -> Module:
    return Module(
        name="BitCell",
        ports=[
            _scalar_port("data_in", PortDirection.INPUT),
            _scalar_port("data_out", PortDirection.OUTPUT),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="data_out"),
                value=Identifier(name="data_in"),
            )
        ],
    )


def _generate(*modules: Module, top: str | None = None) -> str:
    return VerilogGenerator().generate(Design(modules=list(modules), top=top))


def test_m7_for_generate_preserves_label_direction_and_indexed_driver() -> None:
    module = Module(
        name="DescendingGenerate",
        ports=[
            _vector_port("data_in", PortDirection.INPUT),
            _vector_port("data_out", PortDirection.OUTPUT),
        ],
        items=[
            ForGenerate(
                label="g_bits",
                index_name="bit_index",
                range=VectorRange(
                    left=3,
                    right=0,
                    direction=RangeDirection.DESCENDING,
                ),
                body=[
                    ContinuousAssignment(
                        target=Index(
                            value=Identifier(name="data_out"),
                            index=Identifier(name="bit_index"),
                        ),
                        value=Index(
                            value=Identifier(name="data_in"),
                            index=Identifier(name="bit_index"),
                        ),
                    )
                ],
            )
        ],
    )

    output = _generate(module)

    assert "genvar bit_index;" in output
    assert "generate" in output and "endgenerate" in output
    assert (
        "for (bit_index = 3; bit_index >= 0; bit_index = bit_index - 1) "
        "begin : g_bits"
    ) in output
    assert "assign data_out[bit_index] = data_in[bit_index];" in output


def test_m7_if_generate_preserves_mutually_exclusive_driver_hierarchy() -> None:
    module = Module(
        name="ConditionalGenerate",
        parameters=[
            Parameter(name="ENABLE", rtl_type=IntegerType(), default=Literal(value=1))
        ],
        ports=[
            _scalar_port("when_enabled", PortDirection.INPUT),
            _scalar_port("when_disabled", PortDirection.INPUT),
            _scalar_port("result", PortDirection.OUTPUT),
        ],
        items=[
            IfGenerate(
                label="g_select",
                condition=Identifier(name="ENABLE"),
                then_body=[
                    ContinuousAssignment(
                        target=Identifier(name="result"),
                        value=Identifier(name="when_enabled"),
                    )
                ],
                else_body=[
                    ContinuousAssignment(
                        target=Identifier(name="result"),
                        value=Identifier(name="when_disabled"),
                    )
                ],
            )
        ],
    )

    output = _generate(module)

    assert "if (ENABLE) begin : g_select" in output
    assert "end else begin : g_select" in output
    assert "assign result = when_enabled;" in output
    assert "assign result = when_disabled;" in output


def test_m7_generated_instances_keep_source_hierarchy_without_unrolling() -> None:
    top = Module(
        name="GeneratedInstances",
        ports=[
            _vector_port("data_in", PortDirection.INPUT),
            _vector_port("data_out", PortDirection.OUTPUT),
        ],
        items=[
            ForGenerate(
                label="g_cells",
                index_name="cell_index",
                range=VectorRange(
                    left=0,
                    right=3,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    Instance(
                        referenced_unit="BitCell",
                        name="u_cell",
                        port_bindings=[
                            PortBinding(
                                formal="data_in",
                                value=Index(
                                    value=Identifier(name="data_in"),
                                    index=Identifier(name="cell_index"),
                                ),
                            ),
                            PortBinding(
                                formal="data_out",
                                value=Index(
                                    value=Identifier(name="data_out"),
                                    index=Identifier(name="cell_index"),
                                ),
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    output = _generate(_bit_cell(), top, top="GeneratedInstances")

    assert output.count("BitCell u_cell") == 1
    assert "for (cell_index = 0; cell_index <= 3;" in output
    assert ".data_in(data_in[cell_index])" in output
    assert ".data_out(data_out[cell_index])" in output


def test_m7_nested_generate_can_use_local_signal_and_branch_scope() -> None:
    module = Module(
        name="NestedGenerate",
        parameters=[
            Parameter(name="ENABLE", rtl_type=IntegerType(), default=Literal(value=1))
        ],
        ports=[
            _vector_port("data_in", PortDirection.INPUT),
            _vector_port("data_out", PortDirection.OUTPUT),
        ],
        items=[
            ForGenerate(
                label="g_lane",
                index_name="lane",
                range=VectorRange(
                    left=0,
                    right=3,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    Signal(name="local_value", rtl_type=ScalarType()),
                    ContinuousAssignment(
                        target=Identifier(name="local_value"),
                        value=Index(
                            value=Identifier(name="data_in"),
                            index=Identifier(name="lane"),
                        ),
                    ),
                    IfGenerate(
                        label="g_enabled",
                        condition=Identifier(name="ENABLE"),
                        then_body=[
                            ContinuousAssignment(
                                target=Index(
                                    value=Identifier(name="data_out"),
                                    index=Identifier(name="lane"),
                                ),
                                value=Identifier(name="local_value"),
                            )
                        ],
                        else_body=[
                            ContinuousAssignment(
                                target=Index(
                                    value=Identifier(name="data_out"),
                                    index=Identifier(name="lane"),
                                ),
                                value=Literal(
                                    value="0",
                                    literal_kind=LiteralKind.BIT,
                                ),
                            )
                        ],
                    ),
                ],
            )
        ],
    )

    output = _generate(module)

    assert "for (lane = 0; lane <= 3; lane = lane + 1) begin : g_lane" in output
    assert "wire local_value;" in output
    assert "assign local_value = data_in[lane];" in output
    assert "if (ENABLE) begin : g_enabled" in output
    assert "assign data_out[lane] = local_value;" in output
    assert "assign data_out[lane] = 1'b0;" in output


def test_m7_generate_index_collision_is_renamed_deterministically() -> None:
    module = Module(
        name="IndexCollision",
        ports=[
            _scalar_port("lane", PortDirection.INPUT),
            _vector_port("data_out", PortDirection.OUTPUT, width=2),
        ],
        items=[
            ForGenerate(
                label="g_lane",
                index_name="lane",
                range=VectorRange(
                    left=0,
                    right=1,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    ContinuousAssignment(
                        target=Index(
                            value=Identifier(name="data_out"),
                            index=Identifier(name="lane"),
                        ),
                        value=Identifier(name="lane"),
                    )
                ],
            )
        ],
    )
    generator = VerilogGenerator()

    output = generator.generate(Design(modules=[module]))

    assert "input wire lane" in output
    assert "genvar lane_2;" in output
    assert "for (lane_2 = 0; lane_2 <= 1; lane_2 = lane_2 + 1)" in output
    assert "assign data_out[lane_2] = lane_2;" in output
    assert (
        generator.name_mappings[
            "IndexCollision::generate::g_lane::index::lane"
        ]
        == "lane_2"
    )


@pytest.mark.parametrize(
    "items",
    [
        [
            Signal(name="g_cells", rtl_type=ScalarType()),
            ForGenerate(
                label="G_CELLS",
                index_name="i",
                range=VectorRange(
                    left=0,
                    right=0,
                    direction=RangeDirection.ASCENDING,
                ),
            ),
        ],
        [
            IfGenerate(label="g_choice", condition=Literal(value=True)),
            Instance(referenced_unit="ExternalCell", name="G_CHOICE"),
        ],
    ],
    ids=["signal-vs-generate", "generate-vs-instance"],
)
def test_m7_label_and_object_name_collisions_fail_explicitly(items: list[object]) -> None:
    with pytest.raises(SemanticError) as raised:
        _generate(Module(name="Collision", items=items))

    assert raised.value.code == "HDLX-NAME-DUPLICATE"


def test_m7_replicated_unpartitioned_instance_driver_fails_safely() -> None:
    top = Module(
        name="UnsafeGeneratedInstance",
        ports=[
            _scalar_port("data_in", PortDirection.INPUT),
            _scalar_port("data_out", PortDirection.OUTPUT),
        ],
        items=[
            ForGenerate(
                label="g_cells",
                index_name="cell_index",
                range=VectorRange(
                    left=0,
                    right=3,
                    direction=RangeDirection.ASCENDING,
                ),
                body=[
                    Instance(
                        referenced_unit="BitCell",
                        name="u_cell",
                        port_bindings=[
                            PortBinding(
                                formal="data_in", value=Identifier(name="data_in")
                            ),
                            PortBinding(
                                formal="data_out", value=Identifier(name="data_out")
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(SemanticError) as raised:
        _generate(_bit_cell(), top, top="UnsafeGeneratedInstance")

    assert raised.value.code == "HDLX-DRIVER-GENERATE-TARGET"


def test_m7_common_comments_render_at_readable_structural_locations() -> None:
    assignment = ContinuousAssignment(
        target=Identifier(name="assigned_result"),
        value=Identifier(name="source"),
        leading_comments=[Comment(text="concurrent assignment")],
        trailing_comments=[Comment(text="assignment complete")],
    )
    statement = ProceduralAssignment(
        target=Identifier(name="process_result"),
        value=Identifier(name="source"),
        assignment_kind=AssignmentKind.BLOCKING,
        leading_comments=[Comment(text="inside simple process")],
    )
    process = CombinationalProcess(
        label="comb_logic",
        sensitivity=[Identifier(name="source")],
        body=[statement],
        leading_comments=[Comment(text="combinational process")],
    )
    generated_signal = Signal(
        name="local_value",
        rtl_type=ScalarType(),
        leading_comments=[Comment(text="local generated signal")],
    )
    generate = IfGenerate(
        label="g_comments",
        condition=Literal(value=True),
        then_body=[generated_signal],
        leading_comments=[Comment(text="generated structure")],
    )
    module = Module(
        name="CommentedDesign",
        ports=[
            Port(
                name="source",
                direction=PortDirection.INPUT,
                rtl_type=ScalarType(),
                leading_comments=[Comment(text="source port", kind=CommentKind.DOC)],
            ),
            _scalar_port("assigned_result", PortDirection.OUTPUT),
            _scalar_port("process_result", PortDirection.OUTPUT),
        ],
        items=[assignment, process, generate],
        leading_comments=[
            Comment(
                text="module documentation\nsecond line with */ marker",
                kind=CommentKind.BLOCK,
            )
        ],
        trailing_comments=[Comment(text="end module documentation")],
    )

    output = _generate(module)

    assert output.startswith(
        "/* module documentation\n * second line with * / marker\n */\n"
        "module CommentedDesign ("
    )
    assert "    /// source port\n    input wire source," in output
    assert "// concurrent assignment\nassign assigned_result = source;" in output
    assert "// assignment complete" in output
    assert "// combinational process\nalways @(source) begin : comb_logic" in output
    assert "    // inside simple process\n    process_result = source;" in output
    assert "// generated structure\n    if (1'b1) begin : g_comments" in output
    assert "        // local generated signal\n        wire local_value;" in output
    assert output.endswith("endmodule\n// end module documentation\n")


def test_m7_comment_rendering_is_deterministic_and_does_not_mutate_ir() -> None:
    comment = Comment(text="stable comment")
    assignment = ContinuousAssignment(
        target=Identifier(name="result"),
        value=Identifier(name="source"),
        leading_comments=[comment],
    )
    module = Module(
        name="CommentRegression",
        ports=[
            _scalar_port("source", PortDirection.INPUT),
            _scalar_port("result", PortDirection.OUTPUT),
        ],
        items=[assignment],
    )
    design = Design(modules=[module])
    before = design.model_dump_json()
    generator = VerilogGenerator()

    first = generator.generate(design)
    second = generator.generate(design)

    assert first == second
    assert first.count("// stable comment") == 1
    assert design.model_dump_json() == before
