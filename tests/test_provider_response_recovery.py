"""Replay malformed gateway responses and CRUD preflight without paid requests."""

import io
import json
from unittest.mock import patch

import pytest

from scene_completion.domain.contracts import packet
from scene_completion.infrastructure.execution_events import EventStore, bind
from scene_completion.infrastructure.storage import read_json
from scene_completion.models.deepagents_client import DeepAgentsClient
from scene_completion.models.model_client import SemanticClient
from scene_completion.models.provider_response import InvalidProviderResponse
from scene_completion.models.request_context import view
from scene_completion.workflow.scheduler import CallGate, Scheduler, Task, TaskBlocked


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}


def configuration(tmp_path, **options):
    return {
        "api_key": "private-key-12345",
        "base_url": "http://test.invalid/v1",
        "agent_model": "test-model",
        "run_root": str(tmp_path),
        "max_tokens": 512,
        **options,
    }


def body():
    return {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Current evidence"}],
        "max_tokens": 512,
    }


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b'{"error":{"message":"private-key-12345"}}', "provider_error_envelope"),
        (b"", "empty_body"),
        (b"<html>gateway error</html>", "invalid_json"),
        (b"null", "invalid_envelope"),
        (b"{}", "missing_choices"),
        (b'{"choices":[]}', "empty_choices"),
        (b'{"choices":[null]}', "invalid_choices"),
        (b'{"choices":[{"message":"invalid"}]}', "invalid_message"),
        (b'{"choices":[{"message":{}}]}', "empty_message"),
    ],
)
def test_malformed_success_response_is_safe_and_not_resent(tmp_path, raw, reason):
    client = SemanticClient(configuration(tmp_path, max_retries=3))
    with patch("urllib.request.urlopen", return_value=Response(raw)) as request:
        with pytest.raises(InvalidProviderResponse) as raised:
            client.post("/chat/completions", body())
    assert request.call_count == 1
    assert raised.value.response_diagnostic == {
        "failure_category": "invalid_provider_response",
        "phase": "response_decode",
        "reason": reason,
        "http_status": 200,
        "transport_attempts": 1,
    }
    assert "private-key" not in str(raised.value)


@pytest.mark.parametrize("reported", [True, False])
def test_malformed_response_settles_once_and_keeps_unknown_usage_guard(tmp_path, reported):
    client = SemanticClient(
        configuration(
            tmp_path,
            token_budget_limit=50000,
            token_budget_ledger=str(tmp_path / "ledger.json"),
        )
    )
    payload = {"error": {"message": "Internal"}}
    if reported:
        payload["usage"] = {"total_tokens": 12}
    with patch("urllib.request.urlopen", return_value=Response(json.dumps(payload).encode())):
        with pytest.raises(InvalidProviderResponse):
            client.post("/chat/completions", body())
    ledger = read_json(client.token_budget.path)
    (row,) = ledger["requests"].values()
    if reported:
        assert row["status"] == "complete" and row["charged_tokens"] == 12
    else:
        assert row["status"] == "usage_unknown" and row["charged_tokens"] == row["reservation"]
        from scene_completion.models.token_budget import TokenBudgetBlocked

        with pytest.raises(TokenBudgetBlocked):
            client.token_budget.reserve(body())


def test_streamed_tool_only_response_allows_intermediate_usage_event(tmp_path):
    def event(value):
        return f"data: {json.dumps(value)}\n\n".encode()

    chunk = {"id": "call", "function": {"name": "submit_result", "arguments": "{}"}}
    response = Response(
        event({"choices": [{"delta": {"tool_calls": [chunk]}, "finish_reason": "tool_calls"}]})
        + event({"choices": [], "usage": {"total_tokens": 14}})
        + b"data: [DONE]\n\n"
    )
    response.headers = {"Content-Type": "text/event-stream"}
    client = SemanticClient(configuration(tmp_path))
    with patch("urllib.request.urlopen", return_value=response):
        result = client.post("/chat/completions", {**body(), "stream": True})
    assert result["usage"]["total_tokens"] == 14
    assert result["choices"][0]["message"]["tool_calls"][0]["id"] == "call"


def crud_packet(**extra):
    p = packet(
        "business-crud",
        {
            "business-entities": {"entities": [], "pending": []},
            "fused-ssd": {"interactions": [], "rr_sr_links": [], "pending": []},
            "normal-documents": [
                {
                    "source_id": "sr",
                    "name": "SR.md",
                    "channel": "normal",
                    "lines": [{"number": 1, "text": "CURRENT_SOURCE_RULE"}],
                }
            ],
        },
        ["G-004"],
    )
    p.update(skill_text="Only classify explicit effects.", **extra)
    return p


