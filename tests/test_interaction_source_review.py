"""Source-only repair feedback is bound to actual inputs, never effect scores."""
from copy import deepcopy
import hashlib

import pytest

from scene_completion.interaction_source_review import source_review_feedback, source_audit_review_feedback
from scene_completion.semantic_backend import write_json
from scene_completion.sources import index_sources, fingerprint


def fixture(tmp_path):
    source = tmp_path / 'clinic.md'
    source.write_text('# Lab order\n## Basic flow\n1. ClinicAPI calls LaboratoryService.\n', encoding='utf-8')
    index = index_sources([source])
    index['documents'][0]['requirement_layer'] = 'SR'
    sections = index['documents'][0]['chapters'][:1]
    folder = tmp_path / 'model-batches'
    packet = {'input_hash': 'original-input', 'input': {'use_case_id': 'OrderLab', 'sections': sections}}
    raw = {'input_hash': 'original-input', 'model': 'ecnu-max',
        'execution_model_evidence': {'requested_model': 'ecnu-max', 'provider_model': 'deepseek-v4-flash'},
        'exchanges': [{'local_id': 'call'}]}
    model = {'use_cases': [{'use_case_id': 'OrderLab', 'exchanges': raw['exchanges']}]}
    write_json(folder / 'manifest.json', {'batches': [{'batch_id': 'model-lab', 'input_hash': 'original-input'}]})
    write_json(folder / 'packets/model-lab.json', packet)
    write_json(folder / 'results/model-lab.json', raw)
    review = {'schema_version': 1, 'review_type': 'source-only normal-model pre-review',
        'final_effect_acceptance': False, 'metrics_assessed': False,
        'artifact_binding': {'scene_model_canonical_json_sha256': fingerprint(model),
            'source_index_canonical_json_sha256': fingerprint(index)},
        'findings': [{'finding_id': 'source-1', 'batch_id': 'model-lab', 'use_case_id': 'OrderLab',
            'local_exchange_ids': ['call'], 'problem': 'The callee is incorrectly attributed.',
            'recommended_action': 'Re-extract the original participant call.',
            'source_refs': [{'document': source.name, 'line_start': 3, 'line_end': 3,
                'quote': 'ClinicAPI calls LaboratoryService.'}]}]}
    path = tmp_path / 'source-review.json'
    write_json(path, review)
    return path, review, model, index, folder


def test_source_feedback_bound_to_original_current_normal_model(tmp_path):
    path, review, model, index, folder = fixture(tmp_path)
    before = deepcopy(model)
    feedback = source_review_feedback(path, model, index, folder, ['source-1'])
    assert feedback['OrderLab'][0]['source_only']
    assert not feedback['OrderLab'][0]['acceptance_proof']
    assert feedback['OrderLab'][0]['source_review_hash'] == fingerprint(review)
    assert model == before


def test_source_audit_error_cannot_trigger_model_reextract(tmp_path):
    path, review, model, index, folder = fixture(tmp_path)
    review['findings'][0]['target'] = 'source_audit'
    write_json(path, review)
    with pytest.raises(ValueError, match='cannot trigger normal model'):
        source_review_feedback(path, model, index, folder, ['source-1'])


def test_source_audit_feedback_preserves_original_model_and_scopes_actual_audit(tmp_path):
    path, review, model, index, folder = fixture(tmp_path)
    finding = review['findings'][0]
    finding.update(target='source_audit', audit_batch_id='model-lab')
    write_json(path, review)
    before = deepcopy(model)
    feedback = source_audit_review_feedback(path, model, index, folder, ['source-1'])
    assert model == before
    assert not feedback['model-lab'][0]['normal_model_edit_allowed']
    assert not feedback['model-lab'][0]['acceptance_proof']
    assert feedback['model-lab'][0]['audit_result_hash']


@pytest.mark.parametrize('invalid', ['model_target', 'audit_batch', 'quote', 'scope', 'model_hash', 'unknown_finding'])
def test_source_audit_retry_rejects_unbound_or_wrong_role_review(tmp_path, invalid):
    path, review, model, index, folder = fixture(tmp_path)
    finding = review['findings'][0]
    finding.update(target='source_audit', audit_batch_id='model-lab')
    selected = ['source-1']
    if invalid == 'model_target':
        finding['target'] = 'normal_model'
    elif invalid == 'audit_batch':
        finding['audit_batch_id'] = 'different-audit'
    elif invalid == 'quote':
        finding['source_refs'][0]['quote'] = 'not in original source'
    elif invalid == 'scope':
        finding['use_case_id'] = 'UnrelatedUseCase'
    elif invalid == 'model_hash':
        review['artifact_binding']['scene_model_canonical_json_sha256'] = 'old'
    else:
        selected = ['unknown']
    write_json(path, review)
    with pytest.raises(ValueError):
        source_audit_review_feedback(path, model, index, folder, selected)


@pytest.mark.parametrize('invalid', ['source_version', 'model_version', 'effect_review', 'quote', 'scope', 'unknown_exchange', 'nonblocking'])
def test_stale_or_unbound_source_review_cannot_repair_model(tmp_path, invalid):
    path, review, model, index, folder = fixture(tmp_path)
    if invalid == 'source_version':
        review['artifact_binding']['source_index_canonical_json_sha256'] = 'old'
    elif invalid == 'model_version':
        review['artifact_binding']['scene_model_canonical_json_sha256'] = 'old'
    elif invalid == 'effect_review':
        review['metrics_assessed'] = True
    elif invalid == 'quote':
        review['findings'][0]['source_refs'][0]['quote'] = 'Guessed new service'
    elif invalid == 'scope':
        review['findings'][0]['source_refs'][0]['document'] = 'test_spec.md'
    elif invalid == 'unknown_exchange':
        review['findings'][0]['local_exchange_ids'] = ['guessed']
    else:
        review['findings'][0]['blocking'] = False
    write_json(path, review)
    with pytest.raises(ValueError):
        source_review_feedback(path, model, index, folder, ['source-1'])


def test_source_review_requires_deliberate_known_selection(tmp_path):
    path, _, model, index, folder = fixture(tmp_path)
    for selected in ([], ['unknown'], ['source-1', 'source-1']):
        with pytest.raises(ValueError):
            source_review_feedback(path, model, index, folder, selected)


@pytest.mark.parametrize('audit', [False, True])
@pytest.mark.parametrize('changed', ['input', 'packet', 'result'])
def test_review_rejects_changed_explicitly_bound_raw_artifacts(tmp_path, audit, changed):
    path, review, model, index, folder = fixture(tmp_path)
    finding = review['findings'][0]
    if audit:
        finding.update(target='source_audit', audit_batch_id='model-lab')
    prefix = 'audit_' if audit else ''
    packet_path = folder / 'packets/model-lab.json'
    result_path = folder / 'results/model-lab.json'
    finding.update({prefix + 'input_hash': 'original-input',
        prefix + 'packet_raw_sha256': hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        prefix + 'result_raw_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest()})
    write_json(path, review)
    check = source_audit_review_feedback if audit else source_review_feedback
    assert check(path, model, index, folder, ['source-1'])
    if changed == 'input':
        finding[prefix + 'input_hash'] = 'stale'
        write_json(path, review)
    else:
        artifact = packet_path if changed == 'packet' else result_path
        artifact.write_bytes(artifact.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='stale reviewed artifact'):
        check(path, model, index, folder, ['source-1'])
