"""Offline test support extracted without changing builder behavior."""

from copy import deepcopy

from scene_completion.analysis.matching.concern_matching import concern_by_label
from scene_completion.analysis.scenarios.exception_generation import (
    data_exceptions as data_exceptions,
)
from scene_completion.domain.contracts import registry
from scene_completion.inputs.documents.source_documents import read_documents


def parameter(name, location="query", required=False, dtype=None, rules=(), default=None):
    return {
        "name": name,
        "location": location,
        "required": required,
        "data_type": dtype,
        "default": default,
        "constraints": [
            {
                "id": name + "-" + kind,
                "kind": kind,
                "value": v,
                "status": "explicit",
                "source_refs": R,
            }
            for kind, v in rules
        ],
        "source_refs": R,
    }


def exchange(case="CASE-A", sid="req", layer="SR", api="API-M-IF2"):
    return {
        "id": sid,
        "case_id": case,
        "sequence": 1,
        "parent_id": None,
        "layer": layer,
        "sender": {"name": "开发者", "position": "外部Actor（人类）", "source_refs": R},
        "receiver": {"name": "Platform", "position": "系统边界", "source_refs": R},
        "operation": {
            "name": "查询记忆库列表",
            "kinds": ["read"],
            "sequence": ["查询记忆库列表"],
            "optional": [],
            "source_refs": R,
        },
        "data": {"sequence": []},
        "direction": "request",
        "api_id": api,
        "source_refs": R,
    }


def memory_inputs():
    i = exchange()
    params = [
        parameter("x-wisecloud-service-id", "header", True),
        parameter("memoryInstanceID", "path", True),
        parameter("memoryType", rules=[("enum", ["PROFILE", "SEMANTIC"])]),
        parameter("page", dtype="integer", rules=[("minimum", 1)], default=1),
        parameter(
            "pageSize", dtype="integer", rules=[("minimum", 1), ("maximum", 100)], default=20
        ),
    ]
    api = {
        "id": "API-M-IF2",
        "name": "查询记忆库列表",
        "address": "/ms/v1/memory-instances/{memoryInstanceID}/mem-repos",
        "parameters": params,
        "source_refs": R,
    }
    matches = []
    labels = {
        "required": "数据完整性",
        "type": "数据类型",
        "enum": "数据范围",
        "minimum": "数据范围",
        "maximum": "数据范围",
    }
    for p in params:
        keys = set(
            [r["kind"] for r in p["constraints"]]
            + (["required"] if p["required"] else [])
            + (["type"] if p["data_type"] else [])
        )
        for k in keys:
            matches.append(
                {
                    "interaction_id": "req",
                    "target": "data",
                    "object": p["name"],
                    "concern_key": concern_by_label(labels[k]),
                    "basis": "known positive constraint",
                    "concrete_rule": k,
                    "source_refs": R,
                }
            )
    return {
        "components": {"components": [], "relations": []},
        "rr-ssd": {"interactions": []},
        "sr-ssd": {"interactions": [i]},
        "api-map": {"services": []},
        "api-parameters": {"apis": [api]},
        "concern-match": {"matches": matches, "pending": []},
        "enriched-interactions": {"interactions": []},
        "registry": registry(),
    }


def scenario(sid="one", cause="missing_required", status="framework_inferred"):
    return {
        "id": sid,
        "case_id": "CASE-A",
        "interaction_id": "req",
        "layer": "SR",
        "object": "instance",
        "operation": "read",
        "cause": cause,
        "conditions": ["id not found"],
        "concern_key": "service.query_retrieval.resource_existence",
        "field": None,
        "rule_id": None,
        "source_status": status,
        "derivation": "normal contract negation" if status != "explicit" else "",
        "source_refs": R,
        "steps": {"normal_context": ["read"], "trigger": cause, "documented_follow_up": []},
    }


def decision(a, b, status="full"):
    return {
        "left_id": a,
        "right_id": b,
        "status": status,
        "reason": "same complete cause and necessary conditions",
    }


