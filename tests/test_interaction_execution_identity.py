"""Execution identities bind requested models to preserved native artifacts."""
import hashlib
import json
import shutil

import pytest

from scene_completion.interaction_execution_identity import (
    copy_execution_sidecars,
    validate_client_execution_model,
    validate_result_execution,
)
from scene_completion.semantic_backend import write_json


def native_fixture(tmp_path, *, ignore_user_config=False):
    batch_id = "interaction-model-0000-fixture"
    input_hash = "a" * 64
    run_id = "run-fixture-001"
    artifact_root = tmp_path / "batches"
    native_dir = artifact_root / "interaction-model" / "native" / run_id
    native_dir.mkdir(parents=True)
    exe = tmp_path / "codex.exe"
    exe.write_text("local executable fixture", encoding="utf-8")
    output_payload = {"items": [{"value": "source-backed"}]}
    output_bytes = json.dumps(output_payload, ensure_ascii=False).encode("utf-8")
    output_path = native_dir / "output.json"
    output_path.write_bytes(output_bytes)
    events = [
        {"type": "thread.started", "thread_id": "thread-fixture-001"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "item_1", "type": "agent_message",
            "text": output_bytes.decode("utf-8")}},
        {"type": "turn.completed"},
    ]
    events_bytes = ("\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n").encode("utf-8")
    events_path = native_dir / "events.jsonl"
    events_path.write_bytes(events_bytes)
    stderr_path = native_dir / "stderr.txt"
    stderr_path.write_bytes(b"")
    argv = [str(exe.resolve()), "exec"]
    if ignore_user_config:
        argv.append("--ignore-user-config")
    argv.extend(["-m", "gpt-6-luna", "-c", "model_reasoning_effort=max",
        "-s", "read-only", "--ephemeral", "--json", "--output-last-message", str(output_path.resolve()),
        "--skip-git-repo-check", "-"])
    native = {
        "run_id": run_id,
        "batch_id": batch_id,
        "input_hash": input_hash,
        "argv": argv,
        "cwd": str(native_dir.resolve()),
        "exit_code": 0,
        "events_path": str(events_path.resolve()),
        "events_relative_path": "interaction-model/native/" + run_id + "/events.jsonl",
        "events_sha256": hashlib.sha256(events_bytes).hexdigest(),
        "output_path": str(output_path.resolve()),
        "output_relative_path": "interaction-model/native/" + run_id + "/output.json",
        "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "stderr_path": str(stderr_path.resolve()),
        "stderr_relative_path": "interaction-model/native/" + run_id + "/stderr.txt",
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
        "thread_id": "thread-fixture-001",
        "observed_model": None,
        "model_observations": [],
        "started_at": "2026-10-11T00:00:00Z",
        "completed_at": "2026-10-11T00:00:01Z",
    }
    result = {
        **output_payload,
        "model": "gpt-6-luna",
        "batch_id": batch_id,
        "input_hash": input_hash,
        "execution_model_evidence": {
            "provider": "native_subprocess",
            "requested_model": "gpt-6-luna",
            "provider_model": None,
            "thinking": True,
            "reasoning_effort": "max",
            "verification_limit": "The CLI command is pinned; routed provider metadata is not exposed by these events.",
            "native_execution": native,
        },
    }
    result_path = artifact_root / "interaction-model" / "results" / (batch_id + ".json")
    write_json(result_path, result)
    return result, result_path, native_dir


def test_legacy_ecnu_proof_is_preserved_but_model_label_alone_fails():
    result = {"model": "ecnu-max", "execution_model_evidence": {
        "requested_model": "ecnu-max", "provider_model": "deepseek-v4-flash"}}
    assert validate_result_execution(result)["proof_kind"] == "legacy_ecnu_request"
    with pytest.raises(ValueError, match="request evidence"):
        validate_result_execution({"model": "ecnu-max"})


def test_native_tool_use_is_rejected_even_with_successful_json_and_valid_hash(tmp_path):
    result, result_path, directory = native_fixture(tmp_path)
    events_path = directory / 'events.jsonl'
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
    events.insert(1, {'type': 'item.completed', 'item': {'type': 'command_execution',
        'command': 'read another document', 'exit_code': 0}})
    events_path.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
    result['execution_model_evidence']['native_execution']['events_sha256'] = hashlib.sha256(events_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='outside its supplied packet'):
        validate_result_execution(result, result_path=result_path)


def test_native_transport_diagnostic_item_is_not_a_tool_action(tmp_path):
    result, result_path, directory = native_fixture(tmp_path)
    events_path = directory / 'events.jsonl'
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
    events.insert(1, {'type': 'item.completed', 'item': {'type': 'error',
        'message': 'Falling back from WebSockets to HTTPS transport. request timed out'}})
    events_path.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
    result['execution_model_evidence']['native_execution']['events_sha256'] = hashlib.sha256(events_path.read_bytes()).hexdigest()
    assert validate_result_execution(result, result_path=result_path)['proof_kind'] == 'native_subprocess'


