"""Versioned scope corrections; saving never starts model execution."""

import time
from copy import deepcopy
from pathlib import Path

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.review.review_questions import locked


def state(project):
    path = Path(project) / "scope_reviews.json"
    return read_json(path) if path.exists() else {"revision": 0, "items": {}, "history": []}


def reviewed(project, key, inputs):
    row = state(project)["items"].get(key)
    if row and row["input_hash"] == fingerprint(inputs):
        return deepcopy(row["value"])
    return None


def revision(project, key):
    return state(project)["items"].get(key, {}).get("version")


def view(project):
    project = Path(project)
    saved = state(project)
    taskfile = project / "run/workflow_tasks.json"
    tasks = read_json(taskfile)["tasks"] if taskfile.exists() else {}
    rows = []
    for key, t in tasks.items():
        if t.get("stage") != "exception-scope" or t.get("status") != "passed":
            continue
        envelope = read_json(project / "run" / t["output_file"])
        override = saved["items"].get(key)
        rows.append(
            {
                "task_key": key,
                "case_id": t.get("case"),
                "channel": "E" if key.endswith("existing-scope") else "GT",
                "value": override["value"]
                if override and override["input_hash"] == envelope["metadata"]["input_hash"]
                else envelope["payload"],
                "expected_version": fingerprint(
                    [envelope["metadata"]["input_hash"], envelope["payload"], override]
                ),
                "input_hash": envelope["metadata"]["input_hash"],
                "pending_rerun": bool(override and envelope["payload"] != override["value"]),
            }
        )
    from scene_completion.analysis.result_views import ResultView

    positive = ResultView(project)
    return {
        "revision": saved["revision"],
        "records": rows,
        "history": saved["history"],
        "entities": [
            {"id": e["id"], "name": e["name"]}
            for e in positive.payload("business-entities").get("entities", [])
        ],
        "cases": [
            {"id": g["id"], "name": g.get("name", g["id"])}
            for g in positive.payload("use-case-align").get("groups", [])
        ],
    }


@locked
def save(project, body):
    key = body["task_key"]
    current = next((r for r in view(project)["records"] if r["task_key"] == key), None)
    if not current or body.get("expected_version") != current["expected_version"]:
        raise ValueError("粒度判定来源或审核版本已改变，请刷新后重试")
    from scene_completion.domain.contracts import validate

    value = {"units": body["units"]}
    validate("exception-scope", value)
    from scene_completion.analysis.result_views import ResultView

    positive = ResultView(Path(project))
    entity_ids = {e["id"] for e in positive.payload("business-entities").get("entities", [])}
    case_ids = {g["id"] for g in positive.payload("use-case-align").get("groups", [])}
    for u in value["units"]:
        if (
            not u["trigger"].strip()
            or not set(u["entity_ids"]) <= entity_ids
            or not set(u["related_cases"]) <= case_ids
        ):
            raise ValueError("归属须使用已有业务实体/用例；独立触发不能为空")
    originals = {u["source_id"] for u in current["value"]["units"]}
    if {u["source_id"] for u in value["units"]} != originals:
        raise ValueError("不能删除来源记录；不能判定的保留pending")
    for u in value["units"]:
        if u["scope"] == "global" and (
            not u["global_kind"] or not u["entity_ids"] or not u["related_cases"]
        ):
            raise ValueError("全局归属须填写类别、实体和用例；资料不足请保留待确认")
        if u["scope"] != "global" and u["global_kind"] is not None:
            raise ValueError("非全局项不能有全局类别")
    saved = state(project)
    saved["revision"] += 1
    row = {
        "task_key": key,
        "input_hash": current["input_hash"],
        "value": value,
        "reviewer": body.get("reviewer", "业务审核"),
        "reason": body.get("reason", ""),
        "at": time.time(),
        "version": saved["revision"],
    }
    if body.get("dry_run"):
        return {
            "valid": True,
            "saved": False,
            "task_key": key,
            "input_hash": current["input_hash"],
            "recompute_started": False,
        }
    saved["items"][key] = row
    saved["history"].append(deepcopy(row))
    write_json(Path(project) / "scope_reviews.json", saved)
    from scene_completion.infrastructure.execution_events import EventStore

    EventStore(Path(project) / "run").append(
        "scope_review_saved", task_key=key, revision=row["version"], recompute_started=False
    )
    graph = Path(project) / "run/workflow_graph.json"
    nodes = read_json(graph).get("nodes", []) if graph.exists() else []
    affected = {key}
    while True:
        added = {n["id"] for n in nodes if set(n.get("deps", [])) & affected} - affected
        if not added:
            break
        affected |= added
    return {
        "saved": True,
        "revision": saved["revision"],
        "affected_nodes": sorted(affected),
        "recompute_started": False,
    }
