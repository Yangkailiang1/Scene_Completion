import json

import pytest

from scene_completion.domain.contracts import packet
from scene_completion.infrastructure.storage import read_json
from scene_completion.models.clients.deepagents_client import DeepAgentsClient
from scene_completion.workflow.runtime.scheduler import TaskRejected


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("mode", ["tool_calls", "json_text"])
def test_string_question_is_rejected_with_path_and_preserved_for_repair(tmp_path, indexed, mode):
    bad = {"payload": {"services": []}, "review_questions": ["接口所属服务尚未说明"]}

    def transport(url, key, body, *args):
        msg = (
            {
                "content": json.dumps(
                    {"result": bad["payload"], "review_questions": bad["review_questions"]}
                )
            }
            if mode == "json_text"
            else {
                "content": "",
                "tool_calls": [
                    {
                        "id": "submit",
                        "function": {"name": "submit_result", "arguments": json.dumps(bad)},
                    }
                ],
            }
        )
        return {"choices": [{"message": msg, "finish_reason": "stop"}]}

    p = packet("api-map", {"SR": []})
    p["skill_text"] = "Extract and submit."
    client = DeepAgentsClient(
        {
            "api_key": "fixture",
            "base_url": "http://offline/v1",
            "agent_model": "offline",
            "run_root": str(tmp_path),
            "indexed_context": indexed,
            "submission_mode": mode,
        },
        transport=transport,
    )
    with pytest.raises(TaskRejected, match=r"review_questions\[0\].*JSON object") as failure:
        client.agent(p)
    rejected = read_json(tmp_path / failure.value.details["rejected_output"])
    assert (
        rejected["payload"] == {"services": []}
        and rejected["review_questions"] == bad["review_questions"]
    )
    assert not (tmp_path.parent / "business_questions.json").exists()


@pytest.mark.parametrize("mode", ["tool_calls", "json_text"])
def test_ssd_generate_accepts_valid_payload_with_one_invalid_question_reference(tmp_path, mode):
    payload = {"analyses": [], "supplements": []}
    valid = {"question": "原文是否另有限制", "required_answer": "补充规则", "source_refs": []}
    invalid = {**valid, "question": "引用未提供的行", "source_refs": [{"line": 42}]}
    questions = [invalid, valid]

    def transport(*args):
        message = {"content": json.dumps({"result": payload, "review_questions": questions})}
        if mode == "tool_calls":
            message = {
                "content": "",
                "tool_calls": [
                    {
                        "id": "submit",
                        "function": {
                            "name": "submit_result",
                            "arguments": json.dumps(
                                {"payload": payload, "review_questions": questions}
                            ),
                        },
                    }
                ],
            }
        return {"choices": [{"message": message, "finish_reason": "stop"}]}

    root = tmp_path / "run"
    p = packet(
        "ssd-generate", {"templates": [], "concerns": [], "all_failure_conditions": []}, ["UC1"]
    )
    p["skill_text"] = p["instructions"]
    client = DeepAgentsClient(
        {
            "api_key": "fixture",
            "base_url": "http://offline/v1",
            "agent_model": "offline",
            "run_root": str(root),
            "submission_mode": mode,
        },
        transport=transport,
    )
    result = client.agent(p)
    assert {key: result[key] for key in payload} == payload
    (valid_record,) = read_json(tmp_path / "business_questions.json")["items"].values()
    assert valid_record["reason"] == valid["question"]
    trace = read_json(next((root / "question_rejections").glob("*.json")))
    assert trace["index"] == 0 and trace["question"] == invalid
    assert "精确引用" in trace["error"]


@pytest.mark.parametrize(
    "payload,path",
    [
        ('{"services":[]}', "payload"),
        ({"services": "bad"}, "payload.services"),
        ({"services": ["bad"]}, "payload.services[0]"),
        (
            {"services": [{"name": "svc", "interfaces": ["GET /items"], "source_refs": []}]},
            "payload.services[0].interfaces[0]",
        ),
        (
            {"services": [{"name": "svc", "interfaces": [{"method": 123}], "source_refs": []}]},
            "payload.services[0].interfaces[0].method",
        ),
    ],
)
def test_nested_containers_cannot_reach_mapping_normalizer_as_strings(payload, path):
    from scene_completion.domain.contracts import schema
    from scene_completion.models.transport.model_submission import containers

    with pytest.raises(ValueError) as failure:
        containers(payload, schema("api-map"))
    assert path in str(failure.value)


def test_bounded_repair_keeps_good_payload_and_fixes_only_question_envelope(tmp_path):
    from scene_completion.application.execution import Execution

    seen = []

    def transport(url, key, body, *args):
        seen.append(body)
        if len(seen) == 2:
            prompt = json.dumps(body, ensure_ascii=False)
            assert "review_questions[0]" in prompt and "接口所属服务尚未说明" in prompt
        questions = (
            ["接口所属服务尚未说明"]
            if len(seen) == 1
            else [
                {
                    "question": "接口所属服务尚未说明",
                    "required_answer": "请提供所属服务",
                    "source_refs": [],
                }
            ]
        )
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"result": {"services": []}, "review_questions": questions}
                        )
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    root = tmp_path / "project" / "run"
    config = {
        "api_key": "fixture",
        "base_url": "http://offline/v1",
        "agent_model": "offline",
        "run_root": str(root),
        "submission_mode": "json_text",
        "indexed_context": True,
    }
    ex = Execution(
        root, mode="external", client=DeepAgentsClient(config, transport=transport), config=config
    )
    ex.add("api-map", "api-map", static={"SR": []})
    assert ex.finish()["complete"] and len(seen) == 2
    assert len(read_json(root.parent / "business_questions.json")["items"]) == 1


@pytest.mark.parametrize(
    "promoted,fail_at",
    [
        ({"analyses": [], "supplements": []}, None),
        ({"payload": {"analyses": []}, "supplements": []}, None),
        (
            {"payload": {"analyses": [], "supplements": []}, "supplements": []},
            "arguments.supplements",
        ),
        ({"analyses": [], "supplements": [], "extra": []}, "arguments.extra"),
        ({"analyses": [], "supplements": "wrong"}, "payload.supplements"),
    ],
)
def test_ssd_generate_tool_recovers_promoted_fields_or_audits_conflicts(
    tmp_path, promoted, fail_at
):
    from scene_completion.domain.ssd_contracts import packet as ssd_packet

    calls = []

    def transport(url, key, body, *args):
        calls.append(body)
        return {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "submit",
                                "function": {
                                    "name": "submit_result",
                                    "arguments": json.dumps(promoted),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    p = ssd_packet(
        "ssd-generate", {"templates": [], "concerns": [], "all_failure_conditions": []}, ["UC1"]
    )
    p["skill_text"] = "Submit scenario analysis."
    client = DeepAgentsClient(
        {
            "api_key": "fixture",
            "base_url": "http://offline/v1",
            "agent_model": "offline",
            "run_root": str(tmp_path),
            "submission_mode": "tool_calls",
        },
        transport=transport,
    )
    if fail_at:
        with pytest.raises(TaskRejected) as rejection:
            client.agent(p)
        assert fail_at in str(rejection.value)
        raw = read_json(tmp_path / rejection.value.details["rejected_output"])["arguments"]
        assert all(raw[k] == v for k, v in promoted.items())
    else:
        result = client.agent(p)
        assert result["analyses"] == [] and result["supplements"] == []
    assert len(calls) == 1
