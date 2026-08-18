"""Verilog lowering、render IR 与 v0.1 兼容 API 契约。"""

import pytest

from hdl_x.generator import (
    VerilogGenerator,
    VerilogLowering,
    VerilogRenderer,
    VerilogRenderIR,
)
from hdl_x.ir import (
    AssignmentKind,
    ContinuousAssignment,
    Design,
    DriverKind,
    Identifier,
    Module,
    Port,
    PortDirection,
    ProceduralAssignment,
    ScalarType,
)
from hdl_x.transformer import NameStyle


def _design() -> Design:
    return Design(
        modules=[
            Module(
                name="module",
                ports=[
                    Port(
                        name="a",
                        direction=PortDirection.INPUT,
                        rtl_type=ScalarType(four_state=False),
                    ),
                    Port(
                        name="y",
                        direction=PortDirection.OUTPUT,
                        rtl_type=ScalarType(four_state=False),
                    ),
                ],
                items=[
                    ContinuousAssignment(
                        target=Identifier(name="y"),
                        value=Identifier(name="a"),
                    )
                ],
            )
        ]
    )


def test_explicit_lowering_produces_target_render_ir_without_mutating_input() -> None:
    design = _design()
    original_json = design.model_dump_json()

    lowered = VerilogLowering(name_style=NameStyle.PRESERVE).lower(design)

    assert isinstance(lowered, VerilogRenderIR)
    assert lowered.design.modules[0].name == "module_hdl_x"
    assert lowered.design.modules[0].ports[1].driver_kind is DriverKind.CONTINUOUS
    assert lowered.name_mappings["module::module"] == "module_hdl_x"
    assert design.model_dump_json() == original_json


def test_new_lowering_renderer_path_matches_legacy_generate_api() -> None:
    design = _design()
    lowering = VerilogLowering(name_style=NameStyle.PRESERVE)
    renderer = VerilogRenderer()

    explicit = renderer.render(lowering.lower(design))
    legacy = VerilogGenerator(name_style=NameStyle.PRESERVE).generate(design)

    assert explicit == legacy
    assert "module module_hdl_x" in explicit
    assert "assign y = a;" in explicit


def test_renderer_requires_target_render_ir() -> None:
    with pytest.raises(TypeError, match="VerilogRenderIR"):
        VerilogRenderer().render(_design())  # type: ignore[arg-type]


def test_legacy_generate_lowered_adapter_keeps_existing_contract() -> None:
    lowering = VerilogLowering()
    lowered = lowering.lower(_design())
    generator = VerilogGenerator()

    assert generator.generate_lowered(lowered.design) == VerilogRenderer().render(lowered)


def test_v01_compatibility_fields_keep_json_shape_and_are_marked_deprecated() -> None:
    assignment = ProceduralAssignment(
        target=Identifier(name="y"),
        value=Identifier(name="a"),
        assignment_kind=AssignmentKind.BLOCKING,
    )

    assert assignment.model_dump(mode="json")["assignment_kind"] == "blocking"
    assignment_schema = ProceduralAssignment.model_json_schema()
    port_schema = Port.model_json_schema()
    assert assignment_schema["properties"]["assignment_kind"]["deprecated"] is True
    assert port_schema["properties"]["driver_kind"]["deprecated"] is True
