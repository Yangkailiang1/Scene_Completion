"""Evidence-bound atomic step plans; raw imported definitions remain unchanged."""

import json
import re
from collections import defaultdict
from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint

VERSION = "atomic-check-call-return-v3-evidenced-aliases"


def register():
    from scene_completion.domain.contracts import (
        ENRICHED_INTERACTION,
        INPUT_KEYS,
        INTERACTION,
        NULL_S,
        REFS,
        SCHEMAS,
        TASKS,
        S,
        arr,
        enum,
        obj,
    )

    SCHEMAS["interaction-normalize"] = obj(
        steps=arr(
            obj(
                key=S,
                origin_ids=arr(S),
                kind=enum("action", "request", "return"),
                layer=enum("RR", "SR"),
                sender=S,
                receiver=S,
                operation=S,
                request_ref=NULL_S,
                validates=arr(S),
                source_refs=REFS,
            )
        ),
        pending=arr(obj(interaction_id=S, reason=S, source_refs=REFS)),
    )
    TASKS["interaction-normalize"] = ("scene-interaction-normalize", "交互最小步骤规范化")
    INPUT_KEYS["interaction-normalize"] = {
        "candidate",
        "normal-documents",
        "components",
        "case-group",
    }
    for contract in (INTERACTION, ENRICHED_INTERACTION):
        contract["properties"].update(
            source_step_ids=arr(S),
            validates=arr(S),
            execution_order={"type": "integer", "minimum": 1},
        )
    SCHEMAS["fused-ssd"]["properties"]["normalization"] = {"type": "object"}


def compact(value):
    return {
        "interactions": [
            {
                k: deepcopy(i[k])
                for k in (
                    "id",
                    "layer",
                    "step_kind",
                    "direction",
                    "parent_id",
                    "api_id",
                    "source_refs",
                    "sender",
                    "receiver",
                    "operation",
                )
                if k in i
            }
            for i in value["interactions"]
        ],
        "rr_sr_links": value.get("rr_sr_links", []),
    }


def validate_plan(value, inputs):
    source = {i["id"]: i for i in inputs["candidate"]["interactions"]}
    keys = {s["key"] for s in value["steps"]}
    if len(keys) != len(value["steps"]) or not keys:
        raise ValueError("atomic plan needs unique, nonempty step keys")
    names = {p["name"] for i in source.values() for p in (i["sender"], i["receiver"])}
    positions = {s["key"]: n for n, s in enumerate(value["steps"])}
    aliases = defaultdict(set)
    for iid, row in source.items():
        aliases[iid].add(iid)
        for ref in row.get("source_refs", []):
            try:
                node = json.loads(ref["quote"]).get("node", {})
            except (ValueError, AttributeError):
                continue
            if isinstance(node, dict) and isinstance(node.get("id"), str):
                aliases[node["id"]].add(iid)
    for step in value["steps"]:
        resolved = []
        for origin in step["origin_ids"]:
            candidates = aliases.get(origin, set())
            if len(candidates) != 1:
                raise ValueError(
                    "original step ID is unknown or ambiguous: "
                    + origin
                    + "; use "
                    + str(sorted(source))
                )
            resolved.append(next(iter(candidates)))
        step["origin_ids"] = list(dict.fromkeys(resolved))
        if not step["origin_ids"] and (step["kind"] != "action" or not step["source_refs"]):
            raise ValueError(
                "a new local check needs its own positive evidence; messages need original IDs"
            )
        if step["sender"] not in names or step["receiver"] not in names:
            raise ValueError("normalization cannot invent participants")
        if (step["kind"] == "action") != (step["sender"] == step["receiver"]):
            raise ValueError("local checks are self actions; calls/returns need distinct endpoints")
        if not set(step["validates"]) <= keys:
            raise ValueError("check references must use actual normalized step keys")
        if any(positions[k] >= positions[step["key"]] for k in step["validates"]):
            raise ValueError("local validation must follow its actual request or response")
        if step["kind"] != "action" and step["validates"]:
            raise ValueError("only local checks can reference validated messages")
        if step["kind"] == "return":
            request = next((s for s in value["steps"] if s["key"] == step["request_ref"]), None)
            if (
                not request
                or request["kind"] != "request"
                or request["layer"] != step["layer"]
                or (request["sender"], request["receiver"]) != (step["receiver"], step["sender"])
                or positions[request["key"]] >= positions[step["key"]]
            ):
                raise ValueError("return must follow and reverse its actual same-layer request")
        elif step["request_ref"] is not None:
            raise ValueError("only returns have request_ref")
        if step["kind"] == "action":
            # Detect an explicit outbound operation to a known other party.
            for name in names - {step["sender"]}:
                if any(
                    x in step["operation"]
                    for x in ("向" + name + "返回", "向" + name + "发送", "调用" + name)
                ):
                    raise ValueError(
                        "self action contains a separate outbound call/return; split it"
                    )
    for iid, original in source.items():
        if original["direction"] != "return" or not re.search(
            r"执行原子操作|执行原子事务|本地(?:校验|检查|执行)", original["operation"]["name"]
        ):
            continue
        executor = original["sender"]["name"]
        if not any(
            s["kind"] == "action" and s["sender"] == executor and iid in s["origin_ids"]
            for s in value["steps"]
        ):
            raise ValueError(
                "a return contains explicit local execution; retain a separate self action by "
                + executor
                + " from original step "
                + iid
                + "; renaming the return does not account for that execution"
            )
    covered = {i for s in value["steps"] for i in s["origin_ids"]}
    unresolved = {p["interaction_id"] for p in value["pending"]}
    if set(source) - covered - unresolved:
        raise ValueError("normalization omitted original steps without a pending explanation")


