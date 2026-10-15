"""Persistent ten-minute progress watchdog; controller chatter is not progress."""
from pathlib import Path
import time
from .sources import fingerprint
from .semantic_backend import read_json, write_json


def inspect(root, state_file, *, now=None, timeout=600):
    root = Path(root)
    now = time.time() if now is None else now
    state = read_json(root/'case_tasks.json')
    tasks = {k: {field: row.get(field) for field in ('status', 'rounds', 'supervisor_rounds', 'output_hash', 'failure_hash')}
        for k, row in state['tasks'].items()}
    repo = Path(__file__).resolve().parents[3]
    tools = {p.name: fingerprint(p.read_text(encoding='utf8')) for p in (repo/'.cac/tools/scene_completion').glob('*.py')}
    # Only actual persisted diagnosis/correction/test evidence counts. Printing
    # another status, changing log size or thinking longer never resets time.
    evidence = {str(p.relative_to(root)): p.stat().st_mtime_ns for pattern in
        ('verification/*.xml', 'cases/*/repair_rounds/*.json', 'cases/*/diagnosis_format_budget.json',
         'cases/*/batches/*/results/*.json', 'batches/independent-effect-review/results/*.json',
         'batches/independent-effect-review/*/results/*.json',
         'effect_review.json', 'acceptance.json', 'final_snapshot.json') for p in root.glob(pattern)}
    signature = fingerprint({'tasks': tasks, 'tools': tools, 'evidence': evidence})
    path = Path(state_file)
    old = read_json(path) if path.exists() else {}
    changed = old.get('signature') != signature
    last = now if changed else old['last_progress_unix']
    result = {'signature': signature, 'last_progress_unix': last, 'observed_unix': now,
        'idle_seconds': max(0, now-last), 'stagnated': now-last >= timeout,
        'action': 'diagnose_actual_blocker_do_not_repeat_status_or_paid_request' if now-last >= timeout else 'continue'}
    write_json(path, result)
    return result
