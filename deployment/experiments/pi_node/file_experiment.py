#!/usr/bin/env python3
"""Explicit Pi-with-files vs ordinary LLM paired experiment, outside formal results."""

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "src"), str(HERE)]
import harness  # noqa: E402
from file_runtime import runtime_factory  # noqa: E402
from workspace_tools import Workspace  # noqa: E402

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json  # noqa: E402
from scene_completion.models.configuration.model_settings import resolve  # noqa: E402
from scene_completion.workflow_core import run_lock  # noqa: E402

ARMS = {"D": "普通LLM接口循环", "F": "Pi SDK＋受限JSON文件工具"}
OLD_UNKNOWN = {"b174f91ddacd42c69da75701cd51db68": 69098, "09e165e3e73c451e9d1b0a044fdf5330": 94342}


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_identity():
    paths = (
        sorted((REPO / "src").rglob("*.py"))
        + sorted((REPO / "src").rglob("*.json"))
        + sorted(HERE.glob("*.py"))
        + sorted(HERE.glob("*.mjs"))
        + [HERE / "package-lock.json"]
    )
    return fingerprint({str(p.relative_to(REPO)): hash_file(p) for p in paths})


def configuration(manifest):
    path = Path(manifest["source_config"])
    config = resolve(read_json(path), manifest["source_env_file"], path.parent.parent)
    if config.get("agent_model") != "ecnu-max" or config.get("token_budget_limit") != 100_000_000:
        raise ValueError("existing model and 100M shared authorization required")
    config.pop("_experiment_acknowledged_unknown", None)
    config.pop("_experiment_continue_unknown_usage", None)
    config["unknown_usage_policy"] = "stop"
    config["acknowledged_unknown_requests"] = OLD_UNKNOWN
    return config


def safe_guard(config):
    ledger = read_json(config["token_budget_ledger"])
    if ledger["limit"] != config["token_budget_limit"]:
        raise ValueError("shared authorization identity changed")
    unknown = [
        k
        for k, r in ledger["requests"].items()
        if r["status"] == "usage_unknown"
        and not (
            k in OLD_UNKNOWN
            and r.get("charged_tokens") == OLD_UNKNOWN[k]
            and r.get("model") == "ecnu-max"
        )
    ]
    active = [k for k, r in ledger["requests"].items() if r["status"] == "reserved"]
    return {
        "ready": not unknown and not active,
        "reason": "new_unknown_usage_stop" if unknown else "requests_in_flight" if active else None,
        "unknown_ids": unknown,
        "active_ids": active,
        "remaining_tokens": ledger["remaining_tokens"],
    }


def dispatch_failure_reason(result):
    # Infrastructure/configuration failures stop new paid executions. A node
    # exhausting its validation budget remains a normal measured failure.
    return (
        "node_infrastructure_failure"
        if result["status"] in {"blocked", "runtime_failure"}
        else None
    )


def metrics(root, state):
    candidates = 0
    parsed = 0
    for path in (Path(root) / "wire").glob("*-response.json"):
        value = read_json(path)["choices"][0]["message"]
        try:
            decoded = json.loads(value.get("content") or "")
            parsed += 1
        except (ValueError, TypeError):
            candidates += 1
            continue
        if (
            isinstance(decoded, dict)
            and set(decoded) == {"tool", "arguments"}
            and decoded["tool"] != "submit_result"
        ):
            continue
        if isinstance(decoded, dict) and set(decoded) == {"clarification"}:
            continue
        candidates += 1
    return {
        "submission_candidates": candidates,
        "first_submission_passed": state == "delivered" and candidates == 1,
        "repair_attempts": max(candidates - 1, 0),
        "validation_rejections": max(candidates - int(state == "delivered"), 0),
        "parseable_responses": parsed,
        "metrics_version": "file-protocol-candidates-v1",
    }


