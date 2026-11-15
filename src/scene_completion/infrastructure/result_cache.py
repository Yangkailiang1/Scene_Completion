"""Bounded read cache invalidated by atomic file replacement, including worker writes."""

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from scene_completion.infrastructure.storage import read_json


@lru_cache(maxsize=48)
def _read(path, identity):
    return read_json(path)


def read_snapshot(path):
    path = Path(path)
    stat = path.stat()
    return deepcopy(_read(str(path.resolve()), (stat.st_mtime_ns, stat.st_size, stat.st_ino)))


def cached_index(*directories):
    """Cache derived indexes against all persisted revision identities, across workers."""
    from collections import OrderedDict
    from functools import wraps
    from threading import RLock

    def decorate(fn):
        cache, lock = OrderedDict(), RLock()

        @wraps(fn)
        def index(project):
            root = Path(project).resolve()
            files = sorted(
                p for directory in directories for p in (root / directory).rglob("*.json")
            )
            signature = tuple(
                (str(p), s.st_mtime_ns, s.st_size, s.st_ino)
                for p in files
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
