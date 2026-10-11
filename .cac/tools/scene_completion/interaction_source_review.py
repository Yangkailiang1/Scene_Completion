"""Bind source-only human/native review findings to original normal model input.

These findings can request re-extraction, never edit model content or certify
acceptance. Complete model source audit remains mandatory after every repair.
"""
from pathlib import Path
import hashlib

from .semantic_backend import read_json
from .sources import fingerprint, validate_refs
from .interaction_batches import cited_text
from .interaction_execution_identity import validate_result_execution


def _validate_reviewed_artifacts(finding, packet, packet_path, result_path, *, audit=False):
    """Never reuse a finding after its explicitly reviewed raw output changes."""
    prefix = 'audit_' if audit else ''
    bindings = {
        prefix + 'input_hash': packet['input_hash'],
        prefix + 'packet_raw_sha256': hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        prefix + 'result_raw_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(),
    }
    for field, actual in bindings.items():
        if field in finding and finding[field] != actual:
            raise ValueError('source review has stale reviewed artifact: ' + field)


def source_review_feedback(path, model, index, folder, finding_ids):
    review = read_json(path)
    binding = review.get('artifact_binding', {})
    if (review.get('schema_version') != 1 or review.get('review_type') != 'source-only normal-model pre-review'
            or review.get('final_effect_acceptance') is not False or review.get('metrics_assessed') is not False
            or binding.get('scene_model_canonical_json_sha256') != fingerprint(model)
            or binding.get('source_index_canonical_json_sha256') != fingerprint(index)):
        raise ValueError('source-only review is stale or is not bound to the current normal model and original source')
    findings = review.get('findings', [])
    ids = [f.get('finding_id') for f in findings]
    if len(ids) != len(set(ids)) or not finding_ids or not set(finding_ids) <= set(ids):
        raise ValueError('select explicit unique source-only finding IDs; unknown findings cannot repair models')
    if len(finding_ids) != len(set(finding_ids)):
        raise ValueError('source-only finding selection contains duplicates')
    folder = Path(folder)
    manifest = {b['batch_id']: b for b in read_json(folder / 'manifest.json')['batches']}
    feedback = {}
    for finding in findings:
        if finding['finding_id'] not in finding_ids:
            continue
        if finding.get('target', 'normal_model') != 'normal_model':
            raise ValueError('a source-audit output error cannot trigger normal model re-extraction')
        bid = finding.get('batch_id')
        if bid not in manifest or finding.get('blocking', True) is not True:
            raise ValueError('selected finding is not a blocking defect of a current normal model batch')
        packet = read_json(folder / 'packets' / (bid + '.json'))
        result_path = folder / 'results' / (bid + '.json')
        raw = read_json(result_path)
        validate_result_execution(raw, result_path=result_path)
        _validate_reviewed_artifacts(finding, packet, folder / 'packets' / (bid + '.json'), result_path)
        if (raw.get('input_hash') != packet['input_hash'] or packet['input_hash'] != manifest[bid]['input_hash']
                or finding.get('use_case_id') != packet['input']['use_case_id']):
            raise ValueError('source review finding has a different use case, batch or actual model input')
        if not finding.get('problem') or not finding.get('recommended_action'):
            raise ValueError('source review finding needs a concrete source-to-model defect and repair direction')
        refs = finding.get('source_refs')
        if not refs:
            raise ValueError('source review finding must quote verifiable original clauses')
        supplied = packet['input']['sections'] + packet['input'].get('context_sections', [])
        evidence = []
        for ref in refs:
            validated = validate_refs([ref], index, supplied)
            quote = ref.get('quote')
            if (not isinstance(quote, str) or not quote.strip()
                    or quote not in cited_text(validated, index)):
                raise ValueError('source review finding quote differs from its assigned original clauses: '
                    + finding['finding_id'] + ' / ' + str([(r['document'], r['line_start'], r['line_end']) for r in validated]))
            evidence.append({'source_refs': validated, 'evidence_quote': quote})
        local_ids = set(finding.get('local_exchange_ids', []))
        if not local_ids <= {e['local_id'] for e in raw['exchanges']}:
            raise ValueError('source review finding names an unknown normal exchange')
        item = {'source_review_hash': fingerprint(review), 'finding_id': finding['finding_id'],
            'model_result_hash': fingerprint(raw), 'problem': finding['problem'],
            'recommended_action': finding['recommended_action'], 'local_exchange_ids': sorted(local_ids),
            'evidence': evidence, 'source_only': True, 'acceptance_proof': False}
        feedback.setdefault(finding['use_case_id'], []).append(item)
    return feedback


def source_audit_review_feedback(path, model, index, folder, finding_ids):
    """Bind selected review errors to exact original audit packets/results."""
    review = read_json(path)
    binding = review.get('artifact_binding', {})
    if (review.get('schema_version') != 1 or review.get('review_type') != 'source-only normal-model pre-review'
            or review.get('final_effect_acceptance') is not False or review.get('metrics_assessed') is not False
            or binding.get('scene_model_canonical_json_sha256') != fingerprint(model)
            or binding.get('source_index_canonical_json_sha256') != fingerprint(index)):
        raise ValueError('source-audit review is stale or claims effect acceptance')
    findings = review.get('findings', [])
    ids = [f.get('finding_id') for f in findings]
    if len(ids) != len(set(ids)) or not finding_ids or len(finding_ids) != len(set(finding_ids)) or not set(finding_ids) <= set(ids):
        raise ValueError('select explicit unique known source-audit findings')
    folder = Path(folder)
    manifest = {b['batch_id']: b for b in read_json(folder/'manifest.json')['batches']}
    feedback = {}
    for finding in findings:
        if finding['finding_id'] not in finding_ids:
            continue
        bid = finding.get('audit_batch_id')
        if finding.get('target') != 'source_audit' or bid not in manifest:
            raise ValueError('model defects cannot be disguised as source-audit retry findings')
        packet = read_json(folder/'packets'/(bid+'.json'))
        result_path = folder/'results'/(bid+'.json')
        raw = read_json(result_path)
        validate_result_execution(raw, result_path=result_path)
        _validate_reviewed_artifacts(finding, packet, folder / 'packets' / (bid + '.json'), result_path, audit=True)
        if (finding.get('use_case_id') != packet['input']['use_case_id']
                or raw.get('input_hash') != packet['input_hash'] or manifest[bid]['input_hash'] != packet['input_hash']
                ):
            raise ValueError('source-audit review has a different actual batch/use case/input')
        if not finding.get('problem') or not finding.get('recommended_action') or not finding.get('source_refs'):
            raise ValueError('source-audit finding requires a concrete judgment error and original evidence')
        evidence = []
        for ref in finding['source_refs']:
            refs = validate_refs([ref], index, packet['input']['sections'])
            quote = ref.get('quote')
            if not isinstance(quote, str) or not quote.strip() or quote not in cited_text(refs, index):
                raise ValueError('source-audit finding must quote its exact assigned original source')
            evidence.append({'source_refs': refs, 'evidence_quote': quote})
        feedback.setdefault(bid, []).append({'finding_id': finding['finding_id'],
            'problem': finding['problem'], 'recommended_action': finding['recommended_action'],
            'evidence': evidence, 'source_review_hash': fingerprint(review), 'audit_result_hash': fingerprint(raw),
            'source_only': True, 'normal_model_edit_allowed': False, 'acceptance_proof': False})
    return feedback
