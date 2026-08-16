"""HDL-X 结构化诊断公共 API。"""

from .diagnostic import Diagnostic, DiagnosticSeverity
from .errors import (
    FrontendError,
    GenerationError,
    HDLXError,
    SemanticError,
    UnsupportedConstructError,
    ValidationError,
)

__all__ = [
    "Diagnostic",
    "DiagnosticSeverity",
    "FrontendError",
    "GenerationError",
    "HDLXError",
    "SemanticError",
    "UnsupportedConstructError",
    "ValidationError",
]
