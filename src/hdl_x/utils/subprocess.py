"""集中管理外部进程调用。"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


class ExecutableNotFoundError(FileNotFoundError):
    """请求的外部程序不可用。"""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """一次外部命令的完整结果。"""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        """命令是否以零状态码退出。"""

        return self.returncode == 0


def find_executable(name: str) -> Path | None:
    """返回可执行文件的绝对路径；不存在时返回 ``None``。"""

    resolved = shutil.which(name)
    return Path(resolved).resolve() if resolved else None


def run_command(
    args: Sequence[str | os.PathLike[str]],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 30.0,
) -> CommandResult:
    """安全执行参数数组，不经过 shell 解释。"""

    if not args:
        raise ValueError("外部命令参数不能为空")

    normalized = tuple(os.fspath(item) for item in args)
    executable = normalized[0]
    executable_path = Path(executable)
    has_path_component = any(
        separator and separator in executable for separator in (os.sep, os.altsep)
    )

    if executable_path.is_absolute():
        resolved_executable = executable_path.resolve() if executable_path.is_file() else None
    elif has_path_component:
        working_directory = Path(cwd) if cwd is not None else Path.cwd()
        candidate = working_directory.expanduser().resolve() / executable_path
        resolved_executable = candidate.resolve() if candidate.is_file() else None
    else:
        resolved_executable = find_executable(executable)

    if resolved_executable is None:
        raise ExecutableNotFoundError(f"找不到外部程序: {executable}")
    normalized = (os.fspath(resolved_executable), *normalized[1:])

    completed = subprocess.run(
        normalized,
        cwd=os.fspath(cwd) if cwd is not None else None,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    return CommandResult(
        args=normalized,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
