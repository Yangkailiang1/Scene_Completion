"""Audit a controller correction to an unexecuted, reserved diagnostic repair."""
from pathlib import Path

from .case_dag import run_lock
from .semantic_backend import read_json, write_json
from .sources import fingerprint


def request(root, task_key, plan_path, *, repository=None):
    root, repository = Path(root).resolve(), Path(repository or Path.cwd()).resolve()
    plan = read_json(plan_path)
    with run_lock(root):
        state = read_json(root / 'case_tasks.json')
        row = state['tasks'][task_key]
        if row['status'] not in ('awaiting_confirmation', 'diagnosis_blocked', 'pending', 'budget_exhausted'):
            raise ValueError('only a stopped diagnostic protocol can resume its reserved repair')
        if (not row.get('reuse_reserved_round') and row['status'] not in ('awaiting_confirmation', 'budget_exhausted')) or not row.get('failure_hash'):
            raise ValueError('an unexecuted reserved semantic repair and original failure are required')
        if row.get('supervisor_revision_pending'):
            raise ValueError('do not replace a pending supervisor correction')
        if (plan.get('input_hash'), plan.get('failure_hash')) != (row.get('input_hash'), row.get('failure_hash')):
            raise ValueError('diagnostic correction must bind the current source task and failure')
        for key in ('diagnosis', 'correction', 'validation'):
            if not isinstance(plan.get(key), str) or not plan[key].strip():
                raise ValueError('diagnostic correction requires a concrete ' + key)
        case = next((p.parent for p in (root / 'cases').glob('*/case_identity.json')
            if read_json(p).get('use_case_id') == row['case']), None)
        if case is None:
            raise ValueError('original case identity missing')
        journal = case / 'repair_rounds' / (row['stage'] + '-' + str(row['rounds']) + '.json')
        if journal.exists():
            saved = read_json(journal)
            if row['status'] == 'budget_exhausted' and not (
                    saved.get('diagnosis', {}).get('action') == 'confirm'
                    and any(a.get('status') == 'awaiting_confirmation' and a.get('round') == row['rounds']
                        for a in row.get('attempts', []))):
                raise ValueError('exhausted semantic repairs cannot be reopened as diagnosis')
            if row['status'] == 'awaiting_confirmation' and saved.get('diagnosis') != row.get('reason'):
                raise ValueError('confirmation is not bound to the stopped diagnostic execution')
            if row['status'] == 'awaiting_confirmation' and saved.get('diagnosis', {}).get('action') != 'confirm':
                raise ValueError('no reserved diagnostic confirmation to resume')
        elif row['status'] in ('awaiting_confirmation', 'budget_exhausted'):
            raise ValueError('original diagnostic confirmation evidence missing')
        changed = []
        for name in sorted(set(plan.get('changed_files', []))):
            path = (repository / name).resolve()
            relative = path.relative_to(repository).as_posix()
            if not relative.startswith(('.cac/tools/', '.cac/skills/')):
                raise ValueError('only actual methodology corrections may reopen diagnosis')
            changed.append({'path': str(path), 'hash': fingerprint(path.read_bytes().hex())})
        if not changed:
            raise ValueError('actual tested diagnostic tool or Skill changes are required')
        strategy = fingerprint(changed)
        history = row.setdefault('diagnosis_continuations', [])
        if any(v['strategy_hash'] == strategy for v in history):
            raise ValueError('unchanged diagnostic strategy cannot be retried')
        proof = {'strategy_hash': strategy, 'plan': plan, 'changed_files': changed,
            'prior_status': row['status'], 'prior_reason': row.get('reason'),
            'journal_hash': fingerprint(read_json(journal)) if journal.exists() else None,
            'batch_rounds': row['rounds'], 'supervisor_rounds': row.get('supervisor_rounds', 0)}
        history.append(proof)
        row['status'] = 'rejected'
        row['reuse_reserved_round'] = True
        state['events'].append({'task': task_key, 'event': 'diagnosis_protocol_correction', **proof})
        write_json(root / 'case_tasks.json', state)
        return {'task': task_key, 'status': 'reserved_repair_ready', 'model_calls': 0,
            'batch_rounds': row['rounds'], 'supervisor_rounds': row.get('supervisor_rounds', 0)}
