"""Explicit, evidence-bound controller corrections; never reset repair counters."""
from pathlib import Path
import time

from .case_dag import run_lock
from .semantic_backend import read_json, write_json
from .sources import fingerprint


KINDS = {'tool_fix', 'prompt_fix', 'source_reinterpretation', 'split_packet'}


def _local_reservation_refusal(root, record):
    """An oversized, never-admitted packet may be replaced by a smaller plan.

    This is not quota recovery: the next call still reserves against the same
    ledgers and provider limit. Unknown transport usage never qualifies.
    """
    folders = []
    for identity in (root / 'cases').glob('*/case_identity.json'):
        if read_json(identity).get('use_case_id') == record.get('case'):
            folders.append(identity.parent / 'batches' /
                f"{record['stage']}-supervisor-repair-{record.get('supervisor_rounds', 0)}")
    attempts = [p for folder in folders for p in (folder / 'attempts').glob('*.json')]
    if not attempts:
        return False
    for path in attempts:
        value = read_json(path)
        diagnostic = value.get('response_diagnostic', {})
        if (value.get('result') or diagnostic.get('budget_kind') != 'tokens'
                or diagnostic.get('budget_reason') not in {
                    'insufficient_provider_allowance', 'insufficient_remaining_allowance'}):
            return False
    return True


