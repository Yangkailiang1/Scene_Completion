"""Merge independent source channels by actual service and generic failure mode."""

import re
from copy import deepcopy

from scene_completion.domain.current_scope import AVAILABILITY, POLICY
from scene_completion.domain.project_scopes import matching
from scene_completion.domain.ssd import matching as case_matching
from scene_completion.infrastructure.identity import fingerprint

KINDS = ("concerns", "scenarios", "pending")


def ident(*parts):
    return "shared-" + fingerprint(parts)[:24]


def unique(rows):
    return list({fingerprint(r): r for r in rows}.values())


def merge_calls(existing, added):
    result = {(c.get("case_id"), c.get("step_id")): deepcopy(c) for c in existing}
    for call in added:
        key = (call.get("case_id"), call.get("step_id"))
        if key not in result:
            result[key] = deepcopy(call)
        else:
            old = result[key]
            old["source_refs"] = unique(old.get("source_refs", []) + call.get("source_refs", []))
            for field in ("operation", "api_id"):
                if not old.get(field) and call.get(field):
                    old[field] = deepcopy(call[field])
    return list(result.values())


def fault(row):
    variant = row.get("fault_type") or row.get("variant_id")
    if variant:
        return variant
    text = row.get("condition", "").casefold()
    for key, pattern in (
        ("timeout", r"超时|timeout|timed out"),
        ("rate_limited", r"限流|rate.limit"),
        (
            "service_unavailable",
            r"不可用|不可达|无法.*(?:访问|连接)|宕机|unavailable|unreachable|连接.*失败",
        ),
    ):
        if re.search(pattern, text):
            return key
    return case_matching._text(text)


