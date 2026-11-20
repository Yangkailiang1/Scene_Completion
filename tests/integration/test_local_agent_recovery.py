import json
from copy import deepcopy

import pytest

from scene_completion.application.project_service import Workbench
from scene_completion.cli.main import main
from scene_completion.domain.contracts import packet
from scene_completion.domain.ssd_contracts import INSTRUCTIONS
from scene_completion.infrastructure.storage import write_json
from scene_completion.workflow.recovery.node_repair import (
    batch_id,
    export_repair,
    read_repair,
    submit_repair,
)


def project(tmp_path):
    service = Workbench(tmp_path / "data")
    meta = service.create(
        {
            "name": "Agent接管",
            "sources": {
                "RR": [{"name": "RR.md", "content": "# 正常需求\n查询。"}],
                "SR": [{"name": "SR.md", "content": "# 正常设计\n查询。"}],
            },
            "review_mode": "auto",
        }
    )
    return service, meta["id"], service.run_dir(meta["id"])


def compare_input(suffix):
    return {
        "pair": "GT_G",
        "pairs": [{"left": {"id": "GT-" + suffix}, "right": {"id": "G-" + suffix}}],
    }


def test_local_status_and_code_diagnosis_need_no_http(tmp_path, capsys, monkeypatch):
    service, rid, p = project(tmp_path)
    monkeypatch.setattr(
        "scene_completion.cli.main.API",
        lambda *a: (_ for _ in ()).throw(AssertionError("HTTP不得启动")),
    )
    assert main(["--local", "--data-dir", str(service.root), "status", "--project", rid]) == 0
    assert json.loads(capsys.readouterr().out)["project"] == rid
    write_json(p / "job.json", {"status": "error", "error_type": "RuntimeError"})
    write_json(
        p / "run/workflow_tasks.json",
        {
            "tasks": {
                "case:ssd-prepare": {
                    "status": "failed",
                    "stage": "ssd-prepare",
                    "identity": "case-v1",
                    "failure": {"error": "脚本故障"},
                }
            }
        },
    )
    exported = export_repair(p, "case:ssd-prepare")
    assert exported["kind"] == "code_failure"
    assert exported["handoff"]["state"] == "needs_agent"
    with pytest.raises(ValueError, match="代码故障"):
        submit_repair(p, "case:ssd-prepare", {"payload": {}, "note": "不能伪造输出"})
    service.pool.shutdown()


def test_multi_batch_repair_cannot_cross_batches_and_keeps_identity(tmp_path):
    service, rid, p = project(tmp_path)
    root = p / "run"
    write_json(
        root / "workflow_tasks.json",
        {
            "tasks": {
                "case:ssd-compare": {
                    "status": "rejected",
                    "identity": "task-v1",
                    "stage": "ssd-compare",
                    "failure": {"error": "缺少一对匹配"},
                }
            }
        },
    )
    packets = []
    for suffix in ["a", "b"]:
        item = packet("ssd-semantic-compare", compare_input(suffix), ["case"])
        item.update(node_key="case:ssd-compare", skill_text=INSTRUCTIONS)
        write_json(root / "packets" / f"{suffix}.json", item)
        packets.append(item)
    with pytest.raises(ValueError, match="多个语义批次"):
        export_repair(p, "case:ssd-compare")
    doc = export_repair(p, "case:ssd-compare", batch=batch_id(packets[1]))
    doc["payload"] = {
        "decisions": [
            {"left_id": "GT-b", "right_id": "G-b", "status": "partial", "reason": "语义覆盖"}
        ]
    }
    doc["note"] = "独立检查本批允许材料"
    assert submit_repair(p, "case:ssd-compare", doc, validate_only=True)["saved"] is False
    assert submit_repair(p, "case:ssd-compare", doc)["saved"]
    from scene_completion.review.decisions.node_conversations import Conversations

    guidance = Conversations(root).revision("case:ssd-compare")
    assert read_repair(root, packets[1], guidance)["payload"] == doc["payload"]
    assert read_repair(root, packets[0], guidance) is None
    wrong = deepcopy(doc)
    wrong["payload"]["decisions"][0]["left_id"] = "GT-a"
    with pytest.raises(ValueError):
        submit_repair(p, "case:ssd-compare", wrong)
    write_json(
        root / "workflow_tasks.json",
        {
            "tasks": {
                "case:ssd-compare": {
                    "status": "rejected",
                    "identity": "task-v2",
                    "stage": "ssd-compare",
                }
            }
        },
    )
    with pytest.raises(ValueError, match="过期"):
        submit_repair(p, "case:ssd-compare", doc)
    service.pool.shutdown()


