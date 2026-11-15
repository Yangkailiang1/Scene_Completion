"""Transport simulations test integration only, never compare model quality."""

import argparse
import json
import sys
from pathlib import Path

import pytest

from tests.support.paths import ROOT

EXPERIMENT = ROOT / "deployment" / "experiments" / "pi_node"
sys.path.insert(0, str(EXPERIMENT))

from bridge import to_langchain  # noqa: E402
from evaluation import compare, submit_review  # noqa: E402
from experiment import config_identity, execution_order, freeze, load_experiment, report, run  # noqa: E402
from harness import ACKNOWLEDGED_UNKNOWN, cap_for, execute, ledger_guard, submission_metrics  # noqa: E402

from scene_completion.domain.ssd_contracts import packet  # noqa: E402
from scene_completion.infrastructure.storage import read_json, write_json  # noqa: E402


def task():
    p = packet(
        "ssd-generate",
        {"templates": [{"id": "T1"}], "concerns": [], "all_failure_conditions": []},
        ["UC-test"],
    )
    return {**p, "skill_text": p["instructions"], "node_key": "UC-test:ssd-generate"}


def config():
    return {
        "base_url": "http://127.0.0.1:1",
        "api_key": "not-a-real-key",
        "agent_model": "ecnu-max",
        "submission_mode": "json_text",
        "thinking_override": False,
    }


def response(valid=True):
    return {
        "model": "transport-simulation-only",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "analyses": [
                                {"scenario_id": "T1" if valid else "BAD", "analysis": "测试分析"}
                            ],
                            "supplements": [],
                        }
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


def require_sdk():
    assert (EXPERIMENT / "node_modules/@earendil-works/pi-coding-agent/package.json").exists(), (
        "Install the isolated locked Pi dependencies before experiment tests; do not silently skip"
    )


def test_both_loops_deliver_using_identical_first_wire_request(tmp_path):
    require_sdk()
    bodies = {}
    for arm in ("A", "B"):
        captured = []

        def fake(url, key, body, timeout, retries):
            assert retries == 0
            captured.append(body)
            return response()

        result = execute(task(), config(), tmp_path / arm, tmp_path, arm, transport=fake)
        assert result["status"] == "delivered", result["errors"]
        assert result["request_attempts"] == 1
        assert result["reported_tokens"] == 30
        assert result["semantic_review"] == "pending"
        assert result["proof"]["provider"] == (
            "pi_sdk_python_metered" if arm == "B" else "deepagents_openai_compatible"
        )
        bodies[arm] = captured[0]
    assert bodies["A"] == bodies["B"]
    assert sum(r["charged_tokens"] for r in cap_for(tmp_path)._read()["requests"].values()) == 60


@pytest.mark.parametrize("arm", ["A", "B"])
def test_native_tool_calls_and_nonblocking_questions(tmp_path, arm):
    require_sdk()
    count = 0

    def fake(url, key, body, timeout, retries):
        nonlocal count
        count += 1
        if count == 1:
            name = "ask_user"
            args = {
                "question": "是否需要补充规则？",
                "basis": "输入无该规则",
                "decision": "请确认规则",
            }
        else:
            name = "submit_result"
            args = {
                "payload": {
                    "analyses": [{"scenario_id": "T1", "analysis": "保留已知分析"}],
                    "supplements": [],
                }
            }
        value = response()
        value["choices"] = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": f"call-{count}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args, ensure_ascii=False),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
        return value

    result = execute(
        task(),
        {**config(), "submission_mode": "tool_calls"},
        tmp_path / arm,
        tmp_path,
        arm,
        transport=fake,
    )
    assert result["status"] == "delivered", result["errors"]
    assert count == 2


