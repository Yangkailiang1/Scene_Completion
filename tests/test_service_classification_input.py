"""The same classification rubric reaches real semantic inputs and cache keys."""
from pathlib import Path

from scene_completion import interaction_batches as batches
from scene_completion import interaction_model_audit as audit
from scene_completion.semantic_backend import read_json, write_json
from scene_completion.sources import index_sources


RUBRIC = 'scene-extract/references/service_classification.md'


def fixture(tmp_path):
    rr, sr = tmp_path / 'clinic_rr.md', tmp_path / 'clinic_sr.md'
    rr.write_text('# VISIT\n## Basic flow\n1. Patient requests a visit record.\n', encoding='utf-8')
    sr.write_text('# VISIT\n## Basic flow\n1. VisitAPI reads a visit record.\n', encoding='utf-8')
    index = index_sources([rr, sr])
    for document in index['documents']:
        document['requirement_layer'] = 'RR' if document['document'] == rr.name else 'SR'
    return {'use_cases': [{'use_case_id': 'VISIT', 'use_case_name': 'Read visit record'}]}, index


def test_same_complete_rubric_reaches_extractor_and_source_auditor(tmp_path, monkeypatch):
    base, index = fixture(tmp_path)
    folder = tmp_path / 'models'
    manifest = batches.model_packets(base, index, folder)
    batch = manifest['batches'][0]
    packet = read_json(folder / 'packets' / (batch['batch_id'] + '.json'))
    text = packet['input']['extraction_skills'][RUBRIC]
    assert all(code in text for code in batches.SERVICE_TYPES)
    assert '普通参数／权限／状态／金额校验' in text
    assert '支付、退款或发货不自动属于发布生效' in text
    model = {'components': [], 'exchanges': [], 'normal_scenarios': []}
    write_json(folder / 'results' / (batch['batch_id'] + '.json'), model)
    monkeypatch.setattr(audit, 'collect_packets', lambda *args: ([model], {'complete': True}))
    monkeypatch.setattr(batches, 'model_validator', lambda *args: lambda p, r: [r])
    reviewed = audit.model_audit_packets(folder, index, tmp_path / 'audits')
    row = reviewed['batches'][0]
    audited = read_json(tmp_path / 'audits/packets' / (row['batch_id'] + '.json'))
    assert audited['input']['extraction_skills'][RUBRIC] == text
    assert not {'checker', 'generated_scenarios', 'test_scenarios'} & audited['input'].keys()


def test_rubric_revision_invalidates_generator_cache_without_changing_checker(tmp_path, monkeypatch):
    base, index = fixture(tmp_path)
    before = batches.model_packets(base, index, tmp_path / 'before')
    checker_before = batches.checker_packets(base, index, tmp_path / 'checker-before')
    original_read = Path.read_text
    def changed(path, *args, **kwargs):
        value = original_read(path, *args, **kwargs)
        return value + '\nUpdated positive classification evidence rule.\n' if path.name == 'service_classification.md' else value
    monkeypatch.setattr(Path, 'read_text', changed)
    after = batches.model_packets(base, index, tmp_path / 'after')
    checker_after = batches.checker_packets(base, index, tmp_path / 'checker-after')
    assert before['batches'][0]['input_hash'] != after['batches'][0]['input_hash']
    assert checker_before == checker_after
