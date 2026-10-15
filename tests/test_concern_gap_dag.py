"""Exercise the real v2 adapter and packet validation with an offline API fixture."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import threading
import pytest

from scene_completion import concern_gap_dag as dag
from scene_completion.semantic_backend import SemanticClient, read_json, write_json
from scene_completion.sources import validate_refs, fingerprint


def test_unchanged_semantic_inputs_reuse_success_when_producer_returns_no_manifest(tmp_path):
    from scene_completion.case_dag import Scheduler,CallGate
    from scene_completion.semantic_backend import prepare_packets
    calls=[]
    class Client:
        config={'agent_model':'fixture','thinking':False,'model_preflight':'off'}
        def model(self,kind):return 'fixture'
        def agent(self,packet):
            calls.append(1)
            return {'items':[],'execution_model_evidence':{'requested_model':'fixture','thinking':False,'reasoning_effort':None}}
    client=Client()
    def setup(version):
        adapter=dag.Pipeline.__new__(dag.Pipeline)
        adapter.scheduler=Scheduler(tmp_path)
        adapter.packets=dag.Packets(tmp_path,SimpleNamespace(agent_mode='external',reuse_run=None),client,CallGate(1))
        adapter.contexts={'uc':{'root':tmp_path/'case','validators':{},'version':version}}
        def prepare(deps,folder):
            prepare_packets(folder,'gap-fixture',[{'original':'same source'}],[],{'items':[]})
            # Graph-style producers write their manifest without returning it.
        adapter.semantic('uc','audit',(),prepare,lambda p,r:r['items'])
        return adapter
    first=setup(1);assert first.scheduler.run()['complete']
    before=first.scheduler.state['tasks']['uc:audit']['output_hash']
    second=setup(2);assert second.scheduler.run()['complete']
    assert calls==[1] and second.scheduler.state['tasks']['uc:audit']['output_hash']==before


def arguments(tmp_path):
    rr = tmp_path / 'rr.md'
    sr = tmp_path / 'sr.md'
    test = tmp_path / 'test.md'
    rr.write_text('# RR\n## UC-1\n### 主成功路径\n顾客通过商城UI查询商品。\n商城UI展示商品查询结果。\n', encoding='utf8')
    sr.write_text('# SR\n## UC-1-API\n### 基本流程\n商城UI向商品服务请求查询商品。\n商品服务返回商品查询结果。\n', encoding='utf8')
    test.write_text('# Tests\n## 商品查询\n### TEST-001：正常商品查询\n- 场景类型：正常\n- 前置条件：系统正常运行\n- 触发条件：查询商品\n- 关联需求：UC-1\n- 测试目标：查询商品\n- 预期结果：返回商品查询结果\n- 来源定位：rr.md:4\n', encoding='utf8')
    base = tmp_path / 'seed.json'
    write_json(base, {'use_cases': [{'use_case_id': 'UC-1', 'use_case_name': '商品查询',
        'source_use_case_ids': {'SR': ['UC-1-API']}}], 'system_composition': {'nodes': [
            {'name': '顾客', 'kind': 'human_actor', 'layer': 'RR'},
            {'name': '商品服务', 'kind': 'internal_service', 'layer': 'SR'}]}})
    config = tmp_path / 'config.json'
    write_json(config, {'base_url': 'https://fixture.invalid/v1', 'agent_model': 'fixture-model',
        'embedding_model': 'fixture-vector', 'max_concurrency': 3, 'thinking': False, 'model_preflight': 'off'})
    return SimpleNamespace(model=str(base), rr_spec_document=[str(rr)], sr_spec_document=[str(sr)],
        test_spec_document=[str(test)], config=str(config), env_file=None, output_dir=str(tmp_path / 'run'),
        agent_mode='external', agent_runtime=None, agent_model=None, embedding_model=None,
        auto_repair='bounded', max_repair_rounds=2, use_case_id=None, reuse_run=None)


def test_full_dag_packet_flow_final_rebuild_and_zero_call_resume(tmp_path, monkeypatch):
    from scene_completion import role_cli
    from scene_completion.concern_gap_replay import replay, export_snapshot, rebuild_snapshot
    calls = []
    pipeline = None
    def ref(document, first=4, last=None):
        return validate_refs([{'document': document, 'line_start': first, 'line_end': last or first}], pipeline.index)
    def model(packet):
        rr, sr = ref('rr.md'), ref('sr.md')
        rr_both, sr_both = ref('rr.md', 4, 5), ref('sr.md', 4, 5)
        return {'query_data_policy': packet['input']['query_data_policy'],
            'covered_section_ids': packet['input']['required_section_ids'],
            'components': [{'component_id': 'customer', 'name': '顾客', 'kind': 'human_actor', 'layer': 'RR', 'source_refs': rr},
                {'component_id': 'ui', 'name': '商城UI', 'kind': 'frontend_ui', 'layer': 'RR', 'boundary_role': 'ui', 'source_refs': rr},
                {'component_id': 'service', 'name': '商品服务', 'kind': 'internal_service', 'layer': 'SR', 'service_types': ['query_retrieval'], 'source_refs': sr}],
            'use_case_hierarchy': [{'unit_id': 'RR', 'source_id': 'UC-1', 'name': '商品查询', 'layer': 'RR', 'parent_ids': [], 'source_refs': rr},
                {'unit_id': 'SR', 'source_id': 'UC-1-API', 'name': '商品查询', 'layer': 'SR', 'parent_ids': ['RR'], 'source_refs': sr}],
            'exchanges': [{'local_id': 'r1', 'hierarchy_unit_id': 'RR', 'requirement_layer': 'RR', 'from_component_id': 'customer', 'to_component_id': 'ui',
                'operation': '查询商品', 'operation_kinds': ['read'], 'path_type': 'main_success', 'response_fields': ['商品查询结果'], 'source_refs': rr_both},
                {'local_id': 's1', 'hierarchy_unit_id': 'SR', 'requirement_layer': 'SR', 'parent_rr_local_id': 'r1', 'from_component_id': 'ui', 'to_component_id': 'service',
                    'operation': '查询商品', 'operation_kinds': ['read'], 'path_type': 'main_success', 'response_fields': ['商品查询结果'], 'source_refs': sr_both}],
            'normal_scenarios': [{'hierarchy_unit_id': layer, 'requirement_layer': layer, 'scenario_type': 'main_success', 'name': '查询商品',
                'steps': ['查询商品'], 'expected_result': '商品查询结果', 'source_refs': references} for layer, references in [('RR', rr_both), ('SR', sr_both)]],
            'implementation_references': [], 'model_gaps': [], 'pending_details': []}
    def answer(packet):
        data, stage = packet['input'], packet['stage']
        if stage == 'interaction-model':
            return model(packet)
        if stage == 'interaction-checker':
            return {'covered_section_ids': [s['chapter_id'] for s in data['sections']], 'scenarios': []}
        if stage == 'interaction-checker-audit':
            return {'covered_section_ids': [s['chapter_id'] for s in data['sections']], 'reviews': [], 'omitted_conditions': []}
        if stage == 'interaction-participants':
            rows = []
            for node in data['normal_model']['components']:
                quote = dag.old.cited_text(node['source_refs'], pipeline.index)
                rows.append({'component_id': node['component_id'], 'status': 'logical_boundary' if node.get('boundary_role') else 'missing_declaration',
                    'role_quote': quote, 'role_refs': node['source_refs'], 'interaction_quote': quote,
                    'interaction_refs': node['source_refs'], 'reason': 'actual positive call, participant declaration absent'})
            return {'component_reviews': rows, 'missing_model_calls': [], 'unresolved_candidates': []}
        if stage == 'gap-graph-check':
            return {'checks': [{'id': item['exchange_id'] if kind == 'ssd' else item['node_id'], 'kind': kind,
                'valid': True, 'source_refs': item['source_refs'], 'evidence_quote': dag.old.cited_text(item['source_refs'], pipeline.index),
                'reason': 'fixture source check', 'warnings': []} for kind, items in [('ssd', data['exchanges']), ('composition', data['nodes'])] for item in items]}
        if stage == 'gap-features':
            return {'items': [{'exchange_id': e['exchange_id'], 'traits': [{'name': 'operation_kinds', 'value': e['operation_kinds'], 'basis': 'explicit',
                'evidence_quote': dag.old.cited_text(e['source_refs'], pipeline.index), 'source_refs': e['source_refs'], 'rationale': 'positive request'}],
                'pending_details': []} for e in data['exchanges']]}
        if stage == 'gap-generation':
            return {'items': [{'mount_id': m['mount_id'], 'scenarios': [{'name': 'fixture exception', 'exception_object': '商品', 'operation': '查询商品',
                'failure_mechanism': m['concern_key'], 'trigger_condition': m['concern_key'] + ' condition', 'necessary_conditions': [],
                'source_refs': m['source_refs'], 'pending_details': []}]} for m in data['mounts']]}
        if stage == 'gap-test-extract':
            return {'items': [{'test_scenario_id': r['test_scenario_id'], 'conditions': []} for r in data['records']]}
        if stage.startswith('gap-normalize-'):
            return {'items': [{'source_scenario_id': s['scenario_id'], 'units': [{'object_code': 'product',
                'cause_code': s['concern_keys'][0].replace('.', '_'), 'condition_codes': [], 'reason': 'fixture canonical identity'}]} for s in data['scenarios']]}
        if stage.startswith('gap-reverse-check-'):
            originals = {s['scenario_id']: s for s in data['original_scenarios']}
            return {'reviews': [{'unit_id': u['unit_id'], 'source_supported': True, 'atomic': True, 'mapping_correct': True, 'cause_correct': True,
                'evidence_quote': originals[u['source_scenario_id']]['trigger_condition'], 'reason': 'fixture checked cause', 'warnings': []} for u in data['units']]}
        raise AssertionError('unexpected fixture request: ' + stage)
    class FixtureClient(SemanticClient):
        def agent(self, packet):
            calls.append(packet['stage'])
            return {**answer(packet), 'execution_model_evidence': {'requested_model': self.model('agent'), 'thinking': False, 'reasoning_effort': None}}
    monkeypatch.setattr(role_cli, '_client', lambda args, root: FixtureClient(read_json(args.config)))
    args = arguments(tmp_path)
    pipeline = dag.Pipeline(args)
    pipeline.build()
    assert pipeline.scheduler.run(pipeline.progress)['complete']
    result, code = pipeline.aggregate()
    assert code == 0 and result['complete']
    count = len(calls)
    assert count > 10
    assert (Path(args.output_dir) / 'scene_assessment.xlsx').exists()
    assert replay(args.output_dir)['complete']
    snapshot = tmp_path / 'snapshot.json'
    export_snapshot(args.output_dir, snapshot)
    assert rebuild_snapshot(snapshot, tmp_path / 'rebuilt')['result_hash'] == result['result_hash']
    pipeline = dag.Pipeline(args)
    pipeline.build()
    assert pipeline.scheduler.run(pipeline.progress)['complete']
    resumed, code = pipeline.aggregate()
    assert resumed['result_hash'] == result['result_hash'] and len(calls) == count
    # History import is a distinct E-only channel. The selected case still
    # receives fresh normal/G/E/T packets in its own output directory.
    from scene_completion.concern_gap_history import load,verify_binding
    history=load(args.output_dir,pipeline.index,{'UC-1'},['UC-1'])
    assert history['history']==[] and history['source_units']==[]
    verify_binding(history['binding'])
    old_root=args.output_dir
    args.history_run=old_root;args.output_dir=str(tmp_path/'new-run')
    pipeline=dag.Pipeline(args);pipeline.build()
    assert pipeline.scheduler.run(pipeline.progress)['complete']
    new_result,code=pipeline.aggregate()
    assert new_result['complete'] and len(calls)>count
    assert replay(args.output_dir)['complete']
    assert 'history_import' in read_json(Path(args.output_dir)/'result_bundle.json')


def test_history_prefetch_is_independent_cached_and_does_not_rank(tmp_path, monkeypatch):
    from tests.test_concern_gap import unit
    from scene_completion.concern_gap_ranking import rank
    monkeypatch.setenv('VECTOR_TEST_KEY', 'fixture')
    requests = []
    def transport(url, key, body, *args):
        requests.append(body['input'])
        return {'data': [{'index': i, 'embedding': [1., 0.]} for i in range(len(body['input']))]}
    p = dag.Pipeline.__new__(dag.Pipeline)
    p.embedding = SemanticClient({'base_url': 'https://fixture.invalid/v1', 'api_key_env': 'VECTOR_TEST_KEY',
        'embedding_model': 'vector', 'model_preflight': 'off', 'cache_dir': str(tmp_path)}, transport)
    p.embedding_lock = threading.Lock()
    history = [unit('h1'), unit('h2', 'timeout')]
    output = p.prefetch(history)
    assert not output['ranking_published'] and 'selected_ids' not in output
    assert len(requests) == 1
    p.prefetch(history)
    assert len(requests) == 1
    selected = rank([unit('candidate')], history, p.embedding)
    assert selected['complete'] and len(requests) == 1


def test_failed_history_import_does_not_block_normal_and_resume_reuses_success(tmp_path, monkeypatch):
    from scene_completion import concern_gap_history as h
    args=arguments(tmp_path);args.history_run=str(tmp_path/'missing-history');args.agent_mode='packets'
    pipeline=dag.Pipeline(args)  # Invalid history must not abort construction.
    pipeline.build()
    key='@project:history-import'; normal='UC-1:normal'; calls=[]
    assert key not in pipeline.scheduler.tasks[normal].deps
    assert key in pipeline.scheduler.tasks['@project:historical-ranking'].deps
    task=pipeline.scheduler.tasks[normal]
    task.execute=lambda deps,record:(calls.append(1) or {'local_fixture':True})
    task.verify=None
    pipeline.scheduler.run(pipeline.progress, allowed={key,normal})
    assert pipeline.scheduler.state['tasks'][normal]['status']=='passed'
    assert pipeline.scheduler.state['tasks'][key]['status']=='pending'
    assert read_json(Path(args.output_dir)/'progress.json')['formal_metrics'] is None
    corpus={'binding':{'proofs':{},'excluded_use_case_ids':['UC-1'],'corpus_hash':fingerprint([])},
        'history':[],'source_units':[]}
    monkeypatch.setattr(h,'load',lambda *a:copy.deepcopy(corpus))
    monkeypatch.setattr(h,'copy_vectors',lambda *a:0)
    pipeline.scheduler.run(pipeline.progress, allowed={key,normal})
    assert pipeline.scheduler.state['tasks'][key]['status']=='passed'
    assert calls==[1]  # History repair must not regenerate successful modeling.


def test_cli_default_and_packet_mode_never_calls_external_model(tmp_path, monkeypatch):
    from scene_completion import role_cli
    from scene_completion.semantic_backend import SemanticClient
    monkeypatch.setattr(SemanticClient, 'agent', lambda *a: (_ for _ in ()).throw(AssertionError('packet mode called model')))
    args = arguments(tmp_path)
    args.agent_mode = 'packets'
    summary, code = dag.run(args)
    assert not summary['complete'] and code == 0
    assert read_json(Path(args.output_dir) / 'progress.json')['formal_metrics'] is None
    assert not (Path(args.output_dir) / 'metrics.json').exists()
    from scene_completion.concern_gap_replay import export_snapshot, rebuild_snapshot
    snapshot = tmp_path / 'partial.json'
    result = export_snapshot(args.output_dir, snapshot)
    assert result['partial_snapshot'] and not result['complete']
    rebuilt = rebuild_snapshot(snapshot, tmp_path / 'offline')
    assert not rebuilt['complete'] and rebuilt['formal_metrics'] is None
    assert not (tmp_path / 'offline/metrics.json').exists()


def test_packet_cache_does_not_bypass_changed_dynamic_model(tmp_path):
    from scene_completion.case_dag import CallGate
    from scene_completion.semantic_backend import prepare_packets
    calls = []
    class Client:
        config = {'agent_model': 'ecnu-max', 'thinking': False, 'max_concurrency': 1, 'model_preflight': 'off'}
        def model(self, kind):
            return self.config['agent_model']
        def agent(self, packet):
            calls.append(self.model('agent'))
            return {'items': [], 'execution_model_evidence': {'requested_model': self.model('agent'),
                'thinking': False, 'reasoning_effort': None}}
    client = Client()
    args = SimpleNamespace(agent_mode='external', reuse_run=None)
    packets = dag.Packets(tmp_path, args, client, CallGate(1))
    folder = tmp_path / 'batch'
    prepare_packets(folder, 'gap-fixture', [{}], [], {'items': []})
    validator = lambda p, r: r['items']
    packets.execute(folder, validator)
    packets.execute(folder, validator)
    client.config['agent_model'] = 'qwen38-27b-vl'
    packets.execute(folder, validator)
    assert calls == ['ecnu-max', 'qwen38-27b-vl']


def test_legacy_packet_import_preserves_original_batch_identity(tmp_path):
    from scene_completion.case_dag import CallGate
    from scene_completion.semantic_backend import prepare_packets
    class Client:
        config = {'agent_model': 'ecnu-max', 'thinking': False, 'max_concurrency': 1, 'model_preflight': 'off'}
        def model(self, kind):
            return 'ecnu-max'
        def agent(self, packet):
            return {'items': [packet['input']['value']], 'execution_model_evidence': {
                'requested_model': 'ecnu-max', 'thinking': False, 'reasoning_effort': None}}
    validator = lambda p, r: r['items']
    old_root = tmp_path / 'old'
    original = old_root / 'batches/gap-fixture'
    prepare_packets(original, 'gap-fixture', [{'value': 0}, {'value': 1}], [], {'items': []})
    old_packets = dag.Packets(old_root, SimpleNamespace(agent_mode='external'), Client(), CallGate(1))
    old_packets.execute(original, validator)
    preserved = read_json(original / 'manifest.json')['batches'][1]
    destination = tmp_path / 'new/batches/gap-fixture'
    prepare_packets(destination, 'gap-fixture', [{'value': 1}], [], {'items': []})
    packets = dag.Packets(tmp_path / 'new', SimpleNamespace(agent_mode='packets', reuse_run=str(old_root)), Client(), CallGate(1))
    packets.import_valid(destination, validator)
    assert read_json(destination / 'manifest.json')['batches'] == [preserved]
    result = packets.execute(destination, validator)
    assert result['executions'][0]['batch_id'] == preserved['batch_id']
    assert read_json(destination / 'results' / (preserved['batch_id'] + '.json')) == read_json(original / 'results' / (preserved['batch_id'] + '.json'))


def test_targeted_repair_rejects_collateral_change_to_successful_unit(tmp_path):
    from scene_completion.case_dag import CallGate, TaskRejected
    from scene_completion.semantic_backend import prepare_packets
    class Client:
        config = {'agent_model': 'ecnu-max', 'thinking': False, 'max_concurrency': 1, 'model_preflight': 'off'}
        repair = False
        def model(self, kind):
            return 'ecnu-max'
        def agent(self, packet):
            return {'items': [{'scenario_id': 'good', 'value': 2 if self.repair else 1}, {'scenario_id': 'bad', 'value': 1}],
                'execution_model_evidence': {'requested_model': 'ecnu-max', 'thinking': False, 'reasoning_effort': None}}
    client = Client()
    packets = dag.Packets(tmp_path, SimpleNamespace(agent_mode='external'), client, CallGate(1))
    original = tmp_path / 'batches/target'
    prepare_packets(original, 'gap-fixture', [{'scenario_ids': ['good', 'bad']}], [], {'items': []})
    validator = lambda p, r: r['items']
    previous = packets.execute(original, validator)
    old_hash = fingerprint(read_json(Path(previous['executions'][0]['result_path'])))
    client.repair = True
    with pytest.raises(TaskRejected) as rejected:
        packets.repaired(tmp_path, 'target', previous, validator, {'action': 'repair'},
            {'findings': [{'scenario_id': 'bad', 'reason': 'actual defect'}]}, 1)
    assert 'unrelated successful' in str(rejected.value)
    assert fingerprint(read_json(Path(previous['executions'][0]['result_path']))) == old_hash


def test_repair_resolves_last_failed_manifest_instead_of_initial_packet(tmp_path):
    from scene_completion.semantic_backend import prepare_packets
    original = tmp_path / 'batches/normal'
    latest = tmp_path / 'batches/normal-repair-2'
    prepare_packets(original, 'interaction-model', [{'original': 'source'}], [], {'items': []})
    manifest = prepare_packets(latest, 'interaction-model', [{'original': 'source', 'bounded_repair': {'prior_output': 'previous fix'}}], [], {'items': []})
    target = dag.rejected_target(tmp_path, 'normal', {'input_hash': manifest['input_hash']})
    assert Path(target['folder']) == latest.resolve()
    with pytest.raises(ValueError, match='missing or ambiguous'):
        dag.rejected_target(tmp_path, 'normal', {'input_hash': 'unknown'})


def test_supervisor_cache_checks_each_configured_endpoint_and_effort(tmp_path):
    from scene_completion.case_dag import CallGate
    class Client:
        def __init__(self, name, url):
            self.name, self.base_url = name, url
            self.config = {'thinking': True, 'reasoning_effort': 'high'}
        def model(self, kind): return self.name
    batch, supervisor = Client('batch', 'https://batch.invalid'), Client('supervisor', 'https://supervisor.invalid')
    packets = dag.Packets(tmp_path, SimpleNamespace(agent_mode='external'), batch, CallGate(1))
    packets.cache_clients.append(supervisor)
    raw = {'model': 'supervisor', 'execution_model_evidence': {'requested_model': 'supervisor',
        'api_endpoint_hash': fingerprint(supervisor.base_url), 'thinking': True, 'reasoning_effort': 'high'}}
    packets.cache_identity(raw)
    raw['execution_model_evidence']['api_endpoint_hash'] = fingerprint(batch.base_url)
    with pytest.raises(ValueError, match='endpoint'): packets.cache_identity(raw)


def test_supervisor_adapter_validates_real_output_and_cache_resume_without_batch_calls(tmp_path):
    from scene_completion.case_dag import Scheduler, CallGate
    from scene_completion.semantic_backend import prepare_packets
    calls = []
    class Client:
        def __init__(self, name):
            self.name = name
            self.config = {'thinking': False, 'model_preflight': 'off'}
        def model(self, kind): return self.name
        def agent(self, packet):
            calls.append(self.name)
            assert packet['input']['normal_source'] == 'positive flow only'
            if self.name == 'supervisor':
                assert packet['input']['bounded_repair']['prior_output']['items'] is None
            return {'items': [] if self.name == 'supervisor' else None,
                'execution_model_evidence': {'requested_model': self.name, 'thinking': False, 'reasoning_effort': None}}
    for _ in range(2):
        adapter = dag.Pipeline.__new__(dag.Pipeline)
        adapter.args = SimpleNamespace(agent_mode='external')
        adapter.scheduler = Scheduler(tmp_path, max_rounds=0)
        primary, supervisor = Client('batch'), Client('supervisor')
        gate = CallGate(1)
        adapter.packets = dag.Packets(tmp_path, adapter.args, primary, gate)
        adapter.supervisor_packets = dag.Packets(tmp_path, adapter.args, supervisor, gate.budget_scope())
        adapter.packets.cache_clients.append(supervisor)
        adapter.supervisor_packets.cache_clients.append(primary)
        adapter.contexts = {'uc': {'root': tmp_path / 'case', 'validators': {}, 'version': 1}}
        def prepare(deps, directory):
            return prepare_packets(directory, 'interaction-fixture', [{'normal_source': 'positive flow only'}], [], {'items': []})
        def validate(packet, raw):
            if not isinstance(raw.get('items'), list): raise ValueError('items must be a list')
            return raw['items']
        adapter.semantic('uc', 'normal', (), prepare, validate)
        assert adapter.scheduler.run()['complete']
    assert calls == ['batch', 'supervisor']
    record = adapter.scheduler.state['tasks']['uc:normal']
    assert record['supervisor_rounds'] == 1 and record['rounds'] == 0


def test_checker_format_failure_repairs_check_output_not_upstream_model(tmp_path):
    from scene_completion.case_dag import Scheduler, CallGate
    from scene_completion.semantic_backend import prepare_packets
    class Client:
        config = {'agent_model': 'ecnu-max', 'thinking': False, 'max_concurrency': 1, 'model_preflight': 'off'}
        def model(self, kind):
            return 'ecnu-max'
        def agent(self, packet):
            proof = {'requested_model': 'ecnu-max', 'thinking': False, 'reasoning_effort': None}
            if packet['stage'] == 'gap-diagnosis':
                assert packet['input']['allowed_inputs'][0]['checker_marker'] == 'CHECKER_ONLY'
                return {'action': 'repair', 'reason': 'malformed checker result', 'targets': ['items'],
                    'evidence_quotes': [], 'execution_model_evidence': proof}
            return {'items': [] if 'bounded_repair' in packet['input'] else None, 'execution_model_evidence': proof}
    adapter = dag.Pipeline.__new__(dag.Pipeline)
    adapter.scheduler = Scheduler(tmp_path)
    adapter.packets = dag.Packets(tmp_path, SimpleNamespace(agent_mode='external', reuse_run=None), Client(), CallGate(1))
    adapter.contexts = {'uc': {'root': tmp_path / 'case', 'validators': {'source': lambda p, r: r['items']}, 'version': 1}}
    adapter.add('uc', 'source', (), lambda d, r: {'values': [], 'folder': 'upstream-must-not-be-read'})
    def prepare(deps, directory):
        return prepare_packets(directory, 'gap-checker-fixture', [{'checker_marker': 'CHECKER_ONLY'}], [], {'items': []})
    def validate(packet, result):
        if not isinstance(result.get('items'), list):
            raise ValueError('items must be a list')
        return result['items']
    adapter.semantic('uc', 'checker', ('source',), prepare, validate, repair_target='source')
    assert adapter.scheduler.run()['complete']
    assert adapter.scheduler.state['tasks']['uc:checker']['rounds'] == 1
