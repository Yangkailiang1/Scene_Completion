"""Read-only attribution of a whole workflow trial to its actual semantic models."""
from pathlib import Path
from collections import Counter

from .semantic_backend import read_json
from .sources import fingerprint
from .concern_gap_dag import verify_execution_output


def inspect_trial(root, candidate, *, verify_delivery=False):
    """Never promote workflow success or model independence from a report label."""
    root = Path(root)
    manifest = read_json(root / 'run_manifest.json')
    state = read_json(root / 'case_tasks.json')
    selected = set(manifest.get('scope', {}).get('use_case_ids', []))
    models, stages, failures = Counter(), [], []
    for key, task in state['tasks'].items():
        if task.get('case') not in selected:
            continue
        if task.get('status') != 'passed':
            failures.append({'task': key, 'status': task.get('status')})
            continue
        output = read_json(root / task['output_file'])
        if fingerprint(output) != task.get('output_hash'):
            raise ValueError('trial output changed: ' + key)
        verify_execution_output(output)
        evidence = output.get('executions', [])
        actual = []
        for proof in evidence:
            raw = read_json(proof['result_path'])
            model = raw.get('model')
            if not isinstance(model, str) or not model:
                raise ValueError('trial execution lacks actual model identity')
            actual.append(model)
            models[model] += 1
        if actual:
            stages.append({'task': key, 'models': sorted(set(actual)),
                'batch_repair_rounds': task.get('rounds', 0),
                'supervisor_rounds': task.get('supervisor_rounds', 0)})
    from .controller_status import inspect_run
    delivery = inspect_run(root, verify=verify_delivery)
    scope_complete = (manifest.get('scope', {}).get('granularity') == 'complete_use_cases'
        and bool(selected))
    args_path = root / 'pipeline_arguments.json'
    args = read_json(args_path) if args_path.exists() else {}
    fresh_scope = not args.get('reuse_run') and not args.get('exchange_local_id')
    alternate = sorted(model for model in models if model != candidate)
    complete = bool(delivery.get('ready_to_deliver')) and scope_complete and not failures
    independent = complete and bool(models) and not alternate and fresh_scope
    repaired = any(row['batch_repair_rounds'] or row['supervisor_rounds'] for row in stages)
    if independent:
        classification = 'candidate_self_repaired' if repaired else 'candidate_first_pass'
    elif complete and alternate:
        classification = 'supervisor_assisted'
    else:
        classification = 'not_qualified'
    return {'schema': 'scene-model-trial-v1', 'candidate_model': candidate,
        'scope': manifest.get('scope'), 'complete': complete,
        'independently_qualified': independent, 'classification': classification,
        'actual_semantic_models': dict(sorted(models.items())), 'alternate_models': alternate,
        'fresh_complete_scope': fresh_scope and scope_complete, 'stages': stages,
        'pending_tasks': failures, 'delivery': delivery,
        'note': 'Fixed independent review and historical-library imports are external evidence, '
            'not candidate semantic completion. Stage screening is never whole-workflow qualification.'}
