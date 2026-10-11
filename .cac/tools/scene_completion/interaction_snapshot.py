"""Portable metric/report replay without credentials or execution caches.

This validates saved decisions and reconstructs outputs; it does not replace
the complete run's native execution, regression and independent review proof.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

from .semantic_backend import read_json, write_json, collect_packets
from .sources import fingerprint
from . import interaction_batches as b
from .interaction_protocol import baseline, build_ssd, route_mounts, validate_generated
from .interaction_scope import scope_mounts
from .interaction_metrics import compare, adoption
from .interaction_equivalence import equivalence_validator, recommendation_units, eligible_pairs


def export_snapshot(root, path):
    from .interaction_replay import replay
    root = Path(root)
    result = replay(root)  # Requires actual complete, version-bound execution.
    run = read_json(root / 'run_manifest.json')
    data = {'schema': 1, 'source_result_hash': result['result_hash'],
        'scope': run['evaluation_scope'], 'source_quality_gate': run.get('source_quality_gate', 'strict'),
        'source_quality_passed': run.get('source_quality_passed'),
        'comparison_verification': run.get('comparison_verification', 'all')}
    for key, name in {'source_index':'sources_index.json', 'model':'scene_model.json',
            'ssd':'diagrams/ssd.json', 'mounts':'concern_mounts.json',
            'generated':'generated_scenarios.json', 'checked':'assessment_checker_scenarios.json',
            'matches':'scenario_matches.json', 'recommendations':'recommendations.json',
            'test_index':'test_sources_index.json', 'tests':'test_conditions.json',
            'adoption_matches':'adoption_matches.json', 'metrics':'metrics.json',
            'adoption':'adoption.json', 'source_audit':'model_source_audit.json'}.items():
        data[key] = read_json(root / name)
    data['taxonomy'] = baseline()
    data['equivalence'], status = collect_packets(root / 'batches/interaction-equivalence', equivalence_validator)
    if not status['complete']:
        raise ValueError('snapshot requires complete equivalence evidence')
    write_json(path, {'payload': data, 'payload_hash': fingerprint(data)})
    return {'snapshot': str(Path(path)), 'result_hash': result['result_hash']}


def validate_pairs(generated, checked, decisions, stage):
    """Reconstruct the exhaustive source-scoped pair universe, not just matches."""
    with TemporaryDirectory(prefix='scene-snapshot-pairs-') as temporary:
        manifest = b.pair_packets(generated, checked, temporary, stage)
        remaining = {(p['checker_scenario_id'], p['generated_scenario_id']): p for p in decisions}
        if len(remaining) != len(decisions):
            raise ValueError('duplicate snapshot pair')
        validated = []
        for batch in manifest['batches']:
            packet = read_json(Path(temporary) / 'packets' / (batch['batch_id'] + '.json'))
            keys = [(c['scenario_id'], g['scenario_id']) for c in packet['input']['checker']
                for g in packet['input']['generated']]
            try:
                rows = [remaining.pop(key) for key in keys]
            except KeyError as exc:
                raise ValueError('incomplete snapshot pair universe') from exc
            validated.extend(b.pair_validator(packet, {'pairs': rows}))
        if remaining:
            raise ValueError('unknown or cross-scope snapshot pair')
        # Validate the exhaustive universe while preserving the saved semantic
        # output order that participates in the original result hash.
        return decisions


def rebuild_snapshot(path, output):
    saved = read_json(path)
    data = saved['payload']
    if data.get('schema') != 1 or fingerprint(data) != saved.get('payload_hash') or data['taxonomy'] != baseline():
        raise ValueError('snapshot version, integrity or concern framework differs')
    ssd = build_ssd(data['model'])
    mounts = scope_mounts(ssd, route_mounts(ssd), data['scope'].get('exchange_local_ids'))
    if ssd != data['ssd'] or mounts != data['mounts']:
        raise ValueError('snapshot SSD/mounts differ from the normal model')
    generated, checked = data['generated']['scenarios'], data['checked']['scenarios']
    validate_generated(generated, ssd, mounts, data['source_index'])
    pairs = validate_pairs(generated, checked, data['matches']['pairs'], 'interaction-matching')
    metrics = compare(generated, checked, pairs)
    candidates = [s for s in generated if s['scenario_id'] in metrics['layers']['combined']['overall']['unmatched_generated_ids']]
    equivalents = {(r['left_id'],r['right_id']):r for r in data['equivalence']}
    for left,right in eligible_pairs(candidates,ssd):
        key=(left['scenario_id'],right['scenario_id'])
        if key not in equivalents:
            raise ValueError('snapshot equivalence evidence is incomplete')
        equivalence_validator({'input':{'left':left,'right':right,
            'left_concerns':left['concern_keys'],'right_concerns':right['concern_keys']}},equivalents[key])
    units = recommendation_units(candidates, ssd, data['equivalence'])
    tests = data['tests']['scenarios']
    adoption_pairs = validate_pairs(units['units'], tests, data['adoption_matches']['pairs'], 'interaction-adoption')
    adopted = adoption(units['units'], tests, adoption_pairs, equivalence=units)
    result_hash = fingerprint([generated, checked, pairs, metrics, adopted])
    if metrics != data['metrics'] or adopted != data['adoption'] or result_hash != data['source_result_hash']:
        raise ValueError('snapshot metrics or result hash cannot be reproduced')
    recs = data['recommendations']['items']
    if {r['scenario_id'] for r in recs} != {s['scenario_id'] for s in candidates} or len(recs) != len(candidates):
        raise ValueError('snapshot recommendation set is incomplete')
    with TemporaryDirectory(prefix='scene-snapshot-recommendation-') as temporary:
        manifest=b.recommendation_packets(candidates,ssd,temporary,data['source_index'])
        by_id={r['scenario_id']:r for r in recs}
        for batch in manifest['batches']:
            packet=read_json(Path(temporary)/'packets'/(batch['batch_id']+'.json'))
            items=[by_id[s['scenario_id']] for s in packet['input']['candidates']]
            if b.recommendation_validator(data['source_index'])(packet,{'items':items})!=items:
                raise ValueError('snapshot recommendation scores or references differ')
    from .interaction_reports import coverage_diagnosis, export, write_diagrams
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root/'run_manifest.json', {'evaluation_scope':data['scope'],
        'source_quality_gate':data['source_quality_gate'], 'comparison_verification':data['comparison_verification'],
        'complete':True, 'accepted':False, 'offline_report_rebuild':True, 'execution_evidence_verified':False})
    write_json(root/'model_source_audit.json', data['source_audit'])
    write_diagrams(root/'diagrams', ssd, mounts)
    export(root, generated, checked, pairs, metrics, recs, adopted,
        coverage_diagnosis(generated, checked, pairs, metrics, ssd, mounts), mounts)
    return {'complete':True, 'result_hash':result_hash, 'execution_evidence_verified':False,
        'note':'Offline metric/report rebuild only; no model calls or new acceptance claim.'}
