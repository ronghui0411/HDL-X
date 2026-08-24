from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

from hdl_x.frontend import VerilogFrontend
from hdl_x.generator import VhdlGenerator, VhdlLowering, VhdlRenderer, VhdlRenderIR
from hdl_x.ir import Design
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.slang_integration

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parents[1] / "fixtures" / "verilog"
GOLDENS = Path(__file__).parents[1] / "golden_vhdl"


def test_pipeline_lowering_renderer_and_compatibility_api_are_identical() -> None:
    design = VerilogFrontend().parse_design(FIXTURES / "v3_generate_for.v")

    render_ir = VhdlLowering().lower(design)
    direct = VhdlRenderer().render(render_ir)
    compatibility = VhdlGenerator().generate(design)
    pipeline = convert_file(
        FIXTURES / "v3_generate_for.v",
        source_language="verilog",
        target_language="vhdl",
        options=ConversionOptions(strict=True),
    ).text

    assert isinstance(render_ir, VhdlRenderIR)
    assert render_ir.design is design
    assert direct == compatibility == pipeline
    assert direct == (GOLDENS / "v3_generate_for.vhd").read_text(encoding="utf-8")
    _assert_no_pyslang_objects(render_ir)


def test_renderer_rejects_canonical_design_and_canonical_json_round_trips() -> None:
    design = VerilogFrontend().parse_design(FIXTURES / "v3_hierarchy.v")

    with pytest.raises(TypeError, match="requires VhdlRenderIR"):
        VhdlRenderer().render(design)

    restored = Design.model_validate_json(design.model_dump_json())
    assert restored == design


def test_vhdl_templates_do_not_contain_frontend_or_semantic_decisions() -> None:
    templates = ROOT / "src" / "hdl_x" / "templates" / "vhdl"
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(templates.glob("*.j2"))
    )

    for forbidden in (
        "pyslang",
        "Slang",
        "driver_kind",
        "assignment_kind",
        "rtl_type",
        "four_state",
    ):
        assert forbidden not in text


def _assert_no_pyslang_objects(value: object, seen: set[int] | None = None) -> None:
    seen = set() if seen is None else seen
    if value is None or isinstance(value, str | bytes | int | float | bool | Path):
        return
    if id(value) in seen:
        return
    seen.add(id(value))
    assert not type(value).__module__.startswith("pyslang")
    if isinstance(value, dict):
        children = [*value.keys(), *value.values()]
    elif isinstance(value, list | tuple | set | frozenset):
        children = list(value)
    elif is_dataclass(value) and not isinstance(value, type):
        children = [getattr(value, field.name) for field in fields(value)]
    elif hasattr(type(value), "model_fields"):
        children = [getattr(value, name) for name in type(value).model_fields]
    else:
        children = []
    for child in children:
        _assert_no_pyslang_objects(child, seen)
