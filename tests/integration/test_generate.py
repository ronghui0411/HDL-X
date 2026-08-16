"""Milestone 7 真实 generate frontend 与完整 pipeline 回归。"""

from pathlib import Path

import pytest

pytest.importorskip("pyGHDL", reason="真实 GHDL integration 需要 pyGHDL wheel")

from hdl_x.diagnostics import UnsupportedConstructError
from hdl_x.ir import ForGenerate, IfGenerate, Instance, RangeDirection, Signal
from hdl_x.parser.ghdl import PyGhdlBackend, RawForGenerate, RawIfGenerate
from hdl_x.parser.ghdl.pyghdl_backend import _load_api
from hdl_x.pipeline import ConversionOptions, convert_file

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"
GOLDEN = Path(__file__).parents[1] / "golden"


@pytest.mark.parametrize(
    "case_name",
    ["for", "downto", "if", "nested"],
)
def test_m7_real_pipeline_matches_complete_generate_golden(case_name: str) -> None:
    result = convert_file(
        FIXTURES / f"m7_generate_{case_name}.vhd",
        options=ConversionOptions(strict=True),
    )
    expected = (GOLDEN / f"m7_generate_{case_name}.v").read_text(
        encoding="utf-8"
    )

    assert result.text == expected
    assert result.diagnostics == ()


def test_m7_backend_preserves_for_directions_and_if_else() -> None:
    ascending = PyGhdlBackend().parse(FIXTURES / "m7_generate_for.vhd")
    descending = PyGhdlBackend().parse(FIXTURES / "m7_generate_downto.vhd")
    conditional = PyGhdlBackend().parse(FIXTURES / "m7_generate_if.vhd")

    ascending_item = ascending.architectures[0].items[0]
    descending_item = descending.architectures[0].items[0]
    conditional_item = conditional.architectures[0].items[0]
    assert isinstance(ascending_item, RawForGenerate)
    assert ascending_item.range.direction.value == "to"
    assert isinstance(descending_item, RawForGenerate)
    assert descending_item.range.direction.value == "downto"
    assert isinstance(conditional_item, RawIfGenerate)
    assert conditional_item.then_body
    assert conditional_item.else_body


def test_m7_nested_generate_keeps_local_signal_and_instance_without_unrolling() -> None:
    result = convert_file(
        FIXTURES / "m7_generate_nested.vhd",
        options=ConversionOptions(strict=True),
    )
    generated = result.design.modules[1].generates[0]

    assert isinstance(generated, ForGenerate)
    assert generated.range.direction is RangeDirection.ASCENDING
    assert isinstance(generated.body[0], Signal)
    assert isinstance(generated.body[1], Instance)
    assert isinstance(generated.body[2], IfGenerate)
    assert result.text.count("M7BitCell u_cell") == 1


def test_m7_backend_state_survives_normal_generate_normal_generate_normal() -> None:
    backend = PyGhdlBackend()
    paths = (
        "m2_simple_and.vhd",
        "m7_generate_for.vhd",
        "m2_simple_or.vhd",
        "m7_generate_if.vhd",
        "m6_simple_instance.vhd",
    )

    parsed = [backend.parse(FIXTURES / name) for name in paths]

    assert [design.entities[0].name for design in parsed] == [
        "M2SimpleAnd",
        "M7GenerateFor",
        "M2SimpleOr",
        "M7GenerateIf",
        "M6SimpleChild",
    ]


def test_m7_unknown_generate_construct_is_diagnosed_explicitly() -> None:
    with pytest.raises(UnsupportedConstructError) as raised:
        PyGhdlBackend().parse(FIXTURES / "m7_generate_unsupported.vhd")

    assert raised.value.code == "HDLX-VHDL-GENERATE-CONSTRUCT"


def test_m7_elsif_generate_is_diagnosed_explicitly() -> None:
    with pytest.raises(UnsupportedConstructError) as raised:
        PyGhdlBackend().parse(FIXTURES / "m7_generate_elsif.vhd")

    assert raised.value.code == "HDLX-VHDL-GENERATE-ELSIF"


def test_m7_generate_fallback_restores_parser_flags() -> None:
    api = _load_api()
    gather_comments = api.flags.Flag_Gather_Comments.value
    parse_parenthesis = api.vhdl_parse.Flag_Parse_Parenthesis.value
    api.flags.Flag_Gather_Comments.value = False
    api.vhdl_parse.Flag_Parse_Parenthesis.value = False
    try:
        PyGhdlBackend().parse(FIXTURES / "m7_generate_for.vhd")

        assert api.flags.Flag_Gather_Comments.value is False
        assert api.vhdl_parse.Flag_Parse_Parenthesis.value is False
    finally:
        api.flags.Flag_Gather_Comments.value = gather_comments
        api.vhdl_parse.Flag_Parse_Parenthesis.value = parse_parenthesis


@pytest.mark.parametrize(
    "fixture",
    ["m7_generate_unresolved.vhd", "m7_generate_dynamic.vhd"],
)
def test_m7_generate_fallback_runs_real_ghdl_semantics(fixture: str) -> None:
    with pytest.raises(Exception) as raised:
        PyGhdlBackend().parse(FIXTURES / fixture)

    assert getattr(raised.value, "code", None) == "HDLX-GHDL-ANALYZE"
