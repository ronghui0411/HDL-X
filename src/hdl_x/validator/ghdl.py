"""GHDL VHDL 源码验证器。"""

from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from .base import Validator


class GhdlValidator(Validator):
    """使用 GHDL 的语法/语义检查命令验证 VHDL 文件。"""

    display_name: ClassVar[str] = "GHDL"
    executable_name: ClassVar[str] = "ghdl"
    optional: ClassVar[bool] = False

    def __init__(self, *, standard: str = "08") -> None:
        if standard not in {"87", "93", "93c", "00", "02", "08", "19"}:
            raise ValueError(f"不支持的 GHDL VHDL 标准: {standard}")
        self.standard = standard

    def _validation_arguments(self, source: Path) -> Sequence[str]:
        return ("-s", f"--std={self.standard}", str(source))