def fake_pipeline(tmp_path, mocks=None):
    def doc(name, text, channel):
        p = tmp_path / name
        p.write_text(text)
        return read_documents([p], channel)

    rr = doc("rr.md", "# UC-X\nnormal request\n6. 扩展路径：\nexisting empty result\n", "existing")
    sr = doc("sr.md", "# UC-X\nnormal call\n", "existing")
    tests = doc(
        "test.md",
        "# UC-X\n| TEST-UC-X-A01 | failed read | 异常 | available | invalid request | UC-X | check | reject | spec |\n",
        "test",
    )
    empty = {
        "components": {"components": [], "relations": []},
        "rr-ssd": {"interactions": []},
        "sr-ssd": {"interactions": []},
        "api-map": {"services": []},
        "api-parameters": {"apis": []},
        "test-operation-project": {"objects": []},
        "object-operations": {"objects": []},
        "concern-match": {"matches": [], "pending": []},
        "exception-generate": {"scenarios": [], "pending": []},
        "existing-extract": {"scenarios": []},
        "test-ground-truth": {
            "scenarios": [],
            "pending": [
                {
                    "interaction_id": "sr-call",
                    "object": "Platform",
                    "concern_key": "service.query_retrieval.resource_existence",
                    "reason": "fixture: explicit test needs binding",
                    "source_refs": [
                        {
                            "source_id": tests[0]["source_id"],
                            "line_start": 2,
                            "line_end": 2,
                            "quote": tests[0]["lines"][1]["text"],
                        }
                    ],
                }
            ],
        },
        "gap-compare": {"decisions": [], "missing": []},
        "interaction-align": {"aliases": [], "links": []},
    }

    def ref(doc):
        return [
            {
                "source_id": doc[0]["source_id"],
                "line_start": 2,
                "line_end": 2,
                "quote": doc[0]["lines"][1]["text"],
            }
        ]

    def rewrite(v, refs):
        if isinstance(v, dict):
            return {
                k: deepcopy(refs) if k == "source_refs" else rewrite(x, refs) for k, x in v.items()
            }
        if isinstance(v, list):
            return [rewrite(x, refs) for x in v]
        return v

    rr_i = rewrite(exchange(case="UC-X", sid="rr-call", layer="RR", api=None), ref(rr))
    sr_i = rewrite(exchange(case="UC-X", sid="sr-call", layer="SR", api=None), ref(sr))
    empty["rr-ssd"] = {"interactions": [rr_i]}
    empty["sr-ssd"] = {"interactions": [sr_i]}
    empty["components"] = {
        "components": [
            {
                "id": "actor",
                "name": "开发者",
                "composition_type": "外部Actor（人类）",
                "parent_id": None,
                "source_status": "explicit",
                "source_refs": ref(rr),
            },
            {
                "id": "platform",
                "name": "Platform",
                "composition_type": "系统边界",
                "parent_id": None,
                "source_status": "explicit",
                "source_refs": ref(rr),
            },
        ],
        "relations": [],
    }
    if mocks is not None:
        empty = mocks
    empty.setdefault("normal-rules", {"rules": [], "pending": []})
    empty.setdefault("business-entities", {"entities": [], "pending": []})
    empty.setdefault("business-crud", {"rows": [], "pending": []})
    empty.setdefault(
        "data-dependencies", {"entities": [], "relations": [], "flows": [], "pending": []}
    )
    empty.setdefault("business-dependencies", {"dependencies": [], "pending": []})
    install_catalogue_mocks(empty)
    return rr, sr, tests, empty


