"""运行环境与外部 HDL 工具探测。"""

from __future__ import annotations

import importlib.metadata
import platform
import sys
from dataclasses import dataclass

from hdl_x.validator import GhdlValidator, SlangValidator, YosysValidator


@dataclass(frozen=True, slots=True)
class EnvironmentItem:
    """doctor 命令展示的一项环境能力。"""

    name: str
    available: bool
    version: str | None
    detail: str
    required: bool = False


def _distribution_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


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

    pyghdl_version = _distribution_version("pyGHDL")
    libghdl_detail = "官方 pyGHDL/libghdl backend"
    if pyghdl_version is not None:
        try:
            from pyGHDL.dom.NonStandard import Design  # noqa: F401
            from pyGHDL.libghdl import libghdl  # noqa: F401
        except (ImportError, OSError) as error:
            items.append(
                EnvironmentItem(
                    name="GHDL frontend (pyGHDL/libghdl)",
                    available=False,
                    version=pyghdl_version,
                    detail=f"包已安装但 backend 加载失败: {error}",
                    required=True,
                )
            )
        else:
            items.append(
                EnvironmentItem(
                    name="GHDL frontend (pyGHDL/libghdl)",
                    available=True,
                    version=pyghdl_version,
                    detail=libghdl_detail,
                    required=True,
                )
            )
    else:
        items.append(
            EnvironmentItem(
                name="GHDL frontend (pyGHDL/libghdl)",
                available=False,
                version=None,
                detail="未安装匹配版本的官方 pyGHDL wheel",
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
