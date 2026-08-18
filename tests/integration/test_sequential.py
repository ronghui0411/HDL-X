"""VHDL sequential process 的真实 pyGHDL 集成测试。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import UnsupportedConstructError
from hdl_x.frontend import VhdlFrontend
from hdl_x.ir import (
    ActiveLevel,
    AssignmentKind,
    BinaryExpr,
    BinaryOperator,
    CombinationalProcess,
    EdgeKind,
    IfStatement,
    ProceduralAssignment,
    ResetKind,
    SequentialProcess,
)
from hdl_x.parser.ghdl import PyGhdlBackend
from hdl_x.parser.ghdl.raw import RawSequentialProcess
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.ghdl_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "vhdl"


@pytest.mark.parametrize(
    ("fixture", "edge", "reset_kind", "active_level"),
    [
        ("m4_posedge.vhd", EdgeKind.POSITIVE, None, None),
        ("m4_negedge.vhd", EdgeKind.NEGATIVE, None, None),
        (
            "m4_sync_high_reset.vhd",
            EdgeKind.POSITIVE,
            ResetKind.SYNCHRONOUS,
            ActiveLevel.HIGH,
        ),
        (
            "m4_sync_low_reset.vhd",
            EdgeKind.NEGATIVE,
            ResetKind.SYNCHRONOUS,
            ActiveLevel.LOW,
        ),
        (
            "m4_async_high_reset.vhd",
            EdgeKind.POSITIVE,
            ResetKind.ASYNCHRONOUS,
            ActiveLevel.HIGH,
        ),
        (
            "m4_async_low_reset.vhd",
            EdgeKind.NEGATIVE,
            ResetKind.ASYNCHRONOUS,
            ActiveLevel.LOW,
        ),
    ],
)
def test_real_ghdl_classifies_clock_and_reset_semantics(
    fixture: str,
    edge: EdgeKind,
    reset_kind: ResetKind | None,
    active_level: ActiveLevel | None,
) -> None:
    raw = PyGhdlBackend().parse(FIXTURES / fixture)
    assert isinstance(raw.architectures[0].items[0], RawSequentialProcess)

    process = VhdlFrontend().parse_design(FIXTURES / fixture).modules[0].processes[0]
    assert isinstance(process, SequentialProcess)
    assert process.edge is edge
    if reset_kind is None:
        assert process.reset is None
        assert process.reset_body == []
    else:
        assert process.reset is not None
        assert process.reset.kind is reset_kind
        assert process.reset.active_level is active_level
        assert process.reset_body
    assert process.body


def test_real_ghdl_maps_counter_expression_and_nonblocking_assignment() -> None:
    process = VhdlFrontend().parse_design(FIXTURES / "m4_counter.vhd").modules[0].processes[0]

    assert isinstance(process, SequentialProcess)
    assignment = process.body[0]
    assert isinstance(assignment, ProceduralAssignment)
    assert assignment.assignment_kind is AssignmentKind.NON_BLOCKING
    assert isinstance(assignment.value, BinaryExpr)
    assert assignment.value.operator is BinaryOperator.ADD


def test_real_ghdl_preserves_multiple_register_assignments() -> None:
    process = VhdlFrontend().parse_design(
        FIXTURES / "m4_multi_register.vhd"
    ).modules[0].processes[0]

    assert isinstance(process, SequentialProcess)
    assert [assignment.target.name for assignment in process.reset_body] == ["qa", "qb"]
    assert [assignment.target.name for assignment in process.body] == ["qa", "qb"]
    assert all(
        isinstance(assignment, ProceduralAssignment)
        and assignment.assignment_kind is AssignmentKind.NON_BLOCKING
        for assignment in (*process.reset_body, *process.body)
    )


def test_clock_enable_is_preserved_inside_sequential_body() -> None:
    process = VhdlFrontend().parse_design(
        FIXTURES / "m4_clock_enable.vhd"
    ).modules[0].processes[0]

    assert isinstance(process, SequentialProcess)
    assert process.reset is None
    assert isinstance(process.body[0], IfStatement)
    assignment = process.body[0].then_body[0]
    assert isinstance(assignment, ProceduralAssignment)
    assert assignment.assignment_kind is AssignmentKind.NON_BLOCKING


@pytest.mark.parametrize(
    ("fixture", "code"),
    [
        ("m4_ambiguous_clocks.vhd", "HDLX-VHDL-SEQUENTIAL-AMBIGUOUS"),
        (
            "m4_async_reset_missing_sensitivity.vhd",
            "HDLX-VHDL-SEQUENTIAL-SENSITIVITY",
        ),
        (
            "m4_sync_reset_extra_sensitivity.vhd",
            "HDLX-VHDL-SEQUENTIAL-SENSITIVITY",
        ),
    ],
)
def test_real_ghdl_rejects_unsafe_sequential_shapes(
    fixture: str, code: str
) -> None:
    with pytest.raises(UnsupportedConstructError) as raised:
        PyGhdlBackend().parse(FIXTURES / fixture)

    assert raised.value.code == code


def test_clock_level_condition_is_not_misclassified_as_edge() -> None:
    process = VhdlFrontend().parse_design(
        FIXTURES / "m4_level_condition.vhd"
    ).modules[0].processes[0]

    assert isinstance(process, CombinationalProcess)


@pytest.mark.parametrize(
    "options",
    [
        ConversionOptions(strict=True),
        ConversionOptions(strict=False, best_effort=True),
    ],
)
def test_pipeline_rejects_sequential_process_declarations(
    options: ConversionOptions,
) -> None:
    source = (FIXTURES / "m4_process_declaration.vhd").resolve()

    with pytest.raises(UnsupportedConstructError) as raised:
        convert_file(source, options=options)

    diagnostic = raised.value.diagnostic
    assert raised.value.code == "HDLX-VHDL-PROCESS-DECLARATION"
    assert diagnostic.file == str(source)
    assert diagnostic.line == 11
