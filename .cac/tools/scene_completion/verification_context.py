"""Invocation-local replay reuse guarded by content hashes, never disk trust."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import hashlib
import json
from pathlib import Path
import time

_current = ContextVar('scene_verification_context', default=None)


@contextmanager
def session(root):
    if _current.get() is not None:
        yield
        return
    state = {'root': Path(root).resolve(), 'cache': {}, 'events': []}
    token = _current.set(state)
    try:
        yield
    finally:
        _current.reset(token)
        path = state['root'] / 'local_performance.jsonl'
        if state['events']:
            with path.open('a', encoding='utf8') as stream:
                for event in state['events']: stream.write(json.dumps(event) + '\n')


def invocation(method):
    @wraps(method)
    def wrapped(root, *args, **kwargs):
        with session(root): return method(root, *args, **kwargs)
    return wrapped


def measured(name):
    def decorate(method):
        @wraps(method)
        def wrapped(*args, **kwargs):
            start = time.perf_counter()
            try: return method(*args, **kwargs)
            finally:
                state = _current.get()
                if state is not None:
                    state['events'].append({'operation': name, 'seconds': time.perf_counter() - start})
        return wrapped
    return decorate


@measured('dependency_hashing')
def guard(root):
    from .concern_gap_replay import proof_files
    from .sources import fingerprint
    root = Path(root).resolve()
    bindings = proof_files(root)
    paths = {root / name for name in bindings}
    paths |= {root / 'run_manifest.json', root / 'ar_sources_index.json'}
    tools = Path(__file__).parent
    paths |= set(tools.glob('*.py')) | set((tools.parents[1] / 'skills').rglob('*.md'))
    visited, unresolved = set(), False
    missing = set()
    def discover(value):
        nonlocal unresolved
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'proofs' and isinstance(child, dict):
                    for path in child: add(path)
                discover(child)
        elif isinstance(value, list):
            for child in value: discover(child)
        elif isinstance(value, str) and len(value) < 4096 and '\n' not in value:
            if value.startswith('/') or len(value) > 2 and value[1:3] in (':/', ':\\'):
                add(value)
    def add(value):
        nonlocal unresolved
        try:
            path = Path(value)
            if path.is_file(): paths.add(path)
            elif path.suffix in ('.json', '.jsonl', '.txt', '.log'):
                # Imported native proofs may validly use portable sidecars
                # instead of the original absolute path. Bind absence too;
                # the initial real replay must still validate that proof.
                missing.add(str(path))
        except (OSError, ValueError): unresolved = True
    while True:
        pending = [p for p in paths - visited if p.is_file()]
        if not pending: break
        for path in pending:
            visited.add(path)
            if path.suffix == '.json':
                try: discover(json.loads(path.read_text(encoding='utf8')))
                except (ValueError, OSError): unresolved = True
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if p.is_file()}
    return None if unresolved else fingerprint({'files': hashes, 'missing_paths': sorted(missing), 'inventory': bindings})


def cached_replay(method):
    @wraps(method)
    def wrapped(root, cache_resume=False):
        state = _current.get()
        if state is None or cache_resume:
            return measured('replay_cache_resume' if cache_resume else 'replay')(method)(root, cache_resume=cache_resume)
        root = Path(root).resolve()
        before = guard(root)
        key = (str(root), before)
        if before and key in state['cache']:
            state['events'].append({'operation': 'replay_reused', 'seconds': 0})
            return deepcopy(state['cache'][key])
        result = measured('replay')(method)(root, cache_resume=False)
        after = guard(root)
        if before and before == after and result.get('complete'):
            state['cache'][key] = deepcopy(result)
        return result
    return wrapped
