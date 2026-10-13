"""Verify model execution identity without trusting a model label alone.

The legacy ECNU API proof shape is retained for already collected batches.
New Luna batches require a native Codex subprocess record whose command,
session events, output and stderr files are still available and hash correctly.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
import shutil
from .model_configuration import model_name, native_result


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRANSPORT_FIELDS = {"batch_id", "input_hash", "model", "execution_model_evidence", "baseline_execution"}


def validate_client_execution_model(client) -> str:
    """Return a configured request model and check native runtime requirements.

    This is a preflight guard only. Completed Luna outputs still need the
    stronger result-side native subprocess evidence checked below.
    """
    model = model_name(client.model("agent"))
    if model == "gpt-6-luna" or getattr(client, 'config', {}).get('agent_runtime') == 'luna-subprocess':
        config = getattr(client, "config", {}) or {}
        if config.get("thinking") is not True or config.get("reasoning_effort") not in {'high', 'max'}:
            raise ValueError("native gpt-6-luna execution requires thinking=true and reasoning_effort=high or max")
    return model


def _sha256_file(path_value: str, label: str) -> tuple[Path, str]:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError(f"native Luna proof is missing {label} path")
    path = Path(path_value)
    if not path.is_absolute() or not path.is_file():
        raise ValueError(f"native Luna {label} file is missing or not an absolute file: {path_value}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path.resolve(), digest


def _resolve_proof_file(native: dict, path_key: str, hash_key: str, relative_key: str,
                        label: str, result_path=None) -> Path:
    expected = native.get(hash_key)
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise ValueError(f"native Luna {label} proof has an invalid SHA-256")
    absolute_value = native.get(path_key)
    if not isinstance(absolute_value, str) or not absolute_value.strip() or not Path(absolute_value).is_absolute():
        raise ValueError(f"native Luna proof is missing absolute {label} path")
    relative_value = native.get(relative_key)
    if not isinstance(relative_value, str) or not relative_value.strip():
        raise ValueError(f"native Luna proof is missing portable {label} path")
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"native Luna portable {label} path must stay below its artifact root")

    absolute = Path(absolute_value)
    if result_path is None:
        path, digest = _sha256_file(absolute_value, label)
        if digest != expected:
            raise ValueError(f"native Luna {label} file hash differs from recorded proof")
        return path

    result_path = Path(result_path).resolve()
    candidates = []
    for parent in result_path.parents:
        candidate = (parent / relative).resolve()
        if candidate.is_file() and hashlib.sha256(candidate.read_bytes()).hexdigest() == expected:
            candidates.append(candidate)
    if len(candidates) != 1:
        raise ValueError(f"native Luna portable {label} path does not resolve uniquely from this saved run")
    candidate = candidates[0]
    # When the original absolute path remains available, it must still identify
    # the same bytes as the portable copy; imported snapshots may use the copy.
    if absolute.is_file() and hashlib.sha256(absolute.read_bytes()).hexdigest() != expected:
        raise ValueError(f"native Luna original {label} file hash differs from recorded proof")
    return candidate


def _event_message(event: dict) -> str | None:
    if event.get("type") == "agent_message":
        value = event.get("text")
        return value if isinstance(value, str) else None
    if event.get("type") == "item.completed":
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            value = item.get("text")
            return value if isinstance(value, str) else None
    return None


def _read_event_stream(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("native Luna event stream is not readable UTF-8 JSONL") from exc
    if not lines:
        raise ValueError("native Luna event stream is empty")
    events = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            raise ValueError(f"native Luna event stream has an empty line at {number}")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"native Luna event stream has malformed JSON at line {number}") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError(f"native Luna event line {number} has no event type")
        events.append(event)
    return events


def _check_luna_result(result: dict, proof: dict, result_path=None) -> dict:
    evidence = result.get("execution_model_evidence")
    if not isinstance(evidence, dict) or evidence.get("provider") != "native_subprocess":
        raise ValueError("gpt-6-luna result lacks native subprocess execution evidence")
    if (evidence.get("requested_model") != result['model'] or evidence.get("thinking") is not True
            or evidence.get("reasoning_effort") not in {'high', 'max'}):
        raise ValueError("native Luna request identity or reasoning configuration differs")
    if not isinstance(evidence.get("verification_limit"), str) or not evidence["verification_limit"].strip():
        raise ValueError("native Luna proof must state the limit on provider-routing verification")
    native = evidence.get("native_execution")
    if not isinstance(native, dict):
        raise ValueError("gpt-6-luna result lacks its original native execution record")

    if type(native.get("exit_code")) is not int or native["exit_code"] != 0:
        raise ValueError("native Luna process did not exit successfully")
    argv = native.get("argv")
    if not isinstance(argv, list) or not all(isinstance(token, str) and token for token in argv):
        raise ValueError("native Luna proof does not contain actual command arguments")
    executable = Path(argv[0])
    if (not executable.is_absolute() or executable.name.casefold() not in {"codex", "codex.exe", "codex.cmd"}
            or not executable.is_file()):
        raise ValueError("native Luna command must name the resolved Codex executable with an absolute path")

    output_path = native.get("output_path")
    output_flag_positions = [index for index, token in enumerate(argv) if token == "--output-last-message"]
    if (not isinstance(output_path, str) or len(output_flag_positions) != 1
            or output_flag_positions[0] + 1 >= len(argv)):
        raise ValueError("native Luna argv must contain exactly one --output-last-message path")
    output_arg_index = output_flag_positions[0] + 1
    output_arg = argv[output_arg_index]
    from .luna_subprocess import native_argv_tail
    pinned_argvs = [native_argv_tail(output_path, ignore_user_config=ignore, transport=transport,
        reasoning_effort=evidence['reasoning_effort'], output_schema_path=native.get('schema_path'), model=result['model'])
        for ignore in (False, True) for transport in ('auto', 'http')]
    if argv[1:] not in pinned_argvs or output_arg != output_path:
        raise ValueError("native Luna argv does not pin the expected model, effort, read-only mode and output file")
    schema_file = None
    if 'schema_path' in native:
        schema_file = _resolve_proof_file(native, 'schema_path', 'schema_sha256', 'schema_relative_path', 'output schema', result_path)

    run_id = native.get("run_id")
    thread_id = native.get("thread_id")
    cwd_value = native.get("cwd")
    if not isinstance(run_id, str) or not run_id.strip() or not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("native Luna proof lacks run/thread provenance")
    if not isinstance(cwd_value, str) or not Path(cwd_value).is_absolute():
        raise ValueError("native Luna proof lacks its absolute per-run working directory")
    cwd = Path(cwd_value)
    if cwd.name != run_id or (cwd.exists() and not cwd.is_dir()):
        raise ValueError("native Luna run ID does not identify its per-run working directory")

    event_path = _resolve_proof_file(native, "events_path", "events_sha256", "events_relative_path", "events", result_path)
    output_path_resolved = _resolve_proof_file(native, "output_path", "output_sha256", "output_relative_path", "output", result_path)
    stderr_path = _resolve_proof_file(native, "stderr_path", "stderr_sha256", "stderr_relative_path", "stderr", result_path)
    sidecar_dirs = {event_path.parent, output_path_resolved.parent, stderr_path.parent}
    if len(sidecar_dirs) != 1 or next(iter(sidecar_dirs)).name != run_id:
        raise ValueError("native Luna event/output/stderr files do not share the recorded per-run directory")
    if Path(native["output_path"]).resolve() != Path(output_arg).resolve():
        raise ValueError("native Luna output hash does not bind the command's --output-last-message file")

    # A frozen checker result may be imported into a new round under a new
    # packet ID. Its baseline_execution record retains the source packet
    # identity; the native process evidence must continue to bind that
    # original execution rather than being rewritten to the import IDs.
    baseline_execution = result.get("baseline_execution")
    if baseline_execution is None:
        batch_id, input_hash = result.get("batch_id"), result.get("input_hash")
    else:
        if (not isinstance(baseline_execution, dict)
                or baseline_execution.get("model") != result['model']
                or not isinstance(baseline_execution.get("batch_id"), str)
                or not baseline_execution.get("batch_id")
                or not isinstance(baseline_execution.get("input_hash"), str)
                or not _SHA256.fullmatch(baseline_execution["input_hash"])
                or not isinstance(baseline_execution.get("baseline_hash"), str)
                or not _SHA256.fullmatch(baseline_execution["baseline_hash"])):
            raise ValueError("native Luna baseline import lacks a complete original execution binding")
        if (not isinstance(result.get("batch_id"), str) or not result.get("batch_id")
                or not isinstance(result.get("input_hash"), str) or not _SHA256.fullmatch(result["input_hash"])):
            raise ValueError("native Luna baseline import lacks its current batch/input binding")
        batch_id, input_hash = baseline_execution["batch_id"], baseline_execution["input_hash"]
    if (not isinstance(batch_id, str) or not batch_id or native.get("batch_id") != batch_id
            or not isinstance(input_hash, str) or not _SHA256.fullmatch(input_hash)
            or native.get("input_hash") != input_hash):
        if baseline_execution is not None:
            raise ValueError("native Luna baseline import original execution identity differs from the preserved proof")
        raise ValueError("native Luna execution record is not bound to this exact batch/input hash")

    try:
        output_bytes = output_path_resolved.read_bytes()
        output_payload = json.loads(output_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("native Luna output file is not a complete UTF-8 JSON object") from exc
    if not isinstance(output_payload, dict):
        raise ValueError("native Luna output must be a JSON object")
    if schema_file is not None:
        from .interaction_output_schema import validate_output_shape
        validate_output_shape(output_payload, json.loads(schema_file.read_text(encoding='utf-8')))
    result_payload = {key: value for key, value in result.items() if key not in _TRANSPORT_FIELDS}
    original_semantics = {key: value for key, value in output_payload.items() if key not in _TRANSPORT_FIELDS}
    if result_payload != original_semantics:
        raise ValueError("saved Luna result semantic payload differs from its original output file")

    events = _read_event_stream(event_path)
    for event in events:
        item = event.get('item')
        if isinstance(item, dict) and item.get('type') not in {'agent_message', 'reasoning', 'error'}:
            raise ValueError('scoped native Luna batch used a tool or nonsemantic action outside its supplied packet')
    starts = [(i, event) for i, event in enumerate(events) if event.get("type") == "thread.started"]
    if len(starts) != 1 or starts[0][1].get("thread_id") != thread_id:
        raise ValueError("native Luna thread ID is not proved by exactly one thread.started event")
    messages = [(i, _event_message(event)) for i, event in enumerate(events)]
    messages = [(i, text) for i, text in messages if text is not None]
    if not messages:
        raise ValueError("native Luna event stream contains no completed agent message")
    try:
        message_payload = json.loads(messages[-1][1])
    except json.JSONDecodeError as exc:
        raise ValueError("native Luna final agent_message is not JSON") from exc
    if message_payload != output_payload:
        raise ValueError("native Luna output file differs from the final agent_message event")
    completions = [i for i, event in enumerate(events) if event.get("type") == "turn.completed"]
    if not completions or completions[-1] <= messages[-1][0]:
        raise ValueError("native Luna event stream has no completed turn after its final agent message")

    observations = native.get("model_observations")
    observed_model = native.get("observed_model")
    provider_model = evidence.get("provider_model")
    if not isinstance(observations, list) or any(not isinstance(v, str) or not v for v in observations):
        raise ValueError("native Luna model observations must be an explicit list of observed strings")
    event_text = "\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events)
    if any(value not in event_text for value in observations):
        raise ValueError("native Luna provider model observation is not present in the original event stream")
    if observations:
        if observed_model not in observations or provider_model != observed_model:
            raise ValueError("native Luna observed provider identity differs from its event-sourced metadata")
    elif observed_model is not None or provider_model is not None:
        raise ValueError("native Luna provider identity cannot be claimed without an observed session event")

    for key in ("started_at", "completed_at"):
        if not isinstance(native.get(key), str) or not native[key].strip():
            raise ValueError("native Luna proof lacks process timestamps")
    return {"model": result['model'], "proof_kind": "native_subprocess", "run_id": run_id,
        "thread_id": thread_id, "batch_id": batch_id, "input_hash": input_hash,
        "execution_evidence_hash": hashlib.sha256(json.dumps(evidence, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()}


def validate_result_execution(result: dict, *, result_path=None, expected_models=None) -> dict:
    """Validate a completed result's actual execution identity.

    API results retain request-model evidence so frozen C and historical source
    evidence remain valid. Native models can pass only with the
    checked subprocess record and original sidecar files.
    """
    if not isinstance(result, dict):
        raise ValueError("model result is not an object")
    model = model_name(result.get("model"))
    if expected_models is not None and model not in expected_models:
        raise ValueError("model result does not use an explicitly allowed extraction model")
    evidence = result.get("execution_model_evidence")
    if not isinstance(evidence, dict) or evidence.get("requested_model") != model:
        raise ValueError("model result lacks matching actual request evidence")
    if not native_result(result):
        # Preserve the established ECNU proof semantics for already frozen
        # source/C artifacts; provider_model is not an alias for the request.
        return {"model": model, "proof_kind": "legacy_ecnu_request" if model == 'ecnu-max' else 'openai_compatible_request', "execution_evidence_hash":
            hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode("utf-8")).hexdigest()}
    proof = _check_luna_result(result, evidence, result_path)
    return proof


def validate_execution_client(client) -> str:
    """Compatibility spelling for call sites that validate a repair client."""
    return validate_client_execution_model(client)


def copy_execution_sidecars(result: dict, source_result_path, destination_result_path) -> list[Path]:
    """Copy native proof files into another batch snapshot without retagging results."""
    if not native_result(result):
        return []
    source_result_path = Path(source_result_path).resolve()
    destination_result_path = Path(destination_result_path).resolve()
    evidence = result.get("execution_model_evidence", {})
    native = evidence.get("native_execution", {}) if isinstance(evidence, dict) else {}
    validate_result_execution(result, result_path=source_result_path)
    copied = []
    sidecars = (("events_path", "events_relative_path", "events_sha256"),
        ("output_path", "output_relative_path", "output_sha256"),
        ("stderr_path", "stderr_relative_path", "stderr_sha256"))
    if 'schema_path' in native:
        sidecars += (("schema_path", "schema_relative_path", "schema_sha256"),)
    for abs_key, rel_key, hash_key in sidecars:
        relative = Path(native[rel_key])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("native Luna sidecar path cannot be copied outside its artifact root")
        source = _resolve_proof_file(native, abs_key, hash_key, rel_key, rel_key, source_result_path)
        source_root = None
        source_root_index = None
        for index, parent in enumerate(source_result_path.parents):
            if (parent / relative).resolve() == source:
                if source_root is not None:
                    raise ValueError("native Luna sidecar source root is ambiguous")
                source_root, source_root_index = parent, index
        if source_root is None:
            raise ValueError("native Luna sidecar is not rooted in the source batch artifact tree")
        if source_root_index >= len(destination_result_path.parents):
            raise ValueError("destination batch path is too shallow for portable native evidence")
        destination = (destination_result_path.parents[source_root_index] / relative).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != native[hash_key]:
                raise ValueError("destination already contains conflicting native Luna evidence")
        else:
            shutil.copyfile(source, destination)
        copied.append(destination)
    return copied