def freeze(args):
    original = Path(args.source).resolve()
    old = read_json(original / "manifest.json")
    root = Path(args.output).resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("freeze directory must be empty")
    if root == original or root.is_relative_to(original):
        raise ValueError("new experiment must not write the original experiment")
    manifest = {
        "schema": "scene-pi-file-experiment-v1",
        "created_unix": time.time(),
        "historical_experiment": str(original),
        "historical_manifest_hash": hash_file(original / "manifest.json"),
        "source_config": old["source_config"],
        "source_env_file": old["source_env_file"],
        "requested_model": "ecnu-max",
        "arms": ARMS,
        "samples": old["samples"],
        "pilot_ids": old["pilot_ids"],
        "repetitions": 2,
        "planned_executions": 72,
        "max_model_requests_per_execution": 5,
        "code_identity": code_identity(),
        "sdk": old["sdk"],
        "old_unknown_exact_exemption": OLD_UNKNOWN,
        "new_unknown_policy": "stop_dispatch_no_refund_no_resend",
        "cache_policy": "fresh_sessions_no_answer_reuse",
        "business_prompt_schema_inputs": "identical; only capability schemas and procedure notice differ",
        "inference_scope_note": "historical project-scope E/GT batches retained as benchmark, not current workflow tasks",
        "causal_limit": "two arms compare bundled runtime and file capability, not isolated causal effect of file access",
    }
    config = configuration(manifest)
    guard = safe_guard(config)
    if not guard["ready"]:
        raise ValueError(json.dumps(guard))
    ledger = read_json(config["token_budget_ledger"])
    write_json(root / "authorization-before.json", ledger)
    (root / "checklists").mkdir(parents=True, exist_ok=True)
    for sample in old["samples"]:
        packet = read_json(original / "samples" / (sample["id"] + ".json"))
        if fingerprint(packet) != sample["packet_hash"]:
            raise ValueError("old frozen sample changed")
        write_json(root / "samples" / (sample["id"] + ".json"), packet)
        shutil.copy2(
            original / "checklists" / (sample["id"] + ".json"),
            root / "checklists" / (sample["id"] + ".json"),
        )
    if (original / "review-sources").exists():
        shutil.copytree(original / "review-sources", root / "review-sources")
    review_reference = original.parent / "source-reference.json"
    shutil.copy2(review_reference, root / "source-reference.json")
    manifest["source_reference_hash"] = hash_file(root / "source-reference.json")
    manifest["review_sources"] = {
        str(p.relative_to(root)): hash_file(p)
        for p in (root / "review-sources").rglob("*")
        if p.is_file()
    }
    write_json(root / "manifest.json", manifest)
    write_json(
        root / "blinding-private.json",
        {
            f"{s['id']}-{r}-{a}": fingerprint([manifest["created_unix"], s["id"], r, a])[:16]
            for s in old["samples"]
            for r in (1, 2)
            for a in ARMS
        },
    )
    return {
        "status": "frozen",
        "planned_executions": 72,
        "remaining_shared_tokens": guard["remaining_tokens"],
    }


def load(root):
    manifest = read_json(root / "manifest.json")
    if manifest["code_identity"] != code_identity():
        raise ValueError("code changed: freeze or explicitly audit a runtime amendment")
    for sample in manifest["samples"]:
        if (
            fingerprint(read_json(root / "samples" / (sample["id"] + ".json")))
            != sample["packet_hash"]
        ):
            raise ValueError("frozen sample changed")
    for p, h in manifest["review_sources"].items():
        if hash_file(root / p) != h:
            raise ValueError("frozen review source changed")
    if hash_file(root / "source-reference.json") != manifest["source_reference_hash"]:
        raise ValueError("pre-run review reference changed")
    return manifest, configuration(manifest)


def schedule(manifest):
    all_ids = [s["id"] for s in manifest["samples"]]
    pilot = manifest["pilot_ids"]
    groups = [pilot, [s for s in all_ids if s not in pilot]]
    for names in groups:
        for repeat in (1, 2):
            for name in names:
                ix = all_ids.index(name)
                order = ("D", "F") if (ix + repeat) % 2 else ("F", "D")
                for arm in order:
                    yield name, repeat, arm


def blind(root, manifest):
    mapping = read_json(root / "blinding-private.json")
    for path in (root / "executions").glob("*/result.json"):
        summary = read_json(path.parent / "summary.json")
        value = read_json(path)
        value.pop("execution_model_evidence", None)
        rid = mapping[path.parent.name]
        write_json(
            root / "blind-review" / (rid + ".json"),
            {
                "review_id": rid,
                "input_hash": summary["input_hash"],
                "result_hash": fingerprint(value),
                "result": value,
            },
        )


