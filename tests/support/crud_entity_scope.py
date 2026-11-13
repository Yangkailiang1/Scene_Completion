"""Offline test support extracted without changing builder behavior."""

import json

from scene_completion.analysis.interactions.crud_scope import project
from scene_completion.domain.contracts import packet
from tests.support.workflow import exchange


def citation(quote, source="import-fixture-facts-v1", line=1):
    return {"source_id": source, "line_start": line, "line_end": line, "quote": quote}


def entity(n, case=None, name=None):
    shared = citation(SHARED)
    return {
        "id": f"ENTITY-{n:02d}",
        "name": name or f"业务对象{n:02d}",
        "source_refs": [shared],
        "business_rules": [],
        "attributes": [
            {
                "name": "status",
                "data_type": "string",
                "required": False,
                "operation": "any",
                "constraints": [],
                "case_ids": [case],
                "source_refs": [shared],
            }
        ]
        if case
        else [],
    }


def fixture(case="G-004", operation="更新业务对象04的状态", catalogue=None, text=None):
    msg = exchange(sid=f"{case}-op")
    msg["case_id"] = case
    msg["operation"]["name"] = operation
    quote = text or operation
    ref = citation(quote, f"sr-{case}")
    msg["source_refs"] = [ref]
    msg["operation"]["source_refs"] = [ref]
    return {
        "business-entities": {"entities": catalogue or [entity(4, "UC-004")], "pending": []},
        "fused-ssd": {"interactions": [msg], "rr_sr_links": [], "pending": []},
        "normal-documents": [
            {
                "source_id": ref["source_id"],
                "name": "设计.md",
                "channel": "normal",
                "lines": [{"number": 1, "text": quote}],
            }
        ],
    }


def result(inputs, refs, *, entity_id="ENTITY-04"):
    msg = inputs["fused-ssd"]["interactions"][0]
    return {
        "rows": [
            {
                "case_id": msg["case_id"],
                "interaction_id": msg["id"],
                "entity_id": entity_id,
                "service": msg["receiver"]["name"],
                "operation": "update",
                "api_id": None,
                "basis": "当前步骤更新实体状态",
                "source_refs": refs,
            }
        ],
        "reviews": [
            {
                "interaction_id": msg["id"],
                "decision": "crud",
                "basis": "明确更新实体状态",
                "source_refs": refs,
            }
        ],
        "pending": [],
    }


def long_entity():
    e = entity(4, "UC-004")
    e["source_refs"].append(
        citation(
            json.dumps(
                {
                    "case_id": "UC-004",
                    "entity": "ENTITY-04",
                    "name": e["name"],
                    "note": '合法引文\\引号"' * 2000,
                },
                ensure_ascii=False,
            ),
            line=19,
        )
    )
    return e


def scoped_packet():
    inputs = project(
        fixture(catalogue=[long_entity(), entity(30, "UC-030")]),
        ["G-004", "UC-004"],
        {("import-fixture-facts-v1", 19): {"file": "功能树.json", "json_pointer": "/functions/3"}},
    )
    p = packet("business-crud", inputs, ["G-004"])
    p.update(skill_text="Only classify explicit effects.", node_key="G-004:business-crud")
    return p


SHARED = "GLOBAL_SHARED_ENTITY_QUOTE " + "共享业务实体项目级说明。" * 240

__all__ = ["SHARED", "citation", "entity", "fixture", "long_entity", "result", "scoped_packet"]
