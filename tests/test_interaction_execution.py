"""Request provenance and resumable repairs stay explicit."""
import json

from scene_completion.semantic_backend import SemanticClient, prepare_packets, read_json, write_json, run_agent_packets


def test_ecnu_request_thinking_and_provider_identity_are_separate(monkeypatch):
    monkeypatch.setenv("TEST_ECNU_KEY", "dummy-local-test-key")
    requests = []
    def transport(url, key, body, timeout, retries):
        requests.append(body)
        return {"model": "provider-backend-model", "choices": [{"message": {"content": json.dumps({"items": []})}}]}
    client = SemanticClient({"base_url": "https://example.invalid", "api_key_env": "TEST_ECNU_KEY", "agent_model": "ecnu-max", "thinking": True, "reasoning_effort": "high"}, transport)
    result = client.agent({"stage": "interaction-model", "input": {}})
    assert requests[0]["model"] == "ecnu-max" and requests[0]["thinking"] == {"type": "enabled"}
    assert requests[0]["reasoning_effort"] == "high"
    assert result["execution_model_evidence"]["requested_model"] == "ecnu-max"
    assert result["execution_model_evidence"]["provider_model"] == "provider-backend-model"


def test_reprepare_preserves_previous_version_manifest_without_retagging_results(tmp_path):
    from scene_completion.sources import fingerprint
    old = prepare_packets(tmp_path, 'interaction-fixture', [{'value': 1}], ['first rule'], {'items': []})
    bid = old['batches'][0]['batch_id']
    raw = {**old['batches'][0], 'model': 'ecnu-max', 'items': ['original']}
    write_json(tmp_path / 'results' / (bid + '.json'), raw)
    new = prepare_packets(tmp_path, 'interaction-fixture', [{'value': 1}], ['changed rule'], {'items': []})
    assert old != new
    assert read_json(tmp_path / 'manifest_history' / (fingerprint(old) + '.json')) == old
    assert read_json(tmp_path / 'results' / (bid + '.json')) == raw
    assert not (tmp_path / 'results' / (new['batches'][0]['batch_id'] + '.json')).exists()


def test_cache_invalidates_thinking_change_and_keeps_failed_repair_feedback(tmp_path):
    manifest = prepare_packets(tmp_path, "interaction-fixture", [{"value": 1}], [], {"items": []})
    batch = manifest["batches"][0]
    write_json(tmp_path / "results" / (batch["batch_id"] + ".json"), {**batch, "model": "ecnu-max", "items": ["old"], "execution_model_evidence": {"requested_model": "ecnu-max", "thinking": False, "reasoning_effort": None}})
    previous = {**batch, "items": ["bad"]}
    write_json(tmp_path / "attempts" / (batch["batch_id"] + "-previous.json"), {"result": previous, "validation_error": "exact failure", "attempt": 1})
    class Client:
        config = {"max_concurrency": 1, "thinking": True, "reasoning_effort": "high"}
        packets = []
        def model(self, kind):
            return "ecnu-max"
        def agent(self, packet):
            self.packets.append(packet)
            return {"items": ["new"], "execution_model_evidence": {"requested_model": "ecnu-max", "thinking": True, "reasoning_effort": "high"}}
    client = Client()
    assert run_agent_packets(tmp_path, client, lambda p, r: r["items"])["complete"]
    assert len(client.packets) == 1
    assert client.packets[0]["previous_output"] == previous
    assert client.packets[0]["validation_feedback"] == "exact failure"
    assert read_json(tmp_path / "results" / (batch["batch_id"] + ".json"))["items"] == ["new"]


def test_failed_reassessment_removes_previous_acceptance_files(tmp_path, monkeypatch):
    from argparse import Namespace
    from scene_completion import role_cli, interaction_replay
    from scene_completion.interaction_protocol import PROTOCOL
    import pytest
    write_json(tmp_path / "run_manifest.json", {"protocol": PROTOCOL})
    for name in ("acceptance.json", "assessment_status.json", "scene_assessment.xlsx", "report.md"):
        (tmp_path / name).write_text("previous acceptance", encoding="utf-8")
    def fail(directory):
        raise ValueError("changed version")
    monkeypatch.setattr(interaction_replay, "evaluate", fail)
    with pytest.raises(ValueError, match="changed version"):
        role_cli.run_evaluate(Namespace(output_dir=str(tmp_path)))
    assert all(not (tmp_path / name).exists() for name in ("acceptance.json", "assessment_status.json", "scene_assessment.xlsx", "report.md"))
