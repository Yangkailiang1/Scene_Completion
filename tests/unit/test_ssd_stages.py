"""The structured-input workflow stays readable: stages, tasks and docs agree.

These tests pin the contract that makes the flow understandable. They fail when
a stage is added, renamed or retargeted without updating the single stage table,
its semantic tasks or the generated document.
"""

import json
import subprocess
import sys
from pathlib import Path

from scene_completion.workflow.ssd_stages import (
    CASE_SEQUENCE,
    KIND_LABELS,
    MERGE_STAGE,
    STAGES,
    case_stages,
    describe,
    label,
)

ROOT = Path(__file__).resolve().parents[2]
SEMANTICS = ROOT / "src/scene_completion/workflow/task_semantics.json"


def test_case_sequence_is_the_registered_order():
    """Every case stage is declared, and the merge stage closes the sequence."""
    assert CASE_SEQUENCE == ("ssd-prepare", "ssd-resolve", "ssd-generate", "ssd-compare")
    assert MERGE_STAGE == "shared-services-merge"
    assert set(STAGES) == {*CASE_SEQUENCE, MERGE_STAGE}
    assert case_stages() == CASE_SEQUENCE


def test_every_stage_declares_a_kind_and_a_known_dependency():
    """A reader must be able to tell whether a stage spends model budget."""
    for name, stage in STAGES.items():
        assert stage.kind in KIND_LABELS, name
        assert stage.label, name
        assert stage.doc.strip(), name
        assert stage.reads and stage.writes, name
        for dependency in stage.depends_on:
            assert dependency in STAGES, (name, dependency)


def test_stage_chain_is_linear_and_acyclic():
    """The declared dependencies must describe the documented order exactly."""
    for previous, name in zip(CASE_SEQUENCE, CASE_SEQUENCE[1:]):
        assert describe(name).depends_on == (previous,)
    assert describe("ssd-prepare").depends_on == ()
    assert describe(MERGE_STAGE).depends_on == ("ssd-compare",)


def test_semantic_tasks_exist_in_the_semantic_version_table():
    """Cache identity depends on these names; an unknown task silently re-hashes."""
    versions = json.loads(SEMANTICS.read_text(encoding="utf8"))["tasks"]
    for name, stage in STAGES.items():
        for task in stage.semantic_tasks:
            assert task in versions, f"{name} refers to unknown semantic task {task}"


def test_script_stages_declare_no_semantic_task():
    """Script stages must not claim a model task, and must be marked as scripts."""
    for name, stage in STAGES.items():
        if stage.kind == "script":
            assert stage.semantic_tasks == (), name
            assert "脚本" in stage.kind_label, name


def test_every_stage_states_whether_it_calls_a_model():
    """A reader must be able to tell model stages from script stages on the page."""
    for name, stage in STAGES.items():
        if stage.kind == "model" or stage.kind == "model+script":
            assert stage.semantic_tasks, name
        assert "模型" in stage.kind_label or "脚本" in stage.kind_label, name
    # Only the two pure script stages stay free of model calls.
    assert {n for n, s in STAGES.items() if s.kind == "script"} == {
        "ssd-prepare",
        "shared-services-merge",
    }


def test_labels_are_the_ones_the_scheduler_publishes():
    """The page label must come from here, not from a literal in the pipeline."""
    source = (ROOT / "src/scene_completion/workflow/ssd_pipeline.py").read_text(encoding="utf8")
    assert "display_label=stage_label(stage)" in source
    assert "display_label=stage_label(MERGE_STAGE)" in source
    for stage in STAGES.values():
        assert f'"{stage.label}"' not in source


def test_unknown_stage_degrades_to_its_raw_name():
    assert label("unregistered-stage") == "unregistered-stage"


def test_generated_document_matches_the_code():
    """The committed workflow document must not drift from ssd_stages.py."""
    result = subprocess.run(
        [sys.executable, "tools/render_workflow_doc.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
