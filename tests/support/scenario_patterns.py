"""Offline test support extracted without changing builder behavior."""

from copy import deepcopy

from scene_completion.analysis.recommendation.scenario_patterns import (
    applicability as applicability,
)
from scene_completion.analysis.recommendation.scenario_patterns import (
    generated,
)
from tests.support.workflow import R, memory_inputs


def positive():
    x = memory_inputs()
    x["enriched-interactions"] = {"interactions": deepcopy(x["sr-ssd"]["interactions"])}
    x["normal-rules"] = {"rules": [], "pending": []}
    from scene_completion.analysis.matching.concern_alignment import recognize

    x["concern-match"] = recognize(x, x["concern-match"])
    return x


def auth(
    x, key="human.authentication", condition="请求必须携带有效Token，校验Token有效期，过期不可使用"
):
    x["normal-rules"]["rules"].append(
        {
            "id": "nr-" + key,
            "interaction_id": "req",
            "owner_service": "Platform",
            "concern_key": key,
            "condition": condition,
            "violation": "SECRET_INVERSE_NOT_READ",
            "fields": [],
            "functional_kinds": ["read"],
            "resolution": "explicit",
            "pending_details": [],
            "source_refs": R,
        }
    )
    from scene_completion.analysis.matching.concern_alignment import recognize

    x["concern-match"] = recognize(
        x,
        {
            "matches": x["concern-match"]["matches"]
            + [
                {
                    "interaction_id": "req",
                    "target": "sender",
                    "object": "开发者",
                    "concern_key": key,
                    "basis": condition,
                    "concrete_rule": condition,
                    "source_refs": R,
                    "activation_evidence": [
                        {
                            "kind": "authentication"
                            if key.endswith("authentication")
                            else "authorization",
                            "value": True,
                            "condition": condition,
                            "unit": None,
                            "status": "explicit",
                            "source_refs": R,
                        }
                    ],
                }
            ]
        },
    )


def accepted(matrix):
    return generated(matrix)["scenarios"]


__all__ = ["accepted", "applicability", "auth", "positive"]
