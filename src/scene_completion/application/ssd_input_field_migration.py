"""Rebase saved review overrides when SR fields stop using transport locations."""

from collections import defaultdict

from scene_completion.domain.ssd.interface_fields import field_name, legacy_name

IDENTITIES = {"id", "field_id", "left_id", "right_id", "concern_ids", "aligned_concern_ids"}


def _pairs(old, new, old_key, new_key):
    previous, current = defaultdict(list), defaultdict(list)
    for row in old:
        previous[old_key(row)].append(row["id"])
    for row in new:
        current[new_key(row)].append(row["id"])
    return {
        ids[0]: current[key][0]
        for key, ids in previous.items()
        if key is not None and len(ids) == len(current[key]) == 1
    }


def _fields(bundle):
    return [f for step in bundle["steps"] for f in step["data"] if f.get("command_id")]


def rebase(previous, baseline, overrides):
    old_fields = _fields(previous)
    new_fields = [field for field in _fields(baseline) if not field.get("conflicts")]
    rename = _pairs(
        old_fields,
        new_fields,
        lambda row: (row["command_id"], legacy_name(row["name"])),
        lambda row: (row["command_id"], legacy_name(row["name"])),
    )
    old_field_ids = {f["id"] for f in old_fields}

    def record_key(row, kind, old=False):
        field = row.get("field_id")
        if old and field in old_field_ids:
            field = rename.get(field)
            if field is None:
                return None
        if not field:
            return None
        return (
            field,
            row.get("target"),
            row.get("key"),
            *(
                (field_name(row.get("condition")), field_name(row.get("expected")))
                if kind == "scenarios"
                else ()
            ),
        )

    for channel in ("E", "G", "GT"):
        for kind in ("concerns", "scenarios"):
            rename.update(
                _pairs(
                    previous["channels"][channel][kind],
                    baseline["channels"][channel][kind],
                    lambda row: record_key(row, kind, old=True),
                    lambda row: record_key(row, kind),
                )
            )

    def rewrite(value, identity=False, field_list=False, field_row=False):
        if isinstance(value, str):
            return rename.get(value, value) if identity else value
        if isinstance(value, list):
            return [rewrite(item, identity, field_row=field_list) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, current in value.items():
            if (field_row or value.get("id") in old_field_ids) and key in {"location", "direction"}:
                continue
            if key == "$records":
                result[key] = {
                    rename.get(ident, ident): rewrite(
                        row, field_row=field_list and ident in old_field_ids
                    )
                    for ident, row in current.items()
                }
            elif key == "replace":
                result[key] = rewrite(current, identity, field_list, field_row)
            else:
                result[key] = rewrite(current, key in IDENTITIES or key == "$order", key == "data")
        return result

    return rewrite(overrides)
