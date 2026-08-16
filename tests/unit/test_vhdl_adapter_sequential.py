"""Raw sequential process 到 canonical IR 的单元测试。"""

from pathlib import Path

from hdl_x.ir import (
    ActiveLevel,
    AssignmentKind,
    CaseStatement,
    EdgeKind,
    IfStatement,
    ProceduralAssignment,
    ResetKind,
    SequentialProcess,
)
from hdl_x.parser.ghdl.raw import (
    RawActiveLevel,
    RawArchitecture,
    RawCaseAlternative,
    RawCaseStatement,
    RawDesign,
    RawEdgeKind,
    RawEntity,
    RawIdentifier,
    RawIfStatement,
    RawLiteral,
    RawLiteralKind,
    RawPort,
    RawPortDirection,
    RawProceduralAssignment,
    RawResetKind,
    RawResetSpec,
    RawSequentialProcess,
    RawType,
    RawTypeKind,
)
from hdl_x.parser.vhdl_adapter import VhdlAdapter


def _scalar() -> RawType:
    return RawType(
        kind=RawTypeKind.SCALAR,
        source_name="std_logic",
        four_state=True,
    )


def _assignment(target: str, value: str) -> RawProceduralAssignment:
    return RawProceduralAssignment(RawIdentifier(target), RawIdentifier(value))


def _adapt(process: RawSequentialProcess) -> SequentialProcess:
    entity = RawEntity(
        name="Registers",
        ports=tuple(
            RawPort(name, direction, _scalar())
            for name, direction in (
                ("clk", RawPortDirection.IN),
                ("reset_n", RawPortDirection.IN),
                ("d", RawPortDirection.IN),
                ("qa", RawPortDirection.OUT),
                ("qb", RawPortDirection.OUT),
            )
        ),
    )
    raw = RawDesign(
        Path("registers.vhd"),
        (entity,),
        (RawArchitecture("rtl", "Registers", (process,)),),
    )
    canonical = VhdlAdapter().adapt(raw).modules[0].processes[0]
    assert isinstance(canonical, SequentialProcess)
    return canonical


def test_adapter_maps_explicit_edge_and_reset_semantics() -> None:
    process = RawSequentialProcess(
        label="registers_p",
        sensitivity=(RawIdentifier("reset_n"), RawIdentifier("clk")),
        clock=RawIdentifier("clk"),
        edge=RawEdgeKind.NEGATIVE,
        reset=RawResetSpec(
            signal=RawIdentifier("reset_n"),
            kind=RawResetKind.ASYNCHRONOUS,
            active_level=RawActiveLevel.LOW,
        ),
        reset_body=(_assignment("qa", "d"),),
        body=(_assignment("qa", "d"), _assignment("qb", "qa")),
    )

    canonical = _adapt(process)

    assert canonical.label == "registers_p"
    assert canonical.clock.name == "clk"
    assert canonical.edge is EdgeKind.NEGATIVE
    assert canonical.reset is not None
    assert canonical.reset.kind is ResetKind.ASYNCHRONOUS
    assert canonical.reset.active_level is ActiveLevel.LOW


def test_adapter_recursively_uses_nonblocking_for_sequential_statements() -> None:
    nested_if = RawIfStatement(
        condition=RawIdentifier("d"),
        then_body=(_assignment("qa", "d"),),
        else_body=(_assignment("qb", "qa"),),
    )
    nested_case = RawCaseStatement(
        expression=RawIdentifier("d"),
        alternatives=(
            RawCaseAlternative(
                selectors=(RawLiteral("0", RawLiteralKind.BIT),),
                body=(_assignment("qa", "d"),),
            ),
        ),
        default_body=(_assignment("qb", "qa"),),
    )
    process = RawSequentialProcess(
        label=None,
        sensitivity=(RawIdentifier("clk"),),
        clock=RawIdentifier("clk"),
        edge=RawEdgeKind.POSITIVE,
        body=(nested_if, nested_case),
    )

    canonical = _adapt(process)

    if_statement = canonical.body[0]
    case_statement = canonical.body[1]
    assert isinstance(if_statement, IfStatement)
    assert isinstance(case_statement, CaseStatement)
    assignments = (
        *if_statement.then_body,
        *if_statement.else_body,
        *case_statement.alternatives[0].body,
        *case_statement.default_body,
    )
    assert all(
        isinstance(assignment, ProceduralAssignment)
        and assignment.assignment_kind is AssignmentKind.NON_BLOCKING
        for assignment in assignments
    )
