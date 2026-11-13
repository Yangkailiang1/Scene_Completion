"""Support for the current workflow."""

from copy import deepcopy

from scene_completion.analysis.interactions.interaction_enrichment import (
    enrich,
)
from scene_completion.domain.contracts import (
    PROTOCOL,
    TASKS,
)
from scene_completion.infrastructure.paths import PROMPTS_ROOT, SKILLS_ROOT
from scene_completion.infrastructure.storage import fingerprint


def canonical_enrich(d):
    from scene_completion.analysis.interactions.interaction_identity import canonical_fused

    raw = {
        "interactions": d["rr-ssd"]["interactions"] + d["sr-ssd"]["interactions"],
        "rr_sr_links": d["interaction-align"]["links"],
    }
    canonical = canonical_fused(raw, d)
    material = deepcopy(d)
    for layer in ("RR", "SR"):
        material[layer.lower() + "-ssd"] = {
            "interactions": [i for i in canonical["interactions"] if i["layer"] == layer]
        }
    value = enrich(material, d["interaction-align"])
    value["pending"] = [
        p
        for p in value["pending"]
        if p["interaction_id"] not in {a["source_id"] for a in canonical["aliases"]}
    ] + canonical["pending"]
    for i in value["interactions"]:
        if i["id"] in canonical["source_views"]:
            i["source_views"] = canonical["source_views"][i["id"]]
    return value


def payload(value):
    if value.get("protocol") != PROTOCOL:
        raise ValueError("legacy or unversioned task result cannot enter scene-workflow-v5")
    return value["payload"]


def safe_case(case):
    return fingerprint(case)[:12]


def analysis_settings(value):
    """Ranking-only edits must not invalidate identification or GT model work."""
    from copy import deepcopy

    from scene_completion.analysis.recommendation.scenario_patterns import normalize_settings

    v = deepcopy(value)
    for k, default in [("top_k", 10), ("risk_weight", 0.7), ("history_weight", 0.3)]:
        v[k] = default
    return normalize_settings(v)


def skill_path(task):
    tool_skills = {
        "source-index": "scene-context-index",
        "ssd-context": "scene-context-index",
        "interaction-enrich": "scene-interaction-attributes",
        "interaction-align": "scene-ssd-structure",
    }
    if task in tool_skills:
        return SKILLS_ROOT / tool_skills[task] / "SKILL.md"
    if task in TASKS:
        return SKILLS_ROOT / TASKS[task][0] / "SKILL.md"
    internal = {
        "test-operation-project",
        "test-ground-truth",
        "interaction-align",
        "semantic-compare",
        "api-index",
    }
    return PROMPTS_ROOT / ((task if task in internal else "tool-task") + ".md")
