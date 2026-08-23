"""pyslang frontend 的统一版本与装载策略。"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from importlib import import_module

from hdl_x.diagnostics import FrontendError

SUPPORTED_PYSLANG_VERSION = "11.0.0"


@dataclass(frozen=True, slots=True)
class PySlangRuntimeStatus:
    """描述 pyslang backend 的精确版本可用性。"""

    available: bool
    installed_version: str | None
    code: str | None
    detail: str
    suggestion: str | None = None


def _distribution_version() -> str | None:
    try:
        return importlib.metadata.version("pyslang")
    except importlib.metadata.PackageNotFoundError:
        return None


def _load_required_module() -> object:
    module = import_module("pyslang")
    syntax = getattr(module, "syntax", None)
    ast = getattr(module, "ast", None)
    if syntax is None or ast is None:
        raise ImportError("pyslang.syntax / pyslang.ast namespace is unavailable")
    if not hasattr(syntax, "SyntaxTree") or not hasattr(ast, "Compilation"):
        raise ImportError("required SyntaxTree / Compilation API is unavailable")
    return module


def inspect_pyslang_runtime() -> PySlangRuntimeStatus:
    """按 backend 使用的同一规则检查 pyslang。"""

    installed_version = _distribution_version()
    if installed_version is None:
        return PySlangRuntimeStatus(
            available=False,
            installed_version=None,
            code="HDLX-SV-FRONTEND-UNAVAILABLE",
            detail=(
                "未安装 pyslang；SystemVerilog frontend 需要精确版本 "
                f"{SUPPORTED_PYSLANG_VERSION}。"
            ),
            suggestion='安装可选依赖：python -m pip install "hdl-x[systemverilog]"。',
        )

    if installed_version != SUPPORTED_PYSLANG_VERSION:
        return PySlangRuntimeStatus(
            available=False,
            installed_version=installed_version,
            code="HDLX-SV-FRONTEND-VERSION",
            detail=(
                f"不支持 pyslang {installed_version}；当前 backend 已验证版本为 "
                f"{SUPPORTED_PYSLANG_VERSION}。"
            ),
            suggestion=(
                f"安装 pyslang {SUPPORTED_PYSLANG_VERSION}，或为新版本增加并验证独立 backend。"
            ),
        )

    try:
        _load_required_module()
    except (ImportError, OSError) as error:
        return PySlangRuntimeStatus(
            available=False,
            installed_version=installed_version,
            code="HDLX-SV-FRONTEND-LOAD",
            detail=f"pyslang {installed_version} 已安装但 backend 装载失败：{error}",
            suggestion="检查 pyslang wheel、Python ABI、系统架构和运行时 DLL 是否匹配。",
        )

    return PySlangRuntimeStatus(
        available=True,
        installed_version=installed_version,
        code=None,
        detail="官方 pyslang/Slang frontend（精确版本规则已通过）",
    )


def require_pyslang_runtime() -> object:
    """返回已验证模块；不可用时抛出与 doctor 一致的 FrontendError。"""

    status = inspect_pyslang_runtime()
    if not status.available:
        raise FrontendError(
            status.detail,
            code=status.code or "HDLX-SV-FRONTEND-UNAVAILABLE",
            suggestion=status.suggestion,
        )
    return _load_required_module()


__all__ = [
    "SUPPORTED_PYSLANG_VERSION",
    "PySlangRuntimeStatus",
    "inspect_pyslang_runtime",
    "require_pyslang_runtime",
]
