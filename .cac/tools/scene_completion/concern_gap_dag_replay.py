"""Validate retained case executions and rebuild final v2 metrics offline."""
from pathlib import Path
from .semantic_backend import read_json, write_json
from .sources import fingerprint
from .concern_gap_dag import verify_execution_output
from .case_dag import TaskBlocked


def validate_values(output, task, index, test_index):
    from . import interaction_batches as old, concern_gap_batches as b
    from .interaction_participants import participant_validator
    from .interaction_audit import checker_audit_validator
    from .concern_gap_repair import reverse_validator
    from .concern_gap_normalize_diagnostics import validator as normalize_validator
    from .concern_gap_dedup import validator as dedup_validator
    from .concern_gap_comparison import validator as comparison_validator
    from .semantic_backend import collect_packets
    stage = task['stage']
    if stage == 'history-import':
        from .concern_gap_history import verify_binding
        verify_binding(output['binding'])
        if output['binding']['corpus_hash'] != fingerprint(output['source_units']):
            raise ValueError('imported historical corpus changed')
        return
    validators = {'normal': old.model_validator(index), 'E-extract': old.checker_validator(index),
        'E-audit': checker_audit_validator(index), 'participants': participant_validator(index),
        'features': b.feature_validator(index), 'G-generate': b.generation_validator(index),
        'T-extract': old.test_validator(test_index), 'ar-trace': b.ar_validator(index)}
    def graph_validate(packet, result):
        rows = b.graph_validator(index)(packet, result)
        for prior in packet['input'].get('reused_components', []):
            verify_execution_output({'executions': prior['executions']})
            rows.append(prior['check'])
        return rows
    validators['graphs'] = graph_validate
    if stage.startswith('normalize-'):
        validator = normalize_validator(test_index if stage.endswith('-T') else index)
    elif stage.startswith('reverse-'):
        validator = reverse_validator
    elif stage.startswith('dedup-'):
        validator = dedup_validator
    elif stage.startswith('compare-'):
        validator = comparison_validator
    else:
        validator = validators.get(stage)
    if validator and output.get('folder'):
        values, status = collect_packets(output['folder'], validator)
        if not status['complete'] or values != output['values']:
            raise ValueError('case semantic values do not match actual validated executions: ' + stage)


def replay(root, cache_resume=False):
    from .concern_gap_replay import verify_bundle
    from . import concern_gap_batches as b
    root = Path(root)
    manifest = read_json(root / 'run_manifest.json')
    if manifest.get('versions') != b.versions():
        raise ValueError('DAG tool versions changed')
    state = read_json(root / 'case_tasks.json')
    if any(type(t.get('rounds')) is not int or not 0 <= t['rounds'] <= 2 for t in state['tasks'].values()):
        raise ValueError('invalid persistent repair budget')
    for evidence in sorted((root / 'cases').glob('*/repair_rounds/*.json')):
        repair = read_json(evidence)
        verify_execution_output(repair['execution'])
        verify_execution_output(repair['old_output'])
    index = read_json(root / 'sources_index.json')
    test_index = read_json(root / 'test_sources_index.json')
    if (root / 'ar_sources_index.json').exists():
        ar_index = read_json(root / 'ar_sources_index.json')
    else:
        ar_index = index
    records = []
    for key, task in state['tasks'].items():
        if task['status'] != 'passed':
            continue
        output = read_json(root / task['output_file'])
        if fingerprint(output) != task['output_hash']:
            raise ValueError('case task artifact changed: ' + key)
        verify_execution_output(output)
        validate_values(output, task, ar_index if task['stage'] == 'ar-trace' else index, test_index)
        for execution in output.get('executions', []):
            records.append({'stage': task['stage'], 'case': task['case'], 'batch_id': execution['batch_id'],
                'input_hash': execution['input_hash'], 'status': 'cached' if cache_resume else 'verified'})
        for dependency in task['dependencies']:
            if state['tasks'][dependency]['status'] != 'passed':
                raise ValueError('passed task has incomplete dependency: ' + key)
        if fingerprint({'version': task['version'], 'dependencies': {key: state['tasks'][key].get('output_hash')
                for key in task['dependencies']}}) != task['input_hash']:
            raise ValueError('case dependency changed: ' + key)
    if not manifest.get('complete') or any(t['status'] != 'passed' for t in state['tasks'].values()):
        return {'complete': False, 'structurally_valid': True, 'formal_metrics': None, 'batches': records,
            'pending_tasks': [{'key': k, 'case': t['case'], 'stage': t['stage'], 'status': t['status'],
                'reason': t.get('reason', t.get('failure'))} for k, t in state['tasks'].items() if t['status'] != 'passed']}
    bundle = read_json(root / 'result_bundle.json')
    if bundle.get('history_import'):
        from .concern_gap_history import verify_binding
        verify_binding(bundle['history_import'])
    for collection in ('G', 'E', 'T'):
        selected = set(manifest['scope']['use_case_ids'])
        expected = sorted([u for task in state['tasks'].values() if task['stage'] == 'units-' + collection and task['case'] in selected
            for u in read_json(root / task['output_file'])['values']], key=lambda u: u['scenario_id'])
        if expected != bundle[collection]:
            raise ValueError('final set differs from case artifacts: ' + collection)
    result = verify_bundle(bundle)
    if result['result_hash'] != manifest['result_hash']:
        raise ValueError('DAG final bundle disagrees with manifest')
    return {**result, 'structurally_valid': True, 'batches': records}


