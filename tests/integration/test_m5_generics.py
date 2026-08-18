"""Milestone 5 generic/parameter 真实管线与 canonical IR 回归。"""

from pathlib import Path

import pytest

from hdl_x.ir import (
    AssignmentKind,
    BinaryExpr,
    BinaryOperator,
    Design,
    Identifier,
    Instance,
    IntegerType,
    Literal,
    Module,
    Parameter,
    ParameterBinding,
    ProceduralAssignment,
    RangeDirection,
    SequentialProcess,
    VectorType,
)
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.ghdl_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"
GOLDEN = Path(__file__).parents[1] / "golden"


@pytest.mark.parametrize(
    "case_name",
    [
        "generic_width",
        "generic_default",
        "parameterized_vector",
        "parameterized_counter",
        "generic_expression",
        "multi_generic",
    ],
)
def test_m5_real_pipeline_matches_complete_golden(case_name: str) -> None:
    source_path = FIXTURES / f"m5_{case_name}.vhd"
    expected = (GOLDEN / f"m5_{case_name}.v").read_text(encoding="utf-8")

    result = convert_file(source_path, options=ConversionOptions(strict=True))

    assert result.text == expected
    assert result.design.top == result.design.modules[0].name
    if case_name == "parameterized_counter":
        assert [item.code for item in result.diagnostics] == ["HDLX-VHDL-INITIAL-STATE"]
        assert result.diagnostics[0].line == 17
    else:
        assert result.diagnostics == ()


def test_m5_generic_defaults_remain_symbolic_in_declaration_order() -> None:
    result = convert_file(
        FIXTURES / "m5_multi_generic.vhd",
        options=ConversionOptions(strict=True),
    )
    parameters = result.design.modules[0].parameters

    assert [parameter.name for parameter in parameters] == [
        "WORD_WIDTH",
        "LANES",
        "TOTAL_WIDTH",
    ]
    assert [parameter.default.value for parameter in parameters[:2]] == [8, 4]
    total_default = parameters[2].default
    assert isinstance(total_default, BinaryExpr)
    assert total_default.operator is BinaryOperator.MULTIPLY
    assert isinstance(total_default.left, Identifier)
    assert total_default.left.name == "WORD_WIDTH"
    assert isinstance(total_default.right, Identifier)
    assert total_default.right.name == "LANES"


def test_m5_parameterized_vector_preserves_symbolic_ranges_and_direction() -> None:
    result = convert_file(
        FIXTURES / "m5_parameterized_vector.vhd",
        options=ConversionOptions(strict=True),
    )
    ports = result.design.modules[0].ports
    ranges = []
    for port in ports:
        assert isinstance(port.rtl_type, VectorType)
        ranges.append(port.rtl_type.range)

    assert [item.direction for item in ranges] == [
        RangeDirection.DESCENDING,
        RangeDirection.ASCENDING,
        RangeDirection.DESCENDING,
        RangeDirection.ASCENDING,
    ]
    assert all(item.width is None for item in ranges)
    for descending in (ranges[0], ranges[2]):
        assert isinstance(descending.left, BinaryExpr)
        assert descending.left.operator is BinaryOperator.SUBTRACT
        assert isinstance(descending.left.left, Identifier)
        assert descending.left.left.name == "WIDTH"
        assert isinstance(descending.right, Literal)
        assert descending.right.value == 0
    for ascending in (ranges[1], ranges[3]):
        assert isinstance(ascending.left, Literal)
        assert ascending.left.value == 0
        assert isinstance(ascending.right, BinaryExpr)
        assert ascending.right.operator is BinaryOperator.SUBTRACT
        assert isinstance(ascending.right.left, Identifier)
        assert ascending.right.left.name == "WIDTH"


def test_m5_generic_range_expression_keeps_precedence_tree() -> None:
    result = convert_file(
        FIXTURES / "m5_generic_expression.vhd",
        options=ConversionOptions(strict=True),
    )
    rtl_type = result.design.modules[0].ports[0].rtl_type
    assert isinstance(rtl_type, VectorType)
    assert rtl_type.width is None

    bound = rtl_type.range.left
    assert isinstance(bound, BinaryExpr)
    assert bound.operator is BinaryOperator.SUBTRACT
    assert isinstance(bound.left, BinaryExpr)
    assert bound.left.operator is BinaryOperator.ADD
    assert isinstance(bound.left.right, BinaryExpr)
    assert bound.left.right.operator is BinaryOperator.MULTIPLY


def test_m5_parameterized_counter_keeps_width_and_sequential_semantics() -> None:
    result = convert_file(
        FIXTURES / "m5_parameterized_counter.vhd",
        options=ConversionOptions(strict=True),
    )
    module = result.design.modules[0]
    count_type = module.ports[1].rtl_type

    assert isinstance(count_type, VectorType)
    assert count_type.width is None
    assert count_type.range.direction is RangeDirection.DESCENDING
    assert isinstance(count_type.range.left, BinaryExpr)
    assert isinstance(module.processes[0], SequentialProcess)
    assignment = module.processes[0].body[0]
    assert isinstance(assignment, ProceduralAssignment)
    assert assignment.assignment_kind is AssignmentKind.NON_BLOCKING
    assert isinstance(assignment.value, BinaryExpr)
    assert assignment.value.operator is BinaryOperator.ADD


def test_m5_parameter_override_has_language_neutral_ir_foundation() -> None:
    design = Design(
        name="parameter_override",
        modules=[
            Module(
                name="Child",
                parameters=[
                    Parameter(
                        name="WIDTH",
                        rtl_type=IntegerType(),
                        default=Literal(value=8),
                    )
                ],
            ),
            Module(
                name="Top",
                items=[
                    Instance(
                        referenced_unit="Child",
                        name="u_child",
                        parameter_bindings=[
                            ParameterBinding(formal="WIDTH", value=Literal(value=16))
                        ],
                    )
                ],
            ),
        ],
        top="Top",
    )

    restored = Design.model_validate_json(design.model_dump_json())
    binding = restored.modules[1].instances[0].parameter_bindings[0]
    assert binding.formal == "WIDTH"
    assert binding.position is None
    assert binding.value.value == 16
