"""Offline test support extracted without changing builder behavior."""

from scene_completion.infrastructure.storage import fingerprint, write_json
from scene_completion.review.decisions.project_review import (
    registry_view,
)


def custom_definition():
    return {
        "key": "custom.query_quality",
        "label": "自定义查询质量",
        "description": "本项目明确的查询质量要求，必须有正向业务依据。",
        "layer": "functional",
        "group": "query_retrieval",
        "parents": [],
        "kind": "check",
        "guard": "business",
        "failure_family": "custom.query_quality",
        "operation_kinds": ["read"],
        "technology": None,
        "enabled": True,
    }


def project_registry_hash(p):
    return registry_view(p)["current_hash"]


def pending_fixture(project):
    root = project / "run"
    ref = [{"source_id": "doc", "line_start": 2, "line_end": 2, "quote": "明确的原文依据"}]
    state = {}
    nodes = []
    for key, case, stage in [
        ("C:normal-rules--part-a", "C", "normal-rules"),
        ("C:existing-bind--part-b", "C", "existing-bind"),
    ]:
        value = (
            {"pending": [{"interaction_id": "i", "reason": "缺少具体阈值", "source_refs": ref}]}
            if stage == "normal-rules"
            else {
                "bindings": [
                    {
                        "branch_id": "B",
                        "interaction_id": "j",
                        "status": "pending",
                        "basis": "已有异常尚未确定对应步骤",
                        "source_refs": ref,
                    }
                ]
            }
        )
        file = "task_outputs/" + fingerprint(key) + ".json"
        v = {"task": stage, "payload": value}
        write_json(root / file, v)
        state[key] = {
            "status": "passed",
            "case": case,
            "stage": stage,
            "output_file": file,
            "output_hash": fingerprint(v),
        }
        nodes.append({"id": key})
    write_json(root / "workflow_tasks.json", {"tasks": state})
    write_json(root / "workflow_graph.json", {"nodes": nodes})
    return state


__all__ = ["custom_definition", "pending_fixture", "project_registry_hash"]
