"""Reuse verified model responses across tool-only display/identity changes.

Only the current protocol's responses qualify. A seed is rebound to the same independent
task input projection, Skill and model owner, then validated again by the caller.
"""

from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint, read_json

DERIVED = {
    "element_id",
    "binding_id",
    "case_id",
    "direction",
    "identification",
    "policy_id",
    "classification_origin",
    "element_origin",
    "caller",
    "callee",
    "status",
    "status_reason",
    "inheritance_paths",
    "service",
    "functional_types",
    "technologies",
}


def identity(task, inputs, skill, output, model, endpoint, guidance):
    from scene_completion.workflow.task_context import semantic_view

    contract = deepcopy(output)
    if task in {"concern-match", "existing-concerns", "test-concerns"}:
        properties = contract["properties"]["matches"]["items"]["properties"]
        for key in DERIVED:
            properties.pop(key, None)
        contract["properties"].pop("excluded", None)
    if task in {"exception-generate", "existing-extract", "test-ground-truth"}:
        properties = contract["properties"]["scenarios"]["items"]["properties"]
        for key in ("concern_binding_ids", "element_anchors", "matching_version"):
            properties.pop(key, None)
    if "excluded" in contract.get("properties", {}):
        for key in ("interaction_id", "object", "concern_key"):
            contract["properties"]["excluded"]["items"]["properties"].pop(key, None)
    return fingerprint(
        [task, semantic_view(task, inputs), skill, contract, model, endpoint, guidance]
    )


def index(root, model, endpoint, conversations):
    from scene_completion.domain.contracts import PROTOCOL

    eligible = {
        "concern-match",
        "existing-concerns",
        "test-concerns",
        "existing-extract",
        "test-ground-truth",
    }
    seeds = {}
    for path in (root / "packets").glob("*.json"):
        p = read_json(path)
        task = p.get("task")
        if task not in eligible or p.get("protocol") != PROTOCOL:
            continue
        key = p.get("node_key", task)
        guidance = conversations.revision(key)
        # Historical raw-cache identity predates presentation-independent keys.
        old = fingerprint(
            {
                "task": task,
                "input": p["input"],
                "skill": p.get("skill_text"),
                "schema": p["output_schema"],
                "endpoint": endpoint,
                "model": model,
                "guidance": guidance,
            }
        )
        file = root / "semantic_responses" / (old + ".json")
        if not file.exists():
            continue
        try:
            normalized = identity(
                task, p["input"], p.get("skill_text"), p["output_schema"], model, endpoint, guidance
            )
        except (KeyError, ValueError, TypeError):
            continue
        seeds[normalized] = file
    return seeds


def replay(root, cached, task, inputs):
    """Reprocess raw submitted observations, never a lossy derived empty set.

    Older normalized caches may have discarded invalid object observations into
    pending. They cannot establish that a new locator has rechecked those facts.
    """
    import re
    from pathlib import Path

    evidence = cached.get("proof") or {}
    for _ in range(8):
        if isinstance(evidence.get("execution_model_evidence"), dict):
            evidence = evidence["execution_model_evidence"]
            break
        evidence = evidence.get("original_execution") or {}
    raw_file = evidence.get("raw_payload_file")
    if raw_file:
        path = (Path(root) / raw_file).resolve()
        if not path.is_relative_to(Path(root).resolve()) or not path.is_file():
            raise ValueError("raw semantic evidence is absent or outside run")
        original = read_json(path)
        if original.get("task") != task or fingerprint(original.get("payload")) != evidence.get(
            "raw_payload_hash"
        ):
            raise ValueError("raw semantic evidence identity changed")
        value = deepcopy(original["payload"])
    else:
        value = deepcopy(cached["payload"])
        if task in {"concern-match", "existing-concerns", "test-concerns"} and any(
            re.search(
                r"四要素位置|具体对象不唯一|可用性异常的对象|没有绑定到本片|已确认的原分支和交互绑定",
                r.get("reason", ""),
            )
            for r in value.get("pending", [])
        ):
            raise ValueError(
                "lossy normalized cache requires original model observations or re-identification"
            )
    if task in {"concern-match", "existing-concerns", "test-concerns"}:
        from scene_completion.analysis.concern_alignment import recognize

        value = recognize(inputs, value, inverse=task != "concern-match")
    return value