def apply_plan(raw, plan, case_id):
    plan = deepcopy(plan)
    validate_plan(plan, {"candidate": compact(raw)})
    source = {i["id"]: i for i in raw["interactions"]}
    ids = {
        s["key"]: "step-"
        + fingerprint([case_id, s["origin_ids"], s["key"], s["kind"], s["sender"], s["receiver"]])[
            :24
        ]
        for s in plan["steps"]
    }
    for step in plan["steps"]:
        if len(step["origin_ids"]) == 1:
            original = source[step["origin_ids"][0]]
            kind = "action" if original.get("step_kind") == "action" else original["direction"]
            if (
                step["kind"],
                step["layer"],
                step["sender"],
                step["receiver"],
                step["operation"],
            ) == (
                kind,
                original["layer"],
                original["sender"]["name"],
                original["receiver"]["name"],
                original["operation"]["name"],
            ):
                ids[step["key"]] = original["id"]
    parties = {p["name"]: p for i in source.values() for p in (i["sender"], i["receiver"])}
    rows = []
    order = defaultdict(int)
    origins = defaultdict(list)
    for s in plan["steps"]:
        order[s["layer"]] += 1
        carriers = [
            source[k]
            for k in s["origin_ids"]
            if s["kind"] != "action"
            and source[k]["layer"] == s["layer"]
            and source[k]["direction"] == s["kind"]
            and source[k]["sender"]["name"] == s["sender"]
            and source[k]["receiver"]["name"] == s["receiver"]
        ]
        if len(carriers) > 1:
            raise ValueError("multiple original messages cannot be merged by a normalization plan")
        carrier = carriers[0] if carriers else None
        data = deepcopy(carrier["data"]) if carrier else {"sequence": []}
        if s["kind"] == "action" and carrier and carrier.get("step_kind") != "action":
            data = {
                "sequence": []
            }  # Data stays on its request/response; validates links explain the local check.
        row = {
            "id": ids[s["key"]],
            "case_id": case_id,
            "sequence": order[s["layer"]],
            "execution_order": len(rows) + 1,
            "parent_id": ids.get(s["request_ref"]),
            "layer": s["layer"],
            "sender": deepcopy(parties[s["sender"]]),
            "receiver": deepcopy(parties[s["receiver"]]),
            "operation": {
                "name": s["operation"],
                "kinds": deepcopy(carrier["operation"]["kinds"])
                if carrier and s["kind"] != "action"
                else ["process"],
                "sequence": [s["operation"]],
                "optional": [],
                "source_refs": deepcopy(s["source_refs"]),
            },
            "data": data,
            "direction": "return" if s["kind"] == "return" else "request",
            "api_id": carrier.get("api_id") if carrier and s["kind"] != "action" else None,
            "step_kind": "action" if s["kind"] == "action" else "interaction",
            "source_refs": deepcopy(s["source_refs"]),
            "source_step_ids": s["origin_ids"],
            "validates": [ids[k] for k in s["validates"]],
        }
        rows.append(row)
        for origin in s["origin_ids"]:
            origins[origin].append(row["id"])
    links = []
    for link in raw.get("rr_sr_links", []):
        rr = [
            i
            for i in rows
            if i["id"] in origins[link["rr_id"]]
            and i["layer"] == "RR"
            and i["step_kind"] != "action"
        ]
        for parent in rr:
            children = list(
                dict.fromkeys(
                    i
                    for old in link["sr_ids"]
                    for i in origins[old]
                    if next(r for r in rows if r["id"] == i)["layer"] == "SR"
                )
            )
            if children:
                links.append({**deepcopy(link), "rr_id": parent["id"], "sr_ids": children})
    return {
        "interactions": rows,
        "rr_sr_links": links,
        "pending": deepcopy(plan["pending"]),
        "normalization": {
            "version": VERSION,
            "origins": [{"source_id": k, "step_ids": v} for k, v in origins.items()],
        },
    }


