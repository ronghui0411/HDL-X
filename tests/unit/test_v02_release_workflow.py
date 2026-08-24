import re
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_release_workflow_requires_v02_and_v03_semantic_evidence() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-gates.yml").read_text(
        encoding="utf-8"
    )

    assert "tests/equivalence -m systemverilog_equivalence" in workflow
    assert (
        "Slang integration: EXECUTED 96/96 "
        "(passed=96, failed=0, skipped=0, pyslang=11.0.0)"
    ) in workflow
    assert (
        "Slang integration: EXECUTED 8/8 "
        "(passed=8, failed=0, skipped=0, pyslang=11.0.0)"
    ) in workflow
    assert (
        "SystemVerilog equivalence: EXECUTED 8/8 "
        "(passed=8, failed=0, skipped=0, missing=none)"
    ) in workflow
    assert "test_verilog_to_vhdl_differential.py" in workflow
    assert "--require-verilog-to-vhdl-equivalence" in workflow
    assert (
        "Verilog to VHDL equivalence: EXECUTED 7/7 "
        "(passed=7, failed=0, skipped=0, missing=none)"
    ) in workflow
    assert (
        "GHDL integration: EXECUTED 146/146 "
        "(passed=146, failed=0, skipped=0, pyGHDL=6.0.0)"
    ) in workflow
    assert (
        "Slang integration: EXECUTED 111/111 "
        "(passed=111, failed=0, skipped=0, pyslang=11.0.0)"
    ) in workflow
    assert "^403 passed in [0-9.]+s$" in workflow
    assert "python -m compileall -q src tests scripts packaging/windows" in workflow
    assert "git diff --exit-code v0.2.0 -- tests/golden" in workflow


def test_release_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-gates.yml").read_text(
        encoding="utf-8"
    )
    action_uses = re.findall(r"^\s*uses:\s*[^\s@]+@([^\s#]+)", workflow, re.MULTILINE)

    assert action_uses
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for revision in action_uses)
