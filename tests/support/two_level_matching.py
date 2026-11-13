"""Offline test support extracted without changing builder behavior."""

from scene_completion.analysis.matching.concern_alignment import (
    recognize,
)
from tests.support.workflow import (
    R,
)
from tests.support.workflow import (
    memory_inputs as _memory_inputs,
)


def memory_inputs():
    x = _memory_inputs()
    x["enriched-interactions"] = {"interactions": x["sr-ssd"]["interactions"]}
    x["normal-rules"] = {"rules": [], "pending": []}
    return x


def raw(key="api.data.range", field="pageSize", target="data", **extra):
    return {
        "interaction_id": "req",
        "target": target,
        "object": field,
        "concern_key": key,
        "basis": "本交互的明确规则",
        "concrete_rule": "1≤pageSize≤100",
        "source_refs": R,
        "data_location": "query" if target == "data" else None,
        **extra,
    }


def recognized(x, rows):
    return recognize(x, {"matches": rows, "pending": []})


__all__ = ["memory_inputs", "raw", "recognized"]
