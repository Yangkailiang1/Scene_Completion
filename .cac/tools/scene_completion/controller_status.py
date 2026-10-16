"""Compact read-only status; optional offline proof replay may refresh batch status."""
from collections import Counter
import json
import os
from pathlib import Path
import time


ARTIFACTS = ('scene_assessment.xlsx', 'report.md', 'result_bundle.json', 'metrics.json',
    'missing_report.json', 'validation.json', 'effect_review.json', 'acceptance.json', 'diagrams/architecture.mmd')
ACTIVE = {'running', 'repairing', 'supervising'}
BLOCKED = {'awaiting_confirmation', 'awaiting_configuration', 'diagnosis_blocked', 'budget_exhausted', 'rejected', 'supervisor_pending'}


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else default


def verified_acceptance(root, snapshot_file, rebuilt_dir):
    from .concern_gap_replay import replay, acceptance_reasons, verify_bundle
    from .sources import fingerprint
    result = replay(root)
    reasons = acceptance_reasons(root, result) if result.get('complete') else ['pipeline not complete']
    acceptance = read(Path(root) / 'acceptance.json', {})
    if not acceptance.get('accepted') or acceptance.get('result_hash') != result.get('result_hash'):
        reasons.append('accepted result binding missing')
    snapshot = read(snapshot_file, {})
    if snapshot.get('payload_hash') != fingerprint(snapshot.get('payload')):
        reasons.append('offline snapshot missing or invalid')
    elif verify_bundle(snapshot['payload'])['result_hash'] != result.get('result_hash'):
        reasons.append('offline snapshot belongs to a different result')
    status = read(Path(rebuilt_dir) / 'assessment_status.json', {})
    if status.get('offline_rebuild') is not True or status.get('accepted') is not False:
        reasons.append('offline rebuild status missing or incorrectly claims new acceptance')
    return reasons


