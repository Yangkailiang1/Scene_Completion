"""Current concern definitions and project-scoped inheritance DAG."""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import lru_cache, wraps
from pathlib import Path

from scene_completion.infrastructure.identity import fingerprint


def validate_registry(value):
    if value.get("version") != "interaction-global-concerns-v5":
        raise ValueError("unsupported concern registry version")
    digest = fingerprint({k: v for k, v in value.items() if k != "hash"})
    if value.get("hash") != digest:
        raise ValueError("concern registry digest mismatch")
    definitions = value["definitions"]
    if not definitions:
        raise ValueError("empty concern registry")
    visiting = set()
    done = set()

    def visit(key):
        if key not in definitions:
            raise ValueError("unknown concern parent/profile target: " + key)
        if key in visiting:
            raise ValueError("concern inheritance cycle")
        if key in done:
            return
        d = definitions[key]
        if d["key"] != key:
            raise ValueError("concern ID/key mismatch")
        visiting.add(key)
        for parent in d["parents"]:
            visit(parent)
        visiting.remove(key)
        done.add(key)

    for key in definitions:
        visit(key)

    def profiles(node):
        if isinstance(node, dict):
            for v in node.values():
                profiles(v)
        else:
            for key in node:
                visit(key)

    profiles(value["profiles"])
    return value


@lru_cache(maxsize=4)
def _parsed(text):
    return validate_registry(json.loads(text))


_active_registry = ContextVar("project_concern_registry", default=None)


def default_registry():
    value = deepcopy(
        _parsed(Path(__file__).with_name("concern_registry.json").read_text(encoding="utf8"))
    )
    # These archived interaction keys have moved to the global business-operation
    # policy. Interpret that policy consistently without rewriting the user's JSON
    # or manufacturing a registry migration/event on the first project read.
    if value["definitions"].get("global.idempotency", {}).get("enabled", True):
        for key in (
            "service.resource_mutation.idempotency",
            "service.crud.create.idempotency",
            "service.crud.update.idempotency",
            "service.crud.delete.idempotency",
        ):
            if key in value["definitions"]:
                value["definitions"][key]["enabled"] = False
        value["hash"] = fingerprint({k: v for k, v in value.items() if k != "hash"})
    return value


def registry():
    return deepcopy(_active_registry.get() or default_registry())


@contextmanager
def registry_scope(value):
    token = _active_registry.set(validate_registry(deepcopy(value)))
    try:
        yield
    finally:
        _active_registry.reset(token)


def scoped_execution(fn):
    @wraps(fn)
    def call(ex, *args, **kwargs):
        with registry_scope(ex.registry_snapshot):
            return fn(ex, *args, **kwargs)

    return call


def inheritance_paths(key, direction=None, functional_types=None):
    definitions = registry()["definitions"]

    def walk(k):
        parents = definitions[k]["parents"]
        if not parents:
            return [[k]]
        return [path + [k] for p in parents for path in walk(p)]

    paths = walk(key)
    if key.startswith("api.data.") and direction:
        root = (
            "service.base.response_contract"
            if direction == "return"
            else "service.base.request_data"
        )
        paths = [p for p in paths if p[0] == root]
    if functional_types is not None:
        active = set(functional_types)
        paths = [
            path
            for path in paths
            if all(
                definitions[k]["layer"] != "functional"
                or definitions[k]["group"] in active
                or k == "service.resource_mutation.idempotency"
                and bool(active & {"query_retrieval", "update", "delete"})
                for k in path
            )
        ]
        refined = [
            path for path in paths if any(definitions[k]["layer"] == "functional" for k in path)
        ]
        if refined:
            paths = refined
    return paths


def failure_family(key):
    return registry()["definitions"].get(key, {}).get("failure_family", key)


def active_registry_identity(value: dict) -> str:
    """Identify active semantics independently of disabled/audit-only metadata."""
    definitions = {k: v for k, v in value["definitions"].items() if v.get("enabled", True)}

    def profiles(node):
        if isinstance(node, dict):
            return {k: profiles(v) for k, v in node.items()}
        return [key for key in node if key in definitions]

    return fingerprint(
        {
            "version": value["version"],
            "definitions": definitions,
            "profiles": profiles(value["profiles"]),
            "framework_policies": value.get("framework_policies", {}),
        }
    )