@pytest.mark.parametrize("arm", ["A", "B"])
def test_rejected_candidate_repaired_with_shared_validator(tmp_path, arm):
    require_sdk()
    calls = []

    def fake(url, key, body, timeout, retries):
        calls.append(body)
        return response(valid=len(calls) > 1)

    result = execute(task(), config(), tmp_path / arm, tmp_path, arm, transport=fake)
    assert result["status"] == "delivered", result["errors"]
    assert result["first_submission_passed"] is False
    assert result["repair_attempts"] == 1
    assert len(calls) == 2
    assert "BAD" in json.dumps(calls[1], ensure_ascii=False)


@pytest.mark.parametrize("arm", ["A", "B"])
def test_no_more_than_five_requests_including_repairs(tmp_path, arm):
    require_sdk()
    calls = []

    def fake(*args):
        calls.append(1)
        return response(False)

    result = execute(task(), config(), tmp_path / arm, tmp_path, arm, transport=fake)
    assert result["status"] != "delivered"
    assert result["sent_requests"] == len(calls) == 5
    assert not (tmp_path / arm / "result.json").exists()


@pytest.mark.parametrize("arm", ["A", "B"])
def test_transport_failure_is_not_retried_or_counted_as_semantic_defect(tmp_path, arm):
    require_sdk()
    calls = []

    def fake(*args):
        calls.append(1)
        raise ConnectionError("simulated unknown provider usage")

    result = execute(task(), config(), tmp_path / arm, tmp_path, arm, transport=fake)
    assert result["status"] == "blocked"
    assert len(calls) == 1
    assert next(iter(cap_for(tmp_path)._read()["requests"].values()))["status"] == "usage_unknown"


@pytest.mark.parametrize("limit", [2_000_000, 6_000_000])
def test_guard_reads_unknown_usage_without_modifying_original_ledger(tmp_path, limit):
    ledger = tmp_path / "grant.json"
    write_json(
        ledger,
        {
            "limit": limit,
            "requests": {
                "unknown-id": {
                    "status": "usage_unknown",
                    "charged_tokens": 69098,
                    "model": "ecnu-max",
                }
            },
        },
    )
    before = ledger.read_bytes()
    guard = ledger_guard({"token_budget_limit": limit, "token_budget_ledger": str(ledger)})
    assert not guard["ready"]
    assert guard["unknown"][0]["request_id"] == "unknown-id"
    assert ledger.read_bytes() == before


def test_messages_keep_exact_system_blocks_and_tool_identity():
    blocks = [{"type": "text", "text": "frozen system"}]
    result = to_langchain(
        [
            {
                "role": "assistant",
                "content": [{"type": "toolCall", "id": "c1", "name": "ask_user", "arguments": {}}],
            },
            {
                "role": "toolResult",
                "toolCallId": "c1",
                "content": [{"type": "text", "text": "pending"}],
            },
        ],
        blocks,
    )
    assert result[0].content == blocks
    assert result[1].tool_calls[0]["id"] == result[2].tool_call_id


def test_config_identity_does_not_depend_on_credential_value():
    assert config_identity(config()) == config_identity({**config(), "api_key": "rotated-key"})


def test_report_cannot_declare_a_winner_without_real_runs(tmp_path):
    write_json(
        tmp_path / "manifest.json",
        {"schema": "scene-pi-node-experiment-v1", "samples": [{"id": "generation"}]},
    )
    write_json(tmp_path / "blinding-private.json", {})
    write_json(tmp_path / "samples/generation.json", task())
    result = report(argparse.Namespace(output=str(tmp_path)))
    assert result["recommendation"] == "证据不足"
    assert result["completed"] == 0
    assert read_json(tmp_path / "report.json")["local_checks_are_model_evidence"] is False


def test_review_cannot_attach_to_another_result(tmp_path):
    write_json(tmp_path / "blinding-private.json", {"generation-1-A": "opaque1"})
    write_json(tmp_path / "executions/generation-1-A/summary.json", {"input_hash": "input1"})
    write_json(tmp_path / "executions/generation-1-A/result.json", {"analyses": []})
    path = tmp_path / "review.json"
    write_json(path, {"review_id": "opaque1", "input_hash": "input1", "result_hash": "other"})
    with pytest.raises(ValueError, match="different input/result"):
        submit_review(tmp_path, path)


