"""Current concern definitions and project-scoped inheritance DAG."""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import lru_cache, wraps
from pathlib import Path

from scene_completion.infrastructure.identity import fingerprint

SCOPES = {
    "interaction": "交互级关注点",
    "business_chain": "业务链路关注点",
    "architecture": "项目架构关注点",
}


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
        if "scope" in d and d["scope"] not in SCOPES:
            raise ValueError("unknown concern scope: " + str(d["scope"]))
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
    from scene_completion.domain.concern_templates import reference_catalog
    from scene_completion.domain.current_scope import current_registry

    value = current_registry(value)
    value["reference_templates"] = reference_catalog()
    value["scopes"] = {"interaction": SCOPES["interaction"]}
    value["hash"] = fingerprint({k: v for k, v in value.items() if k != "hash"})
    return value


def registry():
    return deepcopy(_active_registry.get() or default_registry())


def upgrade_registry(value):
    """Explicit adoption of current built-ins, retaining project-owned keys.

    Callers must save this as a reviewed revision; reading a pinned snapshot
    never calls this function or changes archived definitions.
    """
    result = default_registry()
    for key, definition in value.get("definitions", {}).items():
        if key not in result["definitions"]:
            custom = deepcopy(definition)
            custom.setdefault(
                "scope", "business_chain" if custom.get("layer") == "global" else "interaction"
            )
            result["definitions"][key] = custom
    result["hash"] = fingerprint({k: v for k, v in result.items() if k != "hash"})
    return result


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
            "reference_templates": value.get("reference_templates", {}),
        }
    )
