"""Input-bound external repair handoff; never edits official artifacts directly."""

from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from scene_completion.analysis.validation import SSD_CANONICAL_SUBMISSIONS, validate_result
from scene_completion.domain.contracts import PROTOCOL, registry
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json


def project_scoped(fn):
    """CLI and direct callers must bind repairs to the executing project's registry."""

    @wraps(fn)
    def call(project, *args, **kwargs):
        from scene_completion.domain.concern_registry import registry_scope
        from scene_completion.review.decisions.project_review import project_registry

        with registry_scope(project_registry(Path(project))):
            return fn(project, *args, **kwargs)

    return call


def path(root, key, batch=None):
    identity = [key, batch] if batch else key
    return Path(root) / "external_repairs" / (fingerprint(identity) + ".json")


def batch_id(packet):
    return fingerprint([packet["task"], packet["input"]])[:24]


def batch_inventory(root, key):
    rows = {}
    for file in sorted((Path(root) / "packets").glob("*.json"), key=lambda p: p.stat().st_mtime_ns):
        packet = read_json(file)
        if packet.get("node_key") == key:
            bid = batch_id(packet)
            rows[bid] = {
                "batch": bid,
                "task": packet["task"],
                "input_hash": fingerprint(packet["input"]),
                "packet_file": str(file.relative_to(root)),
            }
    return list(rows.values())


def repair_revision(root, key):
    batches = []
    for file in (Path(root) / "external_repairs").glob("*.json"):
        value = read_json(file)
        if value.get("binding", {}).get("node_key") == key and value.get("batch"):
            batches.append(value)
    if batches:
        return fingerprint(sorted(batches, key=lambda row: row["batch"]))
    p = path(root, key)
    return fingerprint(read_json(p)) if p.exists() else None


def binding(packet, guidance):
    return {
        "protocol": PROTOCOL,
        "semantic_version": packet.get("semantic_version")
        or __import__(
            "scene_completion.workflow.semantics", fromlist=["code_version"]
        ).code_version(packet["task"]),
        "task": packet["task"],
        "node_key": packet["node_key"],
        "input_hash": fingerprint(packet["input"]),
        "schema_hash": fingerprint(packet["output_schema"]),
        "skill_hash": fingerprint(packet.get("skill_text", "")),
        "instructions_hash": fingerprint(packet.get("instructions", "")),
        "guidance_revision": guidance,
        "registry_hash": packet.get("registry_hash") or registry()["hash"],
    }


def packet_for(root, key, batch=None):
    rows = []
    for p in (Path(root) / "packets").glob("*.json"):
        v = read_json(p)
        if v.get("node_key") == key and (batch is None or batch_id(v) == batch):
            rows.append((p.stat().st_mtime_ns, v))
    if not rows:
        raise ValueError("节点尚无任务包，不能导出修复上下文")
    if batch is None and len({batch_id(p) for _, p in rows}) > 1:
        raise ValueError("节点有多个语义批次，请使用--batch指定；diagnose交接包包含全部批次编号")
    return max(rows, key=lambda row: row[0])[1]


@project_scoped
def export_repair(project, key, batch=None):
    root = Path(project) / "run"
    state = read_json(root / "workflow_tasks.json")["tasks"]
    r = state.get(key)
    if not r or r.get("status") in {"passed", "running", "awaiting_answer", "blocked_dependency"}:
        raise ValueError("请选择失败或配置阻塞的真实节点；运行中节点和待回答问题不能通过修复绕过")
    if (
        r.get("status") == "failed" and r.get("failure", {}).get("traceback")
    ) or not batch_inventory(root, key):
        from scene_completion.application.recovery_handoff import prepare_handoff

        return {
            "kind": "code_failure",
            "node_key": key,
            "state_identity": r.get("identity"),
            "handoff": prepare_handoff(project),
            "instructions": "该节点没有模型任务包。先修复源码并检查，再通过run继续；不接受业务payload覆盖脚本结果。",
        }
    failure_text = str(r.get("failure") or {}).lower()
    if any(
        k in failure_text
        for k in (
            "budget_exhausted",
            "quota",
            "insufficient_balance",
            "unknown_usage",
            "usage_unresolved",
            "insufficient_remaining_allowance",
        )
    ):
        raise ValueError("额度或未决用量阻塞不能通过业务修复绕过，请先处理账本或配置")
    p = packet_for(root, key, batch)
    from scene_completion.domain.contracts import schema
    from scene_completion.workflow.semantics import code_version

    if (
        p.get("semantic_version") and p["semantic_version"] != code_version(p["task"])
    ) or fingerprint(p["output_schema"]) != fingerprint(schema(p["task"])):
        raise ValueError("任务包语义版本或Schema已过期，请先run刷新对应失败批次，再重新导出")
    from scene_completion.review.decisions.node_conversations import Conversations

    revision = Conversations(root).revision(key)
    candidate = None
    for f in sorted(
        (root / "agent_rejections").glob("*.json"), key=lambda f: f.stat().st_mtime_ns, reverse=True
    ):
        v = read_json(f)
        if v.get("node_key") == key and v.get("input_hash") == fingerprint(p["input"]):
            candidate = v.get("payload")
            break
    rejected = (r.get("failure") or {}).get("rejected_output")
    if rejected:
        file = (root / rejected).resolve()
        if file.is_relative_to(root.resolve()) and file.is_file():
            value = read_json(file)
            if (
                value.get("task") == p["task"]
                and value.get("node_key") == key
                and value.get("input_hash") == fingerprint(p["input"])
            ):
                candidate = value.get("payload")
    if candidate is None and isinstance(p.get("repair", {}).get("candidate"), dict):
        candidate = deepcopy(p["repair"]["candidate"])
    return {
        "batch": batch_id(p),
        "binding": binding(p, revision),
        "state_identity": r.get("identity"),
        "task_packet": p,
        "failure": r.get("failure"),
        "payload": candidate,
        "note": "",
        "instructions": "仅修改payload及note。输入为本节点允许材料，不读取其他通道。提交须通过Schema、来源及语义边界校验；不会直接覆盖正式产物。",
    }


