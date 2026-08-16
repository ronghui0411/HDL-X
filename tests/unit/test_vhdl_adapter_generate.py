"""Milestone 7 generate Raw IR 到 canonical IR 的单元测试。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import SemanticError
from hdl_x.ir import ContinuousAssignment, ForGenerate, IfGenerate, Index, Signal
from hdl_x.parser.ghdl import (
    RawArchitecture,
    RawConcurrentAssignment,
    RawDesign,
    RawEntity,
    RawForGenerate,
    RawIdentifier,
    RawIfGenerate,
    RawIndexExpression,
    RawLiteral,
    RawLiteralKind,
    RawPort,
    RawPortDirection,
    RawRange,
    RawRangeDirection,
    RawSignal,
    RawType,
    RawTypeKind,
)
from hdl_x.parser.vhdl_adapter import VhdlAdapter

SCALAR = RawType(kind=RawTypeKind.SCALAR, source_name="bit")


def _literal(value: int) -> RawLiteral:
    return RawLiteral(value=value, kind=RawLiteralKind.INTEGER)


def test_adapter_preserves_for_range_local_signal_and_indexed_driver() -> None:
    generated = RawForGenerate(
        label="g_lane",
        index_name="i",
        range=RawRange(_literal(3), _literal(0), RawRangeDirection.DOWNTO),
        body=(
            RawSignal("local_value", SCALAR),
            RawConcurrentAssignment(
                target=RawIndexExpression(RawIdentifier("y"), RawIdentifier("i")),
                value=RawIdentifier("local_value"),
            ),
        ),
    )
    raw = RawDesign(
        Path("for_generate.vhd"),
        entities=(
            RawEntity(
                "Top",
                ports=(
                    RawPort(
                        "y",
                        RawPortDirection.OUT,
                        RawType(
                            kind=RawTypeKind.VECTOR,
                            source_name="bit_vector",
                            range=RawRange(
                                _literal(3),
                                _literal(0),
                                RawRangeDirection.DOWNTO,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        architectures=(
            RawArchitecture("rtl", "Top", items=(generated,)),
        ),
    )

    item = VhdlAdapter().adapt(raw).modules[0].generates[0]

    assert isinstance(item, ForGenerate)
    assert item.label == "g_lane"
    assert item.index_name == "i"
    assert item.range.direction.value == "descending"
    assert isinstance(item.body[0], Signal)
    assert item.body[0].name == "local_value"
    assignment = item.body[1]
    assert isinstance(assignment, ContinuousAssignment)
    assert isinstance(assignment.target, Index)
    assert assignment.target.index.name == "i"


def test_adapter_preserves_if_else_and_nested_generate() -> None:
    nested = RawIfGenerate(
        label="g_choice",
        condition=RawIdentifier("ENABLE"),
        then_body=(
            RawForGenerate(
                label="g_inner",
                index_name="lane",
                range=RawRange(_literal(0), _literal(1), RawRangeDirection.TO),
            ),
        ),
        else_body=(
            RawConcurrentAssignment(RawIdentifier("y"), RawIdentifier("b")),
        ),
    )
    raw = RawDesign(
        Path("if_generate.vhd"),
        entities=(RawEntity("Top"),),
        architectures=(RawArchitecture("rtl", "Top", items=(nested,)),),
    )

    item = VhdlAdapter().adapt(raw).modules[0].generates[0]

    assert isinstance(item, IfGenerate)
    assert item.condition.name == "ENABLE"
    assert isinstance(item.then_body[0], ForGenerate)
    assert item.then_body[0].range.direction.value == "ascending"
    assert isinstance(item.else_body[0], ContinuousAssignment)


def test_adapter_rejects_generate_local_declaration_colliding_with_index() -> None:
    generated = RawForGenerate(
        label="g_lane",
        index_name="i",
        range=RawRange(_literal(0), _literal(1), RawRangeDirection.TO),
        body=(RawSignal("I", SCALAR),),
    )
    raw = RawDesign(
        Path("collision.vhd"),
        entities=(RawEntity("Top"),),
        architectures=(RawArchitecture("rtl", "Top", items=(generated,)),),
    )

    with pytest.raises(SemanticError) as raised:
        VhdlAdapter().adapt(raw)

    assert raised.value.code == "HDLX-VHDL-DUPLICATE-GENERATE-DECLARATION"
