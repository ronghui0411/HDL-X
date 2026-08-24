import os
import sys
from pathlib import Path

import pytest

from hdl_x.frontend import VhdlFrontend
from hdl_x.generator import VhdlLowering
from hdl_x.pipeline import ConversionOptions, convert_file
from hdl_x.utils import run_command

pytestmark = [pytest.mark.slang_integration, pytest.mark.ghdl_integration]

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parents[1] / "fixtures" / "verilog"
GOLDENS = Path(__file__).parents[1] / "golden_vhdl"


def _validate_with_isolated_pyghdl(source: Path) -> None:
    validation = run_command(
        [
            sys.executable,
            "-c",
            (
                "import sys; from pathlib import Path; "
                "from hdl_x.parser.ghdl import PyGhdlBackend; "
                "PyGhdlBackend().validate(Path(sys.argv[1]))"
            ),
            str(source),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        timeout=60.0,
    )
    assert validation.succeeded, validation.stdout + validation.stderr


def test_real_verilog_to_vhdl_assign_pipeline_matches_golden_and_ghdl(
    tmp_path: Path,
) -> None:
    result = convert_file(
        FIXTURES / "v3_simple_assign.v",
        source_language="verilog",
        target_language="vhdl",
        options=ConversionOptions(strict=True),
    )

    assert result.text == (
        GOLDENS / "v3_simple_assign.vhd"
    ).read_text(encoding="utf-8")
    assert result.design.modules[0].name == "V3SimpleAssign"
    assert result.diagnostics == ()

    generated = tmp_path / "v3_simple_assign.vhd"
    generated.write_text(result.text, encoding="utf-8", newline="\n")
    raw = VhdlFrontend().parse(generated)
    assert [entity.name for entity in raw.entities] == ["V3SimpleAssign"]


def test_vhdl_target_name_mapping_is_reserved_word_and_case_safe() -> None:
    result = convert_file(
        FIXTURES / "v3_names.v",
        source_language="verilog",
        target_language="vhdl",
        options=ConversionOptions(strict=True),
    )

    render_ir = VhdlLowering().lower(result.design)
    assert dict(render_ir.name_mappings) == {
        "entity": "entity_hdl_x",
        "entity.process": "process_hdl_x",
        "entity.Data": "Data",
        "entity.data": "data_2",
        "entity.result": "result",
    }
    assert result.text == (GOLDENS / "v3_names.vhd").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("fixture_name", "entity_names"),
    [
        ("v3_comb_case.v", ["V3CombCase"]),
        ("v3_comments.v", ["V3Comments"]),
        ("v3_register.v", ["V3Register"]),
        ("v3_resets.v", ["V3AsyncReset", "V3SyncReset"]),
        ("v3_signed_parameter.v", ["V3SignedParameter"]),
        ("v3_hierarchy.v", ["V3Child", "V3Hierarchy"]),
        ("v3_generate_for.v", ["V3Generate"]),
        ("v3_generate_if.v", ["V3IfGenerate"]),
        ("v3_integer_counter.v", ["V3IntegerCounter"]),
        ("v3_names.v", ["entity"]),
        ("v3_procedural_x.v", ["V3ProceduralX"]),
        ("v3_unsized_arithmetic.v", ["V3UnsizedArithmetic"]),
    ],
)
def test_real_supported_verilog_profiles_compile_with_libghdl(
    fixture_name: str,
    entity_names: list[str],
    tmp_path: Path,
) -> None:
    result = convert_file(
        FIXTURES / fixture_name,
        source_language="verilog",
        target_language="vhdl",
        options=ConversionOptions(strict=True),
    )

    golden = GOLDENS / f"{Path(fixture_name).stem}.vhd"
    assert result.text == golden.read_text(encoding="utf-8")

    generated = tmp_path / f"{Path(fixture_name).stem}.vhd"
    generated.write_text(result.text, encoding="utf-8", newline="\n")
    _validate_with_isolated_pyghdl(generated)
    assert [module.name for module in result.design.modules] == entity_names
