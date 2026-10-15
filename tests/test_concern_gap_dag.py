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
    graph_task = pipeline.scheduler.tasks['UC-1:graphs']
    graph_state = pipeline.scheduler.state['tasks']['UC-1:graphs']
    graph_deps = {key: read_json(Path(args.output_dir) / pipeline.scheduler.state['tasks'][key]['output_file'])
        for key in graph_task.deps}
    graph_task.compatible(graph_deps, read_json(Path(args.output_dir) / graph_state['output_file']))
    assert len(calls) == count  # Shared component layout changes must stay offline.
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


def test_reverse_review_recheck_keeps_retained_packet_slots_and_replaces_only_failed_unit(tmp_path):
    from scene_completion.semantic_backend import prepare_packets
    from scene_completion.response_contract import contract_view

    folder = tmp_path / 'case' / 'batches' / 'reverse-G'
    inputs = [
        {'units': [{'unit_id': 'U1', 'source_scenario_id': 'S1'}],
         'original_scenarios': [{'scenario_id': 'S1', 'trigger_condition': 'trigger one'}],
         'original_evidence': [{'scenario_id': 'S1', 'source_ref': 'ref-1', 'text': 'source one'}]},
        {'units': [{'unit_id': 'U2', 'source_scenario_id': 'S2'}],
         'original_scenarios': [{'scenario_id': 'S2', 'trigger_condition': 'trigger two'}],
         'original_evidence': [{'scenario_id': 'S2', 'source_ref': 'ref-2', 'text': 'source two'}]},
        {'units': [{'unit_id': 'U3', 'source_scenario_id': 'S3'}],
         'original_scenarios': [{'scenario_id': 'S3', 'trigger_condition': 'trigger three'}],
         'original_evidence': [{'scenario_id': 'S3', 'source_ref': 'ref-3', 'text': 'source three'}]},
    ]
    manifest = prepare_packets(folder, 'gap-reverse-check-G', inputs, [], {'reviews': []})
    old_batches = list(manifest['batches'])

    def review_validator(packet, raw):
        expected = {unit['unit_id'] for unit in packet['input']['units']}
        rows = copy.deepcopy(raw.get('reviews', []))
        if {row.get('unit_id') for row in rows} != expected or len(rows) != len(expected):
            raise ValueError('wrong review unit coverage')
        for row in rows:
            row['passed'] = all(row[key] for key in
                ('source_supported', 'atomic', 'mapping_correct', 'cause_correct'))
        return rows

    for index, row in enumerate(old_batches):
        packet_path = folder / 'packets' / f"{row['batch_id']}.json"
        packet = read_json(packet_path)
        unit_id = packet['input']['units'][0]['unit_id']
        good = unit_id != 'U2'
        raw = {'batch_id': row['batch_id'], 'input_hash': row['input_hash'],
            'model': 'ecnu-max', 'execution_model_evidence': {'requested_model': 'ecnu-max'},
            'reviews': [{'unit_id': unit_id, 'source_supported': good, 'atomic': good,
                'mapping_correct': good, 'cause_correct': good, 'evidence_quote': f'trigger {index + 1}',
                'reason': 'initial review'}]}
        write_json(folder / 'results' / f"{row['batch_id']}.json", raw)
    values = []
    for row in old_batches:
        packet = read_json(folder / 'packets' / f"{row['batch_id']}.json")
        raw = read_json(folder / 'results' / f"{row['batch_id']}.json")
        values.extend(review_validator(packet, raw))
    target = {'folder': str(folder.resolve()), 'values': values}
    failure = {'findings': [{'unit_id': 'U2', 'source_scenario_id': 'S2'}], 'output': target}

    packets = object.__new__(dag.Packets)
    seen = {}

    def execute(repair_folder, validator):
        current = read_json(repair_folder / 'manifest.json')
        seen['batches'] = list(current['batches'])
        merged_values = []
        for batch in current['batches']:
            packet = read_json(repair_folder / 'packets' / f"{batch['batch_id']}.json")
            result_path = repair_folder / 'results' / f"{batch['batch_id']}.json"
            if not result_path.exists():
                unit_id = packet['input']['units'][0]['unit_id']
                seen['repair_units'] = packet['input']['units']
                assert packet['input']['review_patch']['rejected_unit_ids'] == ['U2']
                raw = {'batch_id': batch['batch_id'], 'input_hash': batch['input_hash'],
                    'reviews': [{'unit_id': unit_id, 'source_supported': True, 'atomic': True,
                        'mapping_correct': True, 'cause_correct': True, 'evidence_quote': 'trigger two',
                        'reason': 'rechecked only failed source'}]}
            else:
                raw = read_json(result_path)
            merged_values.extend(validator(packet, contract_view(packet, raw)))
        return {'folder': str(repair_folder.resolve()), 'values': merged_values, 'executions': []}

    packets.execute = execute
    result = packets.repaired(tmp_path / 'case', 'reverse-G', target, review_validator,
        {'action': 'recheck'}, failure, 1)

    assert [row['batch_id'] for row in seen['batches']] == [
        old_batches[0]['batch_id'], seen['batches'][1]['batch_id'], old_batches[2]['batch_id']]
    assert seen['batches'][0] == old_batches[0]
    assert seen['batches'][2] == old_batches[2]
    assert [row['unit_id'] for row in seen['repair_units']] == ['U2']
    assert [row['unit_id'] for row in result['values']] == ['U1', 'U2', 'U3']
    assert all(row['passed'] for row in result['values'])


