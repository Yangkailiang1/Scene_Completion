#!/usr/bin/env python3
"""Explicit opt-in Pi experiment. No imports into the production application."""

import argparse
import hashlib
import html
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

from evaluation import compare, public_result, submit_review  # noqa: E402
from harness import (  # noqa: E402
    ACKNOWLEDGED_UNKNOWN,
    LIMIT,
    ExperimentBlocked,
    cap_for,
    estimate_pair,
    execute,
    experiment_config,
    ledger_guard,
    submission_metrics,
)

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json  # noqa: E402
from scene_completion.models.configuration.model_settings import resolve  # noqa: E402
from scene_completion.workflow.semantics import code_version  # noqa: E402
from scene_completion.workflow_core import run_lock  # noqa: E402

STRATA = {
    "binding": ("ssd-bind", None),
    "existing": ("project-scope-identify", "E"),
    "test": ("project-scope-identify", "GT"),
    "generation": ("ssd-generate", None),
    "comparison": ("ssd-semantic-compare", None),
}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_identity():
    # No production/code edits can silently change an unfinished experiment.
    files = sorted((REPO / "src").rglob("*.py"))
    files += sorted((REPO / "src").rglob("*.json"))
    files += sorted((REPO / "src").rglob("*.md"))
    files += sorted(HERE.glob("*.py")) + sorted(HERE.glob("*.mjs"))
    files += [HERE / "package-lock.json"]
    return fingerprint({str(p.relative_to(REPO)): file_hash(p) for p in files})


def config_for(args):
    raw = read_json(args.config)
    return resolve(raw, args.env_file, Path(args.config).resolve().parent.parent)


def config_identity(config):
    # Credential values never enter manifests or reports.
    clean = {k: v for k, v in config.items() if k not in {"api_key", "_live_env_file"}}
    return fingerprint(experiment_config(clean, Path("EXPERIMENT_SESSION")))


def checklist(packet):
    inputs = packet["input"]
    return {
        "task": packet["task"],
        "channel": inputs.get("channel"),
        "scope": inputs.get("scope", "interaction"),
        "required_template_ids": [r["id"] for r in inputs.get("templates", [])],
        "source_record_ids": [r["id"] for r in inputs.get("records", [])],
        "pair_ids": [[r["left"]["id"], r["right"]["id"]] for r in inputs.get("pairs", [])],
        "checks": [
            "字段、步骤和锚点必须来自冻结输入，检查方向及CRUD，保留人工覆盖。",
            "逐条核对原始记录的失败条件、排除和pending，不以旧模型结果为真值。",
            "固定模板全部保留，分析具体且不虚构接口、阈值或响应。",
            "不同失败值与相反上下界不因关注点相同而匹配。",
            "业务正确性必须独立核对，Schema通过不等于业务正确。",
        ],
        "review_status": "requires_blinded_source_review",
    }


