from pathlib import Path

import pytest

from scene_completion.model_trial import inspect_trial
from scene_completion.semantic_backend import write_json
from scene_completion.sources import fingerprint


def fixture(tmp_path, monkeypatch, models, *, ready=True, rounds=0, reuse=None):
    write_json(tmp_path / 'run_manifest.json', {'scope': {
        'use_case_ids': ['UC'], 'granularity': 'complete_use_cases'}})
    write_json(tmp_path / 'pipeline_arguments.json', {'reuse_run': reuse})
    tasks = {}
    for i, model in enumerate(models):
        result = tmp_path / f'raw-{i}.json'
        write_json(result, {'model': model})
        output = {'executions': [{'result_path': str(result)}]}
        target = f'output-{i}.json'
        write_json(tmp_path / target, output)
        tasks[f'UC:stage-{i}'] = {'case': 'UC', 'status': 'passed', 'rounds': rounds,
            'output_file': target, 'output_hash': fingerprint(output)}
    write_json(tmp_path / 'case_tasks.json', {'tasks': tasks})
    # Attribution unit tests isolate the separately tested execution verifier.
    monkeypatch.setattr('scene_completion.model_trial.verify_execution_output', lambda o: None)
    monkeypatch.setattr('scene_completion.controller_status.inspect_run',
        lambda *a, **k: {'ready_to_deliver': ready})


def test_formal_delivery_and_actual_identity_are_both_required(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, ['candidate'], ready=False)
    assert not inspect_trial(tmp_path, 'candidate')['independently_qualified']
    fixture(tmp_path, monkeypatch, ['candidate'], rounds=2)
    assert inspect_trial(tmp_path, 'candidate')['classification'] == 'candidate_self_repaired'
    fixture(tmp_path, monkeypatch, ['candidate', 'main'])
    result = inspect_trial(tmp_path, 'candidate')
    assert result['classification'] == 'supervisor_assisted'
    assert not result['independently_qualified']


def test_imported_semantic_scope_cannot_be_declared_independent(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, ['candidate'], reuse='old-run')
    assert not inspect_trial(tmp_path, 'candidate')['independently_qualified']


def test_changed_trial_artifact_is_rejected(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, ['candidate'])
    write_json(tmp_path / 'output-0.json', {'executions': []})
    with pytest.raises(ValueError, match='changed'):
        inspect_trial(tmp_path, 'candidate')


def test_returned_provider_mismatch_prevents_independent_qualification(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, ['candidate'])
    write_json(tmp_path/'raw-0.json', {'model':'candidate',
        'execution_model_evidence':{'provider_model':'different-route'}})
    result=inspect_trial(tmp_path,'candidate')
    assert not result['independently_qualified']
    assert result['returned_provider_models']=={'different-route':1}
    assert result['provider_model_mismatches']==['different-route']
    config=tmp_path/'config.json'
    write_json(config, {'accepted_provider_models':['candidate','different-route']})
    write_json(tmp_path/'pipeline_arguments.json',{'config':str(config)})
    assert inspect_trial(tmp_path,'candidate')['independently_qualified']
