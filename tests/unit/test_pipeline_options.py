import pytest

from hdl_x.pipeline import ConversionOptions


def test_conversion_mode_is_mutually_exclusive() -> None:
    assert ConversionOptions(strict=True).strict
    assert ConversionOptions(strict=False, best_effort=True).best_effort

    with pytest.raises(ValueError, match="必须且只能"):
        ConversionOptions(strict=True, best_effort=True)
    with pytest.raises(ValueError, match="必须且只能"):
        ConversionOptions(strict=False, best_effort=False)
