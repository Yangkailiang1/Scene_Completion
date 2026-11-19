"""Resolve a source's use case without treating supplier IDs as shared IDs."""

import unicodedata


def normalized(value):
    return unicodedata.normalize("NFKC", str(value or "")).strip().casefold()


def candidates(rows, name, entity=None, *, explicit_id=None):
    if explicit_id:
        return [
            (i, row)
            for i, row in enumerate(rows)
            if explicit_id == (row.get("functionId") or row.get("ucId") or row.get("id"))
        ]
    hits = [
        (i, row)
        for i, row in enumerate(rows)
        if normalized(name) and normalized(name) == normalized(row.get("name"))
    ]
    if len(hits) > 1 and entity:
        scoped = [(i, row) for i, row in hits if normalized(entity) in entity_names(row)]
        if scoped:
            return scoped
    return hits


def entity_names(row):
    declared = [row.get(key) for key in ("entity", "resource", "entity_name")]
    for layer in ("rrLayer", "srLayer"):
        declared += [
            entry.get("entity") or entry.get("name")
            for entry in (row.get(layer) or {}).get("entities", [])
        ]
    return {normalized(name) for name in declared if isinstance(name, str)}
