"""AST adapter 公共接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from hdl_x.ir import Design

FrontendRepresentation = TypeVar("FrontendRepresentation")


class ParserAdapter(ABC, Generic[FrontendRepresentation]):
    """隔离 frontend 私有节点并产生语言中立 IR。"""

    @abstractmethod
    def adapt(self, representation: FrontendRepresentation) -> Design:
        """将 frontend 私有表示转换为 canonical IR。"""
