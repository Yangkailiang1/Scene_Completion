"""Resolve actual calls and select the first occurrence of each external CRUD."""

from scene_completion.domain.ssd.construction import ident, pending, unique
from scene_completion.domain.ssd_contracts import CRUD
from scene_completion.workflow.ssd.shared.command_bindings import associate_entities, attach
from scene_completion.workflow.ssd.shared.step_bindings import _kinds

TASK = "ssd-operation-units"


def _call(step):
    return (
        step["direction"] == "request"
        and step["kind"] != "action"
        and step["sender"]["id"] != step["receiver"]["id"]
        and step["receiver"]["type"] == "service"
    )


def _notes(step):
    return {
        "id": step["id"],
        "order": step["order"],
        "kind": step["kind"],
        "direction": step["direction"],
        "sender": step["sender"]["name"],
        "receiver": step["receiver"]["name"],
        "receiver_id": step["receiver"]["id"],
        "external": step["receiver"]["external"],
        "operation": step["operation"]["name"],
        "crud": step["operation"].get("kinds", []),
        "entities": step["entity_ids"],
        "source_quotes": [r["quote"] for r in step["source_refs"] if r.get("quote")],
    }


def _unit(case, identity, candidates, **values):
    return {"id": ident("operation-unit", case, *identity), "candidates": candidates, **values}


def _external_call(case, step):
    receiver = step["receiver"]
    return _unit(
        case,
        ("external-call", receiver["id"], step["id"]),
        [step["id"]],
        kind="external",
        step_id=step["id"],
        name=receiver["name"],
        service=receiver["name"],
    )


def _ordered_crud(kinds):
    return [kind for kind in CRUD if kind in kinds]


def resolve(bundle, semantic):
    steps = sorted(bundle["steps"], key=lambda step: step["order"])
    case = bundle["case"]["id"]
    commands = {c["id"]: c for c in bundle["commands"]}
    prior = bundle.get("command_bindings", {})
    by_id = {s["id"]: s for s in steps}
    call_steps = [s for s in steps if _call(s)]
    known_calls = {sid for binding in prior.values() for sid in binding["occurrences"]}
    units = []
    for cid, contract in commands.items():
        owner = prior.get(cid, {}).get("primary_step_id")
        candidates = [
            s["id"]
            for s in call_steps
            if (
                not contract["service"]
                or contract["service"] in {s["receiver"]["id"], s["receiver"]["name"]}
            )
            and (s["id"] not in known_calls or s["id"] == owner)
        ]
        units.append(
            _unit(
                case,
                ("command", cid),
                [owner] if owner else candidates,
                kind="interface",
                command_id=cid,
                step_id=owner,
                name=contract["name"],
                method=contract["method"],
                path=contract["path"],
                quote=contract["quote"],
                service=contract["service"],
            )
        )
    units.extend(
        _external_call(case, step)
        for step in call_steps
        if step["id"] not in known_calls and step["receiver"]["external"]
    )

    answers = {}
    for offset in range(0, len(units), 20):
        batch = units[offset : offset + 20]
        if semantic:
            result = semantic(
                TASK, {"case": bundle["case"], "steps": [_notes(s) for s in steps], "units": batch}
            )
            answers.update({r["unit_id"]: r for r in result["operations"]})
    placements, resolved = {}, []
    for unit in units:
        cid = unit.get("command_id")
        answer = answers.get(unit["id"], {})
        sid = unit["step_id"] or answer.get("step_id") or steps[0]["id"]
        step = by_id[sid]
        if not unit["step_id"]:
            placements[cid] = {
                "step_id": sid,
                "binding_source": "semantic" if answer.get("step_id") else "step1_fallback",
                "reason": answer.get("reason") or "缺少唯一调用依据，按约定挂到主成功流首步",
            }
        declared = step["operation"].get("kinds_source") in {"declared", "manual"}
        if declared and (
            not cid or sid in prior.get(cid, {}).get("occurrences", []) or answer.get("step_id")
        ):
            kinds = step["operation"]["kinds"]
        elif answer:
            kinds = answer["crud"]
        else:
            kinds = (
                _kinds(unit["name"], unit.get("method"))
                if cid
                else step["operation"].get("kinds") or _kinds(step["operation"]["name"])
            )
        resolved.append(
            {
                **unit,
                "step_id": sid,
                "crud": _ordered_crud(kinds),
                "reason": answer.get("reason") or "采用已声明或可直接推导的业务操作",
            }
        )
    attach(bundle, commands, placements)
    _publish_call_units(bundle, resolved)


