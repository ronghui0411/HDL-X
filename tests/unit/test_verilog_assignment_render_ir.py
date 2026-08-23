import pytest

from hdl_x.diagnostics import GenerationError
from hdl_x.generator import (
    VerilogAssignmentOperator,
    VerilogLowering,
    VerilogRenderer,
    VerilogRenderIR,
)
from hdl_x.ir import (
    AssignmentKind,
    CombinationalProcess,
    Design,
    Identifier,
    Module,
    Port,
    PortDirection,
    ProceduralAssignment,
    ScalarType,
)


def test_verilog_lowering_owns_procedural_assignment_operator() -> None:
    render_ir = VerilogLowering().lower(_procedural_design())
    process = render_ir.design.modules[0].items[0]
    assert isinstance(process, CombinationalProcess)
    assignment = process.body[0]
    assert isinstance(assignment, ProceduralAssignment)

    assert render_ir.assignment_operators[id(assignment)] is VerilogAssignmentOperator.BLOCKING
    assignment.assignment_kind = AssignmentKind.NON_BLOCKING

    rendered = VerilogRenderer().render(render_ir)

    assert "y = a;" in rendered
    assert "y <= a;" not in rendered


def test_renderer_rejects_procedural_design_without_target_operator_lowering() -> None:
    render_ir = VerilogRenderIR(
        design=_procedural_design(),
        name_mappings={},
    )

    with pytest.raises(GenerationError) as captured:
        VerilogRenderer().render(render_ir)

    assert captured.value.code == "HDLX-GEN-LOWERING-INCOMPLETE"


def _procedural_design() -> Design:
    scalar = ScalarType(four_state=True)
    return Design(
        modules=[
            Module(
                name="Combinational",
                ports=[
                    Port(
                        name="a",
                        direction=PortDirection.INPUT,
                        rtl_type=scalar.model_copy(deep=True),
                    ),
                    Port(
                        name="y",
                        direction=PortDirection.OUTPUT,
                        rtl_type=scalar.model_copy(deep=True),
                    ),
                ],
                items=[
                    CombinationalProcess(
                        sensitivity=[],
                        body=[
                            ProceduralAssignment(
                                target=Identifier(name="y"),
                                value=Identifier(name="a"),
                                assignment_kind=AssignmentKind.BLOCKING,
                            )
                        ],
                    )
                ],
            )
        ]
    )