def test_retry_and_exact_batch_submission_reuse_successful_batches(tmp_path):
    from scene_completion.application.execution import Execution
    from scene_completion.infrastructure.execution_events import EventStore, bind
    from scene_completion.workflow_core import TaskRejected

    calls = []

    def response(packet):
        suffix = packet["input"]["pairs"][0]["left"]["id"]
        calls.append(suffix)
        if suffix == "GT-b":
            return {"decisions": []}
        return {
            "decisions": [
                {"left_id": suffix, "right_id": "G-a", "status": "partial", "reason": "覆盖"}
            ]
        }

    root = tmp_path / "run"
    ex = Execution(root, mocks={"ssd-semantic-compare": response})
    record = {"case": "case", "rounds": 0}
    store = EventStore(root)
    with bind(store, task_key="case:ssd-compare", case="case", role="checker", attempt=1):
        ex.semantic("ssd-semantic-compare", compare_input("a"), record)
        with pytest.raises(TaskRejected):
            ex.semantic("ssd-semantic-compare", compare_input("b"), record)
    write_json(
        root / "workflow_tasks.json",
        {"tasks": {"case:ssd-compare": {"status": "rejected", "identity": "batch-v1"}}},
    )
    doc = export_repair(
        tmp_path,
        "case:ssd-compare",
        batch=batch_id({"task": "ssd-semantic-compare", "input": compare_input("b")}),
    )
    doc["payload"] = {
        "decisions": [
            {"left_id": "GT-b", "right_id": "G-b", "status": "partial", "reason": "本批独立对应"}
        ]
    }
    doc["note"] = "校验本批输入对应，补齐遗漏决定"
    submit_repair(tmp_path, "case:ssd-compare", doc)
    record["rounds"] = 1
    with bind(store, task_key="case:ssd-compare", case="case", role="checker", attempt=2):
        _, first_proof = ex.semantic("ssd-semantic-compare", compare_input("a"), record)
        _, second_proof = ex.semantic("ssd-semantic-compare", compare_input("b"), record)
    assert calls == ["GT-a", "GT-b"]
    assert first_proof["provider"] == "verified_batch_checkpoint"
    assert second_proof["provider"] == "external_code_agent_repair"


