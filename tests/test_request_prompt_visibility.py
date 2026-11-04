"""Actual assembled prompts, preflight failures and manager operational context."""

import pytest
from fastapi.testclient import TestClient

from scene_completion.api.application import create_app
from scene_completion.infrastructure.execution_events import EventStore, bind, fields
from scene_completion.manager.manager_context import execution_summary, memory_index
from scene_completion.models.model_client import SemanticClient
from scene_completion.models.request_context import prepare, view


def client(root, limit=200000):
    return SemanticClient(
        {
            "run_root": str(root),
            "api_key": "private-key-12345",
            "base_url": "http://model.invalid/v1",
            "agent_model": "model",
            "max_context_tokens": limit,
        }
    )


def body():
    return {
        "model": "model",
        "messages": [
            {"role": "system", "content": "Skill and rules"},
            {"role": "user", "content": "source evidence"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {"name": "submit_result", "parameters": {"type": "object"}},
            }
        ],
        "max_tokens": 256,
    }


def test_actual_request_contains_instructions_tools_and_history_without_credentials(tmp_path):
    c = client(tmp_path)
    b = body()
    b["tools"][0]["function"]["parameters"]["properties"] = {"secret": {"type": "string"}}
    b["messages"].append({"role": "tool", "content": "validation /entities/0/source_refs"})
    b["messages"][1]["content"] += " private-key-12345"
    b["extra"] = {"api_key": "other-credential"}
    with bind(EventStore(tmp_path), task_key="business-entities-part-006", attempt=2):
        with fields(model_call_id="call-1"):
            prepare(c, b, "business-entities")
            prepare(c, b)
    records = view(tmp_path, "business-entities-part-006")
    assert len(records["requests"]) == 1
    record = view(tmp_path, "business-entities-part-006", records["latest"])
    assert record["request"]["tools"] == b["tools"]
    assert record["request"]["messages"][0] == b["messages"][0]
    assert record["attempt"] == 2
    assert "validation" in record["request"]["messages"][-1]["content"]
    assert "private-key-12345" not in str(record) and "other-credential" not in str(record)
    assert "request" not in records["requests"][0]  # summary endpoint is lightweight
    with pytest.raises(ValueError):
        view(tmp_path, "another-node", records["latest"])


def test_context_preflight_is_saved_without_sending_or_spending_quota(tmp_path):
    c = client(tmp_path, limit=100)
    c.transport = lambda *a, **k: pytest.fail("Over-budget request must not be sent")
    with bind(EventStore(tmp_path), task_key="G-003:fused-ssd", attempt=1):
        with pytest.raises(RuntimeError) as error:
            c.post("/chat/completions", body())
    assert error.value.response_diagnostic["not_sent"]
    rows = view(tmp_path, "G-003:fused-ssd")
    record = view(tmp_path, "G-003:fused-ssd", rows["latest"])
    assert record["status"] == "context_blocked" and record["budget"]["max_context_tokens"] == 100
    budget = record["budget"]
    assert (
        sum(m["upper_bound"] for m in budget["messages"]) + budget["metadata_and_tools_upper_bound"]
        == budget["estimated_input_tokens_upper_bound"]
    )


def test_prompt_http_is_node_scoped_and_old_logs_are_not_reconstructed(tmp_path):
    app = create_app(tmp_path)
    http = TestClient(app)
    meta = http.post(
        "/api/projects",
        json={
            "name": "prompts",
            "sources": {r: [{"name": r + ".md", "content": "# source"}] for r in ("RR", "SR")},
        },
    ).json()
    rid = meta["id"]
    url = f"/api/projects/{rid}/prompts?task_key=task"
    assert http.get(url).json()["requests"] == []
    root = tmp_path / rid / "run"
    with bind(EventStore(root), task_key="task", attempt=1):
        prepare(client(root), body())
    listing = http.get(url).json()
    record = http.get(url + "&request_id=" + listing["latest"])
    assert record.status_code == 200 and record.json()["request"]["messages"] == body()["messages"]
    assert http.get(url + "&request_id=../../../project.json").status_code == 400


def test_manager_large_progress_is_indexed_without_losing_root_failure_count():
    state = {
        "complete": False,
        "job": {"status": "running", "internal_log": "do not inline" * 1000},
        "pending_nodes": [
            {
                "id": "bad-" + str(i),
                "status": "awaiting_configuration",
                "failure": {"failure_category": "context_budget_exceeded", "detail": "huge" * 4000},
            }
            for i in range(100)
        ]
        + [{"id": "waiting-" + str(i), "status": "blocked_dependency"} for i in range(1500)],
    }
    summary = execution_summary(state)
    assert summary["root_failure_count"] == 100 and len(summary["root_failures"]) == 12
    assert (
        summary["status_counts"]["blocked_dependency"] == 1500 and summary["pending_count"] == 1600
    )
    assert len(str(summary)) < 30000 and "internal_log" not in str(summary)
    assert "上下文超限" in summary["root_failures"][0]["action"]
    assert len(state["pending_nodes"]) == 1600  # no modification to durable state


def test_memory_index_offloads_large_records_and_retains_lookup_identity():
    memories = [
        {"id": "m" + str(i), "text": "decision" * 1000, "active": True, "revision": 1}
        for i in range(50)
    ]
    text = memory_index(memories, max_chars=2000)
    assert len(text) < 2500 and '"active_count": 50' in text and '"id": "m0"' in text
    assert len(memories[0]["text"]) == 8000


def test_cli_prompts_lists_and_reads_exact_request_without_model(capsys):
    from scene_completion.cli.main import capabilities, main

    class API:
        def call(self, path):
            assert path.endswith("/prompts?task_key=G-003%3Afused-ssd&request_id=one")
            return {"status": "prepared"}

    assert "prompts" in capabilities()["commands"]
    assert (
        main(
            ["prompts", "--project", "a" * 32, "--node", "G-003:fused-ssd", "--request", "one"],
            client=API(),
        )
        == 0
    )
    assert "prepared" in capsys.readouterr().out


def test_manager_context_block_waits_for_change_and_does_not_loop_as_reconnect():
    from scene_completion.manager.manager_runtime import failure_state

    error = RuntimeError("task context exceeds configured budget")
    error.response_diagnostic = {
        "failure_category": "context_budget_exceeded",
        "configuration_required": True,
        "not_sent": True,
    }
    state = failure_state(
        error,
        {"handled_user": 2},
        {"mode": "auto", "reconnect_seconds": 30},
        [{"id": 3}],
        "unchanged",
        100,
    )
    assert state["status"] == "awaiting_configuration" and state["retry_at"] == 0
    assert state["trigger"] == "unchanged" and state["handled_user"] == 3
    assert state["reconnect_failures"] == 0
    network = failure_state(
        OSError("connection lost"), {}, {"mode": "auto", "reconnect_seconds": 30}, [], "same", 100
    )
    assert network["status"] == "waiting_reconnect" and network["retry_at"] == 130


def test_manager_independent_model_change_wakes_auto_without_business_config_change(tmp_path):
    from scene_completion.infrastructure.storage import write_json
    from scene_completion.manager.manager_runtime import signature
    from tests.test_project_manager import project

    service, rid, p = project(tmp_path)
    try:
        before = signature(service, rid)
        write_json(
            p / "manager/model.local.json",
            {"agent_model": "other-model", "max_context_tokens": 200000},
        )
        assert signature(service, rid) != before
    finally:
        service.pool.shutdown()
