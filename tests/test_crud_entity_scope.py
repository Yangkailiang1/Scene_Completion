"""Exercise scoped packets, bounded evidence transport and v5 cache reuse."""

import json
from copy import deepcopy

import pytest

from scene_completion.analysis.crud_scope import project, record_pending
from scene_completion.analysis.validation import validate_result
from scene_completion.domain.contracts import PROTOCOL, packet
from scene_completion.infrastructure.execution_events import EventStore, bind
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.colleague_formats import scoped_entities
from scene_completion.inputs.crud_evidence import MAX_LOOKUP_BYTES, size
from scene_completion.inputs.indexed_context import EvidenceContext
from scene_completion.models.context_budget import check
from scene_completion.models.deepagents_client import DeepAgentsClient
from scene_completion.models.model_client import SemanticClient
from scene_completion.review.node_conversations import Conversations
from scene_completion.workflow.case_pipeline import _build_cases
from scene_completion.workflow.engine import Execution
from scene_completion.workflow.scheduler import TaskBlocked
from tests.test_provider_response_recovery import configuration
from tests.test_workflow import exchange

SHARED = "GLOBAL_SHARED_ENTITY_QUOTE " + "共享业务实体项目级说明。" * 240


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


def test_all_seventeen_registered_packets_and_requests_exclude_foreign_entities(tmp_path):
    cases = [f"G-{n:03d}" for n in range(1, 18)]
    entities = [entity(n, f"UC-{(n - 1) % 17 + 1:03d}") for n in range(1, 53)]
    inputs = {
        case: fixture(
            case,
            f"更新业务对象{n:02d}的状态",
            entities,
            text=f"本用例明确要求更新业务对象{n:02d}的状态。",
        )
        for n, case in enumerate(cases, 1)
    }
    sr = [doc for scope in inputs.values() for doc in scope["normal-documents"]]
    entries = [
        {
            "id": f"UC-{n:03d}",
            "name": f"用例{n}",
            "source_ranges": [
                {
                    "source_id": f"sr-{case}",
                    "start": 1,
                    "end": 1,
                }
            ],
        }
        for n, case in enumerate(cases, 1)
    ]
    groups = [
        {"id": case, "status": "confirmed", "rr_ids": [], "sr_ids": [e["id"]]}
        for case, e in zip(cases, entries, strict=True)
    ]
    ex = Execution(tmp_path / "run")
    _build_cases(ex, [], sr, [], {"RR": [], "SR": entries}, groups, {}, {})
    observed = []
    expected = None

    def transport(_url, _key, body, _timeout, _retries):
        text = body["messages"][1]["content"]
        prompt = json.loads(text)
        seen = {r["id"] for r in prompt["input"]["business-entities"]["entities"]}
        assert seen == expected and "GLOBAL_SHARED_ENTITY_QUOTE" not in text
        doc = prompt["input"]["normal-documents"][0]
        assert text.count(doc["numbered_text"].split(" | ")[-1]) == 1
        observed.append(check(body, client.config))
        return {"choices": [{"message": {"content": '{"rows":[],"pending":[]}'}}]}

    client = SemanticClient(configuration(tmp_path), transport=transport)
    old_entities_bytes = size({"entities": entities, "pending": []})
    for case, entry in zip(cases, entries, strict=True):
        task_key = case + ":business-crud"
        before = inputs[case]
        task = ex.scheduler.tasks[task_key]
        deps = {
            "business-entities": {"protocol": PROTOCOL, "payload": before["business-entities"]},
            case + ":fused-ssd": {"protocol": PROTOCOL, "payload": before["fused-ssd"]},
        }
        with bind(EventStore(ex.root), task_key=task_key, case=case):
            with pytest.raises(TaskBlocked) as pending:
                task.execute(deps, {"case": case, "stage": "business-crud", "rounds": 0})
        p = read_json(ex.root / pending.value.details["packet"])
        expected = {e["id"] for e in entities if e["attributes"][0]["case_ids"] == [entry["id"]]}
        scoped = p["input"]["business-entities"]["entities"]
        assert {e["id"] for e in scoped} == expected
        assert "GLOBAL_SHARED_ENTITY_QUOTE" not in json.dumps(p, ensure_ascii=False)
        assert p["input"]["crud-entity-scope"]["project_entities"] == 52
        assert client.agent(p)["rows"] == []
    assert len(observed) == 17
    assert all(x["request_bytes"] < old_entities_bytes // 10 for x in observed)
    assert all(x["input_budget_tokens"] < 12000 for x in observed)


def test_scope_ambiguity_and_non_entity_names_do_not_select_unrelated_objects():
    entities = [
        entity(1, name="账号"),
        entity(2, name="账号"),
        entity(3, name="Admin"),
        entity(4, name="status"),
    ]
    scoped = project(fixture(operation="更新账号", catalogue=entities), ["UC-004"], {})
    assert not scoped["business-entities"]["entities"]
    scope = scoped["crud-entity-scope"]
    assert scope["ambiguous_interactions"] == {"账号": ["G-004-op"]}
    pending = record_pending({"rows": [], "pending": []}, scope, "G-004")["pending"]
    assert {r["object"] for r in pending} == {"G-004", "G-004-op"}
    no_scope = project(
        fixture(
            operation="处理请求", catalogue=entities, text="| status | 字段 |\n服务名称：Admin"
        ),
        ["UC-004"],
        {},
    )
    assert no_scope["crud-entity-scope"]["missing_entities"]
    service_only = fixture(operation="Admin处理请求", catalogue=entities)
    service_only["fused-ssd"]["interactions"][0]["receiver"]["name"] = "Admin"
    assert project(service_only, ["UC-004"], {})["crud-entity-scope"]["missing_entities"]
    entities[1] = entity(2, "UC-004", "账号")
    resolved = project(fixture(operation="更新账号", catalogue=entities), ["UC-004"], {})
    assert [e["id"] for e in resolved["business-entities"]["entities"]] == ["ENTITY-02"]
    assert not resolved["crud-entity-scope"]["ambiguous_names"]
    entities[2] = entity(3, "UC-030", "Admin")
    entities[2]["attributes"][0]["case_names"] = ["同名用例"]
    entities[2]["source_refs"].append(
        citation(
            '{"case_id":"UC-030","case_name":"同名用例","entity":"ENTITY-03"}',
            line=30,
        )
    )
    assert [
        e["id"]
        for e in project(
            fixture(operation="更新账号", catalogue=entities),
            ["UC-004", "同名用例"],
            {},
        )["business-entities"]["entities"]
    ] == ["ENTITY-02"]


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


def test_deferred_citations_are_bounded_and_recover_exact_source_identity():
    p = scoped_packet()
    ctx = EvidenceContext(p)
    (key,) = [
        key for key, location in ctx.input["evidence_locations"].items() if location["deferred"]
    ]
    assert ctx.input["evidence_locations"][key]["json_pointer"] == "/functions/3"
    assert key not in ctx.input["evidence_catalog"]
    with pytest.raises(ValueError, match="unknown evidence_id"):
        ctx.expand(result(p["input"], [key]))
    with pytest.raises(ValueError, match="isolated"):
        ctx.lookup(["e000000000000"])
    with pytest.raises(ValueError, match="8"):
        ctx.lookup([key] * 9)

    chunks = []
    start = 0
    first_page = None
    while start is not None:
        response = ctx.lookup([key], {key: start})
        assert size(response) <= MAX_LOOKUP_BYTES
        page = response[key]
        first_page = first_page or page
        chunks.append(page["quote"])
        assert page["offset"] == start and page["line_start"] == page["line_end"] == 19
        start = page["next_offset"]
    assert "".join(chunks) == ctx.pool[key]["quote"]
    refs = [first_page["citation_id"], next(iter(ctx.doc_refs))]
    expanded = ctx.expand(result(p["input"], refs))
    validate_result("business-crud", expanded, p["input"])
    assert expanded["rows"][0]["source_refs"][0]["quote"] == first_page["quote"]
    with pytest.raises(ValueError, match="identity alone"):
        validate_result("business-crud", ctx.expand(result(p["input"], refs[:1])), p["input"])
    with pytest.raises(ValueError, match="existing business entity"):
        validate_result(
            "business-crud", ctx.expand(result(p["input"], refs, entity_id="ENTITY-30")), p["input"]
        )


def test_crud_restarts_old_awaiting_answer_and_uses_paged_lookup(tmp_path):
    from langchain_core.messages import ToolMessage, messages_to_dict

    p = scoped_packet()
    task = p["node_key"]
    conversations = Conversations(tmp_path)
    conversations.append(task, "guidance", "KEEP_CURRENT_GUIDANCE")
    stale = "output was truncated due to size limits. /conversation_history/old.md "
    conversations.checkpoint(
        task,
        "legacy-full-catalogue",
        {
            "status": "awaiting_answer",
            "model_calls": 1,
            "messages": messages_to_dict(
                [
                    ToolMessage(content=stale * 14000, tool_call_id="old-1"),
                    ToolMessage(content=stale * 14000, tool_call_id="old-2"),
                ]
            ),
        },
    )
    seen = []
    ctx = EvidenceContext(p)
    key = next(key for key, ref in ctx.input["evidence_locations"].items() if ref["deferred"])
    local_id = next(iter(ctx.doc_refs))

    def transport(_url, _key, body, _timeout, _retries):
        messages = body["messages"]
        text = json.dumps(messages, ensure_ascii=False)
        seen.append(text)
        assert stale not in text and "KEEP_CURRENT_GUIDANCE" in text
        assert "更新业务对象04的状态" in text
        assert "ENTITY-30" not in text and SHARED not in text
        if len(seen) == 1:
            assert "合法引文" not in text
            content = {"evidence_request": [key], "offsets": {key: 0}}
        else:
            (tool,) = [m for m in messages if m["role"] == "tool"]
            pages = json.loads(tool["content"])
            assert size(pages) <= MAX_LOOKUP_BYTES
            content = result(p["input"], [pages[key]["citation_id"], local_id])
        return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}

    client = DeepAgentsClient(
        configuration(tmp_path, submission_mode="json_text"), transport=transport
    )
    with bind(EventStore(tmp_path), task_key=task, case="G-004"):
        value = client.agent(p)
    assert len(seen) == 2 and value["rows"][0]["entity_id"] == "ENTITY-04"
    with conversations.events.connect() as db:
        checkpoint = json.loads(
            db.execute("SELECT state FROM checkpoints WHERE task=?", (task,)).fetchone()[0]
        )
    assert checkpoint["model_calls"] == 3 and checkpoint["messages"] == []