def status(root):
    manifest = read_json(root / "manifest.json")
    rows = [read_json(p) for p in (root / "executions").glob("*/summary.json")]

    def aggregate(arm):
        own = [r for r in rows if r["arm"] == arm]
        return {
            "executions": len(own),
            "delivered": sum(r["status"] == "delivered" for r in own),
            "first_submission_passed": sum(r["first_submission_passed"] for r in own),
            **{
                k: sum(r[k] for r in own)
                for k in (
                    "sent_requests",
                    "reported_tokens",
                    "accounted_tokens",
                    "repair_attempts",
                    "unknown_usage_calls",
                    "elapsed_seconds",
                )
            },
            "file_using_executions": sum(r.get("workspace_events", 0) > 0 for r in own),
        }

    return {
        "completed": len(rows),
        "planned": manifest["planned_executions"],
        "arms": {a: aggregate(a) for a in ARMS},
    }


def run(args):
    root = Path(args.output).resolve()
    manifest, config = load(root)
    with run_lock(root):
        for name, repeat, arm in schedule(manifest):
            if args.phase == "pilot" and name not in manifest["pilot_ids"]:
                continue
            key = f"{name}-{repeat}-{arm}"
            target = root / "executions" / key
            if (target / "summary.json").exists():
                continue
            if target.exists():
                raise ValueError("interrupted execution requires audit; never resend: " + key)
            guard = safe_guard(config)
            if not guard["ready"]:
                write_json(root / "dispatch-stop.json", guard)
                return {"status": "blocked", **guard, **status(root)}
            packet = read_json(root / "samples" / (name + ".json"))
            if guard["remaining_tokens"] < harness.estimate_pair(packet, config):
                return {"status": "budget_stop", **status(root)}
            ws = None
            if arm == "F":
                workspace_root = root / "workspaces" / key
                workspace_root.parent.mkdir(exist_ok=True)
                ws = Workspace(
                    workspace_root,
                    {
                        "task.json": json.dumps(packet, ensure_ascii=False, indent=2),
                        "schema.json": json.dumps(
                            packet["output_schema"], ensure_ascii=False, indent=2
                        ),
                    },
                )
            try:
                with (
                    patch.object(harness, "ledger_guard", safe_guard),
                    patch.object(harness, "submission_metrics", metrics),
                    runtime_factory(target, arm, ws),
                ):
                    result = harness.execute(packet, config, target, root, arm)
                result["workspace_events"] = len(ws.events) if ws else 0
                result["workspace_writes"] = (
                    sum(e["tool"] == "workspace_write" for e in ws.events) if ws else 0
                )
                result["workspace_edits"] = (
                    sum(e["tool"] == "workspace_edit" for e in ws.events) if ws else 0
                )
                result["runtime"] = (
                    "plain_llm_loop" if arm == "D" else "pi_sdk_1.5.2_restricted_files"
                )
                result["first_request_delivered"] = (
                    result["status"] == "delivered" and result["sent_requests"] == 1
                )
                write_json(target / "summary.json", result)
                if ws:
                    write_json(target / "workspace-events.json", ws.events)
                if (target / "result.json").exists():
                    value = read_json(target / "result.json")
                    value["execution_model_evidence"]["provider"] = result["runtime"]
                    write_json(target / "result.json", value)
                print(
                    json.dumps(
                        {
                            "execution": key,
                            "status": result["status"],
                            "calls": result["sent_requests"],
                            "tokens": result["accounted_tokens"],
                            "file_events": result["workspace_events"],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            finally:
                if ws:
                    ws.close()
            blind(root, manifest)
            write_json(root / "progress.json", status(root))
            reason = dispatch_failure_reason(result)
            if reason:
                stop = {"status": "blocked", "reason": reason, "execution": key, **status(root)}
                write_json(root / "dispatch-stop.json", stop)
                return stop
            guard = safe_guard(config)
            if not guard["ready"]:
                write_json(root / "dispatch-stop.json", guard)
                return {"status": "blocked", **guard, **status(root)}
    return {"status": "phase_complete", **status(root)}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--source", required=True)
    f.add_argument("--output", required=True)
    for cmd in ("run", "resume", "status"):
        p = sub.add_parser(cmd)
        p.add_argument("--output", required=True)
        if cmd != "status":
            p.add_argument("--phase", choices=["pilot", "all"], default="all")
    args = parser.parse_args()
    value = (
        freeze(args)
        if args.command == "freeze"
        else status(Path(args.output))
        if args.command == "status"
        else run(args)
    )
    print(json.dumps(value, ensure_ascii=False), flush=True)
    return 2 if value.get("status") in ("blocked", "budget_stop") else 0


if __name__ == "__main__":
    raise SystemExit(main())
