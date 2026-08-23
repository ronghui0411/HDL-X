from pathlib import Path

import pytest

from hdl_x.frontend import SystemVerilogFrontend
from hdl_x.generator import VerilogLowering, VerilogRenderer
from hdl_x.ir import DriverKind

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "systemverilog"
GOLDENS = Path(__file__).parents[1] / "golden"


def test_real_frontend_canonical_lowering_and_renderer_match_golden() -> None:
    canonical = SystemVerilogFrontend().parse_design(FIXTURES / "sv_comb_logic.sv")
    original = canonical.model_copy(deep=True)

    render_ir = VerilogLowering(source_case_sensitive=True).lower(canonical)
    rendered = VerilogRenderer().render(render_ir)

    assert canonical == original
    assert all(port.driver_kind is None for port in canonical.modules[0].ports)
    lowered_ports = {port.name: port for port in render_ir.design.modules[0].ports}
    assert lowered_ports["y"].driver_kind is DriverKind.PROCEDURAL
    assert lowered_ports["parity"].driver_kind is DriverKind.CONTINUOUS
    assert rendered.encode("utf-8") == (GOLDENS / "sv_comb_logic.v").read_bytes()


def test_systemverilog_lowering_preserves_case_sensitive_names() -> None:
    canonical = SystemVerilogFrontend().parse_design(FIXTURES / "sv_case_sensitive.sv")

    render_ir = VerilogLowering(source_case_sensitive=True).lower(canonical)
    rendered = VerilogRenderer().render(render_ir)

    assert [port.name for port in render_ir.design.modules[0].ports][:2] == [
        "data",
        "Data",
    ]
    assert rendered.encode("utf-8") == (GOLDENS / "sv_case_sensitive.v").read_bytes()
