"""Resolve one functional concern owner per interface or external service."""

from scene_completion.domain.ssd.construction import ident, pending, unique
from scene_completion.domain.ssd_contracts import CRUD
from scene_completion.workflow.ssd.shared.command_bindings import associate_entities, attach

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


def resolve(bundle, semantic):
    steps = sorted(bundle["steps"], key=lambda step: step["order"])
    case = bundle["case"]["id"]
    commands = {c["id"]: c for c in bundle["commands"]}
    prior = bundle.get("command_bindings", {})
    by_id = {s["id"]: s for s in steps}
    call_steps = [s for s in steps if _call(s)]
    known_calls = {sid for binding in prior.values() for sid in binding["occurrences"]}
    units, external = [], {}
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
    for step in call_steps:
        if step["id"] in known_calls or not step["receiver"]["external"]:
            continue
        identity = step["receiver"]["id"]
        unit = external.setdefault(
            identity,
            _unit(
                case,
                ("external", identity),
                [],
                kind="external",
                step_id=step["id"],
                name=step["receiver"]["name"],
                service=step["receiver"]["name"],
            ),
        )
        unit["candidates"].append(step["id"])
    units.extend(external.values())

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
        if (
            cid
            and declared
            and (sid in prior.get(cid, {}).get("occurrences", []) or answer.get("step_id"))
        ):
            kinds = step["operation"]["kinds"]
        elif answer:
            kinds = answer["crud"]
        else:
            from scene_completion.workflow.ssd.shared.step_bindings import _kinds

            kinds = (
                _kinds(unit["name"], unit.get("method"))
                if cid
                else [
                    crud
                    for member in unit["candidates"]
                    for crud in by_id[member]["operation"].get("kinds")
                    or _kinds(by_id[member]["operation"]["name"])
                ]
            )
        if not cid:
            kinds = [
                *kinds,
                *[
                    crud
                    for member in unit["candidates"]
                    if by_id[member]["operation"]["kinds_source"] in {"manual", "declared"}
                    for crud in by_id[member]["operation"]["kinds"]
                ],
            ]
        kinds = [kind for kind in CRUD if kind in kinds]
        resolved.append(
            {
                **unit,
                "step_id": sid,
                "crud": kinds,
                "reason": answer.get("reason") or "采用已声明或可直接推导的业务操作",
            }
        )
    attach(bundle, commands, placements)
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
            members = binding["occurrences"]
            refs = commands[cid]["source_refs"]
        else:
            members = [sid for sid in unit["candidates"] if sid not in bound_calls]
            if not members:
                continue
            unit["step_id"] = members[0]
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
        unit.update(
            occurrences=members,
            related_steps=list(dict.fromkeys([*members, *related])),
            receiver_id=by_id[unit["step_id"]]["receiver"]["id"],
            source_refs=unique([*refs, *(r for sid in members for r in by_id[sid]["source_refs"])]),
        )
        unit.pop("candidates")
        result.append(unit)

    by_service = {}
    for unit in result:
        step = by_id[unit["step_id"]]
        if step["receiver"]["external"] and _call(step):
            if (
                unit.get("command_id")
                and bundle["command_bindings"][unit["command_id"]].get("binding_source")
                == "step1_fallback"
            ):
                continue
            by_service.setdefault(unit["receiver_id"], []).append(unit)
    for receiver, members in by_service.items():
        occurrences = {sid for unit in members for sid in unit["occurrences"]}
        calls = [s for s in steps if s["id"] in occurrences]
        first = calls[0]
        owner = next((unit for unit in members if unit["kind"] == "external"), None)
        if owner is None:
            owner = {
                "id": ident("operation-unit", case, "external", receiver),
                "kind": "external",
                "name": first["receiver"]["name"],
                "service": first["receiver"]["name"],
                "receiver_id": receiver,
            }
            result.append(owner)
        for unit in members:
            if unit.get("command_id"):
                unit["functional_owner_id"] = owner["id"]
        owner.update(
            step_id=first["id"],
            occurrences=[s["id"] for s in calls],
            related_steps=list(dict.fromkeys(sid for u in members for sid in u["related_steps"])),
            crud=[kind for kind in CRUD if any(kind in u["crud"] for u in members)],
            reason="；".join(dict.fromkeys(u["reason"] for u in members)),
            source_refs=unique([ref for u in members for ref in u["source_refs"]]),
        )
    _apply_owners(bundle, result)


def _apply_owners(bundle, units):
    from scene_completion.domain.ssd.external_databases import occurrences

    databases = occurrences(bundle["steps"])
    bundle["operation_units"] = units
    associate_entities(bundle)
    for unit in units:
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
        if (
            not unit["crud"]
            and not unit.get("functional_owner_id")
            and unit.get("receiver_id") not in databases
        ):
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
        owners = [u for u in units if u["step_id"] == step["id"]]
        operation = step["operation"]
        operation["kinds"] = [kind for kind in CRUD if any(kind in u["crud"] for u in owners)]
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
