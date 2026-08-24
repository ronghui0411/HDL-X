from __future__ import annotations

from pathlib import Path

import pytest

from hdl_x.diagnostics import (
    DiagnosticSeverity,
    SemanticError,
    UnsupportedConstructError,
)
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.slang_integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "verilog"


@pytest.mark.parametrize("mode", ["strict", "best_effort"])
@pytest.mark.parametrize(
    ("fixture_name", "expected_type", "expected_code"),
    [
        (
            "v3_unsupported_sequential_blocking.v",
            UnsupportedConstructError,
            "HDLX-V2V-SEQUENTIAL-BLOCKING",
        ),
        (
            "v3_unsupported_tristate.v",
            SemanticError,
            "HDLX-V2V-TRISTATE",
        ),
        (
            "v3_unsupported_multiple_drivers.v",
            SemanticError,
            "HDLX-V2V-MULTIPLE-DRIVER",
        ),
        (
            "v3_unsupported_generate_else.v",
            UnsupportedConstructError,
            "HDLX-V2V-GENERATE-ELSE-HIERARCHY",
        ),
        (
            "v3_unsupported_generate_unlabeled.v",
            UnsupportedConstructError,
            "HDLX-V2V-GENERATE-LABEL",
        ),
        (
            "v3_unsupported_procedural_z.v",
            SemanticError,
            "HDLX-V2V-TRISTATE",
        ),
        (
            "v3_unsupported_package.v",
            UnsupportedConstructError,
            "HDLX-V2V-PACKAGE",
        ),
        (
            "v3_unsupported_include.v",
            UnsupportedConstructError,
            "HDLX-V2V-COMPILATION-UNIT",
        ),
        (
            "v3_unsupported_always_comb.v",
            UnsupportedConstructError,
            "HDLX-V2V-SYSTEMVERILOG",
        ),
        (
            "v3_unsupported_mixed_signed.v",
            UnsupportedConstructError,
            "HDLX-V2V-SIGNED-SIZING",
        ),
        (
            "v3_unsupported_width_sizing.v",
            UnsupportedConstructError,
            "HDLX-V2V-SIZING",
        ),
        (
            "v3_unsupported_async_reset_edge.v",
            UnsupportedConstructError,
            "HDLX-V2V-ASYNC-RESET-EVENT",
        ),
        (
            "v3_unsupported_mixed_event.v",
            UnsupportedConstructError,
            "HDLX-V2V-MIXED-EVENT",
        ),
    ],
)
def test_unsafe_verilog_semantics_are_never_silently_converted(
    fixture_name: str,
    expected_type: type[Exception],
    expected_code: str,
    mode: str,
) -> None:
    options = ConversionOptions(
        strict=mode == "strict",
        best_effort=mode == "best_effort",
    )

    with pytest.raises(expected_type) as caught:
        convert_file(
            FIXTURES / fixture_name,
            source_language="verilog",
            target_language="vhdl",
            options=options,
        )

    assert type(caught.value) is expected_type
    assert caught.value.code == expected_code
    assert caught.value.diagnostic.source_span is not None
    assert caught.value.diagnostic.source_span.start.line >= 1
    assert caught.value.diagnostic.source_span.start.column >= 1


@pytest.mark.parametrize(
    ("fixture_name", "expected_codes"),
    [
        ("v3_comb_case.v", {"HDLX-V2V-TIME-ZERO"}),
        (
            "v3_register.v",
            {"HDLX-V2V-EDGE-META", "HDLX-V2V-INITIAL-STATE"},
        ),
        ("v3_resets.v", {"HDLX-V2V-EDGE-META"}),
        (
            "v3_procedural_x.v",
            {"HDLX-V2V-TIME-ZERO", "HDLX-V2V-META-VALUE"},
        ),
        ("v3_unsized_arithmetic.v", {"HDLX-V2V-UNSIZED-SIZING"}),
    ],
)
def test_supported_but_not_bit_exact_boundaries_are_reported(
    fixture_name: str,
    expected_codes: set[str],
) -> None:
    result = convert_file(
        FIXTURES / fixture_name,
        source_language="verilog",
        target_language="vhdl",
        options=ConversionOptions(strict=True),
    )

    matching = [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code in expected_codes
    ]
    assert {diagnostic.code for diagnostic in matching} == expected_codes
    assert all(
        diagnostic.severity is DiagnosticSeverity.WARNING
        for diagnostic in matching
    )