def inspect_run(root, *, process_file=None, budget_ledgers=(), verify=False, snapshot_file=None, rebuilt_dir=None, since_state=None):
    root = Path(root)
    manifest = read(root / 'run_manifest.json', {})
    tasks = read(root / 'case_tasks.json', {}).get('tasks', {})
    process = read(process_file, {}) if process_file else {}
    alive = False
    if process.get('status') == 'running' and type(process.get('pid')) is int:
        try:
            os.kill(process['pid'], 0)
            alive = True
        except ProcessLookupError:
            pass
        except PermissionError:
            alive = True
    budgets = []
    unsafe_usage = False
    unknown_usage = False
    for path in budget_ledgers:
        data = read(path, {})
        unknown = sum(r.get('status') == 'usage_unknown' for r in data.get('requests', {}).values())
        unknown_usage |= bool(unknown)
        conservatively_held = all(type(r.get('reservation')) is int and r['reservation'] > 0
            and r.get('charged_tokens', 0) >= r['reservation'] for r in data.get('requests', {}).values()
            if r.get('status') == 'usage_unknown')
        unsafe_usage |= bool(unknown) and (manifest.get('usage_accounting_policy') != 'retained_reservations' or not conservatively_held)
        budgets.append({'ledger': str(path), 'limit': data.get('limit'), 'committed_tokens': data.get('committed_tokens'),
            'reserved_tokens': data.get('reserved_tokens'), 'unknown_usage_requests': unknown})
    active = [{'task': k, 'stage': t['stage'], 'status': t['status']} for k, t in tasks.items() if t['status'] in ACTIVE]
    blocked = [{'task': k, 'stage': t['stage'], 'status': t['status'], 'rounds': t.get('rounds', 0),
        'supervisor_rounds': t.get('supervisor_rounds', 0),
        'current_reason': str(t.get('reason', ''))[:240],
        'failure_hash': t.get('failure_hash'),
        'failed_batch_count': len((t.get('failure') or {}).get('errors', {})),
        'diagnostic_issue_count': sum(len(d.get('issues', [])) for d in
            (t.get('failure') or {}).get('validation_diagnostics', {}).values())}
        for k, t in tasks.items() if t['status'] in BLOCKED]
    complete = bool(tasks) and manifest.get('complete') is True and all(t['status'] == 'passed' for t in tasks.values())
    artifacts = {name: (root / name).is_file() and (root / name).stat().st_size > 0 for name in ARTIFACTS}
    snapshot_file = Path(snapshot_file) if snapshot_file else root / 'final_snapshot.json'
    rebuilt_dir = Path(rebuilt_dir) if rebuilt_dir else root / 'rebuilt'
    for label, path in [('snapshot', snapshot_file), ('rebuilt_report', rebuilt_dir / 'report.md'),
            ('rebuilt_workbook', rebuilt_dir / 'scene_assessment.xlsx')]:
        artifacts[label] = path.is_file() and path.stat().st_size > 0
    reasons = []
    verified = False
    if verify and complete and not alive and not active:
        try:
            reasons = verified_acceptance(root, snapshot_file, rebuilt_dir)
            verified = not reasons
        except (OSError, ValueError, KeyError, TypeError) as exc:
            reasons = ['verification failed: ' + type(exc).__name__]
    ready = verified and all(artifacts.values()) and not unsafe_usage
    if unsafe_usage:
        action = 'resolve_unknown_usage'
    elif (root / 'pause_requested.json').exists():
        action = 'inspect_paused_run_preserve_inflight_results'
    elif any(t['status'] == 'awaiting_confirmation' for t in blocked):
        action = 'resolve_confirmation_keep_other_tasks_running'
    elif alive:
        action = 'wait_for_state_change_do_not_start_second_pipeline'
    elif active and process_file:
        action = 'inspect_exited_pipeline_with_unfinished_tasks'
    elif active:
        action = 'wait_for_state_change_do_not_start_second_pipeline'
    elif blocked:
        action = 'inspect_failed_task_do_not_reset_budget'
    elif ready:
        action = 'deliver_verified_artifact_paths_and_scope'
    elif complete:
        action = 'finish_regression_resume_review_snapshot_and_verify_delivery'
    else:
        action = 'inspect_pending_dependencies_before_resuming_same_run'
    state = {'scope': manifest.get('scope'), 'configured_batch_model': manifest.get('model'),
        'active_batch_model': manifest.get('active_batch_model', manifest.get('model')),
        'pipeline_alive': alive, 'pipeline_complete': complete, 'recorded_accepted': manifest.get('accepted') is True,
        'verified_accepted': verified, 'ready_to_deliver': ready, 'next_action': action,
        'counts': dict(Counter(t['status'] for t in tasks.values())), 'active': active, 'blocked': blocked,
        'budgets': budgets, 'artifacts': artifacts, 'verification_reasons': reasons,
        'usage_accounting_complete': not unknown_usage,
        'unknown_usage_retained': unknown_usage and not unsafe_usage,
        'passed_tasks_with_historical_failures': sum(t['status'] == 'passed' and bool(t.get('failure') or t.get('reason')) for t in tasks.values())}
    from .sources import fingerprint
    state['state_fingerprint'] = fingerprint(state)
    state['unchanged'] = state['state_fingerprint'] == since_state
    if state['unchanged']:
        return {k: state[k] for k in ('state_fingerprint', 'unchanged', 'next_action', 'ready_to_deliver', 'pipeline_complete')}
    return state


def wait_for_change(root, *, wait_seconds=0, **kwargs):
    if not 0 <= wait_seconds <= 60:
        raise ValueError('wait_seconds must be between 0 and 60')
    state = inspect_run(root, **kwargs)
    if (not wait_seconds or state['pipeline_complete'] or state['ready_to_deliver']
            or state.get('blocked') and not state['pipeline_alive'] and not state['active']):
        return state
    deadline = time.monotonic() + wait_seconds
    # No timestamp/poll counter in the comparison, so unchanged state remains
    # a single compact response rather than repeated controller context.
    while time.monotonic() < deadline:
        time.sleep(min(1, max(0, deadline - time.monotonic())))
        current = inspect_run(root, **kwargs)
        if current != state:
            return current
    return state
