"""Simulated transport verifies isolation, never model quality."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path[:0] = [
    str(Path(__file__).resolve().parents[3] / "src"),
    str(Path(__file__).resolve().parent),
]
import harness  # noqa: E402
from file_runtime import runtime_factory  # noqa: E402
from workspace_tools import Workspace  # noqa: E402

from scene_completion.domain.ssd_contracts import packet  # noqa: E402


def config():
    return {
        "base_url": "http://127.0.0.1:1",
        "api_key": "not-real",
        "agent_model": "ecnu-max",
        "submission_mode": "json_text",
        "thinking_override": False,
    }


def task():
    p = packet(
        "ssd-generate",
        {"templates": [{"id": "T1"}], "concerns": [], "all_failure_conditions": []},
        ["UC-test"],
    )
    return {**p, "skill_text": p["instructions"], "node_key": "UC-test:ssd-generate"}


def response(value):
    return {
        "model": "SIMULATION_ONLY",
        "choices": [
            {
                "message": {"role": "assistant", "content": json.dumps(value)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


def test_workspace_bounds_and_exact_edit(tmp_path):
    ws = Workspace(tmp_path / "ws", {"task.json": '{"input":1}'})
    try:
        assert ws.read("input/task.json")["text"] == '{"input":1}'
        ws.write("work/candidate.json", '{"test":1}')
        ws.edit("work/candidate.json", "1", "2")
        assert ws.read("work/candidate.json")["text"] == '{"test":2}'
        for path in (
            "../outside.json",
            "/etc/passwd",
            "input/task.json",
            "work/../outside.json",
            "work/x/y.json",
            "work/a.py",
            "work\\a.json",
            "work/./a.json",
        ):
            with pytest.raises((ValueError, OSError)):
                ws.write(path, "{}")
        for path in ("../outside.json", "/etc/passwd", "input/no.json", "work/../outside.json"):
            with pytest.raises((ValueError, OSError)):
                ws.read(path)
        with pytest.raises(ValueError):
            ws.write("work/x.json", "not JSON")
        with pytest.raises(ValueError):
            ws.edit("work/candidate.json", "not-present", "3")
    finally:
        ws.close()


def test_symlink_hardlink_and_directory_escape_denied(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret":1}')
    ws = Workspace(tmp_path / "ws", {"task.json": "{}"})
    try:
        for kind in ("symlink", "hardlink"):
            p = ws.root / "work/link.json"
            if kind == "symlink":
                p.symlink_to(outside)
            else:
                os.link(outside, p)
            with pytest.raises((ValueError, OSError)):
                ws.read("work/link.json")
            with pytest.raises((ValueError, OSError)):
                ws.write("work/link.json", "{}")
            p.unlink()
        (ws.root / "work").rmdir()
        (ws.root / "work").symlink_to(tmp_path)
        with pytest.raises((ValueError, OSError)):
            ws.read("work/outside.json")
        assert outside.read_text() == '{"secret":1}'
    finally:
        ws.close()


@pytest.mark.parametrize("arm", ["D", "P", "F"])
def test_real_sdk_loop_common_transport_and_file_delivery(tmp_path, arm):
    p = task()
    ws = (
        Workspace(
            tmp_path / "workspace",
            {"task.json": json.dumps(p), "schema.json": json.dumps(p["output_schema"])},
        )
        if arm == "F"
        else None
    )
    calls = []
    payload = {"analyses": [{"scenario_id": "T1", "analysis": "业务分析"}], "supplements": []}

    def fake(url, key, body, timeout, retries):
        calls.append(body)
        assert retries == 0
        if arm == "F" and len(calls) == 1:
            return response(
                {
                    "tool": "workspace_write",
                    "arguments": {"path": "work/candidate.json", "content": json.dumps(payload)},
                }
            )
        if arm == "F" and len(calls) == 2:
            return response(
                {"tool": "workspace_read", "arguments": {"path": "work/candidate.json"}}
            )
        return response(payload)

    try:
        with runtime_factory(tmp_path / arm, arm, ws):
            result = harness.execute(p, config(), tmp_path / arm, tmp_path, arm, transport=fake)
        assert result["status"] == "delivered", result["errors"]
        assert len(calls) == (3 if arm == "F" else 1)
        if ws:
            assert len(ws.events) == 2
    finally:
        if ws:
            ws.close()


def test_direct_and_pi_first_request_identical(tmp_path):
    bodies = []

    def fake(url, key, body, *_):
        bodies.append(body)
        return response(
            {"analyses": [{"scenario_id": "T1", "analysis": "分析"}], "supplements": []}
        )

    for arm in ("D", "P"):
        with runtime_factory(tmp_path / arm, arm):
            r = harness.execute(task(), config(), tmp_path / arm, tmp_path, arm, transport=fake)
        assert r["status"] == "delivered", r["errors"]
    assert bodies[0] == bodies[1]


@pytest.mark.parametrize("arm", ["D", "F"])
def test_new_loops_share_five_request_validation_budget(tmp_path, arm):
    count = []

    def fake(*args):
        count.append(1)
        return response(
            {"analyses": [{"scenario_id": "WRONG", "analysis": "分析"}], "supplements": []}
        )

    with runtime_factory(tmp_path / arm, arm):
        value = harness.execute(task(), config(), tmp_path / arm, tmp_path, arm, transport=fake)
    assert value["status"] != "delivered" and len(count) == 5
    assert not (tmp_path / arm / "result.json").exists()


def test_node_permissions_reject_outside_files_and_child_process(tmp_path):
    import subprocess

    secret = tmp_path / "secret.json"
    secret.write_text("NOT_VISIBLE")
    program = """const fs=require('node:fs');const cp=require('node:child_process');
let blocked=[];for(const action of [()=>fs.readFileSync(process.argv[1]),()=>cp.execSync('echo forbidden')]) {
try { action();process.exit(3); } catch(error) {if(error.code!=='ERR_ACCESS_DENIED')throw error;blocked.push(error.permission);}}
console.log(JSON.stringify(blocked));"""
    value = subprocess.check_output(["node", "--permission", "-e", program, str(secret)], text=True)
    assert len(json.loads(value)) == 2


def test_new_unknown_stops_without_rewriting_shared_ledger(tmp_path):
    from file_experiment import OLD_UNKNOWN, safe_guard

    path = tmp_path / "ledger.json"
    value = {
        "limit": 100_000_000,
        "remaining_tokens": 99_000_000,
        "requests": {
            key: {"model": "ecnu-max", "status": "usage_unknown", "charged_tokens": charge}
            for key, charge in OLD_UNKNOWN.items()
        },
    }
    path.write_text(json.dumps(value))
    before = path.read_bytes()
    config = {"token_budget_ledger": str(path), "token_budget_limit": 100_000_000}
    assert safe_guard(config)["ready"] and path.read_bytes() == before
    value["requests"]["NEW"] = {
        "model": "ecnu-max",
        "status": "usage_unknown",
        "charged_tokens": 100,
    }
    path.write_text(json.dumps(value))
    before = path.read_bytes()
    assert safe_guard(config)["reason"] == "new_unknown_usage_stop" and path.read_bytes() == before


def test_infrastructure_failure_stops_but_bounded_business_failure_is_measured():
    from file_experiment import dispatch_failure_reason

    assert dispatch_failure_reason({"status": "blocked"})
    assert dispatch_failure_reason({"status": "runtime_failure"})
    assert dispatch_failure_reason({"status": "failed"}) is None
    assert dispatch_failure_reason({"status": "delivered"}) is None
