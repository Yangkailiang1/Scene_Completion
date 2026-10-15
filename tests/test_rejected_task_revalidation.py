from types import SimpleNamespace

import pytest

from scene_completion import concern_gap_dag as dag
from scene_completion.case_dag import Scheduler, CallGate
from scene_completion.semantic_backend import prepare_packets, read_json, write_json
from scene_completion.sources import fingerprint
from scene_completion import rejected_task_revalidation as recovery


def test_offline_revalidation_rejects_changed_packet_before_promoting(tmp_path):
    prepare_packets(tmp_path, 'fixture', [{'source': 'original'}], [], {'items': []})
    row = read_json(tmp_path/'manifest.json')['batches'][0]
    path = tmp_path/'packets'/(row['batch_id']+'.json')
    packet = read_json(path)
    packet['input']['source'] = 'changed'
    write_json(path, packet)
    with pytest.raises(ValueError, match='packet identity changed'):
        recovery.promote_offline(tmp_path, lambda *a: [])


@pytest.mark.parametrize('semantic_defect', [False, True])
def test_offline_rejected_result_uses_original_execution_and_does_not_bypass_semantic_defects(tmp_path, monkeypatch, semantic_defect):
    calls = []
    pipeline_type = dag.Pipeline
    manifest = {'protocol': 'rr-sr-concern-gap-v2', 'source_hash': 'source', 'base_hash': 'base', 'scope': {'use_case_ids': ['UC']}}
    class Client:
        def __init__(self): self.config = {'thinking': False, 'model_preflight': 'off'}
        def model(self, kind): return 'fixture'
        def agent(self, packet):
            calls.append(1)
            return {'items': [{'semantic_defect': semantic_defect}],
                'execution_model_evidence': {'requested_model': 'fixture', 'thinking': False, 'reasoning_effort': None}}
    def setup(args, fixed=True):
        p = pipeline_type.__new__(pipeline_type)
        p.root, p.args, p.profiler, p.manifest = tmp_path, args, None, manifest
        p.client = Client(); p.embedding = Client()
        p.scheduler = Scheduler(tmp_path, auto_repair='off')
        p.packets = dag.Packets(tmp_path, args, p.client, CallGate(1))
        p.contexts = {'UC': {'root': tmp_path / 'case', 'validators': {}, 'version': 1}}
        def prepare(deps, folder): return prepare_packets(folder, 'interaction-fixture', [{'original_source': 'unchanged'}], [], {'items': []})
        def validator(packet, raw):
            if not fixed: raise ValueError('old validator bug')
            if raw['items'][0]['semantic_defect']: raise ValueError('real semantic defect')
            return raw['items']
        p.semantic('UC', 'normal', (), prepare, validator)
        p.build = lambda: None
        p.progress = lambda scheduler: None
        return p
    args = SimpleNamespace(agent_mode='external', output_dir=str(tmp_path))
    # Only a folder every packet of which is provable from local files may reach
    # the batch loop; a dispatch is counted here so the offline promise of this
    # entry point is asserted instead of assumed.
    dispatched = []
    original_execute = dag.Packets.execute
    def counting_execute(self, folder, validator):
        dispatched.append(str(folder)); return original_execute(self, folder, validator)
    monkeypatch.setattr(dag.Packets, 'execute', counting_execute)
    first = setup(args, fixed=False)
    assert not first.scheduler.run()['complete']
    # The original failing dispatch is not what this assertion is about.
    dispatched.clear()
    attempt = next((tmp_path / 'case/batches/normal/attempts').glob('*.json'))
    before = fingerprint(read_json(attempt))
    write_json(tmp_path / 'run_manifest.json', manifest)
    write_json(tmp_path / 'pipeline_arguments.json', vars(args))
    monkeypatch.setattr(dag, 'Pipeline', setup)
    request = SimpleNamespace(output_dir=str(tmp_path), use_case_id=['UC'], stage='normal')
    result, code = recovery.run(request)
    # A rejected result is only re-admitted when its own preserved execution
    # already satisfies the current rule; otherwise the offline tool reports the
    # task and never pays for a regeneration.
    assert result['model_calls'] == 0
    if semantic_defect:
        assert code == 2
        assert result['tasks'][0] == {'task': 'UC:normal', 'status': 'rejected', 'offline_ready': False,
            'dispatched': False, 'proofs': []}
        assert read_json(tmp_path / 'case_tasks.json')['tasks']['UC:normal']['status'] != 'passed'
    else:
        assert code == 0 and result['tasks'][0]['status'] == 'passed'
        assert result['tasks'][0]['proofs'][0]['attempt_hash'] == before
        assert read_json(tmp_path / 'case_tasks.json')['tasks']['UC:normal']['rounds'] == 0
    events = read_json(tmp_path / 'case_tasks.json')['events']
    assert [e['event'] for e in events if e['event'].startswith('offline_rejected_')] == (
        ['offline_rejected_revalidation_not_provable'] if semantic_defect else
        ['offline_rejected_execution_revalidation'])
    assert calls == [1] and fingerprint(read_json(attempt)) == before
    if semantic_defect:
        assert dispatched == []
    else:
        # Only the folder proven offline-ready may reach the batch loop at all.
        assert dispatched and set(dispatched) == {str(tmp_path / 'case/batches/normal')}