def _write_cached_candidate(folder, stage, payload, raw, validator):
    from scene_completion.semantic_backend import prepare_packets
    manifest = prepare_packets(folder, stage, [payload], [], {'items': []})
    batch = manifest['batches'][0]
    raw = {**raw, 'batch_id': batch['batch_id'], 'input_hash': batch['input_hash'],
        'model': 'ecnu-max', 'execution_model_evidence': {'requested_model': 'ecnu-max'}}
    write_json(folder / 'results' / f"{batch['batch_id']}.json", raw)
    return raw


@pytest.mark.parametrize('candidate_scenario_id,should_recheck', [
    ('G-new', True), ('G-rejected', False),
])
def test_recovered_source_candidate_must_change_rejected_g_before_recheck_promotion(
        tmp_path, candidate_scenario_id, should_recheck):
    from scene_completion.case_dag import Scheduler
    from scene_completion.semantic_backend import collect_packets

    root = tmp_path / 'case'
    generation_folder = root / 'batches' / 'G-generate-supervisor-repair-2'
    normalization_folder = root / 'batches' / 'normalize-G-after-source-repair-4'
    generation_values = [{'scenario_id': candidate_scenario_id, 'mount_id': 'M1',
        'trigger_condition': 'new specific trigger' if candidate_scenario_id == 'G-new' else 'old rejected trigger'}]
    normalized_values = [{'unit_id': 'UNIT::' + candidate_scenario_id,
        'source_scenario_id': candidate_scenario_id}]

    def generation_validator(packet, raw):
        return copy.deepcopy(raw['items'])

    def normalization_validator(packet, raw):
        return copy.deepcopy(raw['items'])

    generation_raw = _write_cached_candidate(generation_folder, 'gap-generation',
        {'mounts': [{'mount_id': 'M1'}]}, {'items': generation_values}, generation_validator)
    normalization_raw = _write_cached_candidate(normalization_folder, 'gap-normalize-G',
        {'scenarios': [{'scenario_id': candidate_scenario_id}]}, {'items': normalized_values}, normalization_validator)
    # Ensure the cached packets are real, complete, and validated candidates.
    assert collect_packets(generation_folder, generation_validator)[1]['complete']
    assert collect_packets(normalization_folder, normalization_validator)[1]['complete']

    journal = {'failure': {'findings': [{'source_scenario_id': 'G-rejected'}]},
        'old_output': {'values': [{'scenario_id': 'G-rejected', 'mount_id': 'M1',
            'trigger_condition': 'old rejected trigger'}]}}
    write_json(root / 'repair_rounds' / 'reverse-G-supervisor-2.json', journal)
    review_folder = root / 'batches' / 'reverse-G-latest-recheck'
    review_folder.mkdir(parents=True)
    current_unit_id = 'UNIT::' + candidate_scenario_id
    failure = {'findings': [{'unit_id': current_unit_id, 'source_supported': False,
        'atomic': True, 'source_scenario_id': candidate_scenario_id}],
        'output': {'folder': str(review_folder.resolve()), 'values': [
            {'unit_id': current_unit_id, 'passed': False}]}}

    class Packets:
        def __init__(self):
            self.diagnosed_target = None
            self.rechecked_target = None

        def cache_identity(self, raw):
            return None

        def diagnose(self, case_root, name, target, details, round_number):
            self.diagnosed_target = target
            return {'action': 'recheck', 'reason': 'candidate source was changed and must be independently rechecked'}, {}

        def repaired(self, case_root, name, target, validator, diagnosis, details, round_number):
            self.rechecked_target = target
            assert target['folder'] == str(review_folder.resolve())
            # The fresh reverse review is the only point at which a changed
            # source can be promoted to passed.
            return {'folder': target['folder'], 'values': [
                {'unit_id': current_unit_id, 'passed': True}], 'executions': []}

    packets = Packets()
    pipeline = dag.Pipeline.__new__(dag.Pipeline)
    pipeline.scheduler = Scheduler(root)
    pipeline.args = SimpleNamespace(agent_mode='external')
    pipeline.packets = packets
    pipeline.supervisor_packets = None
    pipeline.contexts = {'uc': {'root': root, 'version': 1,
        'validators': {'G-generate': generation_validator, 'normalize-G': normalization_validator}}}
    # A durable source promotion must bind real registered target tasks even
    # when this unit test invokes the repair callback without running the DAG.
    for stage in ('G-generate', 'normalize-G'):
        pipeline.add('uc', stage, (), lambda deps, record: {})
        registered = pipeline.scheduler.tasks['uc:' + stage]
        pipeline.scheduler.state['tasks'][registered.key]['input_hash'] = pipeline.scheduler.input_hash(registered)
    pipeline.semantic('uc', 'reverse-G', (), lambda deps, folder: None,
        lambda packet, raw: raw['reviews'], reject=lambda rows: [row for row in rows if not row['passed']],
        repair_target='normalize-G')
    task = pipeline.scheduler.tasks['uc:reverse-G']
    record = {'rounds': 4, 'supervisor_rounds': 2, 'input_hash': 'fixture-input-hash',
        'failure': {'findings': failure['findings'], 'output': failure['output']}}

    if should_recheck:
        result = task.repair({}, record)
        assert packets.diagnosed_target['values'] == generation_values
        # The model decision to recheck does not itself change review status;
        # only the fresh validator output is returned as passed.
        assert packets.rechecked_target['folder'] == str(review_folder.resolve())
        assert result['values'] == [{'unit_id': current_unit_id, 'passed': True}]
        assert result['_replacements']['uc:G-generate']['values'] == generation_values
        assert result['_source_repair']['rejected_source_ids'] == ['G-rejected']
    else:
        with pytest.raises(ValueError, match='unchanged'):
            task.repair({}, record)
        assert packets.diagnosed_target is None


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


