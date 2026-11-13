"""Respect an explicitly typed external flag on the cited component itself."""

import json
from copy import deepcopy


def normalize_externality(value):
    out = deepcopy(value)
    for component in out.get("components", []):
        flags = set()
        for ref in component.get("source_refs", []):
            try:
                fact = json.loads(ref["quote"].strip().removeprefix("- "))
            except (ValueError, TypeError):
                continue
            if (
                isinstance(fact, dict)
                and fact.get("canonical_name") == component["name"]
                and type(fact.get("is_external")) is bool
            ):
                flags.add(fact["is_external"])
        if len(flags) != 1:
            continue
        external = flags.pop()
        current = component["composition_type"]
        if current in {"内部数据库", "外部数据库"}:
            component["composition_type"] = "外部数据库" if external else "内部数据库"
        elif current in {"内部服务", "外部Actor（系统）"}:
            component["composition_type"] = "外部Actor（系统）" if external else "内部服务"
    return out
