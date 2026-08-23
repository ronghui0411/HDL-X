from hdl_x.generator import (
    VerilogAssignmentOperator,
    VerilogLowering,
    VerilogRenderer,
    VerilogRenderIR,
    VerilogStorageKind,
)
from hdl_x.ir import (
    AssignmentKind,
    CombinationalProcess,
    Design,
    DriverKind,
    Identifier,
    Module,
    Port,
    PortDirection,
    ProceduralAssignment,
    ScalarType,
)


def test_verilog_render_ir_preserves_v01_positional_assignment_operator_argument() -> None:
    design = Design(modules=[Module(name="Empty")])
    assignment_operators = {123: VerilogAssignmentOperator.BLOCKING}

    render_ir = VerilogRenderIR(design, {}, assignment_operators)

    assert render_ir.assignment_operators == assignment_operators
    assert render_ir.storage_kinds == {}


def test_verilog_lowering_owns_port_storage_after_compatibility_field_changes() -> None:
    design = Design(
        modules=[
            Module(
                name="StorageBoundary",
                ports=[
                    Port(
                        name="a",
                        direction=PortDirection.INPUT,
                        rtl_type=ScalarType(four_state=True),
                    ),
                    Port(
                        name="y",
                        direction=PortDirection.OUTPUT,
                        rtl_type=ScalarType(four_state=True),
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

    render_ir = VerilogLowering().lower(design)
    input_port, output_port = render_ir.design.modules[0].ports
    assert render_ir.storage_kinds[id(input_port)] is VerilogStorageKind.WIRE
    assert render_ir.storage_kinds[id(output_port)] is VerilogStorageKind.REG

    output_port.driver_kind = DriverKind.CONTINUOUS
    rendered = VerilogRenderer().render(render_ir)

    assert "input wire a" in rendered
    assert "output reg y" in rendered
