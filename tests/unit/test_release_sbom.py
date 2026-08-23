from email.parser import Parser

from scripts.generate_cyclonedx_sbom import _dependency_refs


def test_sbom_dependency_resolution_includes_the_active_systemverilog_extra() -> None:
    metadata = Parser().parsestr(
        'Name: hdl-x\nRequires-Dist: pyslang==11.0.0; extra == "systemverilog"\n'
    )
    available = {"pyslang": "pkg:pypi/pyslang@11.0.0"}

    assert _dependency_refs(metadata, available, ()) == []
    assert _dependency_refs(metadata, available, ("systemverilog",)) == [
        "pkg:pypi/pyslang@11.0.0"
    ]