def test_same_quality_preserves_current_runtime(tmp_path):
    mapping = {}
    pairs = []
    for repeat in (1, 2):
        row = {
            "status": "delivered",
            "first_submission_passed": True,
            "sent_requests": 1,
            "reported_tokens": 100,
            "elapsed_seconds": 10,
            "repair_attempts": 0,
        }
        executions = {arm: f"task-{repeat}-{arm}" for arm in ("A", "B")}
        for arm in ("A", "B"):
            key = executions[arm]
            mapping[key] = key
            write_json(
                tmp_path / "reviews" / (key + ".json"),
                {
                    "rubric": {
                        "business_correct": True,
                        "omissions": 0,
                        "wrong_bindings": 0,
                        "unsupported_additions": 0,
                        "invalid_citations": 0,
                    }
                },
            )
        pairs.append({"A": row, "B": row, "executions": executions, "provider_comparable": True})
    assert compare(pairs, tmp_path, mapping)["recommendation"] == "保持当前实现"
    pairs[0]["provider_comparable"] = False
    assert compare(pairs, tmp_path, mapping)["recommendation"] == "证据不足"


def frozen_fixture(tmp_path):
    from scene_completion.workflow.semantics import code_version

    project = tmp_path / "project"
    for name, task_name, channel in (
        ("binding", "ssd-bind", None),
        ("existing", "project-scope-identify", "E"),
        ("test", "project-scope-identify", "GT"),
        ("generation", "ssd-generate", None),
        ("comparison", "ssd-semantic-compare", None),
    ):
        value = task()
        value.update(task=task_name, semantic_version=code_version(task_name))
        value["input"]["channel"] = channel
        value["repair"] = {"candidate": {"must_not_enter_model": True}}
        write_json(project / "run/packets" / (name + ".json"), value)
    ledger = tmp_path / "original-grant.json"
    write_json(
        ledger,
        {
            "limit": 2_000_000,
            "requests": {"supplier-pending": {"status": "usage_unknown", "charged_tokens": 69098}},
        },
    )
    settings = {**config(), "token_budget_limit": 2_000_000, "token_budget_ledger": str(ledger)}
    settings_path = project / "model.local.json"
    write_json(settings_path, settings)
    args = argparse.Namespace(
        project=str(project),
        config=str(settings_path),
        env_file=str(tmp_path / "absent.env"),
        output=str(tmp_path / "experiment"),
    )
    freeze(args)
    return args, ledger


def test_freeze_removes_previous_answers_and_blocks_without_spending(tmp_path):
    args, ledger = frozen_fixture(tmp_path)
    before = ledger.read_bytes()
    frozen = read_json(Path(args.output) / "samples/generation.json")
    assert "repair" not in frozen
    assert "must_not_enter_model" not in json.dumps(frozen)
    result = run(args)
    assert result["status"] == "blocked" and result["new_paid_requests"] == 0
    assert ledger.read_bytes() == before
    assert not (Path(args.output) / "experiment-cap.json").exists()
    assert not (Path(args.output) / "executions").exists()


def test_tampered_input_cannot_resume(tmp_path):
    args, _ = frozen_fixture(tmp_path)
    path = Path(args.output) / "samples/generation.json"
    value = read_json(path)
    value["input"]["templates"].append({"id": "injected"})
    write_json(path, value)
    with pytest.raises(ValueError, match="Frozen packet changed"):
        load_experiment(args)


