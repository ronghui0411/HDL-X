from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_pyslang_references_are_confined_before_canonical_ir() -> None:
    paths = [
        ROOT / "src" / "hdl_x" / "ir",
        ROOT / "src" / "hdl_x" / "transformer",
        ROOT / "src" / "hdl_x" / "generator",
    ]
    files = [ROOT / "src" / "hdl_x" / "pipeline.py"]
    for path in paths:
        files.extend(path.rglob("*.py"))

    for source in files:
        assert "pyslang" not in source.read_text(encoding="utf-8").casefold(), source


def test_verilog_renderer_does_not_repeat_storage_or_assignment_semantics() -> None:
    renderer = (ROOT / "src" / "hdl_x" / "generator" / "verilog.py").read_text(
        encoding="utf-8"
    )

    for forbidden in ("DriverKind", "driver_kind", "AssignmentKind", "assignment_kind"):
        assert forbidden not in renderer


def test_jinja_templates_do_not_read_frontend_or_canonical_semantic_fields() -> None:
    templates = ROOT / "src" / "hdl_x" / "templates"
    forbidden = ("pyslang", "pyghdl", "driver_kind", "assignment_kind", "four_state")

    for template in templates.rglob("*.j2"):
        text = template.read_text(encoding="utf-8").casefold()
        for token in forbidden:
            assert token not in text, f"{template}: {token}"
