"""Regress the customer RR::pending versus RR::local-rr-s001 failure."""

import json
from copy import deepcopy

import pytest

from scene_completion.analysis.validation import validate_result
from scene_completion.domain.contracts import packet, schema
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.api_documents import index_interfaces
from scene_completion.inputs.api_identity import (
    ApiIdentityError,
    mapping_lookup,
    mapping_model_candidate,
    mapping_model_schema,
)
from scene_completion.inputs.api_layers import merge_mappings, qualify_index, qualify_mapping
from scene_completion.models.deepagents_client import DeepAgentsClient
from scene_completion.review.reviews import Reviews
from scene_completion.workflow.scheduler import TaskRejected


def fixture():
    text = "PlatformService: POST /case/instances"
    ref = {"source_id": "rr", "line_start": 1, "line_end": 1, "quote": text}
    doc = {
        "source_id": "rr",
        "name": "rr.md",
        "channel": "normal",
        "lines": [{"number": 1, "text": text}],
    }
    mapping = {
        "services": [
            {
                "name": "PlatformService",
                "source_refs": [ref],
                "interfaces": [
                    {
                        "id": "local-rr-s001",
                        "name": "创建实例",
                        "method": "POST",
                        "address": "/case/instances",
                        "source_refs": [ref],
                    }
                ],
            }
        ]
    }
    return doc, mapping


@pytest.mark.parametrize(
    "placeholder", ["pending", "pending]", "[PENDING]", "unknown", "TBD", "待确认", "null"]
)
def test_raw_placeholder_is_rejected_but_defensive_merge_never_namespaces_the_placeholder(
    placeholder,
):
    doc, raw = fixture()
    raw["services"][0]["interfaces"][0]["declared_id"] = placeholder
    original = deepcopy(raw)
    with pytest.raises(ApiIdentityError) as error:
        validate_result("api-map", raw, {"RR": [doc]})
    assert error.value.identity_details["category"] == "placeholder_identifier"
    assert error.value.identity_details["path"] == "/services/0/interfaces/0/declared_id"
    mapping = merge_mappings([("RR", raw)])
    index = qualify_index(index_interfaces({"RR": [doc], "api-map": raw}), "RR")
    matched = mapping_lookup(mapping, index)
    assert list(matched) == ["RR::local-rr-s001"]
    assert index["apis"][0]["id"] == "RR::local-rr-s001"
    assert raw == original


def test_document_identifier_is_not_the_machine_identity_or_a_lookup_key():
    doc, raw = fixture()
    raw["services"][0]["interfaces"][0]["declared_id"] = "API-DOCUMENT-1"
    mapping = merge_mappings([("RR", raw)])
    index = qualify_index(index_interfaces({"RR": [doc], "api-map": raw}), "RR")
    assert list(mapping_lookup(mapping, index)) == ["RR::local-rr-s001"]
    assert mapping["services"][0]["interfaces"][0]["declared_id"] == "API-DOCUMENT-1"


@pytest.mark.parametrize("boundary", [None, "external"])
def test_qualification_is_idempotent_for_maps_and_indexes_even_without_declared_id(boundary):
    doc, raw = fixture()
    once = qualify_mapping(raw, "RR", boundary)
    twice = qualify_mapping(once, "RR", boundary)
    assert once == twice
    no_metadata = deepcopy(once)
    no_metadata["services"][0]["interfaces"][0].pop("declared_id")
    assert qualify_mapping(no_metadata, "RR", boundary) == once
    index = index_interfaces({"RR": [doc], "api-map": raw})
    index = qualify_index(index, "RR", boundary)
    assert qualify_index(index, "RR", boundary) == index


def test_parameter_expansion_mismatch_is_reported_at_index_validation_not_as_keyerror():
    doc, raw = fixture()
    mapping = merge_mappings([("RR", raw)])
    index = qualify_index(index_interfaces({"RR": [doc], "api-map": raw}), "RR")
    mapping["services"][0]["interfaces"][0]["id"] = "RR::different"
    with pytest.raises(ApiIdentityError) as error:
        validate_result("api-index", index, {"RR": [doc], "api-map": mapping})
    assert error.value.identity_details["category"] == "mapping_index_mismatch"
    assert error.value.identity_details["missing_in_mapping"] == ["RR::local-rr-s001"]


def test_model_schema_and_repair_context_do_not_ask_models_to_write_tool_metadata():
    public = schema("api-map")
    model = mapping_model_schema(public)
    fields = model["properties"]["services"]["items"]["properties"]["interfaces"]["items"][
        "properties"
    ]
    assert "id" in fields
    assert not {"declared_id", "source_layer", "interface_scope"} & fields.keys()
    assert (
        "declared_id"
        in public["properties"]["services"]["items"]["properties"]["interfaces"]["items"][
            "properties"
        ]
    )
    _, raw = fixture()
    api = raw["services"][0]["interfaces"][0]
    api.update(declared_id="pending]", source_layer="RR", interface_scope="system")
    cleaned = mapping_model_candidate(raw)
    assert cleaned["services"][0]["interfaces"][0]["id"] == "local-rr-s001"
    assert "declared_id" not in cleaned["services"][0]["interfaces"][0]
    assert api["declared_id"] == "pending]"


