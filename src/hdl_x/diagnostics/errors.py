"""HDL-X 各编译阶段的结构化异常。"""

from __future__ import annotations

from hdl_x.ir.base import SourceSpan

from .diagnostic import Diagnostic, DiagnosticSeverity


class HDLXError(Exception):
    """所有用户可诊断错误的共同基类。"""

    default_code = "HDLX000"

    def __init__(
        self,
        message: str | None = None,
        *,
        diagnostic: Diagnostic | None = None,
        code: str | None = None,
        file: str | None = None,
        line: int | None = None,
        column: int | None = None,
        source_span: SourceSpan | None = None,
        source_snippet: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        if diagnostic is None:
            if message is None:
                raise TypeError("message or diagnostic is required")
            diagnostic = Diagnostic(
                code=code or self.default_code,
                message=message,
                severity=DiagnosticSeverity.ERROR,
                file=file,
                line=line,
                column=column,
                source_span=source_span,
                source_snippet=source_snippet,
                suggestion=suggestion,
            )
        elif message is not None or code is not None:
            raise TypeError("message/code cannot be combined with diagnostic")

        self.diagnostic = diagnostic
        super().__init__(diagnostic.format())

    @property
    def code(self) -> str:
        """返回异常携带的诊断代码。"""

        return self.diagnostic.code


class FrontendError(HDLXError):
    """HDL frontend 读取或分析失败。"""

    default_code = "HDLX-FRONTEND"


class UnsupportedConstructError(HDLXError):
    """构造超出安全支持子集。"""

    default_code = "HDLX-UNSUPPORTED"


class SemanticError(HDLXError):
    """无法安全规范化的 RTL 语义错误。"""

    default_code = "HDLX-SEMANTIC"


class GenerationError(HDLXError):
    """目标 HDL 生成失败。"""

    default_code = "HDLX-GENERATION"


class ValidationError(HDLXError):
    """生成结果未通过外部或内部验证。"""

    default_code = "HDLX-VALIDATION"
