from scene_completion.controller_watch import inspect
from scene_completion.semantic_backend import write_json


def test_controller_chatter_does_not_reset_watchdog_but_actual_task_progress_does(tmp_path):
    write_json(tmp_path/'case_tasks.json', {'tasks': {'a': {'status': 'pending'}}})
    target = tmp_path/'watch.json'
    assert not inspect(tmp_path, target, now=100)['stagnated']
    (tmp_path/'controller.log').write_text('more thinking and polling')
    assert inspect(tmp_path, target, now=701)['stagnated']
    write_json(tmp_path/'case_tasks.json', {'tasks': {'a': {'status': 'passed', 'output_hash': 'real'}}})
    assert not inspect(tmp_path, target, now=702)['stagnated']
    write_json(tmp_path/'cases/c/batches/G/results/part.json', {'real_partial_execution': True})
    assert not inspect(tmp_path, target, now=1200)['stagnated']
    write_json(tmp_path/'batches/independent-effect-review/results/part.json', {'actual_review': True})
    assert not inspect(tmp_path, target, now=1801)['stagnated']
    write_json(tmp_path/'batches/independent-effect-review/local/results/part.json', {'actual_local_review': True})
    assert not inspect(tmp_path, target, now=2402)['stagnated']
