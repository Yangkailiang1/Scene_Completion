"""Guard mutable retry preparation against all selected and sharded workers."""
from pathlib import Path

from .semantic_backend import read_json


def assert_stage_idle(folder, action):
    active = [p.name for p in sorted(Path(folder).glob('worker-status-*.json')) if read_json(p).get('running') is True]
    if active:
        raise ValueError('stop or finish active stage workers before ' + action + ': ' + ', '.join(active))


def stage_execution_snapshot(folder, collected_status):
    """Explain current pending work; worker claims never certify a result.

    Selection/shard logs survive resume and protocol changes. Only current
    manifest IDs count, newest per-batch observations win, and a successfully
    collected result supersedes an old quota failure. Provider error strings
    are deliberately excluded from the public diagnostic report.
    """
    folder = Path(folder)
    manifest = read_json(folder / 'manifest.json')
    expected = {r['batch_id'] for r in manifest['batches']}
    pending = set(collected_status.get('pending', []))
    errors = collected_status.get('errors', {})
    latest, running, unreadable = {}, [], []
    paths = sorted(folder.glob('worker-status-*.json'), key=lambda p: (p.stat().st_mtime_ns, p.name))
    for path in paths:
        try:
            state = read_json(path)
            if not isinstance(state, dict) or not isinstance(state.get('batches'), list):
                raise ValueError('invalid worker state')
            rows = [r for r in state['batches'] if isinstance(r, dict) and r.get('batch_id') in expected]
            # A starting whole-stage worker has no finished rows yet. Its
            # running state is diagnostic only, never a completeness proof.
            if state.get('running') is True:
                running.append(path.name)
            for row in rows:
                latest[row['batch_id']] = (path.name, row)
        except (OSError, ValueError, TypeError):
            unreadable.append(path.name)
    records = []
    for batch in manifest['batches']:
        bid = batch['batch_id']
        filename, row = latest.get(bid, (None, {}))
        if bid in errors:
            status = 'invalid_result'
        elif bid not in pending:
            status = 'validated_result'
        else:
            status = row.get('status') if row.get('status') in {'failed', 'deferred'} else 'pending'
        record = {'batch_id': bid, 'status': status}
        if status in {'failed', 'deferred'}:
            record['worker_status_file'] = filename
            category = row.get('failure_category', row.get('reason'))
            if category == 'quota_exhausted':
                record['failure_category'] = category
        records.append(record)
    counts = {name: sum(r['status'] == name for r in records) for name in
              ('validated_result', 'invalid_result', 'failed', 'deferred', 'pending')}
    return {'informational_only': True, 'running_worker_files': running,
            'unreadable_worker_files': unreadable, 'counts': counts, 'batches': records,
            'note': 'Validated result means packet collection succeeded; semantic findings and acceptance remain separate.'}
