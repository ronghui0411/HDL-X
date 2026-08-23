from __future__ import annotations

from pathlib import Path

import pytest

from hdl_x.diagnostics import UnsupportedConstructError
from hdl_x.frontend import SystemVerilogFrontend
from hdl_x.ir import (
    BinaryExpr,
    CombinationalProcess,
    ContinuousAssignment,
    DriverKind,
    IntegerType,
    SequentialProcess,
    VectorType,
)

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"


def test_real_slang_frontend_adapts_combination_fixture_to_canonical_ir() -> None:
    design = SystemVerilogFrontend().parse_design(FIXTURES / "sv_comb_logic.sv")

    assert design.top == "SvComb"
    assert len(design.modules) == 1
    module = design.modules[0]
    assert module.name == "SvComb"
    assert [parameter.name for parameter in module.parameters] == ["WIDTH"]
    assert isinstance(module.parameters[0].rtl_type, IntegerType)
    assert {port.name for port in module.ports} == {
        "a",
        "b",
        "sel",
        "opcode",
        "y",
        "parity",
    }
    a_type = next(port.rtl_type for port in module.ports if port.name == "a")
    assert isinstance(a_type, VectorType)
    assert isinstance(a_type.range.left, BinaryExpr)
    assert any(isinstance(item, ContinuousAssignment) for item in module.items)
    processes = [item for item in module.items if isinstance(item, CombinationalProcess)]
    assert len(processes) == 1
    assert processes[0].sensitivity == []
    assert all(port.driver_kind is None for port in module.ports)


def test_real_slang_frontend_adapts_clock_reset_and_edge_semantics() -> None:
    design = SystemVerilogFrontend().parse_design(FIXTURES / "sv_sequential.sv")

    assert [module.name for module in design.modules] == ["SvAsyncReg", "SvSyncReg"]
    async_process = next(
        item
        for item in design.modules[0].items
        if isinstance(item, SequentialProcess)
    )
    sync_process = next(
        item
        for item in design.modules[1].items
        if isinstance(item, SequentialProcess)
    )
    assert async_process.edge.value == "positive"
    assert async_process.reset is not None
    assert async_process.reset.kind.value == "asynchronous"
    assert async_process.reset.active_level.value == "low"
    assert sync_process.edge.value == "negative"
    assert sync_process.reset is not None
    assert sync_process.reset.kind.value == "synchronous"
    assert sync_process.reset.active_level.value == "high"


def test_slang_objects_do_not_leak_beyond_private_backend() -> None:
    frontend = SystemVerilogFrontend()
    raw = frontend.parse(FIXTURES / "sv_hierarchy.sv")
    design = frontend.adapter.adapt(raw)

    assert not type(raw).__module__.startswith("pyslang")
    for module in design.modules:
        for node in (module, *module.parameters, *module.ports, *module.items):
            assert not type(node).__module__.startswith("pyslang")


@pytest.mark.parametrize(
    ("fixture", "code", "line", "column"),
    [
        ("unsupported_interface.sv", "HDLX-SV-INTERFACE", 1, 1),
        ("unsupported_class.sv", "HDLX-SV-CLASS", 1, 1),
        ("unsupported_package.sv", "HDLX-SV-PACKAGE", 1, 1),
        ("unsupported_clocking.sv", "HDLX-SV-CLOCKING", 2, 5),
        ("unsupported_initial.sv", "HDLX-SV-INITIAL", 2, 5),
    ],
)
def test_real_slang_frontend_rejects_unsupported_syntax_with_precise_diagnostic(
    fixture: str,
    code: str,
    line: int,
    column: int,
) -> None:
    with pytest.raises(UnsupportedConstructError) as raised:
        SystemVerilogFrontend().parse_design(FIXTURES / fixture)

    assert raised.value.code == code
    assert raised.value.diagnostic.line == line
    assert raised.value.diagnostic.column == column
    assert raised.value.diagnostic.source_span is not None


def test_frontend_canonical_driver_hints_remain_unset_until_target_lowering() -> None:
    design = SystemVerilogFrontend().parse_design(FIXTURES / "sv_comb_logic.sv")

    assert all(port.driver_kind is None for port in design.modules[0].ports)
    assert all(signal.driver_kind is None for signal in design.modules[0].signals)
    assert DriverKind.PROCEDURAL not in {
        port.driver_kind for port in design.modules[0].ports
    }
