"""Input file inventory, immutable versions and case lookup."""

from pathlib import Path
from threading import RLock

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.artifact_recognition import ROOTS as ROOTS
from scene_completion.inputs.artifact_recognition import TASKS as TASKS
from scene_completion.inputs.artifact_recognition import deterministic as deterministic
from scene_completion.inputs.artifact_recognition import role_hint as role_hint

LOCK = RLock()


def load(project):
    p = Path(project) / "imports/index.json"
    return (
        read_json(p)
        if p.exists()
        else {"version": "artifact-imports-v1", "revision": 0, "items": {}, "history": []}
    )


def save(project, index):
    index["revision"] += 1
    write_json(Path(project) / "imports/index.json", index)


def snapshot(project):
    from scene_completion.inputs.ordered_behaviors import existing_document

    project = Path(project)
    rows = [read_json(project / r["record"]) for r in load(project)["items"].values()]
    for row in rows:
        tree = row.get("colleague_product") or {}
        if tree.get("format") == "function_tree" and "interface_declarations" not in tree:
            import json

            from scene_completion.inputs.colleague_formats import function_interfaces

            original = project / row["original"]
            if original.is_file():
                tree.update(
                    function_interfaces(
                        json.loads(original.read_text(encoding="utf-8-sig")), row["id"], row["name"]
                    )
                )
        product = row.get("behavior_product") or {}
        if product.get("kind") != "ordered_scenario" or product.get("scenario_document"):
            continue
        doc = existing_document(
            product["raw"], row["id"], row["name"], product["layer"], product["case_name"]
        )
        if doc:
            product.update(
                scenario_document=doc, scenario_locations=[{"line": 1, "json_pointer": ""}]
            )
    return rows


def archive(project, row):
    write_json(
        Path(project)
        / "imports/versions"
        / row["id"]
        / (str(row["revision"]) + "-" + fingerprint(row)[:12] + ".json"),
        row,
    )


def resolve_case(project, hint):
    if not hint:
        return None
    root = Path(project) / "run"
    state = (
        read_json(root / "workflow_tasks.json").get("tasks", {})
        if (root / "workflow_tasks.json").exists()
        else {}
    )

    def get(key):
        r = state.get(key, {})
        return (
            read_json(root / r["output_file"])["payload"]
            if r.get("status") == "passed" and r.get("output_file")
            else {}
        )

    groups = get("use-case-align").get("groups", [])
    names = {
        c["id"]: c["name"]
        for k in ("rr-use-cases", "sr-use-cases")
        for c in get(k).get("cases", [])
    }
    hits = [
        g["id"]
        for g in groups
        if hint == g["id"]
        or hint in g["rr_ids"] + g["sr_ids"]
        or any(hint == names.get(i) for i in g["rr_ids"] + g["sr_ids"])
    ]
    return hits[0] if len(hits) == 1 else hint if not groups else None


def case_catalogue(project):
    root = Path(project) / "run"
    state = (
        read_json(root / "workflow_tasks.json").get("tasks", {})
        if (root / "workflow_tasks.json").exists()
        else {}
    )
    out = {"RR": [], "SR": [], "groups": []}
    for key, field, target in [
        ("rr-use-cases", "cases", "RR"),
        ("sr-use-cases", "cases", "SR"),
        ("use-case-align", "groups", "groups"),
    ]:
        record = state.get(key, {})
        if record.get("status") != "passed" or not record.get("output_file"):
            continue
        payload = read_json(root / record["output_file"])["payload"]
        keys = ("id", "name") if field == "cases" else ("id", "rr_ids", "sr_ids", "status")
        out[target] = [{k: v for k, v in item.items() if k in keys} for item in payload[field]]
    return out
