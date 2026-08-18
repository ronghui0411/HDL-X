"""pyGHDL/libghdl backend 的统一版本与装载策略。"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from importlib import import_module

from hdl_x.diagnostics import FrontendError

SUPPORTED_PYGHDL_VERSION = "6.0.0"


@dataclass(frozen=True, slots=True)
class PyGhdlRuntimeStatus:
    """描述 backend 实际可用性以及不可用时的结构化原因。"""

    available: bool
    installed_version: str | None
    code: str | None
    detail: str
    suggestion: str | None = None


def _distribution_version() -> str | None:
    try:
        return importlib.metadata.version("pyGHDL")
    except importlib.metadata.PackageNotFoundError:
        return None


def _load_required_modules() -> None:
    import_module("pyGHDL.dom.NonStandard")
    import_module("pyGHDL.libghdl")


def inspect_pyghdl_runtime() -> PyGhdlRuntimeStatus:
    """按与 backend 完全相同的规则检查 pyGHDL 与 libghdl。"""

    installed_version = _distribution_version()
    if installed_version is None:
        return PyGhdlRuntimeStatus(
            available=False,
            installed_version=None,
            code="HDLX-GHDL-UNAVAILABLE",
            detail="未安装 pyGHDL；VHDL frontend 需要精确版本 6.0.0。",
            suggestion="安装与当前 Python ABI 匹配的官方 pyGHDL 6.0.0 wheel。",
        )

    if installed_version != SUPPORTED_PYGHDL_VERSION:
        return PyGhdlRuntimeStatus(
            available=False,
            installed_version=installed_version,
            code="HDLX-GHDL-VERSION",
            detail=(
                f"不支持 pyGHDL {installed_version}；当前 backend 已验证版本为 "
                f"{SUPPORTED_PYGHDL_VERSION}。"
            ),
            suggestion=(
                "安装 pyGHDL 6.0.0，或为新版本增加并验证独立 backend。"
            ),
        )

    try:
        _load_required_modules()
    except (ImportError, OSError) as error:
        return PyGhdlRuntimeStatus(
            available=False,
            installed_version=installed_version,
            code="HDLX-GHDL-LOAD",
            detail=f"pyGHDL 6.0.0 已安装但 libghdl backend 装载失败：{error}",
            suggestion="检查 wheel、Python ABI、系统架构和运行时 DLL 是否匹配。",
        )

    return PyGhdlRuntimeStatus(
        available=True,
        installed_version=installed_version,
        code=None,
        detail="官方 pyGHDL/libghdl backend（精确版本规则已通过）",
    )


def require_pyghdl_runtime() -> str:
    """返回已验证版本；不可用时抛出与 doctor 一致的 FrontendError。"""

    status = inspect_pyghdl_runtime()
    if not status.available:
        raise FrontendError(
            status.detail,
            code=status.code or "HDLX-GHDL-UNAVAILABLE",
            suggestion=status.suggestion,
        )
    assert status.installed_version is not None
    return status.installed_version


__all__ = [
    "SUPPORTED_PYGHDL_VERSION",
    "PyGhdlRuntimeStatus",
    "inspect_pyghdl_runtime",
    "require_pyghdl_runtime",
]
