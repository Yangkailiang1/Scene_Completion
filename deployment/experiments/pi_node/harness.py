"""Isolated real-node executions; both arms use unchanged production contracts."""

import time
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path

from bridge import pi_factory

from scene_completion.analysis.validation import validate_result
from scene_completion.infrastructure.execution_events import EventStore, bind
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.models.budgets.token_budget import TokenBudget, request_reservation
from scene_completion.models.clients.deepagents_client import DeepAgentsClient
from scene_completion.workflow_core import TaskRejected

LIMIT = 100_000_000
MAX_CALLS = 5
ACKNOWLEDGED_UNKNOWN = {"b174f91ddacd42c69da75701cd51db68": 69098}


class ExperimentBlocked(RuntimeError):
    def __init__(self, reason):
        super().__init__(reason)
        self.response_diagnostic = {"request_not_sent": True, "failure_category": reason}


def ledger_guard(config):
    """Read-only preflight. Never settle, reset, or rewrite supplier usage."""
    if config.get("unknown_usage_policy", "stop") != "stop":
        raise ExperimentBlocked("unknown_usage_policy_must_be_stop")
    limit = config.get("token_budget_limit")
    if type(limit) is not int or limit < 2_000_000:
        raise ExperimentBlocked("expected_existing_authorization_with_append_history")
    ledger = Path(config["token_budget_ledger"])
    if not ledger.is_file():
        raise ExperimentBlocked("existing_authorization_ledger_missing")
    data = read_json(ledger)
    if data.get("limit") != config["token_budget_limit"]:
        raise ExperimentBlocked("authorization_identity_changed")
    acknowledged = config.get("_experiment_acknowledged_unknown", {})
    if acknowledged and acknowledged != ACKNOWLEDGED_UNKNOWN:
        raise ExperimentBlocked("unapproved_unknown_usage_exception")
    unknown = [
        {"request_id": key, "model": row.get("model"), "charged_tokens": row.get("charged_tokens")}
        for key, row in data["requests"].items()
        if row.get("status") == "usage_unknown"
        and not (
            acknowledged.get(key) == row.get("charged_tokens") and row.get("model") == "ecnu-max"
        )
        and not (
            config.get("_experiment_continue_unknown_usage") is True
            and row.get("model") == "ecnu-max"
            and type(row.get("charged_tokens")) is int
            and row["charged_tokens"] > 0
            and row["charged_tokens"] == row.get("reservation")
        )
    ]
    if unknown:
        return {"ready": False, "reason": "needs_supplier_usage_reconciliation", "unknown": unknown}
    active = [key for key, row in data["requests"].items() if row.get("status") == "reserved"]
    if active:
        return {"ready": False, "reason": "existing_requests_in_flight", "request_ids": active}
    return {"ready": True, "remaining_tokens": data["remaining_tokens"]}


def experiment_config(config, root):
    c = deepcopy(config)
    # Do not let stage/role routing choose a different model or repeat transport.
    for key in ("task_models", "role_models", "model_profiles", "responses_dir"):
        c.pop(key, None)
    c.update(
        agent_model="ecnu-max",
        agent_runtime="deepagents",
        run_root=str(root),
        cache_dir=str(root / "cache"),
        _resilience_active=True,
        max_retries=0,
        agent_max_model_calls=MAX_CALLS,
        agent_max_questions=0,
        agent_recursion_limit=24,
        max_concurrency=1,
        max_endpoint_concurrency=1,
        unknown_usage_policy="reserve_and_continue"
        if config.get("_experiment_acknowledged_unknown") == ACKNOWLEDGED_UNKNOWN
        else "stop",
    )
    return c


