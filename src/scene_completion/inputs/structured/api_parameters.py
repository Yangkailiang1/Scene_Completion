"""Canonical wire-field paths shared by API artifacts and interaction analysis."""

from copy import deepcopy


def canonical_parameter(parameter):
    out = deepcopy(parameter)
    location = out["location"]
    if location not in {"header", "path", "query", "body", "response"}:
        return out
    aliases = ("header", "head") if location == "header" else (location,)
    # Strip only the location already declared on this exact field. Keep all
    # nested paths (items[].name), other locations and genuinely distinct fields.
    for prefix in aliases:
        token = prefix + "."
        if out["name"].startswith(token) and len(out["name"]) > len(token):
            out["name"] = out["name"][len(token) :]
            break
    return out


def canonical_contract(value):
    from scene_completion.inputs.imports.artifact_adoption import merge

    def parameters(api, rows):
        # Read-only result projections may contain only id/parameters. These
        # merge scaffolds never add metadata to the original API object.
        base = {
            "id": api["id"],
            "name": api.get("name", api["id"]),
            "address": api.get("address"),
            "source_refs": deepcopy(api.get("source_refs", [])),
        }
        base["parameters"] = []
        incoming = {**base, "parameters": [canonical_parameter(p) for p in rows]}
        # Reuse the established evidence-preserving union for duplicate paths.
        return merge("api-parameters", {"apis": [base]}, [{"payload": {"apis": [incoming]}}])[
            "apis"
        ][0]["parameters"]

    out = deepcopy(value)
    for api in out["apis"]:
        api["parameters"] = parameters(api, api["parameters"])
        for response in api.get("responses", []):
            response["parameters"] = parameters(api, response["parameters"])
    return out
