"""Slang frontend 与 Canonical IR 之间的私有纯 Python 表示。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RawSourceSpan:
    """Slang source manager 提供的 1-based 源区间。"""

    file: Path
    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass(frozen=True, slots=True)
class RawSystemVerilogModule:
    """不持有 pyslang 对象的单个 module 语法快照。"""

    name: str
    syntax: dict[str, Any]
    source: RawSourceSpan


@dataclass(frozen=True, slots=True)
class RawSystemVerilogDesign:
    """一次 Slang compilation 产生的私有 Raw 设计。"""

    source_path: Path
    modules: tuple[RawSystemVerilogModule, ...] = field(default_factory=tuple)
    top_names: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["RawSourceSpan", "RawSystemVerilogDesign", "RawSystemVerilogModule"]
