"""从隔离 wheelhouse 生成确定性的 CycloneDX 运行时 SBOM。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from email.parser import Parser
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_LICENSE_OVERRIDES = {
    "colorama": "BSD-3-Clause",
    "jinja2": "BSD-3-Clause",
    "markdown-it-py": "MIT",
    "mdurl": "MIT",
    "shellingham": "ISC",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata(wheel: Path) -> Any:
    with ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        return Parser().parsestr(archive.read(metadata_name).decode("utf-8", "replace"))


def _license_expression(metadata: Any) -> str:
    expression = metadata.get("License-Expression")
    if expression:
        return expression
    name = canonicalize_name(metadata["Name"])
    if name in _LICENSE_OVERRIDES:
        return _LICENSE_OVERRIDES[name]
    license_value = metadata.get("License", "").strip()
    if license_value and "\n" not in license_value:
        return "ISC" if license_value == "ISC License" else license_value
    classifiers = metadata.get_all("Classifier", [])
    classifier_map = {
        "License :: OSI Approved :: BSD License": "BSD-3-Clause",
        "License :: OSI Approved :: MIT License": "MIT",
    }
    for classifier in classifiers:
        if classifier in classifier_map:
            return classifier_map[classifier]
    return "NOASSERTION"


def _external_references(metadata: Any) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in metadata.get_all("Project-URL", []):
        _, separator, url = entry.partition(",")
        if separator and url.strip() not in seen:
            cleaned = url.strip()
            seen.add(cleaned)
            references.append({"type": "website", "url": cleaned})
    home_page = metadata.get("Home-page", "").strip()
    if home_page and home_page not in seen:
        references.append({"type": "website", "url": home_page})
    return references


def _component(wheel: Path, metadata: Any) -> dict[str, Any]:
    name = metadata["Name"]
    version = metadata["Version"]
    normalized = canonicalize_name(name)
    component: dict[str, Any] = {
        "type": "application" if normalized == "hdl-x" else "library",
        "bom-ref": f"pkg:pypi/{normalized}@{version}",
        "name": name,
        "version": version,
        "hashes": [{"alg": "SHA-256", "content": _sha256(wheel)}],
        "licenses": [{"expression": _license_expression(metadata)}],
        "purl": f"pkg:pypi/{normalized}@{version}",
        "properties": [
            {"name": "hdl-x:wheel-file", "value": wheel.name},
            {"name": "hdl-x:distribution-boundary", "value": "separate-wheel"},
        ],
    }
    references = _external_references(metadata)
    if references:
        component["externalReferences"] = references
    return component


def _vendored_click_component(typer_wheel: Path, typer_version: str) -> dict[str, Any]:
    digest = hashlib.sha256()
    with ZipFile(typer_wheel) as archive:
        members = sorted(
            name
            for name in archive.namelist()
            if name.startswith("typer/_click/") and not name.endswith("/")
        )
        if not members:
            raise RuntimeError("Typer wheel 中没有预期的 vendored Click 源码")
        for name in members:
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(archive.read(name))
            digest.update(b"\0")
    reference = f"urn:hdl-x:vendored:click:typer-{typer_version}"
    return {
        "type": "library",
        "bom-ref": reference,
        "name": "Click",
        "version": f"vendored in Typer {typer_version}",
        "hashes": [{"alg": "SHA-256", "content": digest.hexdigest()}],
        "licenses": [{"expression": "BSD-3-Clause"}],
        "externalReferences": [
            {"type": "website", "url": "https://github.com/pallets/click"}
        ],
        "properties": [
            {"name": "hdl-x:embedded-in", "value": f"typer {typer_version}"},
            {"name": "hdl-x:distribution-boundary", "value": "vendored-dependency-code"},
        ],
    }


def _dependency_refs(metadata: Any, available: dict[str, str]) -> list[str]:
    references: set[str] = set()
    for raw_requirement in metadata.get_all("Requires-Dist", []):
        try:
            requirement = Requirement(raw_requirement)
        except Exception:
            continue
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
            continue
        normalized = canonicalize_name(requirement.name)
        if normalized in available:
            references.add(available[normalized])
    return sorted(references)


def generate_sbom(wheelhouse: Path, output: Path, timestamp: str) -> None:
    wheels = sorted(wheelhouse.glob("*.whl"))
    if not wheels:
        raise RuntimeError(f"wheelhouse 中没有 wheel: {wheelhouse}")

    records = [(wheel, _metadata(wheel)) for wheel in wheels]
    components = [_component(wheel, metadata) for wheel, metadata in records]
    typer_record = next(
        (
            (wheel, metadata)
            for wheel, metadata in records
            if canonicalize_name(metadata["Name"]) == "typer"
        ),
        None,
    )
    if typer_record is not None:
        components.append(_vendored_click_component(typer_record[0], typer_record[1]["Version"]))
    by_name = {canonicalize_name(component["name"]): component for component in components}
    project = by_name.get("hdl-x")
    if project is None:
        raise RuntimeError("wheelhouse 中没有 HDL-X wheel")

    available = {name: component["bom-ref"] for name, component in by_name.items()}
    vendored_click = next(
        (component for component in components if component["name"] == "Click"), None
    )
    dependencies = []
    for _, metadata in records:
        reference = available[canonicalize_name(metadata["Name"])]
        dependency_references = _dependency_refs(metadata, available)
        if canonicalize_name(metadata["Name"]) == "typer" and vendored_click is not None:
            dependency_references.append(vendored_click["bom-ref"])
        dependencies.append({"ref": reference, "dependsOn": sorted(dependency_references)})
    if vendored_click is not None:
        dependencies.append({"ref": vendored_click["bom-ref"], "dependsOn": []})

    fingerprints = "\n".join(
        f"{component['bom-ref']}:{component['hashes'][0]['content']}"
        for component in sorted(components, key=lambda item: item["bom-ref"])
    )
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/ronghui0411/HDL-X\n{fingerprints}")
    project["properties"].extend(
        [
            {"name": "hdl-x:release", "value": "v0.1.1"},
            {"name": "hdl-x:contains-pyghdl", "value": "false"},
            {"name": "hdl-x:sbom-scope", "value": "Windows CPython 3.13 release wheelhouse"},
        ]
    )

    document = {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "component": project,
            "properties": [
                {"name": "hdl-x:pyghdl-bundled-in-project-wheel", "value": "false"},
                {"name": "hdl-x:pyinstaller-exe-released", "value": "false"},
            ],
        },
        "components": sorted(
            (component for component in components if component is not project),
            key=lambda item: item["bom-ref"],
        ),
        "dependencies": sorted(dependencies, key=lambda item: item["ref"]),
    }
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("SBOM.cdx.json"))
    parser.add_argument("--timestamp", required=True)
    arguments = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", arguments.timestamp):
        raise SystemExit("--timestamp 必须使用 UTC YYYY-MM-DDTHH:MM:SSZ 格式")
    generate_sbom(arguments.wheelhouse.resolve(), arguments.output.resolve(), arguments.timestamp)


if __name__ == "__main__":
    main()
