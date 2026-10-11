"""Explicit representative runs reuse full source extraction without retagging it."""
from pathlib import Path
from .semantic_backend import read_json


def selected_use_case_ids(root):
    path = Path(root) / 'run_manifest.json'
    if not path.exists():
        return None
    return read_json(path).get('evaluation_scope', {}).get('use_case_ids') or None


def select_cases(items, selected):
    if not selected:
        return items
    return [item for item in items if item['use_case_id'] in set(selected)]


def assessment_base(base, selected):
    if not selected:
        return base
    available = {u['use_case_id'] for u in base['use_cases']}
    if len(selected) != len(set(selected)) or not set(selected) <= available:
        raise ValueError('representative scope needs unique known use-case IDs')
    return {**base, 'use_cases': select_cases(base['use_cases'], selected)}


def scope_mounts(ssd, mounts, local_ids=None):
    """Explicit smoke scope, never an applicability filter or full-run default."""
    if not local_ids:
        return mounts
    exchanges = ssd['exchanges']
    if len({e['use_case_id'] for e in exchanges}) != 1:
        raise ValueError('interaction-chain scope requires one representative use case')
    by_local = {e['local_id']: e for e in exchanges}
    if len(local_ids) != len(set(local_ids)) or not set(local_ids) <= set(by_local):
        raise ValueError('interaction-chain scope needs unique known local exchange IDs')
    selected = {by_local[key]['exchange_id'] for key in local_ids}
    if {by_local[key]['requirement_layer'] for key in local_ids} != {'RR', 'SR'}:
        raise ValueError('interaction-chain scope requires actual RR and SR exchanges')
    for key in local_ids:
        exchange = by_local[key]
        for parent in ('parent_exchange_id', 'parent_sr_exchange_id'):
            if exchange.get(parent) and exchange[parent] not in selected:
                raise ValueError('interaction-chain scope must retain every SSD parent anchor')
    return [m for m in mounts if m['exchange_id'] in selected]


def saved_scope_mounts(root, ssd, mounts):
    run = read_json(Path(root) / 'run_manifest.json')
    scope = run.get('evaluation_scope', {})
    if scope.get('exchange_local_ids') and scope.get('kind') != 'representative':
        raise ValueError('interaction-chain scope cannot claim full assessment')
    return scope_mounts(ssd, mounts, scope.get('exchange_local_ids'))


def comparison_verification_enabled(root):
    return read_json(Path(root)/'run_manifest.json').get('comparison_verification', 'all') == 'all'


def strict_source_quality(root):
    path=Path(root)/'run_manifest.json'
    return not path.exists() or read_json(path).get('source_quality_gate','strict')=='strict'


def verify_source_model_audit(root,index):
    """Workflow mode retains negative judgments, never labels them passed."""
    from tempfile import TemporaryDirectory
    from .interaction_model_audit import model_audit_packets,model_audit_validator,verify_model_audit
    from .semantic_backend import collect_packets
    from .interaction_execution_identity import validate_result_execution
    if strict_source_quality(root):
        return verify_model_audit(root,index)
    root=Path(root)
    run=read_json(root/'run_manifest.json')
    if run.get('evaluation_scope',{}).get('kind')!='representative':
        raise ValueError('structural source validation requires representative scope')
    folder=root/'batches/interaction-model-audit'
    with TemporaryDirectory(prefix='scene-workflow-source-') as temporary:
        expected=model_audit_packets(root/'batches/interaction-model',index,temporary,use_case_ids=selected_use_case_ids(root))
    if read_json(folder/'manifest.json')!=expected:
        raise ValueError('workflow source audit is missing or stale')
    rows,status=collect_packets(folder,model_audit_validator(index))
    if not status['complete']:
        raise ValueError('workflow source audit is incomplete or invalid')
    for batch in expected['batches']:
        path=folder/'results'/(batch['batch_id']+'.json')
        validate_result_execution(read_json(path),result_path=path)
    return rows