def freeze(args):
    root = Path(args.output).resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Freeze output must be empty; frozen experiments are immutable")
    source = Path(args.project).resolve()
    if root == source or root.is_relative_to(source):
        raise ValueError("Experiment output must be outside the formal source project")
    config = config_for(args)
    if config.get("agent_model") != "ecnu-max":
        raise ValueError("Source project must select the authorized ecnu-max model")
    candidates = []
    for path in sorted((source / "run" / "packets").glob("*.json")):
        packet = read_json(path)
        if packet.get("task") in {t for t, _ in STRATA.values()}:
            if packet.get("semantic_version") != code_version(packet["task"]):
                continue
            candidates.append((path, packet))
    samples = []
    selected = []
    full = getattr(args, "suite", "representative") == "full"
    specifications = []
    if full:
        for family in ("binding", "generation", "comparison"):
            for cid in ("UC-001", "UC-002", "UC-003", "UC-004", "UC-005"):
                specifications.append((family + "-" + cid, family, *STRATA[family], cid, None))
        specifications += [
            ("existing", "existing", "project-scope-identify", "E", None, "architecture"),
            ("test-chain", "test", "project-scope-identify", "GT", None, "business_chain"),
            ("test-architecture", "test", "project-scope-identify", "GT", None, "architecture"),
        ]
    else:
        specifications = [
            (name, name, task, channel, None, None) for name, (task, channel) in STRATA.items()
        ]
    for name, family, task, channel, cid, scope in specifications:
        pool = [
            (p, d)
            for p, d in candidates
            if d["task"] == task
            and (channel is None or d["input"].get("channel") == channel)
            and (cid is None or cid in d.get("case_ids", []))
            and (scope is None or d["input"].get("scope") == scope)
        ]
        if not pool:
            raise ValueError("No actual current-version model packet for " + name)
        # Prefer rich generation and a compact full batch elsewhere; never trim
        # the real input or select by the prior model's outcome.
        pool.sort(key=lambda r: (r[0].stat().st_size, r[0].name))
        path, original = pool[len(pool) // 2] if family == "generation" else pool[0]
        packet = {k: v for k, v in original.items() if k != "repair"}
        packet["batch_id"] = fingerprint(["pi-node-experiment-v2", name, packet])
        sample = {
            "id": name,
            "family": family,
            "task": task,
            "node_key": packet["node_key"],
            "scope": packet["input"].get("scope", "interaction"),
            "channel": channel,
            "source_packet": str(path.relative_to(source)),
            "source_packet_hash": file_hash(path),
            "packet_hash": fingerprint(packet),
            "input_hash": fingerprint(packet["input"]),
            "estimated_pair_reservation": estimate_pair(packet, config),
        }
        samples.append(sample)
        selected.append((name, packet))
    review_sources = []
    for path in sorted((source / "imports" / "files").glob("*/original/*.md")):
        if not path.resolve().is_relative_to(source):
            raise ValueError("Original document escaped the source project")
        relative = Path("review-sources") / path.parent.parent.name / path.name
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        review_sources.append(
            {
                "path": str(relative),
                "hash": file_hash(path),
                "source_path": str(path.relative_to(source)),
            }
        )
    manifest = {
        "schema": "scene-pi-node-experiment-v2",
        "created_unix": time.time(),
        "source_project": str(source),
        "source_config": str(Path(args.config).resolve()),
        "source_env_file": str(Path(args.env_file).resolve()),
        "code_identity": code_identity(),
        "config_identity": config_identity(config),
        "requested_model": "ecnu-max",
        "limit": LIMIT,
        "max_calls_per_node": 5,
        "repetitions": 2,
        "planned_executions": len(samples) * 4,
        "pilot_ids": [
            "binding-UC-004",
            "existing",
            "test-chain",
            "generation-UC-005",
            "comparison-UC-001",
        ]
        if full
        else list(STRATA),
        "acknowledged_unknown": ACKNOWLEDGED_UNKNOWN,
        "exception_authorization": "用户明确保留旧请求69,098 Token未决扣账，仅允许本实验继续；新未决立即停止",
        "samples": samples,
        "sdk": {"name": "@earendil-works/pi-coding-agent", "version": "1.5.2"},
        "cache_policy": "fresh_sessions_no_model_answer_reuse",
        "historical_results_are_gold": False,
        "review_sources": review_sources,
    }
    for name, packet in selected:
        write_json(root / "samples" / (name + ".json"), packet)
        write_json(root / "checklists" / (name + ".json"), checklist(packet))
    write_json(root / "manifest.json", manifest)
    # Deterministic opaque IDs allow independent review without arm labels.
    mapping = {}
    for repeat in (1, 2):
        for name, _packet in selected:
            for arm in ("A", "B"):
                key = f"{name}-{repeat}-{arm}"
                mapping[key] = fingerprint([manifest["created_unix"], key])[:16]
    write_json(root / "blinding-private.json", mapping)
    return {
        "status": "frozen",
        "executions": len(samples) * 4,
        "samples": samples,
        "output": str(root),
    }


def load_experiment(args):
    root = Path(args.output).resolve()
    manifest = read_json(root / "manifest.json")
    if manifest["code_identity"] != code_identity():
        raise ValueError("Code/dependency identity changed; freeze a new experiment")
    config = config_for(
        argparse.Namespace(config=manifest["source_config"], env_file=manifest["source_env_file"])
    )
    if manifest["config_identity"] != config_identity(config):
        raise ValueError("Model configuration identity changed; freeze a new experiment")
    for sample in manifest["samples"]:
        packet = read_json(root / "samples" / (sample["id"] + ".json"))
        if sample["packet_hash"] != fingerprint(packet):
            raise ValueError("Frozen packet changed: " + sample["id"])
    for source in manifest.get("review_sources", []):
        if file_hash(root / source["path"]) != source["hash"]:
            raise ValueError("Frozen source document changed")
    if manifest.get("acknowledged_unknown") != ACKNOWLEDGED_UNKNOWN:
        raise ValueError("Experiment does not carry the exact approved usage exception")
    config["_experiment_acknowledged_unknown"] = ACKNOWLEDGED_UNKNOWN
    config["_experiment_continue_unknown_usage"] = manifest.get(
        "continue_conservatively_charged_unknown", False
    )
    return root, manifest, config


def status(args):
    root, manifest, config = load_experiment(args)
    guard = ledger_guard(config)
    completed = len(list((root / "executions").glob("*/summary.json")))
    return {
        "status": "ready" if guard["ready"] else "blocked",
        "guard": guard,
        "completed": completed,
        "planned": manifest["planned_executions"],
        "paid_requests_started_by_status": 0,
    }


def execution_order(manifest, name, repeat):
    first = manifest.get("first_order", {}).get(name)
    if first is None:
        sample_index = next(i for i, s in enumerate(manifest["samples"]) if s["id"] == name)
        first = "A" if sample_index % 2 == 0 else "B"
    order = (first, "B" if first == "A" else "A")
    return order[::-1] if repeat == 2 else order


def run(args):
    root, manifest, config = load_experiment(args)
    with run_lock(root):
        guard = ledger_guard(config)
        if not guard["ready"]:
            write_json(root / "preflight.json", guard)
            return {"status": "blocked", "guard": guard, "new_paid_requests": 0}
        cap = cap_for(root)
        phases = [
            [s for s in manifest["samples"] if s["id"] in manifest["pilot_ids"]],
            [s for s in manifest["samples"] if s["id"] not in manifest["pilot_ids"]],
        ]
        schedule = [
            (repeat, sample)
            for phase in phases[: 1 if getattr(args, "phase", "all") == "pilot" else 2]
            for repeat in (1, 2)
            for sample in phase
        ]
        for index, (repeat, sample) in enumerate(schedule):
            name = sample["id"]
            packet = read_json(root / "samples" / (name + ".json"))
            order = execution_order(manifest, name, repeat)
            pair = [root / "executions" / f"{name}-{repeat}-{arm}" for arm in order]
            # Never resend an interrupted request whose use is unknown.
            if any(p.exists() and not (p / "summary.json").exists() for p in pair):
                return {
                    "status": "blocked",
                    "reason": "interrupted_execution_needs_audit",
                    "pair": [p.name for p in pair],
                }
            remaining = LIMIT - sum(
                r.get("charged_tokens", 0) for r in cap._read()["requests"].values()
            )
            grant = ledger_guard(config)
            required = sample["estimated_pair_reservation"]
            if not all((p / "summary.json").exists() for p in pair):
                if (
                    not grant["ready"]
                    or min(remaining, grant.get("remaining_tokens", 0)) < required
                ):
                    write_json(
                        root / "preflight.json",
                        {
                            "ready": False,
                            "reason": "pair_budget_or_usage_guard",
                            "remaining_experiment": remaining,
                            "required": required,
                            "grant": grant,
                        },
                    )
                    return {
                        "status": "blocked",
                        "reason": "pair_budget_or_usage_guard",
                        "sample": name,
                    }
            for arm, path in zip(order, pair, strict=True):
                if (path / "summary.json").exists():
                    continue
                result = execute(packet, config, path, root, arm)
                print(json.dumps({"execution": path.name, "status": result["status"]}), flush=True)
                if (
                    result["status"] == "blocked"
                    and result.get("unknown_usage_calls")
                    and config.get("_experiment_continue_unknown_usage")
                ):
                    write_json(
                        root / "transport_incidents" / (path.name + ".json"),
                        {
                            "execution": path.name,
                            "action": "skip_not_resend_continue_independent_nodes",
                            "charged_tokens": result["accounted_tokens"],
                            "settled": False,
                            "authorization": manifest["continuation_authorization"],
                        },
                    )
                    continue
                if result["status"] in {"blocked", "runtime_failure"}:
                    return {
                        "status": "blocked",
                        "execution": path.name,
                        "reason": result["status"],
                    }
        return {
            "status": "execution_complete",
            "planned": len(schedule) * 2,
            "semantic_review": "pending",
        }


def report(args):
    root = Path(args.output).resolve()
    manifest = read_json(root / "manifest.json")
    mapping = read_json(root / "blinding-private.json")

    def write_new(path, value):
        if not path.exists():
            write_json(path, value)

    rows = {}
    for path in (root / "executions").glob("*/summary.json"):
        rows[path.parent.name] = read_json(path)
        rows[path.parent.name].update(
            submission_metrics(path.parent, rows[path.parent.name]["status"])
        )
        result_path = path.parent / "result.json"
        if result_path.exists():
            result = public_result(result_path)
            # Runtime identity is kept out of the independent semantic worksheet.
            write_new(
                root / "blind-review" / (mapping[path.parent.name] + ".json"),
                {
                    "review_id": mapping[path.parent.name],
                    "task": rows[path.parent.name]["task"],
                    "input_hash": rows[path.parent.name]["input_hash"],
                    "result_hash": fingerprint(result),
                    "result": result,
                    "rubric": {
                        "business_correct": None,
                        "omissions": None,
                        "wrong_bindings": None,
                        "unsupported_additions": None,
                        "invalid_citations": None,
                        "template_completeness": None,
                        "match_accuracy": None,
                    },
                    "source_checks": [],
                    "reviewed": False,
                },
            )
    comparisons = []
    for sample in manifest["samples"]:
        write_json(
            root / "blind-review" / "inputs" / (sample["id"] + ".json"),
            read_json(root / "samples" / (sample["id"] + ".json")),
        )
        pairs = []
        for repeat in (1, 2):
            a = rows.get(f"{sample['id']}-{repeat}-A")
            b = rows.get(f"{sample['id']}-{repeat}-B")
            compatible = bool(
                a
                and b
                and len(a["provider_models"]) == 1
                and a["provider_models"] == b["provider_models"]
                and not a.get("unknown_usage_calls")
                and not b.get("unknown_usage_calls")
            )
            pairs.append(
                {
                    "repeat": repeat,
                    "A": a,
                    "B": b,
                    "provider_comparable": compatible,
                    "executions": {arm: f"{sample['id']}-{repeat}-{arm}" for arm in ("A", "B")},
                }
            )
        comparisons.append(
            {"sample": sample["id"], "pairs": pairs, **compare(pairs, root, mapping)}
        )
    value = {
        "schema": manifest["schema"],
        "completed": len(rows),
        "planned": manifest.get("planned_executions", 20),
        "comparisons": comparisons,
        "preflight": read_json(root / "preflight.json")
        if (root / "preflight.json").exists()
        else None,
        "production_runtime_changed": False,
        "local_checks_are_model_evidence": False,
        "operational_totals": {
            arm: {
                "completed": sum(r["arm"] == arm for r in rows.values()),
                "delivered": sum(
                    r["arm"] == arm and r["status"] == "delivered" for r in rows.values()
                ),
                **{
                    key: sum(r.get(key, 0) for r in rows.values() if r["arm"] == arm)
                    for key in (
                        "sent_requests",
                        "reported_tokens",
                        "input_tokens",
                        "output_tokens",
                        "accounted_tokens",
                        "unknown_usage_calls",
                        "elapsed_seconds",
                        "repair_attempts",
                    )
                },
            }
            for arm in ("A", "B")
        },
    }
    write_json(root / "report.json", value)
    table = "".join(
        f"<tr><td>{html.escape(c['sample'])}</td><td>{c['recommendation']}</td><td>{c['reason']}</td></tr>"
        for c in comparisons
    )
    document = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><title>Pi 节点对照实验</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:16px}}td,th{{padding:12px;border:1px solid #ccd}}table{{border-collapse:collapse}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style>
<h1>Pi 与当前节点执行方式对照</h1><p>已记录 {len(rows)}/{manifest.get("planned_executions", 20)} 次节点执行。业务正确性需独立审核；本地接入验证不作为真实模型效果证据。</p>
<table><tr><th>任务</th><th>建议</th><th>依据</th></tr>{table}</table>
<details><summary>运行与门槛详情</summary><pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre></details></html>"""
    (root / "report.html").write_text(document, encoding="utf8")
    return {
        "status": "reported",
        "completed": len(rows),
        "planned": manifest.get("planned_executions", 20),
        "recommendation": "见逐节点建议"
        if all(c["eligible_pairs"] == 2 for c in comparisons)
        else "证据不足",
        "report": str(root / "report.html"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("freeze")
    p.add_argument("--suite", choices=["full", "representative"], default="full")
    p.add_argument("--project", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--env-file", required=True)
    p.add_argument("--output", required=True)
    for name in ("status", "run", "resume", "report"):
        p = sub.add_parser(name)
        p.add_argument("--output", required=True)
        if name in ("run", "resume"):
            p.add_argument("--phase", choices=["pilot", "all"], default="all")
    p = sub.add_parser("review-submit")
    p.add_argument("--output", required=True)
    p.add_argument("--file", required=True)
    args = parser.parse_args()
    try:
        value = {
            "freeze": freeze,
            "status": status,
            "run": run,
            "resume": run,
            "report": report,
            "review-submit": lambda a: submit_review(Path(a.output).resolve(), Path(a.file)),
        }[args.command](args)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 2 if value.get("status") == "blocked" else 0
    except (ValueError, OSError, ExperimentBlocked) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
