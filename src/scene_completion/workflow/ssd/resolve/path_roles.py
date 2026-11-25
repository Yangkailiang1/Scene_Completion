"""Resolve create path roles using only the command and main-success evidence."""

from scene_completion.domain.ssd.path_resources import ROLES, path_parameters

TASK = "ssd-create-path-roles"


def resolve(bundle, semantic):
    commands = {c["id"]: c for c in bundle["commands"]}
    steps = {s["id"]: s for s in bundle["steps"]}
    candidates = []
    for cid, link in bundle["command_bindings"].items():
        command = commands[cid]
        names = path_parameters(command.get("path"))
        if (
            not names
            or "create" not in link["crud"]
            or link.get("binding_source") == "step1_fallback"
        ):
            continue
        candidates.append(
            {
                "command_id": cid,
                "name": command["name"],
                "method": command["method"],
                "path": command["path"],
                "parameters": names,
                "quote": command["quote"],
                "steps": [
                    {
                        "step_id": sid,
                        "operation": steps[sid]["operation"]["name"],
                        "entities": steps[sid]["entity_ids"],
                        "quotes": [r["quote"] for r in steps[sid]["source_refs"] if r.get("quote")],
                    }
                    for sid in dict.fromkeys([link["primary_step_id"], *link["occurrences"]])
                ],
            }
        )
    roles = {}
    if semantic:
        for offset in range(0, len(candidates), 12):
            inputs = {"commands": candidates[offset : offset + 12]}
            result = validate_result(semantic(TASK, inputs), inputs)
            for row in result["parameters"]:
                roles.setdefault(row["command_id"], {})[row["name"]] = {
                    "role": row["role"],
                    "reason": row["reason"],
                }
    bundle["create_path_roles"] = roles


def validate_result(payload, inputs):
    requested = {(c["command_id"], name) for c in inputs["commands"] for name in c["parameters"]}
    rows = payload["parameters"]
    returned = {(row["command_id"], row["name"]) for row in rows}
    if requested != returned or len(returned) != len(rows):
        raise ValueError("必须对当前接口的每个路径参数恰好返回一条角色判定")
    if any(not row["reason"].strip() for row in rows):
        raise ValueError("路径参数的角色判定须保留依据")
    if any(row["role"] not in ROLES for row in rows):
        raise ValueError("路径参数的角色超出已定义范围")
    return payload
