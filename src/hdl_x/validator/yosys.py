"""Yosys Verilog 综合冒烟验证器。"""

from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from .base import Validator


class YosysValidator(Validator):
    """运行轻量 Yosys 流程验证 Verilog 可读性与基本综合性。"""

    display_name: ClassVar[str] = "Yosys"
    executable_name: ClassVar[str] = "yosys"
    optional: ClassVar[bool] = True
    version_arguments: ClassVar[tuple[str, ...]] = ("-V",)

    def _validation_arguments(self, source: Path) -> Sequence[str]:
        source_argument = self._quote_script_argument(source)
        script = f"read_verilog {source_argument}; hierarchy -check; proc; check"
        return ("-q", "-p", script)

    @staticmethod
    def _quote_script_argument(source: Path) -> str:
        normalized = source.as_posix().replace('"', '\\"')
        return f'"{normalized}"'