def test_crud_drops_oversized_candidate_and_persists_unsent_preflight(tmp_path):
    sent = []

    def transport(url, key, request, timeout, retries):
        sent.append(json.dumps(request, ensure_ascii=False))
        return {"choices": [{"message": {"content": '{"rows":[],"pending":[]}'}}]}

    repair = {
        "failure": {"error": "invalid CRUD"},
        "round": 1,
        "candidate": {"rows": ["Z" * 60000]},
    }
    client = DeepAgentsClient(
        configuration(tmp_path, max_context_tokens=50000, submission_mode="json_text"),
        transport=transport,
    )
    with bind(EventStore(tmp_path), task_key="G-004:business-crud"):
        assert client.agent(crud_packet(repair=repair))["rows"] == []
    assert len(sent) == 1 and "CURRENT_SOURCE_RULE" in sent[0] and "ZZZZZZ" not in sent[0]
    client.config["max_context_tokens"] = 100
    with bind(EventStore(tmp_path), task_key="G-017:business-crud"):
        with pytest.raises(TaskBlocked) as blocked:
            client.agent(crud_packet())
    assert len(sent) == 1
    assert blocked.value.status == "awaiting_configuration"
    assert blocked.value.details["not_sent"] and blocked.value.details["output_reserve"] == 512
    assert view(tmp_path, "G-017:business-crud")["requests"][0]["status"] == "context_blocked"


def test_provider_failure_leaves_crud_recoverable_and_other_work_can_finish(tmp_path):
    scheduler = Scheduler(tmp_path, concurrency=1)
    gate = CallGate(1)
    observed = []

    def run_crud(_deps, record):
        observed.append(record)
        if len(observed) == 1:

            def malformed():
                raise InvalidProviderResponse("missing_choices")

            gate.call(malformed)
        return {"rows": []}

    for key, stage, run in (
        ("G-004:business-crud", "business-crud", run_crud),
        ("independent", "independent", lambda *_: {"complete": True}),
    ):
        scheduler.add(Task(key, key, stage, (), version="v1", execute=run))
    scheduler.run()
    assert scheduler.state["tasks"]["G-004:business-crud"]["status"] == "pending"
    assert scheduler.state["tasks"]["independent"]["status"] == "passed"
    scheduler.run()
    assert scheduler.state["tasks"]["G-004:business-crud"]["status"] == "passed"
    assert observed[1]["rounds"] == 0
    assert observed[1]["failure"]["transport_failure"]["reason"] == "missing_choices"


def test_resume_crud_discards_old_transport_history_but_preserves_call_count(tmp_path):
    from langchain_core.messages import HumanMessage, messages_to_dict

    from scene_completion.review.node_conversations import Conversations

    task = "G-004:business-crud"
    sent = []

    def transport(url, key, request, timeout, retries):
        sent.append(json.dumps(request, ensure_ascii=False))
        if len(sent) == 1:
            return {"error": {"message": "gateway body"}}
        return {"choices": [{"message": {"content": '{"rows":[],"pending":[]}'}}]}

    client = DeepAgentsClient(
        configuration(tmp_path, max_context_tokens=50000, submission_mode="json_text"),
        transport=transport,
    )
    gate = CallGate(1)
    original = client.post
    client.shared_call_gate = gate
    client.post = lambda *a, **kw: gate.call(original, *a, **kw)
    with bind(EventStore(tmp_path), task_key=task):
        with pytest.raises(TaskBlocked) as failure:
            client.agent(crud_packet())
        assert failure.value.status == "pending" and len(sent) == 1
        conversations = Conversations(tmp_path)
        with conversations.events.connect() as db:
            ident, data = db.execute(
                "SELECT identity,state FROM checkpoints WHERE task=?", (task,)
            ).fetchone()
        checkpoint = json.loads(data)
        assert checkpoint["status"] == "transport_wait"
        checkpoint["messages"] += messages_to_dict([HumanMessage(content="STALE_HISTORY" * 7000)])
        checkpoint["model_calls"] = 1
        conversations.checkpoint(task, ident, checkpoint)
        assert client.agent(crud_packet())["rows"] == []
        assert conversations.checkpoint(task, ident)["model_calls"] == 2
    assert len(sent) == 2 and "CURRENT_SOURCE_RULE" in sent[1] and "STALE_HISTORY" not in sent[1]


def test_buffered_text_blocks_remain_supported(tmp_path):
    value = {"choices": [{"message": {"content": [{"type": "text", "text": "{}"}]}}]}
    client = SemanticClient(configuration(tmp_path))
    with patch("urllib.request.urlopen", return_value=Response(json.dumps(value).encode())):
        result = client.post("/chat/completions", body())
    assert result["choices"] == value["choices"]
