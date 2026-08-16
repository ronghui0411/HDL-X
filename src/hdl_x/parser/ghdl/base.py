"""GHDL backend 抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .raw import RawDesign


class GhdlFrontendBackend(ABC):
    """把具体 GHDL API 隔离在 frontend 私有边界内。"""

    @abstractmethod
    def parse(self, source_path: Path) -> RawDesign:
        """使用 GHDL 分析 VHDL 源文件并返回私有 Raw IR。"""


__all__ = ["GhdlFrontendBackend"]
