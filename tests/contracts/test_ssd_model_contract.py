import json
from copy import deepcopy

import pytest

from scene_completion.analysis.validation import validate_result
from scene_completion.application.execution import Execution
from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.ssd_contracts import INSTRUCTIONS, packet
from scene_completion.domain.task_catalog import role_for
from scene_completion.models.clients.deepagents_client import DeepAgentsClient
from scene_completion.workflow_core import TaskRejected


def resolve_input():
    return {
        "channel": "E",
        "records": [{"id": "source-1", "condition": "调用者未认证"}],
        "steps": [{"id": "step-1", "data": [], "entity_ids": []}],
        "registry": default_registry(),
    }


def resolved():
    common = {
        "source_record_id": "source-1",
        "step_id": "step-1",
        "target": "sender",
        "key": "human.authentication",
        "field_id": None,
        "entity_id": None,
        "condition": "调用者未认证",
        "status": "active",
    }
    return {
        "resolved_ids": ["source-1"],
        "concerns": [{**common, "id": "concern-1", "label": "认证"}],
        "scenarios": [
            {**common, "id": "scenario-1", "concern_ids": ["concern-1"], "expected": "拒绝"}
        ],
    }


def comparison_input():
    return {
        "pair": "G_E",
        "pairs": [
            {
                side: {
                    "id": identity,
                    "step_id": "step-1",
                    "target": "sender",
                    "key": "human.authentication",
                    "field_id": None,
                    "entity_id": None,
                    "condition": "调用者未认证",
                    "expected": "拒绝",
                    "label": "认证",
                    "status": "active",
                    "concern_ids": ["concern-1"],
                    "source_refs": [{"document_id": "doc-1", "quote": "重复原文" * 2000}],
                }
                for side, identity in (("left", "G-1"), ("right", "E-1"))
            }
        ],
    }


def decision():
    return {
        "decisions": [{"left_id": "G-1", "right_id": "E-1", "status": "full", "reason": "同条件"}]
    }


@pytest.mark.parametrize("task", ["ssd-resolve", "ssd-semantic-compare"])
@pytest.mark.parametrize("skill_suffix", ["", "\n当前节点补充说明。"])
def test_ssd_deepagents_uses_own_role_and_source_contract(tmp_path, task, skill_suffix):
    sent = []
    output = resolved() if task == "ssd-resolve" else decision()

    def transport(url, key, body, *args):
        sent.append(body)
        return {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "submit",
                                "type": "function",
                                "function": {
                                    "name": "submit_result",
                                    "arguments": json.dumps({"payload": output}),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    client = DeepAgentsClient(
        {
            "api_key": "offline-fixture",
            "base_url": "http://offline.test/v1",
            "agent_model": "offline",
            "run_root": str(tmp_path),
            "indexed_context": True,
        },
        transport=transport,
    )
    p = packet(task, resolve_input() if task == "ssd-resolve" else comparison_input(), ["UC-1"])
    p["skill_text"] = INSTRUCTIONS + skill_suffix
    original = deepcopy(p)
    assert client.agent(p)[next(iter(output))] == output[next(iter(output))]
    assert p == original
    assert role_for(task) == "checker"
    assert len(sent) == 1
    system = "\n".join(
        m["content"]
        if isinstance(m["content"], str)
        else "\n".join(block.get("text", "") for block in m["content"])
        for m in sent[0]["messages"]
        if m["role"] == "system"
    )
    assert system.count(INSTRUCTIONS) == (2 if skill_suffix else 1)
    if skill_suffix:
        assert skill_suffix in system
    else:
        assert "指定Skill已全文加载" not in system
    assert "来源由工具按source_record_id保留" in system
    assert "看不到文档已有异常E" not in system
    assert "本次启用indexed_context" not in system
    assert "lookup_evidence" not in {t["function"]["name"] for t in sent[0]["tools"]}
    if task == "ssd-semantic-compare":
        assert "明确允许读取pairs中指定的两侧G/E/GT结果" in system
        assert "重复原文" not in json.dumps(sent, ensure_ascii=False)
        contexts = [json.loads(f.read_text()) for f in (tmp_path / "model_contexts").glob("*.json")]
        assert set(contexts[0]["input"]["pairs"][0]["left"]) == {
            "id",
            "step_id",
            "target",
            "key",
            "field_id",
            "entity_id",
            "condition",
            "expected",
            "label",
        }


@pytest.mark.parametrize(
    "mutation", ["unknown", "missing_scenario", "unresolved_row", "wrong_binding"]
)
def test_resolve_completeness_rejected_before_caching(mutation):
    value = resolved()
    if mutation == "unknown":
        value["resolved_ids"] = ["other-channel"]
    elif mutation == "missing_scenario":
        value["scenarios"] = []
    elif mutation == "unresolved_row":
        value["resolved_ids"] = []
    else:
        value["scenarios"][0]["target"] = "receiver"
    with pytest.raises(ValueError):
        validate_result("ssd-resolve", value, resolve_input())


def test_incomplete_compare_is_not_cached_and_repair_receives_candidate(tmp_path):
    calls = []

    def transport(url, key, body, *args):
        calls.append(body)
        result = {"decisions": []} if len(calls) == 1 else decision()
        return {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "submit",
                                "type": "function",
                                "function": {
                                    "name": "submit_result",
                                    "arguments": json.dumps({"payload": result}),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    root = tmp_path / "run"
    config = {
        "api_key": "offline-fixture",
        "base_url": "http://offline.test/v1",
        "agent_model": "offline",
        "run_root": str(root),
        "indexed_context": True,
    }
    client = DeepAgentsClient(config, transport=transport)
    ex = Execution(root, mode="external", client=client, config=config)
    record = {"case": "UC-1", "stage": "ssd-compare", "rounds": 0}
    with pytest.raises(TaskRejected) as rejection:
        ex.semantic("ssd-semantic-compare", comparison_input(), record)
    assert not list((root / "semantic_responses").glob("*.json"))
    repair = {**deepcopy(record), "rounds": 1, "failure": rejection.value.details}
    result, _ = ex.semantic("ssd-semantic-compare", comparison_input(), repair)
    assert result == decision()
    assert "语义比较必须逐对返回全部候选" in json.dumps(calls[1], ensure_ascii=False)
    assert len(list((root / "semantic_responses").glob("*.json"))) == 1
    cached, proof = ex.semantic("ssd-semantic-compare", comparison_input(), record)
    assert cached == decision() and proof["semantic_response_reused"]
    assert len(calls) == 2
    packets = [json.loads(f.read_text()) for f in (root / "packets").glob("*.json")]
    assert all(p["input"] == comparison_input() for p in packets)
