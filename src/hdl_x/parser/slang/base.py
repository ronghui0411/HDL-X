"""SystemVerilog Slang backend 接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .raw import RawSystemVerilogDesign


class SlangFrontendBackend(ABC):
    """把真实 SystemVerilog source 隔离成私有 Raw 表示。"""

    @abstractmethod
    def parse(self, source_path: Path) -> RawSystemVerilogDesign:
        """执行真实 parse/semantic compilation 并返回纯 Python Raw IR。"""


__all__ = ["SlangFrontendBackend"]