@pytest.mark.parametrize("repair", [False, True])
def test_entity_inference_drops_unrequested_operations_and_reuses_first_batch(tmp_path, repair):
    from scene_completion.application.execution import Execution
    from scene_completion.infrastructure.execution_events import EventStore, bind
    from scene_completion.infrastructure.storage import read_json
    from scene_completion.models.clients.deepagents_client import DeepAgentsClient
    from scene_completion.workflow_core import TaskRejected

    task, key = "ssd-entity-inference", "case:ssd-resolve"
    step_ids = [f"step-{i}" for i in range(7)]
    context = {"steps": [{"id": step_id} for step_id in step_ids], "definitions": {}}
    first = {
        **context,
        "operations": step_ids,
        "constraints": [{"id": f"rule-{i}"} for i in range(7)],
    }
    second = {
        **context,
        "operations": [],
        "constraints": [{"id": f"rule-{i}"} for i in range(7, 14)],
    }
    operations = [
        {"step_id": step_id, "crud": ["read"], "state": "operation", "reason": "证据"}
        for step_id in step_ids
    ]

    def constraints(inputs):
        return [
            {"rule_id": rule["id"], "state": "pending", "reason": "约束待确认", "bindings": []}
            for rule in inputs["constraints"]
        ]

    first_result = {"operations": operations, "constraints": constraints(first)}
    repeated = {
        "operations": [{**row, "crud": ["delete"]} for row in operations],
        "constraints": constraints(second),
    }
    second_result = {**repeated, "operations": []}
    sent = []

    def transport(url, api_key, body, *args):
        sent.append(body)
        if len(sent) == 1:
            result = first_result
        else:
            assert len(sent) == 2
            assert "本批 input.operations=[]" in json.dumps(body, ensure_ascii=False)
            result = (
                {**repeated, "constraints": repeated["constraints"][:-1]} if repair else repeated
            )
        return {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "submit",
                                "type": "function",
                                "function": {
                                    "name": "submit_result",
                                    "arguments": json.dumps({"payload": result}),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    root = tmp_path / "run"
    config = {
        "api_key": "offline-fixture",
        "base_url": "http://offline.test/v1",
        "agent_model": "offline",
        "run_root": str(root),
    }
    ex = Execution(
        root, mode="external", client=DeepAgentsClient(config, transport=transport), config=config
    )
    record = {"case": "case", "stage": "ssd-resolve", "rounds": 0}
    store = EventStore(root)
    second_batch = batch_id({"task": task, "input": second})
    with bind(store, task_key=key, case="case", role="checker", attempt=1):
        assert ex.semantic(task, first, record)[0] == first_result
        if repair:
            with pytest.raises(TaskRejected, match="本批每个来源"):
                ex.semantic(task, second, record)
        else:
            result, proof = ex.semantic(task, second, record)
            assert result == second_result
            raw_file = proof["execution_model_evidence"]["raw_payload_file"]
            assert read_json(root / raw_file)["payload"] == repeated
    if repair:
        write_json(
            root / "workflow_tasks.json",
            {"tasks": {key: {"status": "rejected", "identity": "case-v1"}}},
        )
        document = export_repair(tmp_path, key, batch=second_batch)
        document.update(payload=deepcopy(repeated), note="核对本批约束后补齐漏项")
        assert not submit_repair(tmp_path, key, document, validate_only=True)["saved"]
        assert document["payload"] == repeated
        assert submit_repair(tmp_path, key, document)["saved"]
        history = read_json(next((root / "external_repairs/history").glob("*.json")))
        assert history["raw_payload"] == repeated
        assert history["payload"] == second_result

    record["rounds"] = 1
    with bind(store, task_key=key, case="case", role="checker", attempt=2):
        first_value, first_proof = ex.semantic(task, first, record)
        second_value, second_proof = ex.semantic(task, second, record)
    assert first_value == first_result and second_value == second_result
    assert first_proof["provider"] == "verified_batch_checkpoint"
    assert second_proof["provider"] == (
        "external_code_agent_repair" if repair else "verified_batch_checkpoint"
    )
    assert len(sent) == 2
    event_kind = "external_repair_saved" if repair else "unrequested_operations_discarded"
    audit = [event["data"] for event in store.read(task_key=key) if event["kind"] == event_kind]
    assert len(audit) == 1
    assert audit[0]["semantic_batch"] == second_batch
    assert audit[0]["discarded_step_ids"] == step_ids


def test_wait_attaches_existing_worker_without_duplicate_dispatch(capsys):
    class RunningAPI:
        count = 0

        def call(self, path, body=None, method=None):
            if path.endswith("/execution-status"):
                self.count += 1
                return {
                    "event_cursor": 0,
                    "job": {"status": "running" if self.count == 1 else "complete"},
                    "execution_complete": self.count > 1,
                    "complete": self.count > 1,
                }
            if "/events/history" in path:
                return {"events": []}
            raise AssertionError("cannot dispatch or use HTTP: " + path)

    assert main(["run", "--project", "a" * 32, "--wait"], client=RunningAPI()) == 0
    assert '"attached": true' in capsys.readouterr().out


def test_dead_worker_cannot_expose_previous_completed_manifest(tmp_path, monkeypatch):
    service, rid, p = project(tmp_path)
    write_json(p / "job.json", {"status": "running", "pid": 999999, "worker_heartbeat": 0})
    write_json(p / "run/run_manifest.json", {"complete": True, "execution_complete": True})
    write_json(p / "run/workflow_graph.json", {"nodes": [{"id": "case:ssd-compare"}]})
    write_json(
        p / "run/workflow_tasks.json", {"tasks": {"case:ssd-compare": {"status": "running"}}}
    )
    monkeypatch.setattr(
        "scene_completion.infrastructure.worker_runtime.pid_alive", lambda pid: False
    )
    status = service.execution_status(rid)
    assert not status["execution_complete"] and status["job"]["status"] == "interrupted"
    assert status["recovery_handoff"]["state"] == "needs_agent"
    assert status["recovery_handoff"]["nodes"][0]["category"] == "code_failure"
    service.pool.shutdown()


def test_code_rerun_does_not_change_model_guidance(tmp_path, monkeypatch):
    from scene_completion.application.node_recovery_service import rerun
    from scene_completion.infrastructure.code_retry import revision

    service, rid, p = project(tmp_path)
    write_json(
        p / "run/workflow_tasks.json",
        {
            "tasks": {
                "case:ssd-compare": {
                    "status": "failed",
                    "failure": {"traceback": "fixture code stack"},
                }
            }
        },
    )
    monkeypatch.setattr(service, "_start", lambda project, options: {"status": "running"})
    rerun(service, rid, {"task_key": "case:ssd-compare"})
    assert revision(p / "run", "case:ssd-compare") == 1
    assert service.conversation(rid, "case:ssd-compare").revision("case:ssd-compare") == 0
    service.pool.shutdown()


@pytest.mark.parametrize("local", [True, False])
@pytest.mark.parametrize("successful", [False, True])
def test_rerun_waits_for_dispatched_scope_once(tmp_path, monkeypatch, capsys, local, successful):
    from fastapi.testclient import TestClient

    from scene_completion.api.application import create_app
    from scene_completion.infrastructure.execution_events import EventStore

    service, rid, location = project(tmp_path)
    key = "case-a:ssd-prepare"
    write_json(
        location / "job.json",
        {"status": "waiting", "started_at": 1, "run_options": {"case_ids": ["case-a"]}},
    )
    write_json(
        location / "run/workflow_graph.json",
        {"nodes": [{"id": key, "case": "case-a"}, {"id": "case-b:ssd-prepare", "case": "case-b"}]},
    )
    write_json(
        location / "run/workflow_tasks.json",
        {"tasks": {key: {"status": "failed", "case": "case-a", "stage": "ssd-prepare"}}},
    )
    events = EventStore(location / "run")
    events.append("fixture_old")
    old = events.latest_id()
    starts = []

    def finish_immediately(self, project_id, options=None):
        assert project_id == rid
        starts.append(options)
        events.append("fixture_rerun", task_key=key)
        write_json(
            location / "job.json",
            {
                "status": "complete_with_questions" if successful else "waiting",
                "started_at": 2,
                "run_options": options,
            },
        )
        write_json(
            location / "run/run_manifest.json",
            {"execution_complete": successful, "complete": False, "pending_count": 1},
        )
        compare = "case-a:ssd-compare"
        write_json(
            location / "run/workflow_graph.json",
            {"nodes": [{"id": key, "case": "case-a"}, {"id": compare, "case": "case-a"}]},
        )
        write_json(
            location / "run/workflow_tasks.json",
            {
                "tasks": {
                    key: {"status": "passed", "case": "case-a", "stage": "ssd-prepare"},
                    compare: {
                        "status": "passed" if successful else "failed",
                        "case": "case-a",
                        "stage": "ssd-compare",
                    },
                }
            },
        )
        return {"status": "running", "project_id": rid, "started_at": 2}

    monkeypatch.setattr(Workbench, "_start", finish_immediately)
    args = ["rerun", "--project", rid, "--node", key, "--wait"]
    if local:
        result = main(["--local", "--data-dir", str(service.root), *args])
    else:
        with TestClient(create_app(service.root)) as client:

            class HttpAPI:
                def call(self, path, body=None, method=None):
                    response = client.request(
                        method or ("POST" if body is not None else "GET"), "/api/" + path, json=body
                    )
                    assert response.is_success, response.text
                    return response.json()

            result = main(args, client=HttpAPI())
    assert result == (0 if successful else 2)
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row["kind"] for row in rows] == ["started", "execution_event", "status", "finished"]
    assert rows[1]["event_cursor"] > old
    assert rows[-1]["execution_complete"] is successful and not rows[-1]["review_complete"]
    assert starts == [{"case_ids": ["case-a"]}]
    service.pool.shutdown()


def test_rerun_wait_timeout_stops_polling_not_the_worker(monkeypatch, capsys):
    rid = "a" * 32
    now = iter([0.0, 2.0])
    monkeypatch.setattr("scene_completion.cli.main.time.monotonic", lambda: next(now))
    seen = []

    class Running:
        def call(self, path, body=None, method=None):
            seen.append(path.rsplit("/", 1)[-1].split("?", 1)[0])
            if path.endswith("/rerun-node"):
                return {"project_id": rid, "started_at": 2}
            if path.endswith("/execution-status"):
                return {"event_cursor": 0, "job": {"status": "running", "started_at": 2}}
            return {"events": []}

    assert (
        main(
            ["rerun", "--project", rid, "--node", "test", "--wait", "--timeout", "1"],
            client=Running(),
        )
        == 3
    )
    assert seen == ["execution-status", "rerun-node", "execution-status", "history"]
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["kind"] == "detached"


def test_rerun_dry_run_and_unstarted_affected_plan_do_not_wait(capsys):
    rid = "a" * 32

    class PreviewAPI:
        calls = []

        def call(self, path, body=None, method=None):
            self.calls.append(path)
            if path.endswith("/execution-status"):
                return {"event_cursor": 7}
            if path.endswith("/rerun-affected"):
                return {"started": False}
            raise AssertionError(path)

    api = PreviewAPI()
    assert (
        main(["rerun", "--project", rid, "--node", "test", "--wait", "--dry-run"], client=api) == 0
    )
    assert api.calls == []
    assert not json.loads(capsys.readouterr().out)["saved"]
    assert (
        main(["rerun", "--project", rid, "--affected", "--plan-id", "plan", "--wait"], client=api)
        == 0
    )
    assert len(api.calls) == 2 and not json.loads(capsys.readouterr().out)["started"]


def test_rerun_rejects_live_worker_and_bounds_older_case_scope(tmp_path, monkeypatch):
    import time

    from scene_completion.application.node_recovery_service import rerun
    from scene_completion.infrastructure.code_retry import revision

    service, rid, p = project(tmp_path)
    key = "case-a:ssd-prepare"
    write_json(p / "run/workflow_tasks.json", {"tasks": {key: {"status": "failed"}}})
    write_json(p / "job.json", {"status": "running", "worker_heartbeat": time.time()})
    with pytest.raises(ValueError, match="worker仍在运行"):
        rerun(service, rid, {"task_key": key})
    assert revision(p / "run", key) == 0
    write_json(p / "job.json", {"status": "waiting"})
    monkeypatch.setattr(service, "_start", lambda project, options: options)
    assert rerun(service, rid, {"task_key": key}) == {"case_ids": ["case-a"]}
    service.pool.shutdown()


def test_rerun_reserves_one_worker_before_spawn_and_serializes_retry(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from scene_completion.application.node_recovery_service import rerun
    from scene_completion.infrastructure import worker_runtime as worker
    from scene_completion.infrastructure.code_retry import revision

    service, rid, directory = project(tmp_path)
    key = "case-a:ssd-prepare"
    root = directory / "run"
    write_json(root / "workflow_tasks.json", {"tasks": {key: {"status": "failed"}}})
    monkeypatch.setattr(
        service, "model_config", lambda _: {"api_key": "fixture", "base_url": "http://offline.test"}
    )
    launches = []

    def spawn(_, project_id, token):
        assert project_id == rid
        job = worker.read_job(directory)
        assert job["worker_token"] == token and job["status"] == "running" and "pid" not in job
        with pytest.raises(ValueError, match="run already active"):
            rerun(service, rid, {"task_key": key})
        claimed = worker.register_worker(directory, token, 123)
        assert claimed["pid"] == 123 and worker.register_worker(directory, token, 456) is None
        launches.append(token)
        assert worker.update_job(directory, claimed, status="complete")["worker_token"] == token
        return SimpleNamespace(wait=lambda: 0)

    monkeypatch.setattr(worker, "spawn", spawn)
    dispatch = rerun(service, rid, {"task_key": key})
    assert dispatch["status"] == "running" and len(launches) == 1
    assert worker.read_job(directory)["run_options"] == {"case_ids": ["case-a"]}
    assert revision(root, key) == 1
    service.pool.shutdown()


def test_finished_job_retains_dispatch_identity_and_case_selection(tmp_path, monkeypatch):
    from scene_completion.infrastructure.storage import read_json

    service, rid, p = project(tmp_path)
    service.client_factory = lambda config, root: object()
    started_at = 123
    options = {"case_ids": ["case-a"], "priority_cases": ["case-a"]}
    write_json(
        p / "job.json", {"status": "running", "started_at": started_at, "run_options": options}
    )

    class Execution:
        gate = None

        def __init__(self, *args, case_ids, **kwargs):
            assert case_ids == options["case_ids"]

        def finish(self):
            return {"complete": True}

    monkeypatch.setattr("scene_completion.application.execution.Execution", Execution)
    monkeypatch.setattr(
        "scene_completion.application.execution.build_pipeline", lambda *a, **k: None
    )
    service._execute(rid)
    terminal = read_json(p / "job.json")
    assert terminal["status"] == "complete"
    assert terminal["started_at"] == started_at and terminal["run_options"] == options
    service.pool.shutdown()