def cancel_pending(root, task_key, reason):
    """Retire an unstarted stale plan, never refund an executed repair round."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('cancelling a pending correction requires a reason')
    root = Path(root).resolve()
    with run_lock(root):
        state = read_json(root / 'case_tasks.json')
        record = state['tasks'][task_key]
        rows = [r for r in record.get('supervisor_continuations', [])
            if r['revision_id'] == record.get('supervisor_revision_pending')]
        if len(rows) != 1 or rows[0]['status'] != 'requested':
            raise ValueError('only an unstarted pending correction may be cancelled')
        rows[0].update(status='cancelled_unstarted', cancellation_reason=reason, cancelled_unix=time.time())
        record.pop('supervisor_revision_pending')
        state['events'].append({'task': task_key, 'event': 'controller_correction_cancelled_unstarted',
            'reason': reason, 'revision_id': rows[0]['revision_id']})
        write_json(root / 'case_tasks.json', state)
        return {'task': task_key, 'status': 'cancelled_unstarted', 'model_calls': 0,
            'batch_rounds': record['rounds'], 'supervisor_rounds': record['supervisor_rounds']}


def refresh_pending(root, task_key):
    """Rebind an unstarted correction after tool-version-only reconciliation."""
    root = Path(root).resolve()
    with run_lock(root):
        state = read_json(root / 'case_tasks.json')
        record = state['tasks'][task_key]
        rows = [r for r in record.get('supervisor_continuations', [])
            if r['revision_id'] == record.get('supervisor_revision_pending')]
        if len(rows) != 1 or rows[0]['status'] != 'requested':
            raise ValueError('only an unstarted pending correction may be refreshed')
        revision = rows[0]
        dependencies = {key: state['tasks'][key].get('output_hash') for key in record.get('dependencies', [])}
        previous_input = fingerprint({'version': record.get('previous_version'), 'dependencies': dependencies})
        if (revision['failure_hash'] != record.get('failure_hash')
                or previous_input != revision['input_hash']):
            raise ValueError('correction failure/dependencies changed; a fresh diagnosis is required')
        if fingerprint(revision['plan']) != revision['plan_hash']:
            raise ValueError('controller correction plan changed')
        for row in revision['plan'].get('changes', []):
            if fingerprint(Path(row['path']).read_bytes().hex()) != row['content_hash']:
                raise ValueError('correction files changed; reassess the actual correction')
        binding = {'from_input_hash': revision['input_hash'], 'to_input_hash': record['input_hash'],
            'failure_hash': record['failure_hash'], 'dependencies': dependencies,
            'basis': 'tool_version_only_reconciliation', 'at_unix': time.time()}
        revision.setdefault('input_rebindings', []).append(binding)
        revision['input_hash'] = record['input_hash']
        state['events'].append({'task': task_key, 'event': 'controller_correction_rebound', **binding})
        write_json(root / 'case_tasks.json', state)
        return {'task': task_key, 'correction': revision['revision_id'], 'model_calls': 0,
            'status': 'pending_original_validation', 'batch_rounds': record['rounds'],
            'supervisor_rounds': record['supervisor_rounds']}


def pending_revision(record):
    identifier = record.get('supervisor_revision_pending')
    rows = [r for r in record.get('supervisor_continuations', []) if r['revision_id'] == identifier]
    if len(rows) != 1:
        raise ValueError('missing or ambiguous controller correction')
    revision = rows[0]
    if revision['input_hash'] != record.get('input_hash') or revision['failure_hash'] != record.get('failure_hash'):
        raise ValueError('controller correction is stale; inspect the current failure before continuing')
    if fingerprint(revision['plan']) != revision['plan_hash']:
        raise ValueError('controller correction plan changed')
    for row in revision['plan'].get('changes', []):
        path = Path(row['path'])
        if not path.is_file() or fingerprint(path.read_bytes().hex()) != row['content_hash']:
            raise ValueError('controller correction files changed; register the actual tested correction')
    return revision


def validate_history(record):
    rounds = record.get('supervisor_rounds', 0)
    if type(rounds) is not int or rounds < 0:
        raise ValueError('invalid persistent supervisor budget')
    rows = record.get('supervisor_continuations', [])
    used = [r.get('supervisor_round') for r in rows if r.get('status') == 'started']
    if sorted(used) != list(range(2, rounds + 1)):
        raise ValueError('additional supervisor attempts require distinct controller correction proofs')
    plans = [r['plan_hash'] for r in rows]
    if len(plans) != len(set(plans)):
        raise ValueError('controller correction cannot repeat an unchanged plan')
    for row in rows:
        if fingerprint(row['plan']) != row['plan_hash']:
            raise ValueError('controller correction proof changed')


def request(root, task_key, plan_path, *, repository=None):
    """Schedule one newly diagnosed correction; normal pipeline performs validation."""
    root = Path(root).resolve()
    repository = Path(repository or Path.cwd()).resolve()
    plan = read_json(plan_path)
    with run_lock(root):
        state = read_json(root / 'case_tasks.json')
        record = state['tasks'][task_key]
        if record['status'] not in ('budget_exhausted', 'diagnosis_blocked'):
            raise ValueError('only a stopped failed semantic task can receive a controller correction')
        if not record.get('supervisor_rounds'):
            raise ValueError('use the configured initial supervisor handoff before requesting continuation')
        if record.get('supervisor_revision_pending'):
            raise ValueError('a controller correction is already pending; resume it without registering another')
        reason = record.get('reason')
        local_refusal = _local_reservation_refusal(root, record)
        if isinstance(reason, str) and ('external quota exhausted' in reason or 'usage unresolved' in reason) and not local_refusal:
            raise ValueError('resolve real quota or unknown usage before semantic continuation')
        if isinstance(reason, dict) and (reason.get('failure_category') in ('quota_exhausted', 'budget_exhausted')
                or reason.get('budget_reason') == 'unresolved_previous_request'):
            raise ValueError('resolve real quota or unknown usage before semantic continuation')
        if any(state['tasks'][key]['status'] != 'passed' for key in record.get('dependencies', [])):
            raise ValueError('controller correction dependencies must pass first')
        if plan.get('input_hash') != record.get('input_hash') or plan.get('failure_hash') != record.get('failure_hash'):
            raise ValueError('plan must bind the current input and failure hashes')
        if plan.get('kind') not in KINDS or not isinstance(plan.get('diagnosis'), str) or not plan['diagnosis'].strip():
            raise ValueError('controller correction requires a specific diagnosis and supported correction kind')
        if not isinstance(plan.get('correction'), str) or not plan['correction'].strip():
            raise ValueError('controller correction must explain the changed approach')
        if not isinstance(plan.get('validation'), str) or not plan['validation'].strip():
            raise ValueError('controller correction must record validation evidence or a concrete recheck plan')
        changes = []
        for value in sorted(set(plan.get('changed_files', []))):
            path = (repository / value).resolve()
            relative = path.relative_to(repository).as_posix()
            if not (relative.startswith('.cac/tools/') or relative.startswith('.cac/skills/')):
                raise ValueError('correction file evidence is limited to methodology tools and Skills')
            changes.append({'path': str(path), 'content_hash': fingerprint(path.read_bytes().hex())})
        if not changes:
            raise ValueError('controller corrections require actual tool/Skill changes, including evidence-view or packet-splitting changes')
        # Deliberately exclude timestamps, caller labels and the failure ID from
        # the semantic strategy fingerprint: renaming a plan cannot buy a retry.
        normalized = {k: plan[k].strip() for k in ('kind', 'diagnosis', 'correction', 'validation')}
        if plan.get('action', 'repair') not in ('repair', 'recheck'):
            raise ValueError('controller correction action must be repair or recheck')
        normalized['action'] = plan.get('action', 'repair')
        normalized['changes'] = changes
        plan_hash = fingerprint(normalized)
        strategy_hash = fingerprint(changes)
        if any(r['plan_hash'] == plan_hash for r in record.get('supervisor_continuations', [])):
            raise ValueError('unchanged correction already attempted; diagnose the actual remaining defect')
        if any(r.get('strategy_hash') == strategy_hash for r in record.get('supervisor_continuations', [])):
            raise ValueError('unchanged tool/Skill correction cannot buy another request by rewording its diagnosis')
        revision = {'revision_id': fingerprint({'task': task_key, 'plan': plan_hash}),
            'plan': normalized, 'plan_hash': plan_hash, 'strategy_hash': strategy_hash, 'input_hash': record['input_hash'],
            'failure_hash': record['failure_hash'], 'status': 'requested', 'created_unix': time.time(),
            'prior_local_reservation_refusal': local_refusal}
        record.setdefault('supervisor_continuations', []).append(revision)
        record['supervisor_revision_pending'] = revision['revision_id']
        state['events'].append({'task': task_key, 'event': 'controller_correction_requested',
            'revision_id': revision['revision_id'], 'batch_rounds': record['rounds'],
            'supervisor_rounds': record['supervisor_rounds']})
        write_json(root / 'case_tasks.json', state)
        return {'task': task_key, 'correction': revision['revision_id'], 'status': 'pending_original_validation',
            'model_calls': 0, 'batch_rounds': record['rounds'], 'supervisor_rounds': record['supervisor_rounds']}
