"""完成 Verilog-specific lowering 后交给 renderer 的目标 IR。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from hdl_x.ir import Design


class VerilogAssignmentOperator(str, Enum):
    """已由 Verilog lowering 选择的过程赋值操作符。"""

    BLOCKING = "="
    NON_BLOCKING = "<="


@dataclass(frozen=True, slots=True)
class VerilogRenderIR:
    """封装已完成名称与 driver 决策的 v0.1 目标结构。"""

    design: Design
    name_mappings: Mapping[str, str]
    assignment_operators: Mapping[int, VerilogAssignmentOperator] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.design, Design):
            raise TypeError("VerilogRenderIR.design must be a canonical Design")
        object.__setattr__(self, "name_mappings", MappingProxyType(dict(self.name_mappings)))
        object.__setattr__(
            self,
            "assignment_operators",
            MappingProxyType(dict(self.assignment_operators)),
        )


__all__ = ["VerilogAssignmentOperator", "VerilogRenderIR"]
