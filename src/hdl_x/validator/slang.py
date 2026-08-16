"""slang Verilog/SystemVerilog 验证器。"""

from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from .base import Validator


class SlangValidator(Validator):
    """使用 slang 的 lint-only 模式验证生成的 Verilog。"""

    display_name: ClassVar[str] = "slang"
    executable_name: ClassVar[str] = "slang"
    optional: ClassVar[bool] = True

    def _validation_arguments(self, source: Path) -> Sequence[str]:
        return ("--lint-only", str(source))
