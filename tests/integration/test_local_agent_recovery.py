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
    monkeypatch.setattr(service, "start", lambda project: {"status": "running"})
    rerun(service, rid, {"task_key": "case:ssd-compare"})
    assert revision(p / "run", "case:ssd-compare") == 1
    assert service.conversation(rid, "case:ssd-compare").revision("case:ssd-compare") == 0
    service.pool.shutdown()
