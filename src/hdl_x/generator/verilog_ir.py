"""完成 Verilog-specific lowering 后交给 renderer 的目标 IR。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from hdl_x.ir import Design


@dataclass(frozen=True, slots=True)
class VerilogRenderIR:
    """封装已完成名称与 driver 决策的 v0.1 目标结构。"""

    design: Design
    name_mappings: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.design, Design):
            raise TypeError("VerilogRenderIR.design must be a canonical Design")
        object.__setattr__(self, "name_mappings", MappingProxyType(dict(self.name_mappings)))


__all__ = ["VerilogRenderIR"]
