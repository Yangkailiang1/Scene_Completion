"""Group input checks at the interaction level without changing scenario identity."""

from scene_completion.domain.ssd import concern_policy
from scene_completion.domain.ssd.construction import add_concern, ident, unique

VERSION = "interaction-input-types-v1"
KEYS = {
    concern_policy.FIELD,
    concern_policy.PATH_CHARACTERS,
    *(
        "api.data." + name
        for name in ("completeness", "type", "format", "length", "size", "range", "validity")
    ),
}


def applies(bundle):
    return bundle.get("input_concern_policy") == VERSION


def eligible(record):
    return (
        record.get("key") in KEYS
        and record.get("target") in {"data", "receiver"}
        and record.get("status") == "active"
        and record.get("step_id")
        and not record.get("resource_reference")
    )


def group_id(bundle, channel, step_id, key):
    return ident("input-concern", bundle["case"]["id"], channel, step_id, key)


def add_group(bundle, channel, step, key, refs):
    """Record a verified type match even when no exact scenario is confirmed."""
    output = bundle["channels"][channel]
    ident_ = group_id(bundle, channel, step["id"], key)
    for row in output["concerns"]:
        if row["id"] == ident_:
            row["source_refs"] = unique(row["source_refs"] + list(refs))
            return row
    temporary = {"concerns": []}
    row = add_concern(temporary, bundle, channel, step, key, "data", refs=refs)
    if row:
        row.update(id=ident_, input_group=True)
        output["concerns"].append(row)
    return row


def group_channel(bundle, channel, output):
    """Keep source references and stable scene IDs while replacing fine parents."""
    if not applies(bundle):
        return {}
    remapped, groups, result = {}, {}, []
    for row in output.get("concerns", []):
        if not eligible(row):
            result.append(row)
            continue
        step_id, key = row["step_id"], row["key"]
        target_id = group_id(bundle, channel, step_id, key)
        remapped[row["id"]] = target_id
        group = groups.get(target_id)
        if group is None:
            group = {
                "id": target_id,
                "step_id": step_id,
                "target": "data",
                "key": key,
                "label": row.get("label") or key,
                "condition": row.get("label") or key,
                "status": "active",
                "input_group": True,
                "source_refs": [],
                "field_id": None,
                "entity_id": None,
            }
            groups[target_id] = group
            result.append(group)
        if row.get("input_group") and row["id"] == target_id:
            # A reviewer may edit a group label, explanation, or evidence.
            group.update(
                {
                    key: row[key]
                    for key in ("label", "condition", "analysis", "origin", "display_row_id")
                    if key in row
                }
            )
        group["source_refs"] = unique(group["source_refs"] + row.get("source_refs", []))
    output["concerns"] = result
    for scene in output.get("scenarios", []):
        scene["concern_ids"] = list(
            dict.fromkeys(remapped.get(parent, parent) for parent in scene.get("concern_ids", []))
        )
        if scene.get("status") == "active" and any(
            parent in groups and groups[parent]["step_id"] != scene.get("step_id")
            for parent in scene["concern_ids"]
        ):
            scene.update(
                status="unbound",
                binding_issue="场景应关联同一主挂载交互的数据关注点",
            )
    return remapped


def group_bundle(bundle, pairs):
    if not applies(bundle):
        return
    aliases = {
        name: group_channel(bundle, name, channel) for name, channel in bundle["channels"].items()
    }
    for decision in bundle.get("decisions", []):
        if decision.get("level") == "concern" and decision.get("pair") in pairs:
            left, right = pairs[decision["pair"]]
            for side, channel in (("left_id", left), ("right_id", right)):
                ident_ = decision.get(side)
                if ident_ in aliases[channel]:
                    decision[side] = aliases[channel][ident_]