def check(root):
    root = Path(root)
    try:
        result = replay(root)
        result['formally_accepted'] = False
        code = 0 if result['complete'] else 2
    except (ValueError, KeyError, OSError, TypeError, TaskBlocked) as exc:
        result = {'complete': False, 'structurally_valid': False, 'reason': str(exc), 'formally_accepted': False}
        code = 2
    write_json(root / 'run_checks.json', result)
    (root / 'run_checks.md').write_text('# 用例运行检查\n\n' + str(result) + '\n', encoding='utf8')
    return result, code


def partial_snapshot(root, path):
    root = Path(root)
    result = replay(root)
    if result['complete']:
        raise ValueError('partial snapshot requested for a complete project')
    state = read_json(root / 'case_tasks.json')
    payload = {'schema': 'case-dag-partial-v1', 'source_index': read_json(root / 'sources_index.json'),
        'test_source_index': read_json(root / 'test_sources_index.json'), 'progress': read_json(root / 'progress.json'),
        'cases': [read_json(root / task['output_file']) for task in state['tasks'].values()
            if task['stage'] == 'case-report' and task['status'] == 'passed']}
    from .concern_gap import PROTOCOL
    write_json(path, {'protocol': PROTOCOL, 'partial': True, 'payload_hash': fingerprint(payload), 'payload': payload})
    return {'complete': False, 'partial_snapshot': True, 'completed_cases': len(payload['cases']),
        'pending_tasks': result['pending_tasks']}


def rebuild_partial(payload, root):
    from .concern_gap_dag_reports import partial_case
    from .interaction_protocol import build_ssd, validate_generated
    from .concern_gap_dedup import merge
    from .concern_gap import metrics
    from .concern_gap_dag import case_name
    root = Path(root)
    for case in payload['cases']:
        if build_ssd(case['model']) != case['ssd']:
            raise ValueError('partial SSD changed')
        validate_generated(case['source_generated'] + case['normal'], case['ssd'], case['mounts'], payload['source_index'])
        for collection in ('G', 'E', 'T'):
            units = case['source_units'][collection]
            if merge(units, collection + '2', case['dedup'][collection]) != case[collection]:
                raise ValueError('partial normalized units changed')
            reviews = case['reverse_checks'][collection]['reviews']
            if {r['unit_id'] for r in reviews} != {u['unit_id'] for u in units} or not all(r['passed'] for r in reviews):
                raise ValueError('partial reverse checks incomplete')
        if metrics(case['G'], case['E'], case['T'], [], case['relations'])['missing_ids'] != case['missing_ids']:
            raise ValueError('partial missing set changed')
        case_id = case['model']['use_cases'][0]['use_case_id']
        partial_case(root / 'cases' / case_name(case_id), case)
    write_json(root / 'progress.json', payload['progress'])
    record = {'complete': False, 'accepted': False, 'offline_rebuild': True, 'execution_evidence_verified': False,
        'completed_cases': len(payload['cases']), 'formal_metrics': None}
    write_json(root / 'assessment_status.json', record)
    return record
