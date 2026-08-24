import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).parents[2]


def test_030rc1_candidate_versions_and_sbom_are_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == "0.3.0rc1"
    assert project["optional-dependencies"]["systemverilog"] == ["pyslang==11.0.0"]
    assert project["optional-dependencies"]["verilog"] == ["pyslang==11.0.0"]

    required_text = {
        "README.md": ("0.3.0-rc1", "hdl_x-0.3.0rc1-py3-none-any.whl"),
        "V0_3_VERILOG_TO_VHDL_MVP.md": ("0.3.0-rc1", "7/7"),
        "DEVELOPMENT_LOG.md": ("0.3.0-rc1 Candidate",),
        "THIRD_PARTY_NOTICES": ("HDL-X 0.3.0-rc1 Third-Party Notices",),
    }
    for relative_path, tokens in required_text.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for token in tokens:
            assert token in text, f"{relative_path} 缺少 {token}"

    sbom = json.loads((ROOT / "SBOM.cdx.json").read_text(encoding="utf-8"))
    assert sbom["metadata"]["component"]["version"] == "0.3.0rc1"
    properties = {
        property_["name"]: property_["value"]
        for property_ in sbom["metadata"]["properties"]
    }
    assert properties["hdl-x:active-extras"] == "systemverilog,verilog"
    components = {component["name"].casefold(): component for component in sbom["components"]}
    assert components["pyslang"]["version"] == "11.0.0"
    dependencies = {entry["ref"]: entry["dependsOn"] for entry in sbom["dependencies"]}
    assert "pkg:pypi/pyslang@11.0.0" in dependencies["pkg:pypi/hdl-x@0.3.0rc1"]