@project_scoped
def submit_repair(project, key, document, *, validate_only=False):
    current = export_repair(project, key, batch=document.get("batch"))
    if current.get("kind") == "code_failure":
        raise ValueError("代码故障须修源码后恢复，不能提交业务JSON绕过")
    if (
        document.get("binding") != current["binding"]
        or document.get("state_identity") != current["state_identity"]
    ):
        raise ValueError("修复上下文已过期，请重新导出；不得提交到其他节点/版本")
    value = document.get("payload")
    p = current["task_packet"]
    if not isinstance(value, dict):
        raise ValueError("payload必须是完整业务JSON对象")
    from jsonschema import Draft202012Validator

    raw_payload = value
    if p["task"] in SSD_CANONICAL_SUBMISSIONS:
        value = deepcopy(value)
    if p["task"] == "ssd-ground-align":
        from scene_completion.analysis.ssd.grounding import strip_align_summary

        strip_align_summary(value)
    errors = list(Draft202012Validator(p["output_schema"]).iter_errors(value))
    if errors:
        raise ValueError("修复不满足冻结Schema：" + errors[0].message)
    validate_result(p["task"], value, p["input"])
    if p["task"] == "components" and any(p["input"].values()) and not value["components"]:
        raise ValueError("非空需求不得用空组成跳过节点")
    if p["task"] in {"rr-ssd", "sr-ssd"} and any(p["input"].values()) and not value["interactions"]:
        raise ValueError("非空需求不得用空SSD跳过节点")
    note = document.get("note", "")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("提交修复须填写note说明修改及依据")
    if validate_only:
        return {"valid": True, "saved": False, "task_key": key}
    audit = {"semantic_batch": batch_id(p)} if raw_payload != value else {}
    if audit and p["task"] == "ssd-entity-inference":
        audit["discarded_step_ids"] = [
            operation["step_id"] for operation in raw_payload["operations"]
        ]
    if audit and "records" in value:
        accepted_ids = {record["record_id"] for record in value["records"]}
        audit["discarded_record_ids"] = [
            record["record_id"]
            for record in raw_payload["records"]
            if record["record_id"] not in accepted_ids
        ]
    target = path(Path(project) / "run", key, document.get("batch"))
    old = read_json(target) if target.exists() else {}
    row = {
        "batch": document.get("batch"),
        "binding": current["binding"],
        "payload": deepcopy(value),
        "note": note,
        "revision": old.get("revision", 0) + 1,
        "previous_failure": current["failure"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    history = {**row, **({"raw_payload": raw_payload, **audit} if audit else {})}
    write_json(target.parent / "history" / (fingerprint(history) + ".json"), history)
    write_json(target, row)
    from scene_completion.infrastructure.execution_events import EventStore

    EventStore(Path(project) / "run").append(
        "external_repair_saved", task_key=key, revision=row["revision"], note=note, **audit
    )
    return {
        "valid": True,
        "saved": True,
        "task_key": key,
        "revision": row["revision"],
        "next": "run继续原流水线，复用通过校验的修复；独立任务不受此节点阻塞影响",
    }


def read_repair(root, packet, guidance):
    f = path(root, packet["node_key"], batch_id(packet))
    if not f.exists():
        f = path(root, packet["node_key"])
    if not f.exists():
        for other in (Path(root) / "external_repairs").glob("*.json"):
            candidate = read_json(other)
            if candidate.get("binding", {}).get("node_key") == packet["node_key"]:
                from scene_completion.infrastructure.execution_events import EventStore

                expected = binding(packet, guidance)
                EventStore(root).append(
                    "external_repair_not_reused",
                    task_key=packet["node_key"],
                    revision=candidate.get("revision"),
                    changed_fields=[
                        k for k in expected if candidate["binding"].get(k) != expected[k]
                    ],
                    reason="修复属于其他批次或输入，未采用",
                )
                break
        return None
    row = read_json(f)
    expected = binding(packet, guidance)
    if row["binding"] != expected:
        from scene_completion.infrastructure.execution_events import EventStore

        EventStore(root).append(
            "external_repair_not_reused",
            task_key=packet["node_key"],
            revision=row.get("revision"),
            changed_fields=[k for k in expected if row["binding"].get(k) != expected[k]],
            reason="修复包与当前输入或项目版本不同；未将过期修复用作正式结果",
        )
        return None
    return row