def literal_plan(candidate):
    """Verify an already atomic native Order without asking a model to redraw it.

    Only literal, source-backed structured nodes qualify. Ambiguous return
    pairing or bundled local execution falls back to the semantic task.
    """
    steps = []
    for row in candidate["interactions"]:
        nodes = []
        for ref in row.get("source_refs", []):
            try:
                fact = json.loads(ref["quote"])
            except (ValueError, TypeError):
                continue
            if (
                isinstance(fact, dict)
                and isinstance(fact.get("node"), dict)
                and fact.get("kind") in {"event", "response", "interaction", "action"}
            ):
                nodes.append(fact)
        if not nodes:
            return None
        fact = nodes[0]
        original = fact["node"]
        kind = "action" if row.get("step_kind") == "action" else row["direction"]
        if (kind == "action") != (fact["kind"] == "action"):
            return None
        if row["operation"]["name"] != original.get("content", original.get("message")):
            return None
        aliases = fact.get("participant", {})
        parties = (
            [original.get("executor")] * 2
            if kind == "action"
            else [original.get("sender"), original.get("receiver")]
        )
        if [aliases.get(p, {}).get("name") for p in parties] != [
            row["sender"]["name"],
            row["receiver"]["name"],
        ]:
            return None
        req = None
        if kind == "return":
            requests = [
                s
                for s in steps
                if s["kind"] == "request"
                and s["layer"] == row["layer"]
                and (s["sender"], s["receiver"]) == (row["receiver"]["name"], row["sender"]["name"])
            ]
            selected = [s for s in requests if s["key"] == row.get("parent_id")]
            if len(selected) != 1:
                selected = requests
            if len(selected) != 1:
                return None
            req = selected[0]["key"]
        steps.append(
            {
                "key": row["id"],
                "origin_ids": [row["id"]],
                "kind": kind,
                "layer": row["layer"],
                "sender": row["sender"]["name"],
                "receiver": row["receiver"]["name"],
                "operation": row["operation"]["name"],
                "request_ref": req,
                "validates": [],
                "source_refs": deepcopy(row["source_refs"]),
            }
        )
    value = {"steps": steps, "pending": []}
    try:
        validate_plan(value, {"candidate": candidate})
    except ValueError:
        return None
    return value
