"""Carry saved edits across unambiguous resource-obligation identity changes."""

from collections import Counter

from scene_completion.application.ssd_input_field_migration import rewrite_overrides
from scene_completion.domain.ssd import path_resources as paths


def _equivalent(old, new, fields, *, scenario):
    if not paths.is_existence(new["key"]):
        return False
    ref = new.get("resource_reference")
    if old.get("key") == paths.VALIDITY:
        field = fields.get(old.get("field_id"), {})
        if not ref or (field.get("command_id"), field.get("wire_name") or field.get("name")) != (
            ref["command_id"],
            ref["parameter_name"],
        ):
            return False
    elif (
        not paths.is_existence(old["key"])
        or new["key"] not in {old["key"], *old.get("concern_keys", [])}
        or old.get("operation_unit_id") != new.get("operation_unit_id")
        or old.get("resource_reference")
        and paths.identity(old) != paths.identity(new)
        or ref
        and not old.get("resource_reference")
        and not paths.mentions(ref["parameter_name"], old.get("condition"))
    ):
        return False
    if not scenario:
        return True
    old_failure = old.get("resource_failure") or paths.failure(old.get("condition"))
    if not old_failure and old["key"] == paths.VALIDITY:
        possible = set()
        for ref in old.get("source_refs", []):
            quote = ref.get("quote") or (ref.get("origin") or {}).get("quote")
            possible.update(paths.atom_failures({"concern_key": paths.VALIDITY, "value": quote}))
        if len(possible) == 1:
            old_failure = next(iter(possible))
    if old_failure != (new.get("resource_failure") or paths.failure(new.get("condition"))):
        return False
    sources = set(old.get("source_record_ids", []))
    return not sources or sources == set(new.get("source_record_ids", []))


def rebase(previous, baseline, overrides):
    fields = {field["id"]: field for step in previous["steps"] for field in step["data"]}
    rename = {}
    for channel, old in previous["channels"].items():
        current = baseline["channels"][channel]
        for kind in ("concerns", "scenarios"):
            active = {row["id"]: row for row in current[kind] if row["status"] == "active"}
            unchanged = {row["id"] for row in old[kind]} & active.keys()
            candidates = {
                row["id"]: [
                    new_id
                    for new_id, candidate in active.items()
                    if new_id not in unchanged
                    and _equivalent(row, candidate, fields, scenario=kind == "scenarios")
                ]
                for row in old[kind]
                if row["id"] not in active
            }
            incoming = Counter(hit for hits in candidates.values() for hit in hits)
            rename.update(
                {
                    old_id: hits[0]
                    for old_id, hits in candidates.items()
                    if len(hits) == 1 and incoming[hits[0]] == 1
                }
            )
    return rewrite_overrides(overrides, rename)
