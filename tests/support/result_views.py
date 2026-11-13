"""Offline test support extracted without changing builder behavior."""

from scene_completion.infrastructure.storage import fingerprint, write_json


def fixture(project):
    root = project / "run"
    state = {}

    def put(key, stage, payload, status="passed"):
        file = "task_outputs/" + fingerprint(key) + ".json"
        write_json(root / file, {"payload": payload})
        state[key] = {
            "stage": stage,
            "case": key.split(":")[0] if ":" in key else "shared",
            "status": status,
            "output_file": file,
        }

    interaction = {
        "id": "i1",
        "sequence": 1,
        "sender": {"name": "开发者"},
        "receiver": {"name": "平台"},
        "operation": {"name": "查询"},
        "data": {"sequence": []},
    }
    put("rr-use-cases", "use-case-extract", {"cases": [{"id": "RR1", "name": "查询记忆库"}]})
    put(
        "use-case-align",
        "use-case-align",
        {"groups": [{"id": "C", "rr_ids": ["RR1"], "sr_ids": []}]},
    )
    put("C:enriched-view", "enriched-view", {"interactions": [interaction]})

    def s(id, iid="i1"):
        return {"id": id, "interaction_id": iid, "concern_key": "key", "cause": id}

    put("C:exception-generate", "exception-generate", {"scenarios": [s("early")]})
    put("C:missing-report", "missing-report", {"G": [s("g")], "E": [s("e")], "M": [s("g")]})
    put(
        "C:exception-evaluation",
        "exception-evaluation",
        {
            "G": [s("g")],
            "E": [s("e")],
            "GT": [s("gt"), s("unbound", "unknown")],
            "metrics": {"generation_validity": {"value": 100}},
        },
    )
    put("C:fused-ssd", "fused-ssd", {"interactions": [interaction]})
    put("C:fused-ssd--part-old", "fused-ssd", {"interactions": []})
    put("components", "components", {})
    put("C:failed", "rr-ssd", {}, "failed")
    write_json(root / "workflow_tasks.json", {"tasks": state})
    write_json(
        root / "workflow_graph.json", {"nodes": [{"id": k} for k in state if "--part-" not in k]}
    )
    write_json(
        root / "run_manifest.json",
        {"complete": True, "registry_hash": "frozen", "analysis_by_case": {"C": True}},
    )
    write_json(
        root / "registry_used/frozen.json", {"definitions": {"key": {"label": "执行时定义"}}}
    )
    from scene_completion.domain.concern_registry import default_registry

    write_json(root / "registry_override.json", default_registry())
    folder = root / "artifacts" / fingerprint("C")[:12]
    folder.mkdir(parents=True)
    (folder / "fused-ssd.svg").write_text("<svg/>")
    (folder / "fused-ssd--part-old.svg").write_text("<svg/>")
    (folder / "failed.svg").write_text("<svg/>")
    shared = root / "artifacts/shared"
    shared.mkdir()
    (shared / "components.svg").write_text("<svg/>")


__all__ = ["fixture"]
