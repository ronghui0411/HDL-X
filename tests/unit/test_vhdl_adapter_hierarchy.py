"""Milestone 6 层次 Raw IR 到 canonical IR 的单元测试。"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from hdl_x.diagnostics import SemanticError, UnsupportedConstructError
from hdl_x.ir import Instance, PortBinding, Signal
from hdl_x.parser.ghdl import (
    PyGhdlBackend,
    RawArchitecture,
    RawAssociation,
    RawComponentDeclaration,
    RawDesign,
    RawEntity,
    RawIdentifier,
    RawInstance,
    RawInstantiationKind,
    RawLiteral,
    RawLiteralKind,
    RawParameter,
    RawPort,
    RawPortDirection,
    RawSignal,
    RawType,
    RawTypeKind,
)
from hdl_x.parser.vhdl_adapter import VhdlAdapter

SCALAR = RawType(kind=RawTypeKind.SCALAR, source_name="bit")
INTEGER = RawType(kind=RawTypeKind.INTEGER, source_name="positive", signed=True)


def _child() -> RawEntity:
    return RawEntity(
        name="Child",
        parameters=(
            RawParameter(
                name="WIDTH",
                type=INTEGER,
                default=RawLiteral(8, RawLiteralKind.INTEGER),
            ),
        ),
        ports=(
            RawPort("a", RawPortDirection.IN, SCALAR),
            RawPort("y", RawPortDirection.OUT, SCALAR),
        ),
    )


def test_adapter_preserves_signals_named_instance_and_open_port() -> None:
    top = RawEntity(
        name="Top",
        ports=(RawPort("a", RawPortDirection.IN, SCALAR),),
    )
    architecture = RawArchitecture(
        name="structural",
        entity_name="top",
        signals=(RawSignal("child_y", SCALAR),),
        items=(
            RawInstance(
                referenced_unit="child",
                name="u_child",
                parameter_associations=(
                    RawAssociation(
                        formal="width",
                        position=None,
                        value=RawLiteral(4, RawLiteralKind.INTEGER),
                    ),
                ),
                port_associations=(
                    RawAssociation("a", None, RawIdentifier("a")),
                    RawAssociation("y", None, None),
                ),
            ),
        ),
    )

    design = VhdlAdapter().adapt(
        RawDesign(
            Path("hierarchy.vhd"),
            (_child(), top),
            (RawArchitecture("rtl", "Child"), architecture),
        )
    )

    module = design.modules[1]
    assert isinstance(module.signals[0], Signal)
    assert module.signals[0].name == "child_y"
    instance = module.items[0]
    assert isinstance(instance, Instance)
    assert instance.referenced_unit == "Child"
    assert instance.name == "u_child"
    assert instance.parameter_bindings[0].formal == "WIDTH"
    assert instance.parameter_bindings[0].value.value == 4
    assert [binding.formal for binding in instance.port_bindings] == ["a", "y"]
    assert instance.port_bindings[1].value is None


def test_adapter_preserves_safe_positional_order_for_known_entity() -> None:
    top = RawEntity(name="Top")
    architecture = RawArchitecture(
        "structural",
        "Top",
        items=(
            RawInstance(
                "CHILD",
                "u_child",
                parameter_associations=(
                    RawAssociation(None, 0, RawLiteral(16, RawLiteralKind.INTEGER)),
                ),
                port_associations=(
                    RawAssociation(None, 0, RawIdentifier("source")),
                    RawAssociation(None, 1, None),
                ),
            ),
        ),
    )

    instance = (
        VhdlAdapter()
        .adapt(
            RawDesign(
                Path("positional.vhd"),
                (_child(), top),
                (RawArchitecture("rtl", "Child"), architecture),
            )
        )
        .modules[1]
        .instances[0]
    )

    assert instance.parameter_bindings[0].position == 0
    assert [binding.position for binding in instance.port_bindings] == [0, 1]
    assert instance.port_bindings[1].value is None


@pytest.mark.parametrize(
    ("referenced_unit", "position", "code"),
    [
        ("ExternalChild", 0, "HDLX-VHDL-INSTANCE-POSITIONAL-UNKNOWN"),
        ("Child", 2, "HDLX-VHDL-INSTANCE-PORT-RANGE"),
    ],
)
def test_adapter_rejects_unsafe_positional_associations(
    referenced_unit: str, position: int, code: str
) -> None:
    top = RawEntity(name="Top")
    instance = RawInstance(
        referenced_unit,
        "u_child",
        port_associations=(RawAssociation(None, position, None),),
    )
    raw = RawDesign(
        Path("unsafe.vhd"),
        (_child(), top),
        (
            RawArchitecture("rtl", "Child"),
            RawArchitecture("structural", "Top", items=(instance,)),
        ),
    )

    with pytest.raises(SemanticError) as raised:
        VhdlAdapter().adapt(raw)

    expected = "HDLX-VHDL-INSTANCE-UNKNOWN-UNIT" if referenced_unit == "ExternalChild" else code
    assert raised.value.code == expected


def test_open_port_binding_remains_explicitly_unconnected() -> None:
    binding = PortBinding(formal="y", value=None)

    assert binding.value is None


def test_adapter_rejects_component_interface_name_and_order_mismatch() -> None:
    component = RawComponentDeclaration(
        name="Child",
        parameters=_child().parameters,
        ports=(
            RawPort("y", RawPortDirection.OUT, SCALAR),
            RawPort("a", RawPortDirection.IN, SCALAR),
        ),
    )
    top = RawEntity(name="Top")
    instance = RawInstance(
        referenced_unit="Child",
        name="u_child",
        instantiation_kind=RawInstantiationKind.COMPONENT,
        component_declaration=component,
    )
    raw = RawDesign(
        Path("component_order.vhd"),
        (_child(), top),
        (
            RawArchitecture("rtl", "Child"),
            RawArchitecture(
                "structural",
                "Top",
                items=(instance,),
                components=(component,),
            ),
        ),
    )

    with pytest.raises(SemanticError) as raised:
        VhdlAdapter().adapt(raw)

    assert raised.value.code == "HDLX-VHDL-COMPONENT-BINDING"


def test_backend_rejects_unknown_association_kind_explicitly() -> None:
    class MissingPosition:
        @staticmethod
        def parse(_node: object) -> None:
            raise ValueError

    api = SimpleNamespace(
        nodes=SimpleNamespace(
            Null_Iir=0,
            Iir_Kind=SimpleNamespace(
                Association_Element_By_Expression=20,
                Association_Element_Open=23,
            ),
            Get_Kind=lambda _node: 999,
        ),
        node_utils=SimpleNamespace(chain_iter=lambda node: iter((node,))),
        Position=MissingPosition,
    )

    with pytest.raises(UnsupportedConstructError) as raised:
        PyGhdlBackend()._extract_associations(
            api,
            1,
            role="port",
            allow_open=True,
        )

    assert raised.value.code == "HDLX-VHDL-ASSOCIATION"
