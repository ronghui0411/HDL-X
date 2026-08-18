"""Milestone 6 真实层次 frontend 与完整 pipeline 回归。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import SemanticError
from hdl_x.frontend import VhdlFrontend
from hdl_x.ir import Instance
from hdl_x.parser.ghdl import (
    PyGhdlBackend,
    RawInstance,
    RawInstantiationKind,
    RawLiteral,
    RawPortDirection,
    RawTypeKind,
)
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.ghdl_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"
GOLDEN = Path(__file__).parents[1] / "golden"


@pytest.mark.parametrize(
    "case_name",
    [
        "simple_instance",
        "component_instances",
        "generic_map",
        "positional_open",
    ],
)
def test_m6_real_pipeline_matches_complete_hierarchy_golden(case_name: str) -> None:
    result = convert_file(
        FIXTURES / f"m6_{case_name}.vhd",
        options=ConversionOptions(strict=True),
    )
    expected = (GOLDEN / f"m6_{case_name}.v").read_text(encoding="utf-8")

    assert result.text == expected
    assert len(result.design.modules) == 2
    assert result.design.top is None
    assert result.diagnostics == ()


def test_m6_real_backend_extracts_multi_identifier_signals_and_direct_instance() -> None:
    raw = PyGhdlBackend().parse(FIXTURES / "m6_simple_instance.vhd")
    architecture = raw.architectures[1]

    assert [signal.name for signal in architecture.signals] == ["child_a", "child_y"]
    instance = architecture.items[1]
    assert isinstance(instance, RawInstance)
    assert instance.name == "u_child"
    assert instance.referenced_unit == "M6SimpleChild"
    assert [item.formal for item in instance.port_associations] == ["a", "y"]


def test_m6_real_component_instances_preserve_labels_and_hierarchy() -> None:
    source = FIXTURES / "m6_component_instances.vhd"
    raw = PyGhdlBackend().parse(source)
    architecture = raw.architectures[1]
    raw_instance = architecture.items[1]

    assert [component.name for component in architecture.components] == ["M6ComponentChild"]
    assert [port.name for port in architecture.components[0].ports] == ["a", "y"]
    assert [port.direction for port in architecture.components[0].ports] == [
        RawPortDirection.IN,
        RawPortDirection.OUT,
    ]
    assert all(
        port.type.kind is RawTypeKind.SCALAR
        and port.type.source_name.casefold() == "bit"
        and port.default is None
        for port in architecture.components[0].ports
    )
    assert isinstance(raw_instance, RawInstance)
    assert raw_instance.instantiation_kind is RawInstantiationKind.COMPONENT
    assert raw_instance.component_declaration == architecture.components[0]

    design = VhdlFrontend().parse_design(source)
    instances = design.modules[1].instances

    assert [item.name for item in instances] == ["u_first", "u_second"]
    assert all(isinstance(item, Instance) for item in instances)
    assert {item.referenced_unit for item in instances} == {"M6ComponentChild"}


def test_m6_real_backend_preserves_component_generic_default() -> None:
    raw = PyGhdlBackend().parse(FIXTURES / "m6_component_default_mismatch.vhd")
    component = raw.architectures[1].components[0]
    parameter = component.parameters[0]

    assert parameter.name == "WIDTH"
    assert parameter.type.kind is RawTypeKind.INTEGER
    assert parameter.type.source_name.casefold() == "positive"
    assert isinstance(parameter.default, RawLiteral)
    assert parameter.default.value == 4


@pytest.mark.parametrize(
    "fixture_name",
    [
        "m6_component_direction_mismatch.vhd",
        "m6_component_type_mismatch.vhd",
        "m6_component_default_mismatch.vhd",
    ],
)
def test_m6_real_component_binding_requires_exact_entity_interface(
    fixture_name: str,
) -> None:
    with pytest.raises(SemanticError) as raised:
        VhdlFrontend().parse_design(FIXTURES / fixture_name)

    assert raised.value.code == "HDLX-VHDL-COMPONENT-BINDING"


def test_m6_real_named_generic_and_port_maps_keep_formal_actual_direction() -> None:
    instance = VhdlFrontend().parse_design(FIXTURES / "m6_generic_map.vhd").modules[1].instances[0]

    assert [item.formal for item in instance.parameter_bindings] == ["WIDTH", "ENABLE"]
    assert [item.value.value for item in instance.parameter_bindings] == [16, False]
    assert [item.formal for item in instance.port_bindings] == ["a", "y"]
    assert [item.value.name for item in instance.port_bindings] == ["a", "y"]


def test_m6_real_positional_maps_are_range_checked_and_open_is_preserved() -> None:
    instance = (
        VhdlFrontend().parse_design(FIXTURES / "m6_positional_open.vhd").modules[1].instances[0]
    )

    assert [item.position for item in instance.parameter_bindings] == [0]
    assert [item.position for item in instance.port_bindings] == [0, 1, 2]
    assert instance.port_bindings[2].value is None
