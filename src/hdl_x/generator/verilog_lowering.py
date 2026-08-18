"""Canonical Design 到 Verilog render IR 的显式 lowering。"""

from __future__ import annotations

from hdl_x.ir import Design
from hdl_x.transformer.identifier_resolver import DesignIdentifierResolver, NameStyle
from hdl_x.transformer.type_lowering import DriverAnalysis

from .verilog_ir import VerilogRenderIR


class VerilogLowering:
    """集中执行 Verilog 标识符与 net/reg driver 决策。"""

    def __init__(
        self,
        *,
        name_style: NameStyle = NameStyle.PRESERVE,
        driver_analysis: DriverAnalysis | None = None,
    ) -> None:
        self._name_style = name_style
        self._driver_analysis = driver_analysis or DriverAnalysis()

    def lower(self, design: Design) -> VerilogRenderIR:
        """返回独立目标 IR，不修改调用方传入的 canonical Design。"""

        resolver = DesignIdentifierResolver(self._name_style)
        resolved = resolver.lower(design)
        lowered = self._driver_analysis.lower(resolved)
        return VerilogRenderIR(design=lowered, name_mappings=resolver.mappings)


__all__ = ["VerilogLowering"]