def _publish_call_units(bundle, resolved):
    steps = sorted(bundle["steps"], key=lambda step: step["order"])
    by_id = {s["id"]: s for s in steps}
    commands = {c["id"]: c for c in bundle["commands"]}
    # An interface established by the model takes precedence over an inferred interface-less unit.
    bound_calls = {
        sid
        for binding in bundle["command_bindings"].values()
        if binding.get("binding_source") != "step1_fallback"
        for sid in binding["occurrences"]
    }
    result = []
    for unit in resolved:
        cid = unit.get("command_id")
        if cid:
            binding = bundle["command_bindings"][cid]
            unit["step_id"] = binding["primary_step_id"]
            members = binding["occurrences"]
            refs = commands[cid]["source_refs"]
        else:
            if unit["step_id"] in bound_calls:
                continue
            members = [unit["step_id"]]
            refs = []
        related = (
            [*binding.get("validation_step_ids", []), *binding.get("response_step_ids", [])]
            if cid
            else [
                s["id"]
                for s in steps
                if set(members).intersection(s.get("validates", []))
                or s.get("parent_id") in members
            ]
        )
        result.append(
            dict(
                unit,
                occurrences=members,
                related_steps=list(dict.fromkeys([*members, *related])),
                receiver_id=by_id[unit["step_id"]]["receiver"]["id"],
                source_refs=unique(
                    [*refs, *(r for sid in members for r in by_id[sid]["source_refs"])]
                ),
            )
        )

    bundle["operation_call_units"] = [
        {k: v for k, v in unit.items() if k != "candidates"} for unit in result
    ]
    _apply_owners(bundle, _external_owners(bundle, bundle["operation_call_units"], by_id))


def _external_owners(bundle, call_units, steps):
    by_service = {}
    for unit in call_units:
        step = steps[unit["step_id"]]
        link = bundle["command_bindings"].get(unit.get("command_id"), {})
        if (
            unit["crud"]
            and step["receiver"]["external"]
            and _call(step)
            and link.get("binding_source") != "step1_fallback"
        ):
            by_service.setdefault(unit["receiver_id"], []).append(unit)
    owners, redirects = [], {}
    for receiver, members in by_service.items():
        per_operation = {}
        for kind in CRUD:
            calls = tuple(unit["id"] for unit in members if kind in unit["crud"])
            if calls:
                per_operation.setdefault(calls, []).append(kind)
        for call_ids, kinds in per_operation.items():
            sources = [unit for unit in members if unit["id"] in call_ids]
            occurrences = sorted(
                {sid for unit in sources for sid in unit["occurrences"]},
                key=lambda sid: steps[sid]["order"],
            )
            first = steps[occurrences[0]]
            owner_id = ident(
                "operation-unit", bundle["case"]["id"], "external-crud", receiver, kinds
            )
            owners.append(
                {
                    "id": owner_id,
                    "kind": "external",
                    "name": first["receiver"]["name"],
                    "service": first["receiver"]["name"],
                    "receiver_id": receiver,
                    "step_id": first["id"],
                    "occurrences": occurrences,
                    "related_steps": list(
                        dict.fromkeys(sid for u in sources for sid in u["related_steps"])
                    ),
                    "crud": kinds,
                    "reason": "；".join(dict.fromkeys(u["reason"] for u in sources)),
                    "source_refs": unique([ref for u in sources for ref in u["source_refs"]]),
                    "command_ids": sorted(
                        {u["command_id"] for u in sources if u.get("command_id")}
                    ),
                    "external_crud_owner": True,
                }
            )
            for unit_id in call_ids:
                redirects.setdefault(unit_id, []).append(owner_id)
    return [
        {**u, **({"functional_owner_ids": redirects[u["id"]]} if u["id"] in redirects else {})}
        for u in call_units
        if u.get("command_id") or u["id"] not in redirects
    ] + owners


def functional_owner(unit):
    return not (unit.get("functional_owner_id") or unit.get("functional_owner_ids"))


def in_operation_scope(unit, actual, command_id=None):
    if not unit.get("external_crud_owner"):
        return True
    if actual:
        return actual in unit["related_steps"]
    return not command_id or command_id in unit["command_ids"]


def _apply_owners(bundle, units):
    from scene_completion.domain.ssd.external_databases import occurrences

    databases = occurrences(bundle["steps"])
    bundle["operation_units"] = units
    associate_entities(bundle)
    call_units = bundle.get("operation_call_units", units)
    for unit in call_units:
        if cid := unit.get("command_id"):
            link = bundle["command_bindings"][cid]
            link["crud"] = unit["crud"]
            if link.get("binding_source") == "step1_fallback":
                bundle["pending"].append(
                    pending(
                        ident("operation-step-fallback", unit["id"]),
                        "接口主挂载步待确认",
                        unit["source_refs"],
                        step_id=unit["step_id"],
                        reason=link["reason"],
                        command_gap=True,
                    )
                )
        if not unit["crud"] and functional_owner(unit) and unit.get("receiver_id") not in databases:
            bundle["pending"].append(
                pending(
                    ident("operation-pending", unit["id"]),
                    "实际 CRUD 待确认",
                    unit["source_refs"],
                    step_id=unit["step_id"],
                    reason=unit["reason"],
                    command_gap=True,
                )
            )
    for step in bundle["steps"]:
        owners = [u for u in call_units if u["step_id"] == step["id"]]
        operation = step["operation"]
        operation["kinds"] = _ordered_crud({kind for u in owners for kind in u["crud"]})
        if not owners or operation.get("kinds_source") not in {"declared", "manual"}:
            operation["kinds_source"] = (
                "semantic" if operation["kinds"] else "pending" if owners else "none"
            )


