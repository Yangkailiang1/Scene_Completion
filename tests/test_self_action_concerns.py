from copy import deepcopy

from scene_completion.analysis.concern_alignment import recognize
from tests.test_workflow import R, exchange


def packet():
    interaction = exchange()
    interaction["sender"]["name"] = interaction["receiver"]["name"] = "Platform"
    return {"enriched-interactions": {"interactions": [interaction]}}


def row(iid, target, key="service.base.availability", refs=None, direction=None):
    return {
        "interaction_id": iid,
        "target": target,
        "object": "Platform",
        "concern_key": key,
        "basis": "本次检查",
        "concrete_rule": "服务可用",
        "source_refs": deepcopy(refs or R),
    }


def test_self_sender_and_receiver_same_binding_merge_refs_once():
    x = packet()
    refs2 = [{**R[0], "source_id": "second"}]
    result = recognize(x, {"matches": [row("req", "sender"), row("req", "receiver", refs=refs2)]})
    matches = [m for m in result["matches"] if m["concern_key"] == "service.base.availability"]
    assert len(matches) == 1
    assert matches[0]["target"] == "receiver"
    assert {r["source_id"] for r in matches[0]["source_refs"]} == {"positive", "second"}


def test_self_normalization_does_not_merge_interactions_or_directions():
    x = packet()
    second = deepcopy(x["enriched-interactions"]["interactions"][0])
    second["id"] = "other"
    second["direction"] = "return"
    x["enriched-interactions"]["interactions"].append(second)
    result = recognize(x, {"matches": [row("req", "sender"), row("other", "sender")]})
    assert (
        len([m for m in result["matches"] if m["concern_key"] == "service.base.availability"]) == 2
    )