def build(views, legacy=None):
    out = {
        "version": "project-scope-v1",
        "scope": {"id": "architecture", "name": "共用外部服务"},
        "analysis_policy": POLICY,
        "coverage_policy": "coverage-any-confirmed-v2",
        "anchors": [],
        "cases": [],
        "documents": [],
        "channels": {c: {k: [] for k in KINDS} for c in ("E", "G", "GT")},
        "decisions": [],
        "pending": [],
        "source_versions": {},
        "legacy_projection": bool(legacy),
    }
    anchors, groups, documents, mapped, evidence = {}, {}, {}, {}, {}
    sources = sorted(
        [("interaction", v["bundle"]["case"]["id"], v) for v in views], key=lambda s: s[1]
    )
    if legacy:
        sources.append(("legacy_architecture", "architecture", legacy))
    for source, key, view in sources:
        b = view["bundle"]
        out["source_versions"][source + ":" + key] = view["revision"]
        if source == "interaction":
            out["cases"].append(deepcopy(b["case"]))
        docmap = {}
        for d in b.get("documents", []):
            did = ident("document", d.get("role"), d.get("name"), d.get("content"))
            documents[did] = {**deepcopy(d), "id": did}
            docmap[d["id"]] = did

        def refs(values):
            return unique(
                [
                    {**deepcopy(r), "document_id": docmap.get(r["document_id"], r["document_id"])}
                    for r in values
                ]
            )

        calls = {}
        if source == "interaction":
            for step in b["steps"]:
                if (
                    step.get("kind") == "action"
                    or step.get("direction") != "request"
                    or step["sender"]["id"] == step["receiver"]["id"]
                ):
                    continue
                for role in ("receiver",):
                    party = step[role]
                    if not party.get("external") or party.get("type") == "human":
                        continue
                    identity = [
                        party.get("id"),
                        party.get("name", "").casefold(),
                        party.get("technology"),
                    ]
                    aid = ident("service", identity)
                    a = anchors.setdefault(
                        aid,
                        {
                            "id": aid,
                            "identity": identity,
                            "kind": "external_service",
                            "name": party["name"],
                            "type": "service",
                            "technology": party.get("technology"),
                            "external": True,
                            "api_ids": [],
                            "case_ids": [],
                            "source_refs": [],
                            "calls": [],
                        },
                    )
                    a["calls"] = merge_calls(
                        a["calls"],
                        [
                            {
                                "case_id": key,
                                "step_id": step["id"],
                                "api_id": step.get("api_id"),
                                "operation": step["operation"]["name"],
                                "source_refs": refs(step.get("source_refs", [])),
                            }
                        ],
                    )
                    a["case_ids"] = sorted(set(a["case_ids"] + [key]))
                    a["api_ids"] = sorted(
                        set(a["api_ids"] + ([step["api_id"]] if step.get("api_id") else []))
                    )
                    a["source_refs"] = unique(a["source_refs"] + refs(step.get("source_refs", [])))
                    calls[(step["id"], role)] = aid
        else:
            for old in b.get("anchors", []):
                candidates = [
                    aid
                    for aid, a in anchors.items()
                    if (
                        isinstance(a["identity"], list)
                        and a["identity"][0] == old.get("identity")
                        and a["name"].casefold() == old.get("name", "").casefold()
                    )
                    or bool(
                        {(c["case_id"], c["step_id"]) for c in a.get("calls", [])}
                        & {(c.get("case_id"), c.get("step_id")) for c in old.get("calls", [])}
                    )
                ]
                aid = (
                    candidates[0]
                    if len(candidates) == 1
                    else ident("legacy-service", old.get("identity") or old["id"], old["id"])
                )
                a = anchors.setdefault(
                    aid,
                    {
                        **deepcopy(old),
                        "id": aid,
                        "identity": old.get("identity", old["id"]),
                        "source_refs": [],
                        "calls": [],
                        "case_ids": [],
                        "api_ids": [],
                    },
                )
                a["source_refs"] = unique(a["source_refs"] + refs(old.get("source_refs", [])))
                known = {
                    (v["bundle"]["case"]["id"], s["id"]): s
                    for v in views
                    for s in v["bundle"]["steps"]
                }
                for call in old.get("calls", []):
                    step = known.get((call.get("case_id"), call.get("step_id")))
                    updated_call = {
                        **deepcopy(call),
                        "source_refs": refs(call.get("source_refs", [])),
                    }
                    if step and (
                        step.get("kind") == "action" or step.get("direction") != "request"
                    ):
                        a.setdefault("legacy_contexts", []).append(updated_call)
                    else:
                        a["calls"] = merge_calls(a["calls"], [updated_call])
                for field in ("case_ids", "api_ids"):
                    a[field] = sorted(set(a.get(field, [])) | set(old.get(field, [])))
                calls[(old["id"], "service")] = aid
        for c, data in b["channels"].items():
            for kind in KINDS:
                for original in data.get(kind, []):
                    if original.get("key") != AVAILABILITY:
                        continue
                    aid = calls.get(
                        (original.get("step_id", original.get("anchor_id")), original.get("target"))
                    )
                    if not aid:
                        out["channels"][c]["pending"].append(
                            {
                                **deepcopy(original),
                                "id": ident("unbound", source, key, c, original["id"]),
                                "status": "unbound",
                                "reason": "服务身份或调用位置待确认，未强制合并",
                                "source_refs": refs(original.get("source_refs", [])),
                                "member_identity": {
                                    "source": source,
                                    "case_id": key,
                                    "record_id": original["id"],
                                    "revision": view["revision"],
                                },
                            }
                        )
                        continue
                    mode = "availability" if kind == "concerns" else fault(original)
                    gid = ident(c, kind, aid, mode)
                    member = {
                        "source": source,
                        "case_id": key if source == "interaction" else None,
                        "step_id": original.get("step_id"),
                        "record_id": original["id"],
                        "source_revision": view["revision"],
                        "condition": original.get("condition"),
                        "expected": original.get("expected", ""),
                        "analysis": original.get("analysis", ""),
                        "status": original.get("status"),
                        "generation_pending": original["id"] in b.get("generation_pending", [])
                        or original["id"]
                        in b.get("scenario_generation", {}).get("pending_ids", []),
                        "source_refs": refs(original.get("source_refs", [])),
                        "requirement_refs": refs(original.get("requirement_refs", [])),
                    }
                    labels = {
                        "service_unavailable": "外部服务不可用",
                        "timeout": "外部服务调用超时",
                        "rate_limited": "外部服务限流",
                    }
                    row = groups.setdefault(
                        (c, kind, gid),
                        {
                            **deepcopy(original),
                            "id": gid,
                            "anchor_id": aid,
                            "target": "service",
                            "field_id": None,
                            "entity_id": None,
                            "condition": "服务可用性"
                            if kind == "concerns"
                            else labels.get(mode, original.get("condition", "")),
                            "expected": "见各调用的处理预期" if kind == "scenarios" else "",
                            "fault_type": mode,
                            "source_refs": [],
                            "requirement_refs": [],
                            "members": [],
                            "scope": "shared_services",
                        },
                    )
                    row.pop("step_id", None)
                    row["members"].append(member)
                    row["source_refs"] = unique(row["source_refs"] + member["source_refs"])
                    row["requirement_refs"] = unique(
                        row["requirement_refs"] + member["requirement_refs"]
                    )
                    if original.get("status") == "active":
                        row["status"] = "active"
                    if original.get("analysis") and not row.get("analysis"):
                        row["analysis"] = original["analysis"]
                    mapped[(source, key, c, kind, original["id"])] = gid
        matcher = case_matching if source == "interaction" else matching
        for kind in ("concerns", "scenarios"):
            units, aliases = matcher._units(b, kind)
            edges = matcher._edges(b, kind, units, aliases)
            for pair, matches in edges.items():
                left, right = pair.split("_")
                for (a, z), status in matches.items():
                    left_gid = mapped.get((source, key, left, kind, a))
                    right_gid = mapped.get((source, key, right, kind, z))
                    if left_gid and right_gid:
                        evidence.setdefault((kind, pair, left_gid, right_gid), []).append(
                            {
                                "status": status,
                                "source": source,
                                "case_id": key,
                                "left_id": a,
                                "right_id": z,
                            }
                        )
    for (c, kind, _), row in groups.items():
        if kind == "scenarios":
            row["concern_ids"] = [ident(c, "concerns", row["anchor_id"], "availability")]
        out["channels"][c][kind].append(row)
    for (kind, pair, left, right), values in evidence.items():
        status = (
            "full"
            if any(d["status"] == "full" for d in values)
            else "partial"
            if any(d["status"] == "partial" for d in values)
            else "none"
        )
        out["decisions"].append(
            {
                "id": ident("decision", kind, pair, left, right),
                "level": "concern" if kind == "concerns" else "scenario",
                "pair": pair,
                "left_id": left,
                "right_id": right,
                "status": status,
                "origin": "auto",
                "reason": "保留调用成员已有判定",
                "member_decisions": values,
            }
        )
    out["anchors"] = list(anchors.values())
    out["documents"] = list(documents.values())
    out["generation_pending"] = [
        r["id"]
        for r in out["channels"]["G"]["scenarios"]
        if any(m["generation_pending"] for m in r["members"])
    ]
    out["gt_identification_run_complete"] = all(
        v["bundle"].get(
            "gt_identification_run_complete",
            not any(
                r.get("needs_semantic") for r in v["bundle"]["channels"]["GT"].get("pending", [])
            ),
        )
        for _, _, v in sources
    )
    return out
