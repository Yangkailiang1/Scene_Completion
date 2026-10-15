"""Persistent dependency-local scheduling; no model or domain decisions here."""
from __future__ import annotations

from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import copy
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
    def __init__(self, concurrency=1, *, adaptive=True, on_change=None, pause_file=None):
        self.limit = concurrency_limit(concurrency)
        self.effective_limit = self.limit
        self.active = 0
        self.condition = threading.Condition()
        self.adaptive, self.on_change = adaptive, on_change
        self.quota = threading.Event()
        self.retry_not_before=0.
        self.pause_file = Path(pause_file) if pause_file else None

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
            if self.pause_file and self.pause_file.exists():
                raise TaskBlocked('pending', {'admission_paused': True, 'semantic_round_not_consumed': True})
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
                    blocked = TaskBlocked('budget_exhausted', diagnostic or 'external quota exhausted')
                    blocked.response_diagnostic = diagnostic or {}
                    raise blocked from exc
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
        scope = CallGate(self.limit, adaptive=self.adaptive, pause_file=self.pause_file)
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
        elif record['status'] == 'diagnosis_blocked':
            # Resume the reserved repair, not the initial extraction. Keeping
            # rejection status also permits source-bound failure revalidation
            # when a diagnostic protocol fix changes the task version.
            record['status'] = 'rejected'
        elif record['status'] == 'awaiting_configuration':
            record['status'] = 'pending'

    def save(self):
        write_json(self.path, self.state)

    def input_hash(self, task):
        return fingerprint({'version': task.version, 'dependencies': {
            key: self.state['tasks'][key].get('output_hash') for key in task.deps}})

    def invalidate(self, key, *, persist=True):
        affected = {key}
        while True:
            expanded = affected | {t.key for t in self.tasks.values() if set(t.deps) & affected}
            if expanded == affected:
                break
            affected = expanded
        for item in affected:
            r = self.state['tasks'][item]
            if r['status'] == 'passed' and r.get('output_hash'):
                r['retained_success'] = {key: r[key] for key in ('input_hash', 'output_file', 'output_hash')}
                r['retained_success']['version'] = r.get('previous_version', r.get('version'))
            r['status'] = 'stale'
            r.pop('output_hash', None)
            r.pop('reuse_reserved_round', None)
        if persist:
            self.save()
        return affected

    def _promotion_dir(self):
        return self.root / 'promotion_intents'

    def _promotion_path(self, task_key, input_hash, output_hash):
        return self._promotion_dir() / (fingerprint([task_key, input_hash, output_hash]) + '.json')

    @staticmethod
    def _sealed_intent(payload):
        return {**payload, 'intent_hash': fingerprint(payload)}

    @staticmethod
    def _verify_intent_seal(intent):
        payload = {key: value for key, value in intent.items() if key != 'intent_hash'}
        if intent.get('intent_hash') != fingerprint(payload):
            raise ValueError('promotion intent hash mismatch')
        if intent.get('schema') != 'case-dag-promotion-v1':
            raise ValueError('unsupported promotion intent schema')
        return payload

    def _task_binding(self, task):
        record = self.state['tasks'][task.key]
        dependencies = {}
        for key in task.deps:
            dependency = self.state['tasks'][key]
            if dependency.get('status') != 'passed' or not dependency.get('output_file') or not dependency.get('output_hash'):
                raise ValueError(f'promotion dependency is not a verified success: {key}')
            expected_hash = dependency['output_hash']
            output_path = self.root / dependency['output_file']
            valid = False
            if output_path.exists():
                try:
                    valid = fingerprint(read_json(output_path)) == expected_hash
                except (ValueError, OSError, TypeError):
                    valid = False
            if not valid:
                # A pending promotion may have partially overwritten a dependency;
                # its pre-promotion output must still exist in the history archive.
                history = self.root / 'task_history' / (expected_hash + '.json')
                if history.exists():
                    try:
                        valid = fingerprint(read_json(history)) == expected_hash
                    except (ValueError, OSError, TypeError):
                        valid = False
            if not valid:
                raise ValueError(f'promotion dependency output changed: {key}')
            dependencies[key] = expected_hash
        return {'version': task.version, 'dependencies': list(task.deps),
            'input_hash': self.input_hash(task),
            'dependency_outputs': dependencies}

    def _new_promotion_intent(self, task, output, replacements):
        if not isinstance(replacements, dict) or not replacements:
            raise ValueError('promotion replacements must be a non-empty object')
        keys = [task.key, *replacements]
        if len(keys) != len(set(keys)) or any(key not in self.tasks for key in replacements):
            raise ValueError('promotion references an unknown or duplicate task')
        raw_output = copy.deepcopy(output)
        output_payload = copy.deepcopy(output)
        output_payload.pop('_replacements', None)
        bindings = {key: self._task_binding(self.tasks[key]) for key in keys}
        records = {key: copy.deepcopy(self.state['tasks'][key]) for key in keys}
        prior_outputs = {}
        for key in replacements:
            record = self.state['tasks'][key]
            old = None
            if record.get('output_file'):
                old_path = self.root / record['output_file']
                if old_path.exists():
                    old = read_json(old_path)
                    if record.get('output_hash') and fingerprint(old) != record['output_hash']:
                        raise ValueError(f'cannot promote over changed prior output for {key}')
            prior_outputs[key] = old
        payload = {'schema': 'case-dag-promotion-v1', 'status': 'pending',
            'task_key': task.key, 'task_input_hash': self.input_hash(task),
            'task_output_raw': raw_output, 'task_output_raw_hash': fingerprint(raw_output),
            'task_output': output_payload, 'task_output_hash': fingerprint(output_payload),
            'replacements': copy.deepcopy(replacements),
            'replacement_hashes': {key: fingerprint(value) for key, value in replacements.items()},
            'bindings': bindings, 'records_before': records, 'prior_outputs': prior_outputs,
            'round': self.state['tasks'][task.key].get('rounds', 0),
            'supervisor_round': self.state['tasks'][task.key].get('supervisor_rounds', 0),
            'supervisor_revision': self.state['tasks'][task.key].get('active_supervisor_revision')}
        intent = self._sealed_intent(payload)
        path = self._promotion_path(task.key, payload['task_input_hash'], payload['task_output_hash'])
        if path.exists():
            existing = read_json(path)
            existing_payload = self._verify_intent_seal(existing)
            # A worker may stage this before returning. The scheduler must
            # reuse that exact durable intent and must never replace a pending
            # intent for the same task/output identity with different bindings.
            comparable_existing = {key: value for key, value in existing_payload.items() if key != 'status'}
            comparable_new = {key: value for key, value in payload.items() if key != 'status'}
            if comparable_existing != comparable_new:
                raise ValueError('existing promotion intent conflicts with the current task binding or output')
            if existing_payload.get('status') not in ('pending', 'committed'):
                raise ValueError('existing promotion intent is not recoverable')
            return path, existing
        write_json(path, intent)
        return path, intent

    def stage_promotion(self, task_key, output):
        """Durably stage a successful worker output before it writes active candidates."""
        if task_key not in self.tasks:
            raise ValueError(f'cannot stage promotion for unregistered task {task_key}')
        if not isinstance(output, dict) or not output.get('_replacements'):
            raise ValueError('staged promotion output must contain non-empty _replacements')
        return self._new_promotion_intent(self.tasks[task_key], output, output['_replacements'])[0]

    def _check_promotion_binding(self, payload):
        task_key = payload.get('task_key')
        if task_key not in self.tasks:
            raise ValueError('promotion task is not registered in the current scheduler')
        task = self.tasks[task_key]
        if fingerprint(payload.get('task_output')) != payload.get('task_output_hash'):
            raise ValueError('promotion task output hash mismatch')
        if fingerprint(payload.get('task_output_raw')) != payload.get('task_output_raw_hash'):
            raise ValueError('promotion original output hash mismatch')
        replacements = payload.get('replacements')
        if not isinstance(replacements, dict) or not replacements:
            raise ValueError('promotion replacements are missing')
        if set(replacements) != set(payload.get('replacement_hashes', {})):
            raise ValueError('promotion replacement manifest mismatch')
        for key, value in replacements.items():
            if key not in self.tasks or fingerprint(value) != payload['replacement_hashes'].get(key):
                raise ValueError(f'promotion replacement hash mismatch for {key}')
        keys = [task_key, *replacements]
        if set(payload.get('bindings', {})) != set(keys) or set(payload.get('records_before', {})) != set(keys):
            raise ValueError('promotion task binding manifest mismatch')
        for key in keys:
            current = self._task_binding(self.tasks[key])
            before = payload['bindings'][key]
            if current != before:
                raise ValueError(f'promotion binding expired for {key}')
            expected_record = payload['records_before'][key]
            record = self.state['tasks'][key]
            # add() changes a persisted running record to pending after a crash.
            allowed_statuses = {expected_record.get('status')}
            if key == task_key and expected_record.get('status') == 'running':
                allowed_statuses.add('pending')
            for field in ('version', 'dependencies', 'input_hash', 'rounds', 'attempts', 'output_hash', 'output_file'):
                if record.get(field) != expected_record.get(field):
                    raise ValueError(f'promotion record changed for {key}: {field}')
            if record.get('status') not in allowed_statuses:
                raise ValueError(f'promotion status changed for {key}')
        if payload.get('task_input_hash') != payload['bindings'][task_key].get('input_hash'):
            raise ValueError('promotion task input hash does not match its dependency binding')
        return task

    def _archive_prior_output(self, key, prior):
        if prior is None:
            return
        write_json(self.root / 'task_history' / (fingerprint(prior) + '.json'), prior)

    def _apply_promotion(self, intent, *, recovering=False):
        payload = self._verify_intent_seal(intent)
        task = self._check_promotion_binding(payload)
        task_key = task.key
        output = copy.deepcopy(payload['task_output'])
        replacements = payload['replacements']
        state_before = copy.deepcopy(self.state)
        # Back up every prior candidate before the first replacement can land.
        for key, prior in payload['prior_outputs'].items():
            self._archive_prior_output(key, prior)
        try:
            for key, replacement in replacements.items():
                self.invalidate(key, persist=False)
                old = self.state['tasks'][key]
                target = 'task_outputs/' + fingerprint(key) + '.json'
                write_json(self.root / target, replacement)
                old.update(status='passed', output_file=target, output_hash=fingerprint(replacement))
                old.pop('previous_version', None)
                old.pop('retained_success', None)
                old['input_hash'] = self.input_hash(self.tasks[key])
            record = self.state['tasks'][task_key]
            record['input_hash'] = self.input_hash(task)
            if task.verify:
                from .performance import span
                with span(self.profiler, 'validation', case=task.case, stage=task.stage, reuse=recovering):
                    task.verify(output)
            filename = 'task_outputs/' + fingerprint(task.key) + '.json'
            write_json(self.root / filename, output)
            record.update(status='passed', output_file=filename, output_hash=fingerprint(output))
            record.pop('previous_version', None)
            record.pop('retained_success', None)
            record.pop('failure', None)
            record.pop('reason', None)
            return output
        except Exception:
            self.state = state_before
            for key, prior in payload['prior_outputs'].items():
                record = payload['records_before'][key]
                if prior is not None and record.get('output_file'):
                    write_json(self.root / record['output_file'], prior)
            raise

    def _restore_prior_outputs(self):
        # If an intent cannot be trusted, keep every still-proven prior output
        # available from its content-addressed history copy.
        for key, record in self.state.get('tasks', {}).items():
            if record.get('status') != 'passed' or not record.get('output_file') or not record.get('output_hash'):
                continue
            current_path = self.root / record['output_file']
            try:
                if current_path.exists() and fingerprint(read_json(current_path)) == record['output_hash']:
                    continue
            except (ValueError, OSError, TypeError):
                pass
            history = self.root / 'task_history' / (record['output_hash'] + '.json')
            if history.exists():
                old = read_json(history)
                if fingerprint(old) == record['output_hash']:
                    write_json(current_path, old)

    def _block_promotion(self, path, message):
        self._restore_prior_outputs()
        intent_name = path.name
        try:
            intent = read_json(path)
            task_key = intent.get('task_key')
        except (ValueError, OSError, TypeError):
            task_key = None
        if task_key in self.state.get('tasks', {}):
            record = self.state['tasks'][task_key]
            record.update(status='promotion_blocked', reason={'promotion_intent': intent_name, 'error': message})
            self.state['events'].append({'task': task_key, 'event': 'promotion_blocked', 'intent': intent_name})
            self.save()

    def _recover_promotions(self):
        for path in sorted(self._promotion_dir().glob('*.json')) if self._promotion_dir().exists() else ():
            try:
                intent = read_json(path)
                payload = self._verify_intent_seal(intent)
                if payload.get('status') == 'committed':
                    continue
                if payload.get('status') != 'pending':
                    raise ValueError('promotion intent has an invalid status')
                if self._promotion_already_committed(payload, path.name):
                    write_json(path, self._sealed_intent({**payload, 'status': 'committed'}))
                    continue
                self._apply_promotion(intent, recovering=True)
                task_key = payload['task_key']
                record = self.state['tasks'][task_key]
                # A crash after state save but before marking committed is safe;
                # avoid duplicating the original attempt and event.
                attempts = record.setdefault('attempts', [])
                if not any(a.get('promotion_intent') == path.name for a in attempts):
                    attempts.append({'round': payload['round'], 'status': 'passed',
                        'supervisor_round': payload.get('supervisor_round', 0),
                        'supervisor_revision': payload.get('supervisor_revision'),
                        'failure': None, 'input_hash': record['input_hash'], 'promotion_intent': path.name})
                if not any(e.get('promotion_intent') == path.name for e in self.state['events']):
                    self.state['events'].append({'task': task_key, 'event': 'passed',
                        'round': payload['round'], 'promotion_intent': path.name})
                self.save()
                committed = self._sealed_intent({**payload, 'status': 'committed'})
                try:
                    write_json(path, committed)
                except OSError:
                    # State is already durable and carries the intent identity;
                    # the next resume will recognize this as committed.
                    pass
            except Exception as exc:
                self.state = read_json(self.path) if self.path.exists() else self.state
                self._block_promotion(path, str(exc))

    def _promotion_already_committed(self, payload, intent_name):
        task_key = payload.get('task_key')
        records = self.state.get('tasks', {})
        if task_key not in records or records[task_key].get('status') != 'passed':
            return False
        task_record = records[task_key]
        if task_record.get('output_hash') != payload.get('task_output_hash'):
            return False
        for key, expected_hash in payload.get('replacement_hashes', {}).items():
            if key not in records or records[key].get('status') != 'passed' or records[key].get('output_hash') != expected_hash:
                return False
        return any(a.get('promotion_intent') == intent_name for a in task_record.get('attempts', []))

    def _ready(self, task):
        return all(self.state['tasks'][key]['status'] == 'passed' for key in task.deps)

    def _refresh(self, *, stale_only=False):
        for task in self.tasks.values():
            record = self.state['tasks'][task.key]
            if record.get('status') == 'promotion_blocked':
                continue
            if stale_only and record['status'] != 'stale':
                continue
            if not self._ready(task):
                continue
            current = self.input_hash(task)
            retained = record.get('retained_success')
            if record['status'] == 'stale' and retained and task.compatible:
                previous = fingerprint({'version': retained['version'], 'dependencies': {
                    key: self.state['tasks'][key].get('output_hash') for key in task.deps}})
                if previous == retained['input_hash']:
                    try:
                        output = read_json(self.root / retained['output_file'])
                        if fingerprint(output) != retained['output_hash']:
                            raise ValueError('retained successful output changed')
                        deps = {key: read_json(self.root / self.state['tasks'][key]['output_file']) for key in task.deps}
                        task.compatible(deps, output)
                    except (ValueError, KeyError, OSError, TypeError, TaskBlocked):
                        pass
                    else:
                        record.update(status='passed', input_hash=current,
                            output_file=retained['output_file'], output_hash=retained['output_hash'])
                        record.pop('previous_version', None)
                        self.state['events'].append({'task': task.key, 'event': 'compatible_retained_reuse',
                            'input_hash': current, 'output_hash': retained['output_hash']})
                        self.save()
                        continue
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
                        if record.get('supervisor_revision_pending'):
                            from .supervisor_continuation import pending_revision
                            revision = pending_revision(record)
                            revision.setdefault('input_rebindings', []).append({
                                'from_input_hash': record['input_hash'], 'to_input_hash': current,
                                'failure_hash': record.get('failure_hash'),
                                'dependencies': {key: self.state['tasks'][key].get('output_hash') for key in task.deps},
                                'basis': 'original_allowed_input_revalidated'})
                            revision['input_hash'] = current
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
        if (self.root / 'pause_requested.json').exists() and self.allowed is None:
            return None
        queues = {k: deque() for k in ('progress', 'repair', 'discovery')}
        for task in self.tasks.values():
            r = self.state['tasks'][task.key]
            if self._ready(task) and task.key not in self.ready_times:
                self.ready_times[task.key]=time.perf_counter()
            if task.key in running or task.key in seen or not self._ready(task):
                continue
            if getattr(self, 'allowed', None) is not None and task.key not in self.allowed:
                continue
            if task.supervisor and r['status'] == 'supervisor_pending' and r.get('reuse_supervisor_round'):
                queues['repair'].append((task, 'supervisor'))
            elif (task.supervisor and r['status'] in ('budget_exhausted', 'diagnosis_blocked')
                    and r.get('supervisor_revision_pending')):
                from .supervisor_continuation import pending_revision
                pending_revision(r)
                queues['repair'].append((task, 'supervisor'))
            elif (task.supervisor and r['status'] in ('budget_exhausted', 'diagnosis_blocked')
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
        self._recover_promotions()
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
                        if not record.pop('reuse_supervisor_round', False):
                            record['supervisor_rounds'] = record.get('supervisor_rounds', 0) + 1
                            if record.get('supervisor_revision_pending'):
                                from .supervisor_continuation import pending_revision
                                revision = pending_revision(record)
                                revision.update(status='started', supervisor_round=record['supervisor_rounds'])
                                record['active_supervisor_revision'] = record.pop('supervisor_revision_pending')
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
                    promotion_path = None
                    try:
                        output = future.result()
                        replacements = output.get('_replacements', {}) if isinstance(output, dict) else {}
                        if replacements:
                            promotion_path, intent = self._new_promotion_intent(task, output, replacements)
                            output = self._apply_promotion(intent)
                        else:
                            record['input_hash'] = self.input_hash(task)
                            if task.verify:
                                from .performance import span
                                with span(self.profiler,'validation',case=task.case,stage=task.stage):
                                    task.verify(output)
                            filename = 'task_outputs/' + fingerprint(task.key) + '.json'
                            write_json(self.root / filename, output)
                            record.update(status='passed', output_file=filename, output_hash=fingerprint(output))
                            record.pop('previous_version', None)
                            record.pop('retained_success', None)
                            record.pop('failure', None)
                    except TaskBlocked as exc:
                        if promotion_path:
                            self.state = read_json(self.path) if self.path.exists() else self.state
                            self._block_promotion(promotion_path, str(exc.details))
                            record = self.state['tasks'][task.key]
                            seen.add(task.key)
                        else:
                            record.update(status=exc.status, reason=exc.details)
                            if repairing == 'supervisor' and isinstance(exc.details, dict) and exc.details.get('admission_paused'):
                                record.update(status='supervisor_pending', reuse_supervisor_round=True)
                            if repairing and repairing != 'supervisor' and exc.status in ('pending', 'budget_exhausted', 'awaiting_configuration','diagnosis_blocked'):
                                record['reuse_reserved_round'] = True
                            if repairing == 'supervisor' or not task.supervisor or exc.status not in ('budget_exhausted', 'diagnosis_blocked'):
                                seen.add(task.key)
                    except Exception as exc:
                        if promotion_path:
                            self.state = read_json(self.path) if self.path.exists() else self.state
                            self._block_promotion(promotion_path, str(exc))
                            record = self.state['tasks'][task.key]
                            seen.add(task.key)
                        else:
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
                                record['reason'] = 'supervisor output rejected; controller must diagnose and register a revised correction before continuing'
                                seen.add(task.key)
                            if repeated:
                                record['reason'] = 'same failure; no semantic progress'
                            if not task.repair or self.auto_repair == 'off':
                                seen.add(task.key)
                    attempt = {'round': record['rounds'], 'status': record['status'],
                        'supervisor_round': record.get('supervisor_rounds', 0),
                        'supervisor_revision': record.get('active_supervisor_revision') if repairing == 'supervisor' else None,
                        'failure': record.get('failure'), 'input_hash': record['input_hash']}
                    if promotion_path:
                        attempt['promotion_intent'] = promotion_path.name
                    record['attempts'].append(attempt)
                    event = {'task': task.key, 'event': record['status'], 'round': record['rounds']}
                    if promotion_path:
                        event['promotion_intent'] = promotion_path.name
                    self.state['events'].append(event)
                    self.save()
                    if promotion_path:
                        payload = self._verify_intent_seal(read_json(promotion_path))
                        write_json(promotion_path, self._sealed_intent({**payload, 'status': 'committed'}))
                    if on_update:
                        on_update(self)
                # A completed deterministic upstream task may restore exactly
                # the previous dependency hash. Reconcile retained successes
                # before the next ready task is dispatched, not just at startup.
                self._refresh(stale_only=True)
        self.save()
        return self.summary()

    def resume_external_budget(self, *, batch_transition=None):
        # A configured forward model switch may resume a never-completed
        # initial batch. It does not grant another semantic repair or bypass
        # an already diagnosed supervisor correction.
        transition = batch_transition or {}
        switched = (type(transition.get('from_index')) is int
            and type(transition.get('to_index')) is int
            and transition['to_index'] > transition['from_index'] >= 0
            and transition.get('reason') in ('configured_profile_selection', 'quota_exhausted')
            and (transition.get('reason') != 'configured_profile_selection'
                or bool(str(transition.get('basis', '')).strip())))
        transition_hash = fingerprint(transition) if switched else None
        for key, r in self.state['tasks'].items():
            reason = r.get('reason')
            provider_quota = isinstance(reason, dict) and reason.get('failure_category') in ('quota_exhausted', 'budget_exhausted')
            if r.get('supervisor_revision_pending') and r['status'] in ('pending', 'rejected', 'budget_exhausted'):
                # A diagnosed supervisor continuation must never fall back to
                # the initial batch request when a quota window is resumed.
                r['status'] = 'budget_exhausted'
                continue
            if r['status'] == 'budget_exhausted' and (reason == 'external quota exhausted' or provider_quota):
                if r.get('supervisor_rounds'):
                    if (not switched or r.get('rounds', 0) or r.get('failure_hash')
                            or r.get('batch_budget_resume_transition') == transition_hash):
                        continue
                    r['batch_budget_resume_transition'] = transition_hash
                    self.state['events'].append({'task': key, 'event': 'batch_budget_profile_resume',
                        'transition': transition, 'supervisor_rounds': r['supervisor_rounds'],
                        'rounds': r.get('rounds', 0)})
                r['status'] = 'rejected' if r.get('reuse_reserved_round') else 'pending'

    def summary(self):
        rows = [dict(key=k, **self.state['tasks'][k]) for k in self.tasks]
        return {'complete': all(r['status'] == 'passed' for r in rows),
            'admission_paused': (self.root / 'pause_requested.json').exists(),
            'counts': dict(Counter(r['status'] for r in rows)),
            'pending_tasks': [{'key': r['key'], 'case': r['case'], 'stage': r['stage'], 'status': r['status'],
                'reason': r.get('reason', r.get('failure')), 'dependencies': r['dependencies']} for r in rows if r['status'] != 'passed']}
