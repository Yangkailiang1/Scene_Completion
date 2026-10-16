import pytest

from scene_completion.diagnosis_continuation import request
from scene_completion.semantic_backend import read_json, write_json


def test_only_bound_changed_diagnostic_plan_resumes_without_reset(tmp_path):
    root = tmp_path / 'run'
    tool = tmp_path / '.cac/tools/check.py'
    tool.parent.mkdir(parents=True)
    tool.write_text('fixed = True')
    reason = {'action': 'confirm', 'reason': 'empty findings caused by incorrect lineage'}
    row = {'case': 'uc', 'stage': 'reverse-G', 'status': 'awaiting_confirmation',
        'reason': reason, 'rounds': 2, 'supervisor_rounds': 1, 'reuse_reserved_round': True,
        'input_hash': 'source', 'failure_hash': 'failure'}
    write_json(root / 'case_tasks.json', {'tasks': {'a': row}, 'events': []})
    write_json(root / 'cases/c/case_identity.json', {'use_case_id': 'uc'})
    write_json(root / 'cases/c/repair_rounds/reverse-G-2.json', {'diagnosis': reason})
    plan = tmp_path / 'plan.json'
    write_json(plan, {'input_hash': 'source', 'failure_hash': 'failure', 'diagnosis': 'wrong source IDs',
        'correction': 'use bound mounts', 'validation': 'lineage tests passed',
        'changed_files': ['.cac/tools/check.py']})
    assert request(root, 'a', plan, repository=tmp_path)['model_calls'] == 0
    state = read_json(root / 'case_tasks.json')
    assert state['tasks']['a']['status'] == 'rejected'
    assert state['tasks']['a']['rounds'] == 2 and state['tasks']['a']['supervisor_rounds'] == 1
    assert state['tasks']['a']['reuse_reserved_round']
    state['tasks']['a']['status'] = 'awaiting_confirmation'
    write_json(root / 'case_tasks.json', state)
    with pytest.raises(ValueError, match='unchanged'):
        request(root, 'a', plan, repository=tmp_path)
    state['tasks']['a']['reuse_reserved_round'] = False
    state['tasks']['a']['status'] = 'pending'
    write_json(root / 'case_tasks.json', state)
    with pytest.raises(ValueError, match='reserved'):
        request(root, 'a', plan, repository=tmp_path)


def test_actual_exhausted_semantic_failure_cannot_use_diagnosis_continuation(tmp_path):
    root = tmp_path / 'run'
    row = {'case': 'uc', 'stage': 'reverse-G', 'status': 'budget_exhausted',
        'rounds': 2, 'supervisor_rounds': 1, 'input_hash': 'input', 'failure_hash': 'failure'}
    write_json(root / 'case_tasks.json', {'tasks': {'a': row}, 'events': []})
    write_json(root / 'cases/c/case_identity.json', {'use_case_id': 'uc'})
    write_json(root / 'cases/c/repair_rounds/reverse-G-2.json',
        {'diagnosis': {'action': 'repair', 'reason': 'actual semantic repair failed'}})
    plan = tmp_path / 'plan.json'
    write_json(plan, {'input_hash': 'input', 'failure_hash': 'failure', 'diagnosis': 'exhausted',
        'correction': 'same attempt', 'validation': 'no new evidence'})
    with pytest.raises(ValueError, match='exhausted semantic'):
        request(root, 'a', plan, repository=tmp_path)