def test_native_luna_proof_checks_args_events_output_and_portable_paths(tmp_path):
    result, result_path, _ = native_fixture(tmp_path)
    identity = validate_result_execution(result, result_path=result_path)
    assert identity["model"] == "gpt-6-luna"
    assert identity["proof_kind"] == "native_subprocess"
    assert identity["thread_id"] == result["execution_model_evidence"]["native_execution"]["thread_id"]


def test_native_luna_accepts_pinned_ignore_user_config_variant(tmp_path):
    result, result_path, _ = native_fixture(tmp_path, ignore_user_config=True)
    identity = validate_result_execution(result, result_path=result_path)
    assert identity["proof_kind"] == "native_subprocess"


def test_native_luna_result_can_be_validated_before_target_is_written(tmp_path):
    result, result_path, _ = native_fixture(tmp_path)
    result_path.unlink()
    identity = validate_result_execution(result, result_path=result_path)
    assert identity["proof_kind"] == "native_subprocess"


def test_native_luna_frozen_baseline_import_keeps_original_execution_binding(tmp_path):
    result, result_path, _ = native_fixture(tmp_path)
    result["baseline_execution"] = {
        "batch_id": result["batch_id"],
        "input_hash": result["input_hash"],
        "model": "gpt-6-luna",
        "baseline_hash": "c" * 64,
    }
    result["batch_id"] = "interaction-checker-imported"
    result["input_hash"] = "b" * 64
    identity = validate_result_execution(result, result_path=result_path)
    assert identity["batch_id"] == "interaction-model-0000-fixture"


@pytest.mark.parametrize("field", ["batch_id", "input_hash", "model", "baseline_hash"])
def test_native_luna_frozen_import_rejects_unbound_baseline_metadata(tmp_path, field):
    result, result_path, _ = native_fixture(tmp_path)
    result["baseline_execution"] = {
        "batch_id": result["batch_id"],
        "input_hash": result["input_hash"],
        "model": "gpt-6-luna",
        "baseline_hash": "c" * 64,
    }
    result["batch_id"] = "interaction-checker-imported"
    result["input_hash"] = "b" * 64
    result["baseline_execution"][field] = "invalid"
    with pytest.raises(ValueError, match="baseline import"):
        validate_result_execution(result, result_path=result_path)


@pytest.mark.parametrize("tamper", ["exit", "model_arg", "event_hash", "output_payload", "thread", "batch_binding", "invented_provider"])
def test_native_luna_rejects_unproved_or_mismatched_identity(tmp_path, tamper):
    result, result_path, _ = native_fixture(tmp_path)
    native = result["execution_model_evidence"]["native_execution"]
    if tamper == "exit":
        native["exit_code"] = 1
    elif tamper == "model_arg":
        native["argv"][3] = "other-model"
    elif tamper == "event_hash":
        native["events_sha256"] = "0" * 64
    elif tamper == "output_payload":
        result["items"] = [{"value": "edited after process"}]
    elif tamper == "thread":
        native["thread_id"] = "unobserved-thread"
    elif tamper == "batch_binding":
        native["input_hash"] = "b" * 64
    else:
        result["execution_model_evidence"]["provider_model"] = "invented-model"
        result["execution_model_evidence"]["native_execution"]["observed_model"] = "invented-model"
    with pytest.raises(ValueError):
        validate_result_execution(result, result_path=result_path)


def test_native_proof_sidecars_copy_and_validate_without_retagging_result(tmp_path):
    result, source_result, source_native_dir = native_fixture(tmp_path)
    destination = tmp_path / "snapshot" / "batches" / "interaction-model" / "results" / source_result.name
    write_json(destination, result)
    copied = copy_execution_sidecars(result, source_result, destination)
    assert len(copied) == 3
    shutil.rmtree(source_native_dir)
    identity = validate_result_execution(result, result_path=destination)
    assert identity["proof_kind"] == "native_subprocess"
    assert result["execution_model_evidence"]["native_execution"]["output_path"].startswith(str(source_native_dir))


@pytest.mark.parametrize("model,config,valid", [
    ("ecnu-max", {}, True),
    ("gpt-6-luna", {"thinking": True, "reasoning_effort": "max"}, True),
    ("gpt-6-luna", {"thinking": False, "reasoning_effort": "max"}, False),
    ("qwen38-27b-vl", {}, True),
    ("other", {}, True),
    ("", {}, False),
])
def test_repair_client_preflight_is_explicit(model, config, valid):
    class Client:
        def model(self, _kind):
            return model
    client = Client()
    client.config = config
    if valid:
        assert validate_client_execution_model(client) == model
    else:
        with pytest.raises(ValueError):
            validate_client_execution_model(client)
