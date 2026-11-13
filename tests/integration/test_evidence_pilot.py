"""Exercise the opt-in tools through the actual model transport adapters."""

import json

import pytest

from scene_completion.domain.contracts import packet
from scene_completion.infrastructure.execution_events import EventStore, bind
from scene_completion.inputs.extraction.crud_evidence import MAX_LOOKUP_BYTES, size
from scene_completion.inputs.provenance.indexed_context import EvidenceContext
from scene_completion.inputs.provenance.task_evidence_tools import (
    TaskEvidenceTools,
    require_positive_documents,
)
from scene_completion.inputs.structured.api_boundaries import partition_documents
from scene_completion.inputs.structured.external_interfaces import mapping_view
from scene_completion.models.clients.deepagents_client import DeepAgentsClient
from scene_completion.review.decisions.node_conversations import Conversations
from tests.support.crud_entity_scope import result, scoped_packet
from tests.support.external_api_evidence import document
from tests.support.provider_response_recovery import configuration


def response(mode, name, args, call_number):
    if mode == "tool_calls":
        message = {
            "tool_calls": [
                {
                    "id": f"offline-{call_number}",
                    "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                }
            ]
        }
    elif name == "lookup_evidence":
        message = {
            "content": json.dumps(
                {"evidence_request": args["evidence_ids"], "offsets": args["offsets"]}
            )
        }
    elif name == "submit_result":
        message = {"content": json.dumps(args["payload"], ensure_ascii=False)}
    else:
        message = {
            "content": json.dumps({"evidence_tool": name, "arguments": args}, ensure_ascii=False)
        }
    return {"choices": [{"message": message}]}


@pytest.mark.parametrize("mode", ["tool_calls", "json_text"])
def test_crud_queries_current_interaction_and_uses_its_evidence(tmp_path, mode):
    p = scoped_packet()
    interaction = p["input"]["fused-ssd"]["interactions"][0]
    calls = []

    def transport(_url, _key, body, _timeout, _retries):
        calls.append(body)
        text = json.dumps(body["messages"], ensure_ascii=False)
        assert "ENTITY-30" not in text
        if mode == "tool_calls":
            names = {tool["function"]["name"] for tool in body["tools"]}
            assert "execute" not in names and "read_file" not in names
        else:
            assert "tools" not in body
        outputs = [json.loads(m["content"]) for m in body["messages"] if m["role"] == "tool"]
        assert all(size(x) <= MAX_LOOKUP_BYTES for x in outputs)
        if len(calls) == 1:
            return response(mode, "search_evidence", {"query": "更新业务对象04"}, 1)
        if len(calls) == 2:
            assert outputs[-1]["matches"]
            return response(
                mode,
                "inspect_task_record",
                {"kind": "interaction", "record_id": interaction["id"], "pointer": "/operation"},
                2,
            )
        operation = outputs[-1]["value"]
        assert operation["name"] == interaction["operation"]["name"]
        return response(
            mode, "submit_result", {"payload": result(p["input"], operation["source_refs"])}, 3
        )

    client = DeepAgentsClient(
        configuration(
            tmp_path, agent_evidence_pilot=True, submission_mode=mode, agent_max_model_calls=3
        ),
        transport=transport,
    )
    with bind(EventStore(tmp_path), task_key=p["node_key"], case="G-004"):
        value = client.agent(p)
    assert value["rows"][0]["interaction_id"] == interaction["id"] and len(calls) == 3


def external_packet():
    services = [
        {"name": "CloudMapService", "aliases": []},
        {"name": "ExternalDatabase", "aliases": []},
    ]
    doc = document()
    doc["lines"] = [r for r in doc["lines"] if r["number"] != 12]
    docs = {
        "SR": partition_documents([doc], services, "external"),
        "interface-scope": {"boundary": "external", "external_services": services},
    }
    inputs = mapping_view(docs)
    p = packet("api-map", inputs)
    p.update(skill_text="test skill", node_key="sr-external-api-map")
    return p


@pytest.mark.parametrize("mode", ["tool_calls", "json_text"])
def test_external_api_queries_verified_declarations_and_restores_without_tool_history(
    tmp_path, mode
):
    p = external_packet()
    conversations = Conversations(tmp_path)
    conversations.append(p["node_key"], "guidance", "KEEP_NODE_GUIDANCE")
    conversations.checkpoint(
        p["node_key"],
        "legacy-transport",
        {"status": "transport_wait", "model_calls": 1, "messages": ["OLD_TOOL_TEXT" * 10000]},
    )
    calls = []

    def transport(_url, _key, body, _timeout, _retries):
        calls.append(body)
        text = json.dumps(body["messages"], ensure_ascii=False)
        assert "OLD_TOOL_TEXT" not in text and "KEEP_NODE_GUIDANCE" in text
        assert "/mx/v2/instances" not in text and "/db/v9/records" not in text
        outputs = [json.loads(m["content"]) for m in body["messages"] if m["role"] == "tool"]
        if len(calls) == 1:
            return response(mode, "search_evidence", {"query": "/cloudmap/v3/resources"}, 1)
        if len(calls) == 2:
            found = next(
                x for x in outputs[-1]["matches"] if x.get("kind") == "interface_declaration"
            )
            return response(mode, "inspect_task_record", {**found, "pointer": "/receiver"}, 2)
        assert outputs[-1]["value"] == "CloudMapService"
        return response(mode, "submit_result", {"payload": {"services": []}}, 3)

    client = DeepAgentsClient(
        configuration(
            tmp_path, agent_evidence_pilot=True, submission_mode=mode, agent_max_model_calls=4
        ),
        transport=transport,
    )
    with bind(EventStore(tmp_path), task_key=p["node_key"]):
        value = client.agent(p)
    assert [s["name"] for s in value["services"]] == ["CloudMapService"]
    assert len(value["services"][0]["interfaces"]) == 2 and len(calls) == 3
    with conversations.events.connect() as db:
        saved = json.loads(
            db.execute(
                "SELECT state FROM checkpoints WHERE task=?",
                (p["node_key"],),
            ).fetchone()[0]
        )
    assert saved["model_calls"] == 4 and saved["messages"] == []


def test_evidence_pilot_rejects_foreign_sources_and_only_cites_retrieved_long_text():
    p = scoped_packet()
    doc = p["input"]["normal-documents"][0]
    doc["lines"].append({"number": 2, "text": "很长的原始文字。" * 4000})
    context = EvidenceContext(p, evidence_pilot=True)
    evidence = TaskEvidenceTools(context)
    key = evidence.search("很长的原始文字", source_id=doc["source_id"])["matches"][0]["evidence_id"]
    assert not context.visible_reference(key)
    assert "很长的原始文字" not in json.dumps(context.input, ensure_ascii=False)
    page = context.lookup([key])[key]
    assert size(page) < MAX_LOOKUP_BYTES and page["next_offset"]
    assert context.visible_reference(page["citation_id"]) and not context.visible_reference(key)
    with pytest.raises(ValueError, match="source is outside"):
        evidence.search("SECRET", source_id="gt-foreign")
    with pytest.raises(ValueError, match="outside this task"):
        evidence.inspect("interaction", "foreign")
    with pytest.raises(ValueError, match="positive task"):
        require_positive_documents([doc, {**doc, "channel": "test"}])


@pytest.mark.parametrize(
    ("mode", "tool", "limit", "error"),
    [
        ("tool_calls", "read_file", 2, "tool was not offered"),
        ("tool_calls", "search_evidence", 1, "tool was not offered"),
        ("json_text", "search_evidence", 1, "exhausted model-call budget"),
    ],
)
def test_pilot_blocks_unoffered_tools_before_execution(tmp_path, mode, tool, limit, error):
    p = scoped_packet()
    events = EventStore(tmp_path)
    calls = []

    def transport(_url, _key, body, _timeout, _retries):
        calls.append(body)
        return response(mode, tool, {"query": "更新业务对象04"}, len(calls))

    client = DeepAgentsClient(
        configuration(
            tmp_path, agent_evidence_pilot=True, submission_mode=mode, agent_max_model_calls=limit
        ),
        transport=transport,
    )
    with bind(events, task_key=p["node_key"], case="G-004"):
        with pytest.raises(ValueError, match=error):
            client.agent(p)
    assert len(calls) == 1
    assert not any(row["kind"] == "tool_started" for row in events.read(task_key=p["node_key"]))
