"""The core runs dynamically registered Python tasks without the Scene adapter."""

import subprocess
import sys
from pathlib import Path

from scene_completion.workflow_core import Scheduler, Task
from scene_completion.workflow_core.scheduler import partition_key


def test_deferred_parent_expands_under_same_key_and_resumes(tmp_path):
    dispatched = []
    key = partition_key("merge", "row-a")

    def run():
        scheduler = Scheduler(tmp_path)

        def run_source(_deps, _record):
            dispatched.append("source")
            return {"value": 3}

        def run_child(deps, _record):
            dispatched.append(key)
            return deps["source"]["value"] + 1

        def run_merge(deps, _record):
            dispatched.append("merge")
            return {"payload": deps[key]}

        scheduler.add(Task("source", "case", "source", execute=run_source))
        scheduler.add(Task("merge", "case", "merge", ("source",), deferred=True))

        def expand():
            scheduler.add(Task(key, "case", "row", ("source",), execute=run_child))
            scheduler.replace_deferred(
                "merge",
                lambda: scheduler.add(Task("merge", "case", "merge", (key,), execute=run_merge)),
            )

        scheduler.defer_expansion(("source",), expand)
        assert scheduler.run() == {"complete": True}
        records = scheduler.state["tasks"]
        assert scheduler.store.load_output(records["merge"]) == {"payload": 4}
        return records

    first = run()
    assert dispatched == ["source", key, "merge"]
    assert run() == first
    assert dispatched == ["source", key, "merge"]


def test_core_import_does_not_require_scene_or_site_packages():
    source = Path(__file__).resolve().parents[1] / "src"
    code = """
import sys
sys.path.insert(0, sys.argv[1])
from scene_completion.workflow_core import Scheduler
forbidden = (
    "scene_completion.analysis", "scene_completion.domain", "scene_completion.inputs",
    "scene_completion.models", "scene_completion.review", "scene_completion.workflow.",
)
assert not any(name.startswith(forbidden) for name in sys.modules)
"""
    subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code, str(source)], check=True)
