"""结构化 diagnostics 与阶段异常测试。"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from hdl_x.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    FrontendError,
    GenerationError,
    SemanticError,
    UnsupportedConstructError,
    ValidationError,
)
from hdl_x.ir import SourceLocation, SourceSpan


def _span() -> SourceSpan:
    return SourceSpan(
        start=SourceLocation(file="counter.vhd", line=12, column=7),
        end=SourceLocation(file="counter.vhd", line=12, column=15),
    )


def test_diagnostic_carries_source_context() -> None:
    diagnostic = Diagnostic(
        code="VHDL1001",
        message="wait statement is outside the synthesizable subset",
        severity=DiagnosticSeverity.ERROR,
        source_span=_span(),
        source_snippet="wait for 10 ns;",
        suggestion="replace delay-based behavior with clocked RTL",
    )

    assert diagnostic.file == "counter.vhd"
    assert diagnostic.line == 12
    assert diagnostic.column == 7
    assert diagnostic.source_snippet == "wait for 10 ns;"
    assert diagnostic.suggestion is not None
    assert (
        diagnostic.format()
        == "counter.vhd:12:7: error [VHDL1001]: "
        "wait statement is outside the synthesizable subset"
    )


def test_diagnostic_rejects_inconsistent_locations() -> None:
    with pytest.raises(PydanticValidationError, match="conflicts with source span"):
        Diagnostic(
            code="VHDL1002",
            message="invalid source location",
            file="other.vhd",
            source_span=_span(),
        )

    with pytest.raises(PydanticValidationError, match="column requires line"):
        Diagnostic(code="HDLX1000", message="invalid location", column=3)


@pytest.mark.parametrize(
    ("error_type", "expected_code"),
    [
        (FrontendError, "HDLX-FRONTEND"),
        (UnsupportedConstructError, "HDLX-UNSUPPORTED"),
        (SemanticError, "HDLX-SEMANTIC"),
        (GenerationError, "HDLX-GENERATION"),
        (ValidationError, "HDLX-VALIDATION"),
    ],
)
def test_stage_errors_wrap_structured_diagnostics(
    error_type: type[Exception], expected_code: str
) -> None:
    error = error_type("conversion failed", source_span=_span())

    assert error.code == expected_code
    assert error.diagnostic.source_span == _span()
    assert "counter.vhd:12:7" in str(error)


def test_error_accepts_an_existing_diagnostic() -> None:
    diagnostic = Diagnostic(
        code="CUSTOM42",
        message="unsafe omission",
        severity=DiagnosticSeverity.FATAL,
    )
    error = UnsupportedConstructError(diagnostic=diagnostic)

    assert error.diagnostic is diagnostic
    assert error.code == "CUSTOM42"
