"""Bounded read cache invalidated by atomic file replacement, including worker writes."""

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from scene_completion.infrastructure.storage import read_json


@lru_cache(maxsize=48)
def _read(path, identity):
    return read_json(path)


def read_snapshot(path, *, isolate=True):
    path = Path(path)
    stat = path.stat()
    value = _read(str(path.resolve()), (stat.st_mtime_ns, stat.st_size, stat.st_ino))
    return deepcopy(value) if isolate else value


def cached_index(*directories, files=()):
    """Cache derived indexes against all persisted revision identities, across workers."""
    from collections import OrderedDict
    from functools import wraps
    from threading import RLock

    def decorate(fn):
        cache, lock = OrderedDict(), RLock()

        @wraps(fn)
        def index(project):
            root = Path(project).resolve()
            paths = sorted(
                [p for directory in directories for p in (root / directory).rglob("*.json")]
                + [root / name for name in files]
            )
            signature = tuple(
                (str(p), s.st_mtime_ns, s.st_size, s.st_ino)
                for p in paths
                if p.is_file()
                for s in [p.stat()]
            )
            key = (str(root), signature)
            with lock:
                if key in cache:
                    cache.move_to_end(key)
                    return deepcopy(cache[key])
            value = fn(project)
            with lock:
                cache[key] = deepcopy(value)
                while len(cache) > 12:
                    cache.popitem(last=False)
            return value

        return index

    return decorate
