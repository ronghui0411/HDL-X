"""Generator 公共接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from hdl_x.ir import Design


class Generator(ABC):
    """从 canonical IR 生成目标 HDL。"""

    @abstractmethod
    def generate(self, design: Design) -> str:
        """生成确定性的目标源码。"""
