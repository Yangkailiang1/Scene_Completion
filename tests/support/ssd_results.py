"""Shared SSD result fixtures."""

from copy import deepcopy

from scene_completion.domain.coverage import POLICY


def bundle():
    value = {
        "version": "ssd-case-v1",
        "case": {"id": "case", "name": "case"},
        "steps": [
            {
                "id": "step",
                "order": 1,
                "kind": "interaction",
                "direction": "request",
                "layer": "SR",
                "sender": {"id": "a", "name": "a", "type": "human"},
                "receiver": {"id": "b", "name": "b", "type": "service"},
                "operation": {"name": "call", "kinds": []},
                "data": [],
                "api_id": None,
                "entity_ids": [],
                "source_refs": [],
            }
        ],
        "channels": {},
        "documents": [],
        "decisions": [],
        "pending": [],
        "apis": [{"id": "positive-api", "fields": []}],
        "entities": [{"id": "positive-entity", "attributes": []}],
    }
    for channel, condition in (("G", "身份认证不满足"), ("E", "无有效凭证"), ("GT", "凭证已过期")):
        concern = {
            "id": channel + "-c",
            "step_id": "step",
            "target": "sender",
            "key": "human.authentication",
            "label": "身份认证",
            "condition": condition,
            "field_id": None,
            "status": "active",
            "source_refs": [],
        }
        scenario = {
            "id": channel + "-s",
            "step_id": "step",
            "target": "sender",
            "key": "human.authentication",
            "field_id": None,
            "concern_ids": [channel + "-c"],
            "condition": condition,
            "expected": "",
            "status": "active",
            "source_refs": [],
        }
        value["channels"][channel] = {"concerns": [concern], "scenarios": [scenario], "pending": []}
        if channel != "G":
            value["channels"][channel]["pending"] = [
                {
                    "id": channel + "-pending",
                    "condition": channel + "-private-source",
                    "status": "pending",
                    "needs_semantic": True,
                    "source_refs": [],
                }
            ]
    return value


sample = bundle


def coverage_bundle():
    b = sample()
    b["channels"]["E"] = {"concerns": [], "scenarios": [], "pending": []}
    for ch in b["channels"].values():
        ch["pending"] = []
    b["coverage_policy"] = POLICY
    first = b["channels"]["G"]["scenarios"][0]
    extra = {**deepcopy(first), "id": "G-second", "condition": "凭证为空"}
    missing = {**deepcopy(first), "id": "G-third", "condition": "凭证格式错误"}
    b["channels"]["G"]["scenarios"] += [extra, missing]
    b["decisions"] = [
        {
            "id": "m" + str(n),
            "pair": "GT_G",
            "left_id": "GT-s",
            "right_id": r["id"],
            "level": "scenario",
            "status": "partial" if n < 2 else "none",
            "origin": "manual",
            "reason": "审核对应",
        }
        for n, r in enumerate(b["channels"]["G"]["scenarios"])
    ]
    return b
