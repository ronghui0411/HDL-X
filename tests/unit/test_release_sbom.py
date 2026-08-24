from email.parser import Parser

from scripts.generate_cyclonedx_sbom import _dependency_refs


def test_sbom_dependency_resolution_includes_each_active_slang_extra() -> None:
    metadata = Parser().parsestr(
        'Name: hdl-x\n'
        'Requires-Dist: pyslang==11.0.0; extra == "systemverilog"\n'
        'Requires-Dist: pyslang==11.0.0; extra == "verilog"\n'
    )
    available = {"pyslang": "pkg:pypi/pyslang@11.0.0"}

    assert _dependency_refs(metadata, available, ()) == []
    for extras in (("systemverilog",), ("verilog",), ("systemverilog", "verilog")):
        assert _dependency_refs(metadata, available, extras) == [
            "pkg:pypi/pyslang@11.0.0"
        ]