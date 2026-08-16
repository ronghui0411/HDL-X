"""结构化诊断模型。"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from hdl_x.ir.base import HDLXModel, SourceSpan


class DiagnosticSeverity(str, Enum):
    """诊断严重程度。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class Diagnostic(HDLXModel):
    """可由 CLI、frontend、generator 和 validator 统一消费的诊断。"""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    source_span: SourceSpan | None = None
    source_snippet: str | None = None
    suggestion: str | None = None

    @model_validator(mode="after")
    def populate_and_validate_location(self) -> Diagnostic:
        if self.column is not None and self.line is None:
            raise ValueError("diagnostic column requires line")
        if self.source_span is None:
            return self

        location = self.source_span.start
        if self.file is not None and location.file is not None and self.file != location.file:
            raise ValueError("diagnostic file conflicts with source span")
        if self.line is not None and self.line != location.line:
            raise ValueError("diagnostic line conflicts with source span")
        if self.column is not None and self.column != location.column:
            raise ValueError("diagnostic column conflicts with source span")

        if self.file is None:
            object.__setattr__(self, "file", location.file)
        if self.line is None:
            object.__setattr__(self, "line", location.line)
        if self.column is None:
            object.__setattr__(self, "column", location.column)
        return self

    def format(self) -> str:
        """生成稳定、适合终端显示的单行摘要。"""

        location = ""
        if self.file is not None:
            location = self.file
        if self.line is not None:
            location += f":{self.line}"
            if self.column is not None:
                location += f":{self.column}"
        if location:
            location += ": "
        return f"{location}{self.severity.value} [{self.code}]: {self.message}"
