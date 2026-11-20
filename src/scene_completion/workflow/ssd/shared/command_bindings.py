"""Single command placement and entity associations shared across stages."""

import re
from copy import deepcopy

from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, FIRST_CALL_PROFILES
from scene_completion.domain.ssd.construction import (
    ident,
    pending,
)

_HTTP = re.compile(r"\b(GET|HEAD|POST|PUT|PATCH|DELETE)\s+(/[^\s`，。；]+)", re.I)


def _pick(step, commands):
    declared = step.get("api_id") or step.get("declared_command") or step.get("call_command_id")
    text = step["operation"]["name"]
    operation = step["operation"]
    observed = {(m.upper(), p) for m, p in _HTTP.findall(text)}
    if operation.get("http_method") and operation.get("http_path"):
        observed.add((operation["http_method"].upper(), operation["http_path"]))
    if declared:
        command = commands.get(declared)
        if not command:
            return None
        if command["service"] and command["service"] not in {
            step["receiver"]["id"],
            step["receiver"]["name"],
        }:
            return None
        if (
            command["method"]
            and command["path"]
            and observed
            and (command["method"], command["path"]) not in observed
        ):
            return None
        return declared
    direct = [
        cid
        for cid, row in commands.items()
        if (row["method"], row["path"]) in observed
        and (
            not row["service"]
            or row["service"] in {step["receiver"]["id"], step["receiver"]["name"]}
        )
    ]
    if not direct and not observed:
        evidence = " ".join(
            ref.get("quote", "") for ref in step["source_refs"] if ref.get("kind") == "origin"
        )
        direct = [
            cid
            for cid in commands
            if re.search(r"(?<![\w-])" + re.escape(cid) + r"(?![\w-])", evidence)
        ]
    return direct[0] if len(direct) == 1 else None


def attach(bundle, commands, placements=None):
    """Build one obligation owner per command, preserving every call occurrence."""
    steps = sorted(bundle["steps"], key=lambda step: step["order"])
    first_call = bundle.get("analysis_profile") in FIRST_CALL_PROFILES
    primary_only = bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE
    bundle["pending"] = [p for p in bundle["pending"] if not p.get("command_gap")]
    calls = {cid: [] for cid in commands}
    for step in steps:
        step["data"] = []
        operation = step["operation"]
        operation.pop("command_id", None)
        operation.pop("command_ids", None)
        if step["direction"] != "request" or step["kind"] == "action":
            continue
        cid = _pick(step, commands)
        step["api_id"] = cid
        if primary_only:
            step.pop("call_command_id", None)
        if cid:
            calls[cid].append(step)
        elif step.get("declared_command"):
            _gap(
                bundle,
                step["declared_command"],
                "声明接口与 SR 命令或调用双方不一致",
                step["source_refs"],
            )
    bundle["commands"] = deepcopy(list(commands.values()))
    bundle["command_bindings"] = {}
    bundle["operation_hints"] = [
        {k: row[k] for k in ("id", "name", "method", "path", "quote")} for row in commands.values()
    ]
    for cid, command in commands.items():
        occurrences = calls[cid]
        placement = (placements or {}).get(cid)
        if command.get("conflict"):
            _gap(bundle, cid, command["conflict"], command["source_refs"])
        if not occurrences:
            if placement is None:
                _gap(bundle, cid, "功能树命令在主成功流缺少明确的调用步骤", command["source_refs"])
                continue
            occurrences = [next(step for step in steps if step["id"] == placement["step_id"])]
        primary = occurrences[0]
        for step in occurrences:
            if primary_only and step is not primary:
                step["call_command_id"] = cid
                step["api_id"] = None
                continue
            operation = step["operation"]
            if placement is None or placement["binding_source"] != "step1_fallback":
                operation.setdefault("command_id", cid)
                step["api_id"] = step.get("api_id") or cid
                if operation["command_id"] == cid:
                    for key in ("method", "path"):
                        if command[key]:
                            operation["http_" + key] = command[key]
            if placements is not None:
                operation.setdefault("command_ids", []).append(cid)
        fallback = bool(placement and placement["binding_source"] == "step1_fallback")
        validation = [s for s in steps if not fallback and primary["id"] in s.get("validates", [])]
        owner = validation[0] if len(validation) == 1 else primary
        if len(validation) > 1:
            _gap(bundle, cid, "参数校验步骤有歧义", command["source_refs"])
        returns = [
            s
            for s in steps
            if not fallback and s["direction"] == "return" and s.get("parent_id") == primary["id"]
        ]
        bundle["command_bindings"][cid] = {
            "primary_step_id": primary["id"],
            "occurrences": [s["id"] for s in occurrences],
            "validation_step_id": owner["id"] if owner is not primary else None,
            **(
                {k: placement[k] for k in ("binding_source", "reason")}
                if placement
                else {"binding_source": "evidence"}
                if placements is not None
                else {}
            ),
        }
        if first_call:
            occurrence_ids = {s["id"] for s in occurrences}
            validators = [
                s["id"]
                for s in steps
                if not fallback and occurrence_ids.intersection(s.get("validates", []))
            ]
            responses = [
                s["id"]
                for s in steps
                if not fallback
                and s["direction"] == "return"
                and s.get("parent_id") in occurrence_ids
            ]
            bundle["command_bindings"][cid].update(
                validation_step_ids=validators, response_step_ids=responses
            )
        for field in command["fields"]:
            location = field["location"]
            if not location or (
                location == "response" and len(returns) != 1 and placements is None
            ):
                _gap(bundle, cid, "未能唯一定位 SR 字段：" + field["name"], field["source_refs"])
                continue
            target = primary if first_call else returns[0] if location == "response" else owner
            target["data"].append(
                {
                    **deepcopy(field),
                    "id": ident(
                        "command-field", bundle["case"]["id"], cid, location, field["name"]
                    ),
                    "command_id": cid,
                    "call_step_id": primary["id"],
                    "direction": "response" if location == "response" else "request",
                    **(
                        {
                            "validation_step_ids": validators if location != "response" else [],
                            "response_step_ids": responses if location == "response" else [],
                        }
                        if first_call
                        else {}
                    ),
                }
            )


def associate_entities(bundle):
    """Connect commands to evidenced business entities without adding them to source steps."""
    steps = {s["id"]: s for s in bundle["steps"]}
    entities = {e["id"] for e in bundle.get("entities", [])}
    commands = {c["id"]: c for c in bundle["commands"]}
    for cid, link in bundle["command_bindings"].items():
        primary = steps[link["primary_step_id"]]
        related = [
            *link["occurrences"],
            *link.get("validation_step_ids", []),
            *link.get("response_step_ids", []),
        ]
        observed = {e for sid in related for e in steps[sid]["entity_ids"]}
        fields = {
            (f.get("entity_binding") or {}).get("entity_id")
            for f in primary["data"]
            if f["command_id"] == cid
        }
        selected = (observed | fields) & entities
        if not selected and len(commands) == len(entities) == 1:
            selected = entities
        link["entity_ids"] = sorted(selected)
        if not selected:
            choices = sorted(entities)
            _gap(
                bundle,
                cid,
                "接口的操作实体待确认" + (" · " + "、".join(choices) if choices else ""),
                commands[cid]["source_refs"],
            )


def _gap(bundle, cid, reason, refs):
    bundle["pending"].append(
        pending(
            ident("command-gap", cid, reason),
            reason,
            refs,
            command_id=cid,
            command_gap=True,
            reason=reason,
        )
    )
