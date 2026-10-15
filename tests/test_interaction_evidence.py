"""Acceptance consumes actual artifacts; booleans and structural completion fail."""
import copy
from argparse import Namespace

import pytest

from scene_completion import interaction_evidence as e, interaction_replay as r, interaction_audit as a
from scene_completion.semantic_backend import read_json, write_json, prepare_packets
from scene_completion.interaction_protocol import baseline, PROTOCOL
from scene_completion.interaction_cli import versions
from scene_completion.sources import fingerprint
from tests.test_interaction_baseline import original


def result():
    return {'complete': True, 'protocol': PROTOCOL, 'result_hash': 'actual-result',
        'coverage_threshold_met': True, 'miss_rates': {'RR': 0, 'SR': 0, 'combined': 0}}


def test_validation_identity_binds_pytest_collection_config(monkeypatch):
    from pathlib import Path
    config = e.repository() / 'pytest.ini'
    if not config.is_file():
        pytest.skip('repository has no pytest.ini')
    before = e.validation_identity()
    original_hash = e.file_hash
    def changed_hash(path):
        if Path(path).resolve() == config.resolve():
            return 'changed-pytest-config-hash'
        return original_hash(path)
    monkeypatch.setattr(e, 'file_hash', changed_hash)
    assert e.validation_identity() != before


def validation_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'replay', lambda root: result())
    monkeypatch.setattr(e, 'validation_identity', lambda: 'actual-tools-and-tests')
    monkeypatch.setattr(e, 'resume_cached', lambda root: [])
    (tmp_path / 'batches').mkdir()
    def execute(command, **kwargs):
        path = command[-1].split('=', 1)[1]
        from pathlib import Path
        Path(path).write_text('<testsuites><testsuite tests="3" errors="0" failures="0" skipped="0"/></testsuites>')
        return Namespace(returncode=0, stdout='3 passed', stderr='')
    monkeypatch.setattr(e.subprocess, 'run', execute)
    return e.run_validation(Namespace(output_dir=str(tmp_path)))


def test_boolean_only_acceptance_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'replay', lambda root: result())
    write_json(tmp_path / 'acceptance_checks.json', {'result_hash': 'actual-result',
        'full_regression_passed': True, 'same_version_resume_passed': True})
    write_json(tmp_path / 'effect_review.json', {'model': 'gpt-6-luna', 'reasoning_effort': 'max',
        'result_hash': 'actual-result', 'passed': True, 'unresolved_findings': []})
    assessed = r.evaluate(tmp_path)
    assert not assessed['accepted'] and len(assessed['reasons']) == 2


def test_validation_records_actual_command_junit_and_resume(tmp_path, monkeypatch):
    outcome, code = validation_fixture(tmp_path, monkeypatch)
    assert code == 0 and outcome['junit_counts']['tests'] == 3
    assert e.verify_validation(tmp_path, result())
    record = read_json(tmp_path / 'verification/regression.json')
    assert record['command'][1:4] == ['-m', 'pytest', '-q']
    assert record['exit_code'] == 0


@pytest.mark.parametrize('change', ['log', 'junit', 'resume', 'versions', 'results'])
def test_changed_validation_artifacts_or_versions_fail(tmp_path, monkeypatch, change):
    validation_fixture(tmp_path, monkeypatch)
    if change == 'versions':
        monkeypatch.setattr(e, 'validation_identity', lambda: 'changed')
    elif change == 'results':
        (tmp_path / 'batches/interaction-fixture').mkdir()
        write_json(tmp_path / 'batches/interaction-fixture/manifest.json', {'batches': []})
    elif change == 'log':
        (tmp_path / 'verification/regression.log').write_text('modified')
    elif change == 'junit':
        (tmp_path / 'verification/regression.xml').write_text('<testsuites/>')
    else:
        data = read_json(tmp_path / 'verification/resume.json')
        data['after_replay']['result_hash'] = 'changed'
        write_json(tmp_path / 'verification/resume.json', data)
    assert not e.verify_validation(tmp_path, result())


def test_failed_regression_cannot_produce_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'replay', lambda root: result())
    monkeypatch.setattr(e.subprocess, 'run', lambda *a, **k: Namespace(returncode=1, stdout='failed', stderr=''))
    outcome, code = e.run_validation(Namespace(output_dir=str(tmp_path)))
    assert code == 2 and not outcome['complete']
    assert not (tmp_path / 'acceptance_checks.json').exists()


