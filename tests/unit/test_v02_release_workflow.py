import re
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_v02_release_workflow_requires_all_freeze_systemverilog_evidence() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-gates.yml").read_text(
        encoding="utf-8"
    )

    assert "tests/equivalence -m systemverilog_equivalence" in workflow
    assert (
        "Slang integration: EXECUTED 41/41 "
        "(passed=41, failed=0, skipped=0, pyslang=11.0.0)"
    ) in workflow
    assert (
        "Slang integration: EXECUTED 8/8 "
        "(passed=8, failed=0, skipped=0, pyslang=11.0.0)"
    ) in workflow
    assert (
        "SystemVerilog equivalence: EXECUTED 8/8 "
        "(passed=8, failed=0, skipped=0, missing=none)"
    ) in workflow


def test_release_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-gates.yml").read_text(
        encoding="utf-8"
    )
    action_uses = re.findall(r"^\s*uses:\s*[^\s@]+@([^\s#]+)", workflow, re.MULTILINE)

    assert action_uses
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for revision in action_uses)
