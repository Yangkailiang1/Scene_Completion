"""One machine identity for API maps, indexes and parameter work items.

Declared document identifiers are provenance metadata. They must never replace
the machine ID when a producer adds a layer/boundary namespace.
"""

import json
from copy import deepcopy

PLACEHOLDERS = {
    "pending",
    "unknown",
    "null",
    "none",
    "tbd",
    "todo",
    "n/a",
    "na",
    "undefined",
    "待确认",
    "待定",
    "未知",
    "未指定",
    "未提供",
}


class ApiIdentityError(ValueError):
    def __init__(self, category, path, **detail):
        self.identity_details = {"category": category, "path": path, **detail}
        super().__init__(
            "API identity contract: " + json.dumps(self.identity_details, ensure_ascii=False)
        )


def checked_identifier(value, path):
    if not isinstance(value, str) or not value.strip():
        raise ApiIdentityError("invalid_identifier", path, received=value)
    word = value.strip().strip("[]{}()<>【】（）'\"` \t\r\n:;，。；")
    if word.casefold() in PLACEHOLDERS:
        raise ApiIdentityError(
            "placeholder_identifier",
            path,
            received=value,
            instruction="Use the evidenced API ID or a stable local ID; omit unknown optional metadata, never pending/null/TBD.",
        )
    if value != value.strip():
        raise ApiIdentityError("identifier_whitespace", path, received=value)
    return value


def identity_parts(identifier, path="/id"):
    identifier = checked_identifier(identifier, path)
    layer, boundary, base = None, None, identifier
    if identifier.startswith(("RR::", "SR::")):
        layer, base = identifier.split("::", 1)
        if base.startswith("external::"):
            boundary, base = "external", base[len("external::") :]
        if base.startswith(("RR::", "SR::")):
            raise ApiIdentityError("repeated_namespace", path, received=identifier)
        checked_identifier(base, path)
    return layer, boundary, base


def qualified_identity(api, layer, boundary=None):
    old_layer, old_boundary, base = identity_parts(api.get("id"))
    if old_layer and old_layer != layer:
        raise ApiIdentityError(
            "namespace_layer_conflict", "/id", received=api["id"], expected_layer=layer
        )
    if old_boundary and boundary == "system":
        raise ApiIdentityError("namespace_boundary_conflict", "/id", received=api["id"])
    scope = boundary or api.get("interface_scope") or old_boundary
    identifier = layer + "::" + ("external::" if scope == "external" else "") + base
    # A defensive merge derives missing/placeholder metadata from the known
    # machine ID; it never renames an interface to a model's placeholder.
    declared = api.get("declared_id")
    try:
        checked_identifier(declared, "/declared_id")
    except ApiIdentityError:
        declared = base
    return identifier, declared


def validate_mapping_identifiers(mapping):
    seen = set()
    for s, service in enumerate(mapping.get("services", [])):
        for n, api in enumerate(service.get("interfaces", [])):
            path = f"/services/{s}/interfaces/{n}"
            layer, boundary, _ = identity_parts(api.get("id"), path + "/id")
            if api["id"] in seen:
                raise ApiIdentityError("duplicate_identifier", path + "/id", received=api["id"])
            seen.add(api["id"])
            if "declared_id" in api:
                checked_identifier(api["declared_id"], path + "/declared_id")
            if layer and api.get("source_layer", layer) != layer:
                raise ApiIdentityError(
                    "namespace_layer_conflict",
                    path + "/source_layer",
                    received=api.get("source_layer"),
                    expected_layer=layer,
                )
            if boundary and api.get("interface_scope", boundary) != boundary:
                raise ApiIdentityError(
                    "namespace_boundary_conflict",
                    path + "/interface_scope",
                    received=api.get("interface_scope"),
                )


def mapping_model_schema(schema):
    """The model names interfaces; tools own layer/display metadata."""
    out = deepcopy(schema)
    interface = out["properties"]["services"]["items"]["properties"]["interfaces"]["items"]
    for key in ("declared_id", "source_layer", "interface_scope"):
        interface["properties"].pop(key, None)
        if key in interface.get("required", []):
            interface["required"].remove(key)
    return out


def mapping_model_candidate(candidate):
    out = deepcopy(candidate)
    if not isinstance(out, dict):
        return out
    for service in out.get("services", []):
        if not isinstance(service, dict):
            continue
        for api in service.get("interfaces", []):
            if isinstance(api, dict):
                for key in ("declared_id", "source_layer", "interface_scope"):
                    api.pop(key, None)
    return out


def mapping_lookup(mapping, index):
    validate_mapping_identifiers(mapping)
    interfaces = {a["id"]: a for s in mapping["services"] for a in s["interfaces"]}
    indexed = []
    for n, api in enumerate(index["apis"]):
        identity_parts(api["id"], f"/apis/{n}/id")
        indexed.append(api["id"])
    if len(indexed) != len(set(indexed)):
        raise ApiIdentityError("duplicate_index_identifier", "/apis", received=indexed)
    missing, omitted = set(indexed) - interfaces.keys(), interfaces.keys() - set(indexed)
    if missing or omitted:
        raise ApiIdentityError(
            "mapping_index_mismatch",
            "/apis",
            missing_in_mapping=sorted(missing),
            missing_in_index=sorted(omitted),
            instruction="Rebuild derived mapping/index from the same canonical interface IDs; do not edit formal artifacts or match IDs by case/path similarity.",
        )
    return interfaces
