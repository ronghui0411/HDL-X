"""Frontend 公共接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

FrontendRepresentation = TypeVar("FrontendRepresentation")


class Frontend(ABC, Generic[FrontendRepresentation]):
    """读取源文件并返回 frontend 私有表示。"""

    @abstractmethod
    def parse(self, source_path: Path) -> FrontendRepresentation:
        """解析源文件，失败时抛出结构化 frontend 异常。"""