def test_comparison_repair_prefers_latest_semantic_attempt_over_stale_result_and_cache_snapshot(tmp_path):
    from scene_completion.semantic_backend import prepare_packets

    source = tmp_path / 'case' / 'batches' / 'gap-ambiguity-EG'
    input_data = {'checker': [{'scenario_id': 'C1'}],
        'generated': [{'scenario_id': 'G1'}, {'scenario_id': 'G2'}],
        'canonical_metadata': {'C1': {}, 'G1': {}, 'G2': {}}}
    manifest = prepare_packets(source, 'gap-ambiguity-EG', [input_data],
        ['Compare every pair.'], {'pairs': []})
    batch = manifest['batches'][0]

    def comparison_validator(packet, result):
        expected = {(c['scenario_id'], g['scenario_id'])
            for c in packet['input']['checker'] for g in packet['input']['generated']}
        rows = result.get('pairs')
        if not isinstance(rows, list):
            raise ValueError('missing pair decisions')
        seen = set()
        for row in rows:
            key = (row.get('checker_scenario_id'), row.get('generated_scenario_id'))
            if key not in expected or key in seen:
                raise ValueError('unknown or duplicate pair')
            seen.add(key)
            if row.get('decision') != 'valid':
                raise ValueError('invalid pair decision')
        if seen != expected:
            raise ValueError('missing decisions')
        return rows

    proof = {'model': 'ecnu-max', 'execution_model_evidence': {'requested_model': 'ecnu-max'}}
    valid_g1 = {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G1', 'decision': 'valid'}
    stale_result = {**proof, 'batch_id': batch['batch_id'], 'input_hash': batch['input_hash'],
        'pairs': [valid_g1]}
    write_json(source / 'results' / f"{batch['batch_id']}.json", stale_result)

    attempts_dir = source / 'attempts'
    cache_path = attempts_dir / f"{batch['batch_id']}-cache-snapshot.json"
    semantic_path = attempts_dir / f"{batch['batch_id']}-semantic-result.json"
    write_json(cache_path, {'result': stale_result, 'cached_result_revalidation': True})
    semantic_result = {**proof, 'batch_id': batch['batch_id'], 'input_hash': batch['input_hash'],
        'pairs': [valid_g1, {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2',
            'decision': 'invalid'}]}
    write_json(semantic_path, {'result': semantic_result,
        'validation_error': 'invalid pair decision', 'attempt': 1})
    # Even a newer synthetic cache snapshot must not shadow a real semantic attempt.
    import os
    semantic_stat = semantic_path.stat()
    os.utime(cache_path, ns=(semantic_stat.st_atime_ns + 2_000_000,
        semantic_stat.st_mtime_ns + 2_000_000))

    packets = object.__new__(dag.Packets)
    packets.cache_identity = lambda raw: None
    seen = {}

    def execute(folder, validator):
        repair_manifest = read_json(folder / 'manifest.json')
        repair_packet = read_json(folder / 'packets' / f"{repair_manifest['batches'][0]['batch_id']}.json")
        seen['binding'] = repair_packet['input']['comparison_patch_binding']
        seen['expected_pairs'] = repair_packet['input']['expected_pairs']
        seen['feedback'] = repair_packet['input']['repair_feedback']
        return {'folder': str(folder.resolve()), 'values': []}

    packets.execute = execute
    target = {'folder': str(source.resolve()), 'values': []}
    failure = {'errors': {batch['batch_id']: 'current validator rejected result'}, 'output': target}
    packets.repaired(tmp_path / 'case', 'EG', target, comparison_validator,
        {'action': 'recheck'}, failure, 1)

    assert seen['binding']['prior_attempt_path'] == str(semantic_path.resolve())
    assert seen['expected_pairs'] == [{'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2'}]
    assert seen['feedback'][0]['validation_error'] == 'invalid pair decision'


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