class Recorder:
    def __init__(self, original, root, cap):
        self.original = original
        self.root = Path(root)
        self.cap = cap
        self.rows = []
        self.failure = None

    def __call__(self, url, key, body, timeout, retries):
        if len(self.rows) >= MAX_CALLS:
            raise ExperimentBlocked("node_model_call_limit")
        # Secondary experiment cap, in addition to the unchanged shared grant.
        local = self.cap.reserve(body)
        row = {"request_number": len(self.rows) + 1, "started_unix": time.time(), "sent": False}
        self.rows.append(row)
        write_json(self.root / "requests.json", self.rows)
        write_json(self.root / "wire" / f"{len(self.rows)}-request.json", body)
        try:
            row["sent"] = True
            response = self.original(url, key, body, timeout, 0)
            usage = response.get("usage")
            self.cap.settle(local, usage=usage)
            row.update(usage=usage, provider_model=response.get("model"), status="reported")
            write_json(self.root / "wire" / f"{len(self.rows)}-response.json", response)
            return response
        except Exception as exc:
            diagnostic = getattr(exc, "response_diagnostic", {}) or {}
            status = diagnostic.get("http_status")
            refused = (
                diagnostic.get("request_not_sent") is True
                or status in (400, 401, 403, 404, 422, 429)
                or status == 413
                and diagnostic.get("failure_category") == "provider_context_limit"
                or diagnostic.get("failure_category") == "quota_exhausted"
                and type(status) is int
                and 400 <= status < 500
            )
            # Do not re-settle if writing an audit file failed after settlement.
            if self.cap._read()["requests"][local]["status"] == "reserved":
                self.cap.settle(local, usage=getattr(exc, "usage", None), refused=refused)
            row.update(status="failed", error_type=type(exc).__name__, diagnostic=diagnostic)
            self.failure = exc
            raise
        finally:
            accounting = self.cap._read()["requests"][local]
            row.update(
                accounting_status=accounting["status"],
                charged_tokens=accounting.get("charged_tokens", 0),
            )
            row["elapsed_seconds"] = time.time() - row["started_unix"]
            write_json(self.root / "requests.json", self.rows)


def cap_for(experiment):
    manifest_path = Path(experiment) / "manifest.json"
    continued = (
        read_json(manifest_path).get("continue_conservatively_charged_unknown", False)
        if manifest_path.exists()
        else False
    )
    return TokenBudget(
        {
            "token_budget_limit": LIMIT,
            "token_budget_ledger": str(Path(experiment) / "experiment-cap.json"),
            "unknown_usage_policy": "reserve_and_continue" if continued else "stop",
        }
    )


def estimate_pair(packet, config):
    """Conservative first-request admission, including shared full instructions."""
    from scene_completion.models.clients.deepagents_client import task_message

    # Extra framing/schema allowance. Full positive input is retained verbatim.
    body = {
        "model": "ecnu-max",
        "messages": [
            {"role": "system", "content": packet["instructions"] + packet["skill_text"]},
            {"role": "user", "content": task_message(packet)},
        ],
        "tools": [{"type": "function", "function": {"parameters": packet["output_schema"]}}],
        "max_tokens": config.get("stage_max_tokens", {}).get(
            packet["task"], config.get("max_tokens", 12000)
        ),
    }
    return 2 * (request_reservation(body) + 16_384)


def submission_metrics(root, state):
    """Count SDK-internal rejected candidates as well as Python exceptions."""
    candidates = 0
    for path in (Path(root) / "wire").glob("*-response.json"):
        raw = read_json(path)
        message = raw.get("choices", [{}])[0].get("message", {})
        tools = message.get("tool_calls") or []
        if tools:
            candidates += sum(t.get("function", {}).get("name") == "submit_result" for t in tools)
        elif message.get("content"):
            candidates += 1
    return {
        "submission_candidates": candidates,
        "first_submission_passed": state == "delivered" and candidates == 1,
        "repair_attempts": max(candidates - 1, 0),
        "validation_rejections": max(candidates - int(state == "delivered"), 0),
        "metrics_version": "candidate-sequence-v2",
    }