@pytest.mark.parametrize("indexed", [False, True])
def test_bad_model_declared_id_fails_at_submission_with_precise_diagnostics(tmp_path, indexed):
    from scene_completion.inputs.indexed_context import EvidenceContext

    doc, raw = fixture()
    p = packet("api-map", {"RR": [doc]})
    p.update(skill_text="test", node_key="rr-api-map")
    candidate = EvidenceContext(p).encode_output(raw) if indexed else deepcopy(raw)
    candidate["services"][0]["interfaces"][0]["declared_id"] = "pending]"
    sent = []

    def transport(*args):
        sent.append(args[2])
        return {
            "choices": [{"message": {"content": json.dumps(candidate)}, "finish_reason": "stop"}]
        }

    client = DeepAgentsClient(
        {
            "api_key": "offline",
            "base_url": "http://offline.invalid/v1",
            "agent_model": "offline",
            "run_root": str(tmp_path),
            "indexed_context": indexed,
            "submission_mode": "json_text",
        },
        transport=transport,
    )
    with pytest.raises(TaskRejected) as rejected:
        client.agent(p)
    assert len(sent) == 1
    record = read_json(tmp_path / rejected.value.details["rejected_output"])
    assert record["identity_error"]["category"] == "placeholder_identifier"
    assert record["identity_error"]["path"] == "/services/0/interfaces/0/declared_id"


def test_invalid_legacy_automatic_review_does_not_lock_the_task_into_reusing_it(tmp_path):
    doc, raw = fixture()
    raw["services"][0]["interfaces"][0]["declared_id"] = "pending"
    inputs = {"RR": [doc]}
    reviews = Reviews(tmp_path, "auto")
    path = reviews.path("rr-api-map")
    legacy = {
        "key": "rr-api-map",
        "status": "auto",
        "input_hash": fingerprint(inputs),
        "execution_identity": "same",
        "payload": raw,
    }
    write_json(path, legacy)
    assert reviews.cached("rr-api-map", "api-map", inputs, "same") is None
    assert read_json(path) == legacy


def test_real_identifier_containing_pending_is_not_a_placeholder():
    doc, raw = fixture()
    raw["services"][0]["interfaces"][0]["id"] = "list-pending-jobs"
    validate_result("api-map", raw, {"RR": [doc]})


def test_resume_rejects_old_placeholder_artifact_and_review_without_manual_edits(tmp_path):
    from scene_completion.workflow.engine import Execution, build_pipeline
    from tests.test_workflow import fake_pipeline

    rr, sr, tests, mocks = fake_pipeline(tmp_path)
    line = {"number": len(rr[0]["lines"]) + 1, "text": "POST /case/instances"}
    # Keep the API in the normal channel rather than after the exception heading.
    rr[0]["lines"].insert(2, line)
    for number, row in enumerate(rr[0]["lines"], 1):
        row["number"] = number
    ref = {
        "source_id": rr[0]["source_id"],
        "line_start": 3,
        "line_end": 3,
        "quote": line["text"],
    }
    calls = []

    def mapping(p):
        calls.append((p["node_key"], p["task"]))
        if "RR" not in p["input"]:
            return {"services": []}
        return {
            "services": [
                {
                    "name": "Platform",
                    "source_refs": [ref],
                    "interfaces": [
                        {
                            "id": "local-rr-s001",
                            "name": "创建实例",
                            "method": "POST",
                            "address": "/case/instances",
                            "source_refs": [ref],
                        }
                    ],
                }
            ]
        }

    def parameters(p):
        calls.append((p["node_key"], p["task"]))
        api = p["input"]["interface"]
        return {
            "apis": [
                {
                    "id": api["id"],
                    "name": api["name"],
                    "address": api["address"],
                    "parameters": [],
                    "source_refs": [ref],
                }
            ]
        }

    mocks.update({"api-map": mapping, "api-parameters": parameters})
    run = tmp_path / "run"
    execution = Execution(run, mocks=mocks)
    build_pipeline(execution, rr, sr, tests)
    assert execution.finish()["complete"]

    def output(key):
        return read_json(run / execution.scheduler.state["tasks"][key]["output_file"])["payload"]

    before_components = deepcopy(execution.scheduler.state["tasks"]["components"])
    before_params = deepcopy(output("api-parameters"))
    assert before_params["apis"][0]["id"] == "RR::local-rr-s001"
    before_calls = len(calls)

    # Simulate artifacts sealed by the old validator, including its accepted
    # automatic review. Only this isolated fixture changes saved task files.
    state = read_json(run / "workflow_tasks.json")
    for key in ("rr-api-map", "api-map"):
        record = state["tasks"][key]
        path = run / record["output_file"]
        envelope = read_json(path)
        api = envelope["payload"]["services"][0]["interfaces"][0]
        api["declared_id"] = "pending]"
        if key == "api-map":
            api["id"] = "RR::pending]"
        write_json(path, envelope)
        record["output_hash"] = fingerprint(envelope)
    write_json(run / "workflow_tasks.json", state)
    review_path = execution.reviews.path("rr-api-map")
    legacy_review = read_json(review_path)
    legacy_review["payload"]["services"][0]["interfaces"][0]["declared_id"] = "pending]"
    write_json(review_path, legacy_review)

    execution = Execution(run, mocks=mocks)
    build_pipeline(execution, rr, sr, tests)
    result = execution.finish()
    assert result["complete"], {
        key: value.get("failure")
        for key, value in execution.scheduler.state["tasks"].items()
        if value["status"] != "passed"
    }
    assert list(mapping_lookup(output("api-map"), output("api-index"))) == ["RR::local-rr-s001"]
    assert output("api-parameters") == before_params
    assert (
        execution.scheduler.state["tasks"]["components"]["output_hash"]
        == before_components["output_hash"]
    )
    assert calls[before_calls:] == [("rr-api-map", "api-map")]
    assert "pending]" not in json.dumps(output("rr-api-map"))
