"""Persistent dependency-local scheduling; no model or domain decisions here."""
from __future__ import annotations

from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
from pathlib import Path
import threading
import time
from contextvars import copy_context
from contextlib import contextmanager

from .semantic_backend import read_json, write_json
from .sources import fingerprint
from .model_configuration import concurrency_limit


@contextmanager
def run_lock(root):
    path = Path(root) / '.case_dag.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if not path.stat().st_size:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if __import__('os').name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError('this run already has an active scheduler/repair process') from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError('this run already has an active scheduler/repair process') from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class TaskBlocked(Exception):
    def __init__(self, status, details):
        super().__init__(str(details))
        self.status, self.details = status, details


class TaskRejected(Exception):
    def __init__(self, details):
        super().__init__(str(details))
        self.details = details


@dataclass
class Task:
    key: str
    case: str
    stage: str
    deps: tuple = ()
    version: object = None
    lane: str = 'progress'
    execute: object = None
    repair: object = None
    verify: object = None
    compatible: object = None
    supervisor: object = None
    compatible_failure: object = None


class CallGate:
    """One global permit per actual API/native request, including embedding."""
    def __init__(self, concurrency=1, *, adaptive=True, on_change=None):
        self.limit = concurrency_limit(concurrency)
        self.effective_limit = self.limit
        self.active = 0
        self.condition = threading.Condition()
        self.adaptive, self.on_change = adaptive, on_change
        self.quota = threading.Event()
        self.retry_not_before=0.

    @contextmanager
    def slot(self):
        with self.condition:
            while self.active >= self.effective_limit or time.monotonic()<self.retry_not_before:
                cooldown=max(0.,self.retry_not_before-time.monotonic())
                self.condition.wait(timeout=cooldown if cooldown else None)
            self.active += 1
        try:
            yield
        finally:
            with self.condition:
                self.active -= 1
                self.condition.notify_all()

    def observe(self, diagnostic):
        if not isinstance(diagnostic, dict) or diagnostic.get('failure_category') != 'rate_limited':
            return
        with self.condition:
            if self.adaptive:self.effective_limit = max(1, self.effective_limit // 2)
            delay=max(1.,min(300.,float(diagnostic.get('retry_after_seconds') or 30)))
            self.retry_not_before=max(self.retry_not_before,time.monotonic()+delay)
            self.condition.notify_all()
        if self.on_change:
            self.on_change({'configured_max': self.limit, 'effective_max': self.effective_limit, 'reason': 'rate_limited',
                'not_before_unix':time.time()+max(0.,self.retry_not_before-time.monotonic())})

    def call(self, function, *args, **kwargs):
        with self.slot():
            if self.quota.is_set():
                raise TaskBlocked('budget_exhausted', 'external quota exhausted')
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                diagnostic = getattr(exc, 'response_diagnostic', None)
                self.observe(diagnostic)
                if diagnostic and diagnostic.get('configuration_required'):
                    raise TaskBlocked('awaiting_configuration', diagnostic) from exc
                if quota_error(str(exc)) or quota_error(str(diagnostic)):
                    self.quota.set()
                    raise TaskBlocked('budget_exhausted', 'external quota exhausted') from exc
                if diagnostic:
                    raise TaskBlocked('pending', {'transport_failure': diagnostic, 'semantic_round_not_consumed': True}) from exc
                raise
            if quota_error(str(result)):
                self.quota.set()
            if isinstance(result, dict):
                for row in result.get('batches', []):
                    self.observe(row)
            return result

    def budget_scope(self):
        """Separate provider quota, sharing permits, throttling and cooldown."""
        scope = CallGate(self.limit, adaptive=self.adaptive)
        scope.slot = self.slot
        scope.observe = self.observe
        return scope


def quota_error(text):
    value = text.lower()
    return any(v in value for v in ('insufficient_quota', 'quota_exhausted', 'credits limit',
        'credit limit', 'quota exceeded', 'usage limit', '额度', 'budget_exhausted'))


def failure_signature(details):
    if isinstance(details, dict):
        if 'findings' in details:
            return fingerprint(details['findings'])
        if 'errors' in details:
            return fingerprint(sorted(details['errors'].values()))
        details = {k: v for k, v in details.items() if k not in ('output', 'executions', 'folder')}
    return fingerprint(details)


class Scheduler:
    def __init__(self, root, *, concurrency=1, auto_repair='bounded', max_rounds=2, profiler=None):
        if auto_repair not in ('bounded', 'off') or not 0 <= max_rounds <= 2:
            raise ValueError('automatic repair is bounded to at most two rounds')
        self.root = Path(root)
        self.path = self.root / 'case_tasks.json'
        self.state = read_json(self.path) if self.path.exists() else {'schema': 'case-dag-v1', 'tasks': {}, 'events': []}
        self.tasks = {}
        self.limit = concurrency_limit(concurrency)
        self.auto_repair, self.max_rounds = auto_repair, max_rounds
        self.cursor = 0
        self.profiler = profiler
        self.ready_times = {}

    def add(self, task):
        if task.key in self.tasks:
            raise ValueError('duplicate task key')
        self.tasks[task.key] = task
        if task.key not in self.state['tasks'] and task.key in self.state.get('inactive_tasks', {}):
            self.state['tasks'][task.key] = self.state['inactive_tasks'].pop(task.key)
        record = self.state['tasks'].setdefault(task.key, {'case': task.case, 'stage': task.stage,
            'status': 'pending', 'rounds': 0, 'attempts': []})
        if record.get('version')!=task.version and 'previous_version' not in record:
            record['previous_version']=record.get('version')
        record.update(case=task.case, stage=task.stage, dependencies=list(task.deps), version=task.version)
        # A crash cannot replenish a reserved semantic repair round.
        if record['status'] == 'repairing':
            record['status'] = 'rejected'
        elif record['status'] == 'supervising':
            record.update(status='budget_exhausted', reason='supervisor execution interrupted; reserved attempt retained')
        elif record['status'] == 'running':
            record['status'] = 'pending'
        elif record['status'] in ('awaiting_configuration','diagnosis_blocked'):
            record['status'] = 'pending'

    def save(self):
        write_json(self.path, self.state)

    def input_hash(self, task):
        return fingerprint({'version': task.version, 'dependencies': {
            key: self.state['tasks'][key].get('output_hash') for key in task.deps}})

    def invalidate(self, key):
        affected = {key}
        while True:
            expanded = affected | {t.key for t in self.tasks.values() if set(t.deps) & affected}
            if expanded == affected:
                break
            affected = expanded
        for item in affected:
            r = self.state['tasks'][item]
            r['status'] = 'stale'
            r.pop('output_hash', None)
            r.pop('reuse_reserved_round', None)
        self.save()
        return affected

    def _ready(self, task):
        return all(self.state['tasks'][key]['status'] == 'passed' for key in task.deps)

    def _refresh(self):
        for task in self.tasks.values():
            record = self.state['tasks'][task.key]
            if not self._ready(task):
                continue
            current = self.input_hash(task)
            if record.get('input_hash')==current:
                record.pop('previous_version',None)
            if record.get('input_hash') != current:
                previous=fingerprint({'version':record.get('previous_version'),'dependencies':{
                    key:self.state['tasks'][key].get('output_hash') for key in task.deps}})
                if (record['status'] in ('rejected', 'budget_exhausted', 'diagnosis_blocked')
                        and task.compatible_failure and previous == record.get('input_hash')):
                    try:
                        deps = {key: read_json(self.root / self.state['tasks'][key]['output_file']) for key in task.deps}
                        task.compatible_failure(deps, record)
                    except (ValueError, KeyError, OSError, TypeError, TaskBlocked):
                        pass
                    else:
                        self.state['events'].append({'task': task.key, 'event': 'failed_context_revalidated',
                            'old_input_hash': record['input_hash'], 'input_hash': current})
                        record['input_hash'] = current
                        record.pop('previous_version', None)
                        self.save()
                        continue
                if record['status']=='passed' and task.compatible and previous==record.get('input_hash'):
                    try:
                        output=read_json(self.root/record['output_file'])
                        if fingerprint(output)!=record['output_hash']:raise ValueError('task output changed')
                        deps={key:read_json(self.root/self.state['tasks'][key]['output_file']) for key in task.deps}
                        task.compatible(deps,output)
                    except (ValueError,KeyError,OSError,TypeError,TaskBlocked):pass
                    else:
                        self.state['events'].append({'task':task.key,'event':'compatible_version_reuse',
                            'old_input_hash':record['input_hash'],'input_hash':current,'output_hash':record['output_hash']})
                        record['input_hash']=current
                        record.pop('previous_version',None)
                        self.save()
                        if self.profiler:self.profiler.emit('cache',case=task.case,stage=task.stage,compatible_version=True)
                        continue
                self.invalidate(task.key)
                record['input_hash'] = current
                record.pop('previous_version',None)
                record.pop('failure', None)
            if record['status'] == 'stale' and task.compatible_failure:
                prior = next((attempt for attempt in reversed(record.get('attempts', []))
                    if attempt.get('failure') and attempt.get('status') in ('rejected', 'budget_exhausted')), None)
                if prior:
                    try:
                        deps = {key: read_json(self.root / self.state['tasks'][key]['output_file']) for key in task.deps}
                        task.compatible_failure(deps, {**record, 'failure': prior['failure']})
                    except (ValueError, KeyError, OSError, TypeError, TaskBlocked):
                        pass
                    else:
                        record.update(failure=prior['failure'], status='budget_exhausted'
                            if prior['status'] == 'budget_exhausted' or record['rounds'] >= self.max_rounds else 'rejected')
                        self.state['events'].append({'task': task.key, 'event': 'failed_context_revalidated',
                            'input_hash': current, 'original_attempt_input_hash': prior['input_hash']})
                        self.save()
            if record['status'] == 'passed':
                try:
                    output = read_json(self.root / record['output_file'])
                    if fingerprint(output) != record['output_hash']:
                        raise ValueError('task output changed')
                    if task.verify:
                        from .performance import span
                        with span(self.profiler,'validation',case=task.case,stage=task.stage,reuse=True):
                            task.verify(output)
                    if self.profiler:self.profiler.emit('cache',case=task.case,stage=task.stage)
                except TaskBlocked as exc:
                    self.invalidate(task.key)
                    record.update(status=exc.status, reason=exc.details)
                except (ValueError, KeyError, OSError, TypeError):
                    self.invalidate(task.key)

    def _pick(self, running, seen):
        queues = {k: deque() for k in ('progress', 'repair', 'discovery')}
        for task in self.tasks.values():
            r = self.state['tasks'][task.key]
            if self._ready(task) and task.key not in self.ready_times:
                self.ready_times[task.key]=time.perf_counter()
            if task.key in running or task.key in seen or not self._ready(task):
                continue
            if getattr(self, 'allowed', None) is not None and task.key not in self.allowed:
                continue
            if (task.supervisor and r['status'] in ('budget_exhausted', 'diagnosis_blocked')
                    and not r.get('supervisor_rounds', 0)):
                queues['repair'].append((task, 'supervisor'))
            elif r.get('reuse_reserved_round') and r['status'] in ('pending', 'rejected') and task.repair and self.auto_repair == 'bounded':
                queues['repair'].append((task, True))
            elif r['status'] in ('pending', 'stale'):
                queues[task.lane].append((task, False))
            elif r['status'] == 'rejected' and self.auto_repair == 'bounded' and task.repair:
                if r['rounds'] >= self.max_rounds:
                    r['status'] = 'budget_exhausted'
                    r['reason'] = 'semantic repair rounds exhausted'
                    if task.supervisor and not r.get('supervisor_rounds', 0):
                        queues['repair'].append((task, 'supervisor'))
                else:
                    queues['repair'].append((task, True))
        lanes = ('progress', 'repair', 'discovery')
        for _ in lanes:
            lane = lanes[self.cursor % 3]
            self.cursor += 1
            if queues[lane]:
                return queues[lane].popleft()
        return None

    def run(self, on_update=None, allowed=None):
        self.allowed = set(allowed) if allowed is not None else None
        for key in list(self.state['tasks']):
            if key not in self.tasks:
                self.state.setdefault('inactive_tasks', {})[key] = self.state['tasks'].pop(key)
        seen, running = set(), {}
        self._refresh()
        with ThreadPoolExecutor(max_workers=self.limit) as pool:
            while True:
                while len(running) < self.limit:
                    item = self._pick({t.key for t, _ in running.values()}, seen)
                    if not item:
                        break
                    task, repairing = item
                    record = self.state['tasks'][task.key]
                    record['input_hash'] = self.input_hash(task)
                    supervising = repairing == 'supervisor'
                    record['status'] = 'supervising' if supervising else ('repairing' if repairing else 'running')
                    if supervising:
                        record['supervisor_rounds'] = record.get('supervisor_rounds', 0) + 1
                    elif repairing:
                        if not record.pop('reuse_reserved_round', False):
                            record['rounds'] += 1
                    self.state['events'].append({'task': task.key, 'event': record['status'], 'round': record['rounds']})
                    self.save()
                    deps = {key: read_json(self.root / self.state['tasks'][key]['output_file']) for key in task.deps}
                    function = task.supervisor if supervising else (task.repair if repairing else task.execute)
                    def timed_execute(function=function, deps=deps, record=dict(record), task=task, repairing=repairing):
                        from .performance import span
                        with span(self.profiler, 'task', case=task.case,stage=task.stage,
                                task_key=task.key,dependencies=list(task.deps),
                                phase='supervisor' if repairing == 'supervisor' else ('repair' if repairing else 'execute'), round=record['rounds'],
                                queue_seconds=time.perf_counter()-self.ready_times.pop(task.key,time.perf_counter())):
                            return function(deps,record)
                    future = pool.submit(copy_context().run, timed_execute)
                    running[future] = (task, repairing)
                if not running:
                    break
                done, _ = wait(running, return_when=FIRST_COMPLETED)
                for future in done:
                    task, repairing = running.pop(future)
                    record = self.state['tasks'][task.key]
                    try:
                        output = future.result()
                        replacements = output.pop('_replacements', {}) if isinstance(output, dict) else {}
                        for key, replacement in replacements.items():
                            self.invalidate(key)
                            old = self.state['tasks'][key]
                            target = 'task_outputs/' + fingerprint(key) + '.json'
                            if (self.root / target).exists():
                                write_json(self.root / 'task_history' / (fingerprint(read_json(self.root / target)) + '.json'), read_json(self.root / target))
                            write_json(self.root / target, replacement)
                            old.update(status='passed', output_file=target, output_hash=fingerprint(replacement))
                            old['input_hash'] = self.input_hash(self.tasks[key])
                        record['input_hash'] = self.input_hash(task)
                        if task.verify:
                            from .performance import span
                            with span(self.profiler,'validation',case=task.case,stage=task.stage):
                                task.verify(output)
                        filename = 'task_outputs/' + fingerprint(task.key) + '.json'
                        write_json(self.root / filename, output)
                        record.update(status='passed', output_file=filename, output_hash=fingerprint(output))
                        record.pop('failure', None)
                    except TaskBlocked as exc:
                        record.update(status=exc.status, reason=exc.details)
                        if repairing and repairing != 'supervisor' and exc.status in ('pending', 'budget_exhausted', 'awaiting_configuration','diagnosis_blocked'):
                            record['reuse_reserved_round'] = True
                        if repairing == 'supervisor' or not task.supervisor or exc.status not in ('budget_exhausted', 'diagnosis_blocked'):
                            seen.add(task.key)
                    except Exception as exc:
                        details = exc.details if isinstance(exc, TaskRejected) else {'error': str(exc)}
                        failure = failure_signature(details)
                        repeated = repairing and failure == record.get('failure_hash')
                        if not isinstance(exc, TaskRejected):
                            record.update(status='pending', failure=details, failure_hash=failure,
                                reason={'tool_error': str(exc)})
                            seen.add(task.key)
                        else:
                            record.update(status='budget_exhausted' if repeated or repairing == 'supervisor' else 'rejected', failure=details,
                                failure_hash=failure)
                        if repairing == 'supervisor':
                            record['reason'] = 'supervisor output rejected; no further automatic semantic attempts'
                            seen.add(task.key)
                        if repeated:
                            record['reason'] = 'same failure; no semantic progress'
                        if not task.repair or self.auto_repair == 'off':
                            seen.add(task.key)
                    record['attempts'].append({'round': record['rounds'], 'status': record['status'],
                        'failure': record.get('failure'), 'input_hash': record['input_hash']})
                    self.state['events'].append({'task': task.key, 'event': record['status'], 'round': record['rounds']})
                    self.save()
                    if on_update:
                        on_update(self)
        self.save()
        return self.summary()

    def resume_external_budget(self):
        for r in self.state['tasks'].values():
            if r['status'] == 'budget_exhausted' and r.get('reason') == 'external quota exhausted':
                r['status'] = 'rejected' if r.get('reuse_reserved_round') else 'pending'

    def summary(self):
        rows = [dict(key=k, **self.state['tasks'][k]) for k in self.tasks]
        return {'complete': all(r['status'] == 'passed' for r in rows),
            'counts': dict(Counter(r['status'] for r in rows)),
            'pending_tasks': [{'key': r['key'], 'case': r['case'], 'stage': r['stage'], 'status': r['status'],
                'reason': r.get('reason', r.get('failure')), 'dependencies': r['dependencies']} for r in rows if r['status'] != 'passed']}