def rebind(bundle, previous):
    """Keep accepted model mounts on unchanged steps during ordinary edits."""
    steps = {s["id"]: s for s in bundle["steps"]}
    previous_steps = {s["id"]: s for s in previous["steps"]}
    commands = {c["id"]: c for c in bundle["commands"]}
    placements = {}
    for cid, link in previous.get("command_bindings", {}).items():
        sid = link["primary_step_id"]
        origin = link.get("binding_source")
        if cid not in commands or sid not in steps or origin not in {"semantic", "step1_fallback"}:
            continue
        if any(
            steps[sid].get(key) != previous_steps.get(sid, {}).get(key)
            for key in ("api_id", "sender", "receiver", "direction")
        ):
            continue
        placements[cid] = {
            "step_id": sid,
            "binding_source": origin,
            "reason": link.get("reason", ""),
        }
    attach(bundle, commands, placements)
    if "operation_call_units" in bundle:
        _rebind_calls(bundle, previous_steps, commands)
        return
    kept = []
    for unit in bundle["operation_units"]:
        sid = unit["step_id"]
        cid = unit.get("command_id")
        if not cid:
            members = [
                step["id"]
                for step in bundle["steps"]
                if step["id"] in unit["occurrences"]
                and _call(step)
                and step["receiver"]["id"] == unit["receiver_id"]
                and step["receiver"]["external"]
            ]
            if not members:
                continue
            unit.update(step_id=members[0], occurrences=members)
            sid = members[0]
        if sid not in steps or (
            cid and bundle["command_bindings"].get(cid, {}).get("primary_step_id") != sid
        ):
            continue
        op = steps[sid]["operation"]
        if op.get("kinds_source") == "manual":
            unit["crud"] = op["kinds"]
        unit["occurrences"] = [member for member in unit["occurrences"] if member in steps]
        unit["related_steps"] = [member for member in unit["related_steps"] if member in steps]
        kept.append(unit)
    available = {unit["id"] for unit in kept}
    for unit in kept:
        if unit.get("functional_owner_id") not in available:
            unit.pop("functional_owner_id", None)
    _apply_owners(bundle, kept)


def _rebind_calls(bundle, previous_steps, commands):
    previous = {
        (unit.get("command_id"), None if unit.get("command_id") else unit["step_id"]): unit
        for unit in bundle["operation_call_units"]
    }
    steps = {step["id"]: step for step in bundle["steps"]}
    resolved = []
    for cid, link in bundle["command_bindings"].items():
        sid = link["primary_step_id"]
        operation = steps[sid]["operation"]
        unit = previous.get((cid, None))
        contract = commands[cid]
        if unit is None:
            unit = _unit(
                bundle["case"]["id"],
                ("command", cid),
                [sid],
                kind="interface",
                command_id=cid,
                name=contract["name"],
                reason="依据接口声明重新定位",
                crud=_ordered_crud(_kinds(contract["name"], contract["method"])),
            )
        kinds = operation["kinds"] if operation.get("kinds_source") == "manual" else unit["crud"]
        resolved.append({**unit, "step_id": sid, "crud": _ordered_crud(kinds)})
    for sid, step in steps.items():
        if not _call(step) or not step["receiver"]["external"]:
            continue
        operation = step["operation"]
        unit = previous.get((None, sid), {})
        if operation.get("kinds_source") in {"manual", "declared"}:
            kinds = operation["kinds"]
        elif (
            unit.get("receiver_id") == step["receiver"]["id"]
            and operation["name"] == previous_steps[sid]["operation"]["name"]
        ):
            kinds = unit["crud"]
        else:
            kinds = _kinds(operation["name"], operation.get("http_method"))
        resolved.append(
            {
                **_external_call(bundle["case"]["id"], step),
                "crud": _ordered_crud(kinds),
                "reason": unit.get("reason") or "依据当前调用重新定位",
            }
        )
    _publish_call_units(bundle, resolved)


def validate_result(payload, inputs):
    units = {u["id"]: u for u in inputs["units"]}
    answers = {row["unit_id"]: row for row in payload["operations"]}
    if set(units) != set(answers) or len(answers) != len(payload["operations"]):
        raise ValueError("每个接口或外部服务操作必须恰好有一条判定")
    for uid, answer in answers.items():
        unit = units[uid]
        step = answer["step_id"]
        if step is not None and (
            step not in unit["candidates"] or (unit["step_id"] and step != unit["step_id"])
        ):
            raise ValueError("接口只能挂载到本批该接口的候选交互")
        if not answer["reason"].strip() or len(set(answer["crud"])) != len(answer["crud"]):
            raise ValueError("CRUD 判定必须包含依据且操作不得重复")
    return payload


def functional(key):
    return key.startswith(("service.crud.", "service.query_retrieval."))


def functional_family(key):
    return key.rsplit(".", 1)[-1] if functional(key) else key