def execute(packet, config, root, experiment, arm, *, transport=None):
    root = Path(root)
    if root.exists():
        raise ValueError(
            "Fresh node session directory already exists; never overwrite or replay it"
        )
    root.mkdir(parents=True)
    write_json(root / "started.json", {"arm": arm, "started_unix": time.time()})
    client = DeepAgentsClient(experiment_config(config, root), transport=transport)
    original_post = client.post

    def checked_post(*args, **kwargs):
        if config.get("token_budget_ledger"):
            guard = ledger_guard(config)
            if not guard["ready"]:
                raise ExperimentBlocked(guard["reason"])
        return original_post(*args, **kwargs)

    client.post = checked_post
    recorder = Recorder(client.transport, root, cap_for(experiment))
    client.transport = recorder
    client._custom_transport = recorder
    current = deepcopy(packet)
    started = time.monotonic()
    errors = []
    value = None
    state = "failed"
    store = EventStore(root / "events.sqlite3")
    with bind(store, task_key=packet["node_key"], task=packet["task"], attempt=1):
        while len(recorder.rows) < MAX_CALLS:
            before = len(recorder.rows)
            try:
                with pi_factory(root) if arm == "B" else nullcontext():
                    value = client.agent(current)
                public = {k: v for k, v in value.items() if k != "execution_model_evidence"}
                validate_result(packet["task"], public, packet["input"])
                if arm == "B":
                    value["execution_model_evidence"]["provider"] = "pi_sdk_python_metered"
                write_json(root / "result.json", value)
                state = "delivered"
                break
            except Exception as exc:
                diagnostic = getattr(exc, "response_diagnostic", {}) or {}
                failure = getattr(exc, "detail", None) or getattr(exc, "details", None) or {}
                if isinstance(exc, TaskRejected):
                    failure = exc.details
                errors.append({"type": type(exc).__name__, "error": str(exc), "detail": failure})
                if (
                    recorder.failure
                    or not isinstance(exc, (TaskRejected, ValueError))
                    or len(recorder.rows) == before
                ):
                    state = "blocked" if diagnostic or recorder.failure else "runtime_failure"
                    break
                if isinstance(failure, dict) and failure.get("rejected_output"):
                    candidate_path = (root / failure["rejected_output"]).resolve()
                    if candidate_path.is_relative_to(root.resolve()) and candidate_path.is_file():
                        candidate = read_json(candidate_path).get("payload")
                        current["repair"] = {
                            "failure": failure,
                            "candidate": candidate,
                            "round": len(errors),
                            "rule": "仅修复本任务已报告的错误，不读取其他通道。",
                        }
                else:
                    current["repair"] = {
                        "failure": {"error": str(exc)},
                        "round": len(errors),
                        "rule": "修复本任务输出格式；保留全部固定项，不猜测原文事实。",
                    }
    rows = recorder.rows
    evidence = (value or {}).get("execution_model_evidence", {})
    result = {
        "arm": arm,
        "status": state,
        "task": packet["task"],
        "input_hash": fingerprint(packet["input"]),
        "requested_model": "ecnu-max",
        "provider_models": sorted({r["provider_model"] for r in rows if r.get("provider_model")}),
        "request_attempts": len(rows),
        "sent_requests": sum(r["sent"] for r in rows),
        "reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in rows),
        "accounted_tokens": sum(r.get("charged_tokens", 0) for r in rows),
        "unknown_usage_calls": sum(r.get("accounting_status") == "usage_unknown" for r in rows),
        "input_tokens": sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in rows),
        "output_tokens": sum((r.get("usage") or {}).get("completion_tokens", 0) for r in rows),
        "elapsed_seconds": time.monotonic() - started,
        **submission_metrics(root, state),
        "exception_events": len(errors),
        "errors": errors,
        "proof": evidence,
        "semantic_review": "pending" if state == "delivered" else "not_delivered",
    }
    write_json(root / "summary.json", result)
    return result