def install_catalogue_mocks(m):
    def catalogue(p):
        cases = []
        for d in p["input"]["documents"]:
            title = d["lines"][0]
            cid = title["text"].lstrip("# ").split("：")[0]
            cases.append(
                {
                    "id": cid,
                    "name": cid,
                    "goal": "normal request",
                    "actors": ["开发者"],
                    "layer": p["input"]["layer"],
                    "source_ranges": [
                        {
                            "source_id": d["source_id"],
                            "start": title["number"],
                            "end": d["lines"][-1]["number"],
                        }
                    ],
                    "source_refs": [
                        {
                            "source_id": d["source_id"],
                            "line_start": title["number"],
                            "line_end": title["number"],
                            "quote": title["text"],
                        }
                    ],
                }
            )
        return {"cases": cases}

    def align(p):
        rr = p["input"]["rr-cases"]["cases"]
        sr = p["input"]["sr-cases"]["cases"]
        return {
            "groups": [
                {
                    "id": a["id"],
                    "rr_ids": [a["id"]],
                    "sr_ids": [b["id"] for b in sr if b["id"] == a["id"]],
                    "status": "confirmed",
                    "reason": "test fixture explicit shared case",
                    "source_refs": a["source_refs"],
                }
                for a in rr
            ]
        }

    def fused(p):
        values = []
        for t in ("rr-ssd", "sr-ssd"):
            v = m[t](p) if callable(m[t]) else deepcopy(m[t])
            if "interactions" not in v:
                return v
            values += v["interactions"]
        rr = [i for i in values if i["layer"] == "RR"]
        sr = [i for i in values if i["layer"] == "SR"]
        return {
            "interactions": values,
            "rr_sr_links": [
                {
                    "rr_id": rr[0]["id"],
                    "sr_ids": [i["id"] for i in sr],
                    "status": "confirmed",
                    "basis": "explicit fixture refinement",
                    "source_refs": rr[0]["source_refs"],
                }
            ],
            "pending": [],
        }

    def api_index(p):
        v = m.get("api-parameters", {"apis": []})
        v = v(p) if callable(v) else v
        docs = p["input"]["SR"]
        return {
            "apis": [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "source_ranges": [
                        {
                            "source_id": d["source_id"],
                            "start": d["lines"][0]["number"],
                            "end": d["lines"][-1]["number"],
                        }
                        for d in docs
                    ],
                    "source_refs": a["source_refs"],
                }
                for a in v.get("apis", [])
            ]
        }

    m.setdefault("existing-concerns", {"matches": [], "pending": []})
    m.setdefault("test-concerns", {"matches": [], "pending": []})
    m.setdefault("existing-branches", {"branches": []})
    m.setdefault("existing-bind", {"bindings": []})
    m.setdefault("api-index", api_index)

    def atomic(p):
        return {
            "steps": [
                {
                    "key": i["id"],
                    "origin_ids": [i["id"]],
                    "kind": "action" if i.get("step_kind") == "action" else i["direction"],
                    "layer": i["layer"],
                    "sender": i["sender"]["name"],
                    "receiver": i["receiver"]["name"],
                    "operation": i["operation"]["name"],
                    "request_ref": i["parent_id"] if i["direction"] == "return" else None,
                    "validates": [],
                    "source_refs": i["source_refs"],
                }
                for i in p["input"]["candidate"]["interactions"]
            ],
            "pending": [],
        }

    def scopes(p):
        return {
            "units": [
                {
                    "source_id": r["id"],
                    "trigger": r["description"],
                    "scope": "interaction",
                    "global_kind": None,
                    "entity_ids": [],
                    "related_cases": [],
                    "reason": "explicit fixture local failure",
                }
                for r in p["input"]["source-records"]
            ]
        }

    m.setdefault("interaction-normalize", atomic)
    m.setdefault("exception-scope", scopes)
    m.update({"use-case-extract": catalogue, "use-case-align": align, "fused-ssd": fused})


REF = {
    "source_id": "positive",
    "line_start": 1,
    "line_end": 1,
    "quote": "known positive constraint",
}

R = [REF]

__all__ = [
    "R",
    "REF",
    "data_exceptions",
    "decision",
    "exchange",
    "fake_pipeline",
    "install_catalogue_mocks",
    "memory_inputs",
    "parameter",
    "scenario",
]
