"""外部 HDL 验证器的公共抽象。"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import ClassVar

from hdl_x.utils.subprocess import (
    CommandResult,
    ExecutableNotFoundError,
    find_executable,
    run_command,
)


class ValidationStatus(str, Enum):
    """一次验证的终止状态。"""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ToolAvailability:
    """外部验证工具的发现结果。"""

    validator: str
    executable_name: str
    available: bool
    optional: bool
    executable: Path | None
    message: str

    @property
    def blocks_translation(self) -> bool:
        """缺少该工具是否应阻止翻译流程。"""

        return not self.available and not self.optional


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """外部验证器的结构化执行结果。"""

    validator: str
    source: Path
    status: ValidationStatus
    optional: bool
    message: str
    command: tuple[str, ...] = ()
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""

    @property
    def passed(self) -> bool:
        """验证是否明确通过。"""

        return self.status is ValidationStatus.PASSED

    @property
    def failed(self) -> bool:
        """验证是否明确发现错误。"""

        return self.status is ValidationStatus.FAILED

    @property
    def unavailable(self) -> bool:
        """验证是否因工具不可用而未执行。"""

        return self.status is ValidationStatus.UNAVAILABLE

    @property
    def succeeded(self) -> bool:
        """提供与外部命令结果一致的成功判定。"""

        return self.passed

    @property
    def blocks_translation(self) -> bool:
        """该结果是否应阻止翻译输出被接受。"""

        if self.failed:
            return True
        return self.unavailable and not self.optional


class Validator(ABC):
    """基于命令行工具的 HDL 验证器基类。"""

    display_name: ClassVar[str]
    executable_name: ClassVar[str]
    optional: ClassVar[bool] = False
    version_arguments: ClassVar[tuple[str, ...]] = ("--version",)

    def availability(self) -> ToolAvailability:
        """查询验证工具是否可从当前进程环境调用。"""

        executable = find_executable(self.executable_name)
        if executable is None:
            qualifier = "可选验证器，将跳过验证" if self.optional else "必需验证器不可用"
            return ToolAvailability(
                validator=self.display_name,
                executable_name=self.executable_name,
                available=False,
                optional=self.optional,
                executable=None,
                message=f"未找到外部程序 {self.executable_name}；{qualifier}",
            )

        return ToolAvailability(
            validator=self.display_name,
            executable_name=self.executable_name,
            available=True,
            optional=self.optional,
            executable=executable,
            message=f"已找到 {self.display_name}: {executable}",
        )

    def version(self, *, timeout: float = 10.0) -> str | None:
        """返回工具报告的首个非空版本行；不可用或查询失败时返回 ``None``。"""

        availability = self.availability()
        if availability.executable is None:
            return None

        try:
            result = run_command(
                [availability.executable, *self.version_arguments],
                timeout=timeout,
            )
        except (ExecutableNotFoundError, OSError, subprocess.SubprocessError):
            return None

        if not result.succeeded:
            return None

        for stream in (result.stdout, result.stderr):
            for line in stream.splitlines():
                if stripped := line.strip():
                    return stripped
        return None

    def validate(
        self,
        source: str | PathLike[str],
        *,
        timeout: float = 30.0,
    ) -> ValidationResult:
        """验证单个 HDL 文件并将工具退出状态转换为结构化结果。"""

        source_path = Path(source).expanduser().resolve()
        if not source_path.is_file():
            return ValidationResult(
                validator=self.display_name,
                source=source_path,
                status=ValidationStatus.FAILED,
                optional=self.optional,
                message=f"待验证文件不存在: {source_path}",
            )

        availability = self.availability()
        if availability.executable is None:
            return ValidationResult(
                validator=self.display_name,
                source=source_path,
                status=ValidationStatus.UNAVAILABLE,
                optional=self.optional,
                message=availability.message,
            )

        command = (
            str(availability.executable),
            *self._validation_arguments(source_path),
        )
        try:
            command_result = run_command(command, timeout=timeout)
        except ExecutableNotFoundError as error:
            return ValidationResult(
                validator=self.display_name,
                source=source_path,
                status=ValidationStatus.UNAVAILABLE,
                optional=self.optional,
                message=str(error),
                command=command,
            )
        except subprocess.TimeoutExpired as error:
            return ValidationResult(
                validator=self.display_name,
                source=source_path,
                status=ValidationStatus.FAILED,
                optional=self.optional,
                message=f"{self.display_name} 验证超时（{timeout:g} 秒）",
                command=command,
                stdout=self._exception_text(error.stdout),
                stderr=self._exception_text(error.stderr),
            )
        except (OSError, subprocess.SubprocessError) as error:
            return ValidationResult(
                validator=self.display_name,
                source=source_path,
                status=ValidationStatus.FAILED,
                optional=self.optional,
                message=f"无法执行 {self.display_name}: {error}",
                command=command,
            )

        return self._result_from_command(source_path, command_result)

    @abstractmethod
    def _validation_arguments(self, source: Path) -> Sequence[str]:
        """构造可执行文件名称之后的验证命令参数。"""

    def _result_from_command(
        self,
        source: Path,
        command_result: CommandResult,
    ) -> ValidationResult:
        status = (
            ValidationStatus.PASSED if command_result.succeeded else ValidationStatus.FAILED
        )
        message = (
            f"{self.display_name} 验证通过"
            if command_result.succeeded
            else f"{self.display_name} 验证失败，退出码 {command_result.returncode}"
        )
        return ValidationResult(
            validator=self.display_name,
            source=source,
            status=status,
            optional=self.optional,
            message=message,
            command=command_result.args,
            returncode=command_result.returncode,
            stdout=command_result.stdout,
            stderr=command_result.stderr,
        )

    @staticmethod
    def _exception_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
