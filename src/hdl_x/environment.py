"""运行环境与外部 HDL 工具探测。"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

from hdl_x.parser.ghdl.runtime import inspect_pyghdl_runtime
from hdl_x.validator import GhdlValidator, SlangValidator, YosysValidator


@dataclass(frozen=True, slots=True)
class EnvironmentItem:
    """doctor 命令展示的一项环境能力。"""

    name: str
    available: bool
    version: str | None
    detail: str
    required: bool = False


def inspect_environment() -> list[EnvironmentItem]:
    """返回 Python、frontend 与 validator 的实际可用状态。"""

    items = [
        EnvironmentItem(
            name="Python",
            available=True,
            version=platform.python_version(),
            detail=sys.executable,
            required=True,
        )
    ]

    pyghdl = inspect_pyghdl_runtime()
    items.append(
        EnvironmentItem(
            name="GHDL frontend (pyGHDL/libghdl)",
            available=pyghdl.available,
            version=pyghdl.installed_version,
            detail=pyghdl.detail,
            required=True,
        )
    )

    for validator in (GhdlValidator(), SlangValidator(), YosysValidator()):
        availability = validator.availability()
        is_standalone_ghdl = isinstance(validator, GhdlValidator)
        detail = availability.message
        if is_standalone_ghdl and not availability.available:
            detail = (
                "未找到独立 ghdl.exe；转换仍使用上方已报告的 pyGHDL/libghdl frontend，"
                "仅跳过额外 CLI 源码验证"
            )
        items.append(
            EnvironmentItem(
                name=f"{availability.validator} CLI validator",
                available=availability.available,
                version=validator.version(),
                detail=detail,
                required=False,
            )
        )
    return items