def test_legacy_passed_cache_revalidates_current_entity_and_evidence_scope(tmp_path):
    inputs = fixture(catalogue=[entity(4, "UC-004"), entity(30, "UC-030")])
    ex = Execution(tmp_path / "run")
    for dep, value in (
        ("business-entities", inputs["business-entities"]),
        ("G-004:fused-ssd", inputs["fused-ssd"]),
    ):
        name = dep.replace(":", "-") + ".json"
        write_json(ex.root / name, {"protocol": PROTOCOL, "payload": value})
        ex.scheduler.state["tasks"][dep] = {"output_file": name}
    ex.add(
        "G-004:business-crud",
        "business-crud",
        ("business-entities", "G-004:fused-ssd"),
        build=lambda d: {
            **inputs,
            "business-entities": d["business-entities"],
            "fused-ssd": d["G-004:fused-ssd"],
            "_crud_scope": (["G-004", "UC-004"], ["UC-004"], {}),
        },
        case="G-004",
    )
    old_inputs = {
        **inputs,
        "business-entities": scoped_entities(inputs["business-entities"], ["UC-004"]),
    }
    refs = inputs["fused-ssd"]["interactions"][0]["source_refs"]
    old = {
        "task": "business-crud",
        "protocol": PROTOCOL,
        "payload": result(inputs, refs),
        "metadata": {"input_hash": fingerprint(old_inputs)},
    }
    verify = ex.scheduler.tasks["G-004:business-crud"].verify
    verify(old)
    invalid = deepcopy(old)
    invalid["payload"]["rows"][0]["entity_id"] = "ENTITY-30"
    with pytest.raises(ValueError, match="existing business entity"):
        verify(invalid)
    old["metadata"]["input_hash"] = "different"
    with pytest.raises(ValueError, match="cached task input changed"):
        verify(old)
