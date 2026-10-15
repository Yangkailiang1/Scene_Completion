from types import SimpleNamespace
import pytest

from scene_completion.case_dag import CallGate, TaskRejected
from scene_completion.concern_gap_dag import Packets
from scene_completion.semantic_backend import prepare_packets, read_json


def test_partial_success_keeps_original_identity_across_execution_metadata_change(tmp_path):
    calls = []
    class Client:
        config = {'thinking': False, 'model_preflight': 'off'}
        def model(self, kind): return 'fixture'
        def agent(self, packet):
            number = packet['input']['number']
            calls.append(number)
            return {'items': [number] if number == 1 or calls.count(2) > 1 else 'bad',
                'execution_model_evidence': {'requested_model': 'fixture', 'thinking': False, 'reasoning_effort': None}}
    packets = Packets(tmp_path, SimpleNamespace(agent_mode='external', reuse_run=None), Client(), CallGate(1))
    def check(packet, raw):
        if not isinstance(raw['items'], list): raise ValueError('wrong shape')
        return raw['items']
    def prepare(version, prose):
        return lambda folder: prepare_packets(folder, 'gap-fixture',
            [{'number': n, 'execution_versions': version,
              'skill': '---\nname: scene-concern-gap\n---\n\n生成原子异常\n\n批量无法完成时' + prose}
             for n in (1, 2)], ['unchanged actual generation instruction'], {'items': []})
    folder = packets.prepare(tmp_path, 'G', prepare(1, '自动接手一次'), check)
    with pytest.raises(TaskRejected): packets.execute(folder, check)
    original = read_json(folder / 'manifest.json')['batches'][0]
    raw = (folder / 'results' / (original['batch_id'] + '.json')).read_bytes()
    folder = packets.prepare(tmp_path, 'G', prepare(2, '主控持续处理'), check)
    assert packets.execute(folder, check)['values'] == [1, 2]
    assert calls == [1, 2, 2]
    assert read_json(folder / 'manifest.json')['batches'][0] == original
    assert (folder / 'results' / (original['batch_id'] + '.json')).read_bytes() == raw


@pytest.mark.parametrize('field', ['instructions', 'source', 'output_contract'])
def test_semantic_input_or_contract_changes_cannot_reuse_partial_packets(tmp_path, field):
    from scene_completion.partial_packet_reuse import semantic_packet
    old = {'stage': 'gap-generation', 'input': {'source': 'original', 'execution_versions': 1},
        'instructions': ['preserve semantics'], 'output_contract': {'items': []}}
    import copy
    new = copy.deepcopy(old)
    if field == 'source': new['input'][field] = 'different source'
    else: new[field] = ['different meaning']
    assert semantic_packet(new) != semantic_packet(old)
