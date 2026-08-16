"""Canonical IR 降低接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from hdl_x.ir import Design


class SemanticLowering(ABC):
    """在 frontend adapter 与 generator 之间执行语义归一化。"""

    @abstractmethod
    def lower(self, design: Design) -> Design:
        """返回面向目标能力但仍保持语言中立的 canonical IR。"""