def test_skipped_required_tests_block_regression(tmp_path, monkeypatch):
    validation_fixture(tmp_path, monkeypatch)
    path = tmp_path / 'verification/regression.xml'
    path.write_text('<testsuites><testsuite tests="3" errors="0" failures="0" skipped="1"/></testsuites>')
    record = read_json(tmp_path / 'verification/regression.json')
    record.update(junit_counts=e.junit_counts(path), junit_hash=e.file_hash(path))
    write_json(tmp_path / 'verification/regression.json', record)
    checks = read_json(tmp_path / 'acceptance_checks.json')
    checks['regression_hash'] = e.file_hash(tmp_path / 'verification/regression.json')
    write_json(tmp_path / 'acceptance_checks.json', checks)
    assert not e.verify_validation(tmp_path, result())


def test_cached_resume_network_guard_rejects_socket_and_restores_it():
    import socket
    original_socket = socket.socket
    with e.deny_resume_network() as calls:
        with pytest.raises(RuntimeError, match='network access is forbidden'):
            socket.create_connection(('example.invalid', 80))
        assert calls['attempts'] == 1
    assert socket.socket is original_socket


def test_review_binds_raw_findings_materials_and_required_areas(tmp_path, monkeypatch):
    materials = {'result_hash': 'actual-result', 'files': {'metrics.json': 'hash'}, 'batches': {},
        'review_areas': sorted(e.REVIEW_AREAS)}
    monkeypatch.setattr(e, 'review_materials', lambda root, value: materials)
    write_json(tmp_path / 'effect_review_materials.json', materials)
    raw = {'materials_hash': fingerprint(materials), 'unresolved_findings': [], 'areas': [
        {'area': name, 'passed': True, 'reason': 'checked concrete artifacts', 'evidence_files': ['metrics.json']}
        for name in sorted(e.REVIEW_AREAS)]}
    write_json(tmp_path / 'effect_review_raw.json', raw)
    review = {'model': 'gpt-6-luna', 'reasoning_effort': 'max', 'result_hash': 'actual-result',
        'passed': True, 'unresolved_findings': [], 'agent_id': 'actual-review-agent',
        'materials_hash': fingerprint(materials), 'raw_review_hash': e.file_hash(tmp_path / 'effect_review_raw.json')}
    write_json(tmp_path / 'effect_review.json', review)
    assert e.verify_effect_review(tmp_path, result())
    raw['areas'].pop()
    write_json(tmp_path / 'effect_review_raw.json', raw)
    review['raw_review_hash'] = e.file_hash(tmp_path / 'effect_review_raw.json')
    write_json(tmp_path / 'effect_review.json', review)
    assert not e.verify_effect_review(tmp_path, result())


@pytest.mark.parametrize('threshold', [True, False])
def test_complete_structural_run_is_not_formal_acceptance(tmp_path, monkeypatch, threshold):
    root, index, *_ = original(tmp_path)
    write_json(root / 'sources_index.json', index)
    write_json(root / 'test_sources_index.json', index)
    write_json(root / 'concern_baseline.json', baseline())
    write_json(root / 'run_manifest.json', {'protocol': PROTOCOL, 'complete': True, 'accepted': False,
        'source_hash': fingerprint(index), 'tool_versions': versions()})
    for stage in ('interaction-model', 'interaction-model-audit', 'interaction-generation', 'interaction-matching', 'interaction-verification',
                  'interaction-recommendation', 'interaction-adoption', 'interaction-test-conditions',
                  'interaction-participants', 'interaction-equivalence'):
        prepare_packets(root / 'batches' / stage, stage, [], [], {})
    assessed = {**result(), 'coverage_threshold_met': threshold, 'accepted': False, 'reasons': ['missing real review']}
    monkeypatch.setattr(r, 'evaluate', lambda root: assessed)
    checked = a.check_run(root)
    assert checked['structurally_valid'] and not checked['formally_accepted'] and not checked['passed']
    assert checked['status'] == 'pending'
    assert not any(i['code'] == 'coverage_threshold' for i in checked['issues'])


def test_baseline_review_binds_source_audit_execution(tmp_path):
    root, index, base, _ = original(tmp_path)
    from scene_completion.interaction_baseline import import_baseline
    folder = root / 'batches/interaction-checker-audit'
    path = next((folder / 'results').glob('*.json'))
    raw = read_json(path)
    raw['execution_model_evidence']['provider_model'] = 'changed-provider-proof'
    write_json(path, raw)
    with pytest.raises(ValueError, match='source audit differs'):
        import_baseline(root / 'existing_scenarios.json', tmp_path / 'next', index, base)