def test_exact_old_unknown_exception_allows_only_that_request(tmp_path):
    ledger = tmp_path / "grant.json"
    old_id = next(iter(ACKNOWLEDGED_UNKNOWN))
    data = {
        "limit": 100_000_000,
        "remaining_tokens": 99_930_902,
        "requests": {
            old_id: {"status": "usage_unknown", "model": "ecnu-max", "charged_tokens": 69098}
        },
    }
    write_json(ledger, data)
    config = {
        "token_budget_limit": data["limit"],
        "token_budget_ledger": str(ledger),
        "_experiment_acknowledged_unknown": ACKNOWLEDGED_UNKNOWN,
    }
    before = ledger.read_bytes()
    assert ledger_guard(config)["ready"]
    assert ledger.read_bytes() == before
    data["requests"]["new-unknown"] = {
        "status": "usage_unknown",
        "model": "ecnu-max",
        "charged_tokens": 100,
    }
    write_json(ledger, data)
    assert not ledger_guard(config)["ready"]
    assert ledger_guard(config)["unknown"][0]["request_id"] == "new-unknown"


def test_sdk_internal_rejection_counts_as_first_submission_failure(tmp_path):
    require_sdk()
    calls = 0

    def fake(*args):
        nonlocal calls
        calls += 1
        value = response()
        if calls == 1:
            data = json.loads(value["choices"][0]["message"]["content"])
            data["analyses"][0]["analysis"] = ""
            value["choices"][0]["message"]["content"] = json.dumps(data)
        return value

    result = execute(task(), config(), tmp_path / "B", tmp_path, "B", transport=fake)
    assert result["status"] == "delivered", result["errors"]
    assert calls == 2 and result["first_submission_passed"] is False
    assert result["repair_attempts"] == 1 and result["validation_rejections"] == 1


def test_metric_derivation_counts_candidates_not_question_calls(tmp_path):
    question = response()
    question["choices"][0]["message"] = {"tool_calls": [{"function": {"name": "ask_user"}}]}
    write_json(tmp_path / "wire/1-response.json", question)
    write_json(tmp_path / "wire/2-response.json", response())
    value = submission_metrics(tmp_path, "delivered")
    assert value["first_submission_passed"] and value["submission_candidates"] == 1


def test_repetitions_counterbalance_first_runtime_for_every_sample():
    manifest = {"samples": [{"id": str(i)} for i in range(18)]}
    for sample in manifest["samples"]:
        first = execution_order(manifest, sample["id"], 1)
        assert execution_order(manifest, sample["id"], 2) == first[::-1]
    manifest["first_order"] = {"0": "B"}
    assert execution_order(manifest, "0", 1) == ("B", "A")
    assert execution_order(manifest, "0", 2) == ("A", "B")


def test_explicit_continuation_requires_full_conservative_charge(tmp_path):
    ledger = tmp_path / "grant.json"
    data = {
        "limit": 100_000_000,
        "remaining_tokens": 99_999_900,
        "requests": {
            "new": {
                "status": "usage_unknown",
                "model": "ecnu-max",
                "reservation": 100,
                "charged_tokens": 100,
            }
        },
    }
    write_json(ledger, data)
    c = {"token_budget_limit": data["limit"], "token_budget_ledger": str(ledger)}
    assert not ledger_guard(c)["ready"]
    assert ledger_guard({**c, "_experiment_continue_unknown_usage": True})["ready"]
    data["requests"]["new"]["charged_tokens"] = 1
    write_json(ledger, data)
    assert not ledger_guard({**c, "_experiment_continue_unknown_usage": True})["ready"]


def test_secondary_cap_continues_without_clearing_unknown_charge(tmp_path):
    write_json(tmp_path / "manifest.json", {"continue_conservatively_charged_unknown": True})
    cap = cap_for(tmp_path)
    body = {"model": "ecnu-max", "messages": [], "max_tokens": 10}
    first = cap.reserve(body)
    cap.settle(first)
    charged = cap._read()["requests"][first]["charged_tokens"]
    second = cap.reserve(body)
    cap.settle(second, refused=True)
    assert cap._read()["requests"][first]["status"] == "usage_unknown"
    assert cap._read()["requests"][first]["charged_tokens"] == charged
