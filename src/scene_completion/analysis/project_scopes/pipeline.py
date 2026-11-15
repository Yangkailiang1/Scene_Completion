"""Positive project facts, direct relation identities and deterministic rule mounting."""

import re
from copy import deepcopy

from scene_completion.domain.project_scopes.validation import KEYS, SCOPES, VERSION
from scene_completion.domain.ssd.construction import channel, ident, unique
from scene_completion.inputs.documents.source_documents import normal_projection


def documents_and_lines(bundles, documents=()):
    """Keep full original documents for traceability; expose positive lines only to G."""
    originals = {d["id"]: deepcopy(d) for b in bundles for d in b.get("documents", [])}
    for document in documents:
        rows = document.get("lines", [])
        content = [""] * max((r["number"] for r in rows), default=0)
        for row in rows:
            content[row["number"] - 1] = row["text"]
        sid = document.get("source_id", document.get("id"))
        role = {"rr": "RR", "sr": "SR", "ar": "AR", "architecture": "AR", "test": "test"}.get(
            str(document.get("channel", "")).lower(), document.get("role", "intermediate")
        )
        originals.setdefault(
            sid,
            {
                "id": sid,
                "name": document.get("name", sid),
                "role": role,
                "content": "\n".join(content),
            },
        )
    source_lines = []
    for doc in originals.values():
        if doc.get("role") not in {"RR", "SR", "AR"}:
            continue
        projected = normal_projection(
            [
                {
                    "source_id": doc["id"],
                    "name": doc["name"],
                    "channel": "normal",
                    "lines": [
                        {"number": n, "text": line}
                        for n, line in enumerate(doc["content"].splitlines(), 1)
                    ],
                }
            ]
        )
        for row in projected[0]["lines"] if projected else []:
            if row["text"].strip():
                source_lines.append(
                    {
                        "id": doc["id"] + ":" + str(row["number"]),
                        "document_id": doc["id"],
                        "line": row["number"],
                        "text": row["text"],
                    }
                )
    return list(originals.values()), source_lines


def source_ref(row):
    return {
        "document_id": row["document_id"],
        "start_line": row["line"],
        "end_line": row["line"],
        "quote": row["text"],
        "kind": "origin",
    }


def _party(value):
    return {"id": value.get("id"), "name": value.get("name"), "type": value.get("type")}


def _constraints(value):
    return [{"kind": c.get("kind"), "value": c.get("value")} for c in value.get("constraints", [])]


def _field(value):
    return {
        "name": value.get("name"),
        "location": value.get("location"),
        "type": value.get("type"),
        "required": value.get("required"),
        "constraints": _constraints(value),
    }


def _attribute(value):
    return {
        "name": value.get("name"),
        "type": value.get("type"),
        "constraints": _constraints(value),
    }


def _entity(value):
    return {
        "id": value["id"],
        "name": value.get("name", value["id"]),
        "attributes": [_attribute(a) for a in value.get("attributes", [])],
    }


def _step(value):
    operation = value.get("operation") or {}
    return {
        "id": value["id"],
        "kind": value["kind"],
        "direction": value["direction"],
        "operation": (operation.get("name") or "")[:80],
        "kinds": list(operation.get("kinds", [])),
        "sender": _party(value["sender"]),
        "receiver": _party(value["receiver"]),
        "api_id": value.get("api_id"),
        "entity_ids": list(value.get("entity_ids", [])),
        "fields": [_field(f) for f in value.get("data", [])],
    }


def positive_catalogue(bundles):
    """Compact forward-only facts for semantic project tasks.

    The model needs case names, operations, object roles, entities and declared
    constraints, not source quotations or full extraction documents. Keeping
    this projection small also keeps published project bundles and the offline
    review HTML portable.
    """
    return [
        {
            "case": {"id": b["case"]["id"], "name": b["case"].get("name", b["case"]["id"])},
            "steps": [_step(s) for s in b["steps"]],
            "entities": [_entity(e) for e in b.get("entities", [])],
        }
        for b in bundles
    ]


def structure_inputs(bundles, documents=()):
    docs, lines = documents_and_lines(bundles, documents)
    entities = {e["id"]: e for b in bundles for e in b.get("entities", [])}
    positive = positive_catalogue(bundles)
    return docs, {
        "cases": [deepcopy(b["case"]) for b in bundles],
        "entities": [{"id": e["id"], "name": e.get("name", e["id"])} for e in entities.values()],
        "source_lines": lines,
        "known_external_services": [
            {"identity": p["id"], "name": p["name"], "case_id": b["case"]["id"]}
            for b in bundles
            for s in b["steps"]
            for p in (s["sender"], s["receiver"])
            if p.get("external") and p.get("type") != "human"
        ],
        "human_parties": list(
            {
                p["id"]: {"id": p["id"], "name": p["name"]}
                for b in bundles
                for s in b["steps"]
                for p in (s["sender"], s["receiver"])
                if p.get("type") == "human"
            }.values()
        ),
        "positive_cases": positive,
    }


def structure_bundles(bundles, documents, inputs, parts, registry, *, pending_reason=None):
    refs = {r["id"]: source_ref(r) for r in inputs["source_lines"]}
    dependencies, services, pending = {}, {}, []
    for part in parts:
        for raw in part["dependencies"]:
            row = {k: deepcopy(v) for k, v in raw.items() if k != "source_ref_ids"}
            row.update(
                kind="dependency", source_refs=unique(refs[i] for i in raw["source_ref_ids"])
            )
            row["id"] = ident(
                "dependency",
                row["from_case_id"],
                row["to_case_id"],
                row["relation_type"],
                re.sub(r"\s+", "", row["condition"]).casefold(),
                re.sub(r"\s+", "", row["obligation"]).casefold(),
                sorted(row["entity_ids"]),
            )
            if row["id"] in dependencies:
                row["source_refs"] = unique(
                    dependencies[row["id"]]["source_refs"] + row["source_refs"]
                )
            dependencies[row["id"]] = row
        for raw in part["services"]:
            identity = re.sub(r"\s+", "", raw["identity"]).casefold()
            key = next(
                (
                    k
                    for k, v in services.items()
                    if k == identity or v["name"].casefold() == raw["name"].casefold()
                ),
                identity,
            )
            row = services.setdefault(
                key,
                {
                    "id": ident("external-service", key),
                    "kind": "external_service",
                    "name": raw["name"],
                    "identity": raw["identity"],
                    "description": raw["description"],
                    "type": "service",
                    "technology": raw["technology"],
                    "external": True,
                    "api_ids": [],
                    "case_ids": [],
                    "source_refs": [],
                    "calls": [],
                },
            )
            for field in ("api_ids", "case_ids"):
                row[field] = sorted(set(row[field]) | set(raw[field]))
            row["source_refs"] = unique(
                row["source_refs"] + [refs[i] for i in raw["source_ref_ids"]]
            )
        pending += [
            {
                "id": ident("structure-pending", p),
                "condition": p["reason"],
                "reason": p["reason"],
                "source_refs": [refs[i] for i in p["source_ref_ids"]],
                "status": "pending",
            }
            for p in part["pending"]
        ]
    # Explicit component identities survive incomplete document coverage and let
    # multiple API/case calls share the same external-service anchor.
    for b in bundles:
        for step in b["steps"]:
            for party in (step["sender"], step["receiver"]):
                if not party.get("external") or party.get("type") == "human":
                    continue
                key = next(
                    (
                        k
                        for k, v in services.items()
                        if v["identity"] == party["id"]
                        or v["name"].casefold() == party["name"].casefold()
                    ),
                    party["id"].casefold(),
                )
                row = services.setdefault(
                    key,
                    {
                        "id": ident("external-service", key),
                        "kind": "external_service",
                        "identity": party["id"],
                        "name": party["name"],
                        "description": "",
                        "type": "service",
                        "technology": party.get("technology"),
                        "external": True,
                        "api_ids": [],
                        "case_ids": [],
                        "source_refs": [],
                        "calls": [],
                    },
                )
                row["case_ids"] = sorted(set(row["case_ids"] + [b["case"]["id"]]))
                if step.get("api_id"):
                    row["api_ids"] = sorted(set(row["api_ids"] + [step["api_id"]]))
                row["calls"] = unique(
                    row["calls"]
                    + [
                        {
                            "case_id": b["case"]["id"],
                            "step_id": step["id"],
                            "api_id": step.get("api_id"),
                        }
                    ]
                )
                row["source_refs"] = unique(row["source_refs"] + step.get("source_refs", []))
    if pending_reason:
        pending.append(
            {
                "id": "project-structure-unavailable",
                "reason": pending_reason,
                "condition": pending_reason,
                "status": "pending",
                "source_refs": [],
            }
        )
    outputs = {}
    for scope, anchors in (
        ("business_chain", list(dependencies.values())),
        ("architecture", list(services.values())),
    ):
        result = {
            "version": VERSION,
            "coverage_policy": "coverage-any-confirmed-v2",
            "scope": {"id": scope, "name": SCOPES[scope]},
            "anchors": anchors,
            "cases": deepcopy(inputs["cases"]),
            "channels": {c: channel() for c in ("G", "E", "GT")},
            "documents": deepcopy(documents),
            "registry": deepcopy(registry),
            "decisions": [],
            "pending": deepcopy(pending),
            "positive_cases": deepcopy(inputs["positive_cases"]),
            "source_records": {"E": [], "GT": []},
        }
        for b in bundles:
            for c in ("E", "GT"):
                own = b["channels"][c]
                candidates = (
                    own.get("project_records", [])
                    + [r for r in own.get("scenarios", []) if r.get("key") in KEYS[scope]]
                    + [
                        r
                        for r in own.get("pending", [])
                        if not r.get("key") or r.get("key") in KEYS[scope]
                    ]
                )
                for record in candidates:
                    if record.get("scope") not in (None, scope):
                        continue
                    result["source_records"][c].append(
                        {
                            "id": b["case"]["id"] + ":" + record["id"],
                            "original_id": record["id"],
                            "case_id": b["case"]["id"],
                            "declared_scope": record.get("scope"),
                            "declared_key": record.get("key"),
                            "condition": record.get("condition", ""),
                            "expected": record.get("expected", ""),
                            "source_refs": deepcopy(record.get("source_refs", [])),
                        }
                    )
                result["source_records"][c] = unique(result["source_records"][c])
        result["channels"]["G"] = generate_g(result)
        outputs[scope] = result
    return outputs


def generate_g(bundle):
    from scene_completion.domain.concern_templates import templates_for

    out = channel()
    scope = bundle["scope"]["id"]
    target = "dependency" if scope == "business_chain" else "service"
    for anchor in bundle["anchors"]:
        for key in sorted(KEYS[scope]):
            if key == "global.cascade_operation" and anchor.get("relation_type") != "cascade":
                continue
            if not bundle["registry"]["definitions"].get(key, {}).get("enabled", True):
                continue
            cid = ident("G-project-concern", scope, anchor["id"], key)
            concern = {
                "id": cid,
                "anchor_id": anchor["id"],
                "target": target,
                "key": key,
                "entity_id": None,
                "field_id": None,
                "label": bundle["registry"]["definitions"].get(key, {}).get("label", key),
                "condition": bundle["registry"]["definitions"].get(key, {}).get("label", key),
                "status": "active",
                "source_refs": deepcopy(anchor.get("source_refs", [])),
                "rule_id": "project-mount-v1:" + key,
            }
            out["concerns"].append(concern)
            for template in templates_for(key):
                out["scenarios"].append(
                    {
                        **deepcopy(concern),
                        **deepcopy(template),
                        "id": ident("G-project-scenario", cid, template["template_id"]),
                        "concern_ids": [cid],
                    }
                )
    return out


def add_observations(bundle, channel_name, payload, records):
    out = bundle["channels"][channel_name]
    sources = {r["id"]: r for r in records}
    for row in payload["observations"]:
        cid = ident(
            channel_name + "-project-concern", bundle["scope"]["id"], row["anchor_id"], row["key"]
        )
        ref = deepcopy(sources[row["source_record_id"]]["source_refs"])
        concern = next((r for r in out["concerns"] if r["id"] == cid), None)
        if concern is None:
            concern = {
                "id": cid,
                "anchor_id": row["anchor_id"],
                "target": "dependency" if bundle["scope"]["id"] == "business_chain" else "service",
                "key": row["key"],
                "label": bundle["registry"]["definitions"]
                .get(row["key"], {})
                .get("label", row["key"]),
                "entity_id": None,
                "field_id": None,
                "condition": row["condition"],
                "status": "active",
                "source_refs": ref,
            }
            out["concerns"].append(concern)
        else:
            concern["source_refs"] = unique(concern["source_refs"] + ref)
        sid = ident(channel_name + "-project-scenario", cid, row["condition"], row["expected"])
        scenario = next((r for r in out["scenarios"] if r["id"] == sid), None)
        if scenario:
            scenario["source_refs"] = unique(scenario["source_refs"] + ref)
        else:
            out["scenarios"].append(
                {
                    **deepcopy(concern),
                    "id": sid,
                    "concern_ids": [cid],
                    "condition": row["condition"],
                    "expected": row["expected"],
                    "source_record_id": row["source_record_id"],
                    "source_refs": ref,
                }
            )
    for row in payload["pending"]:
        out["pending"].append(
            {
                **deepcopy(sources[row["source_record_id"]]),
                "status": "pending",
                "reason": row["reason"],
                "needs_semantic": True,
            }
        )
    bundle.setdefault("excluded", {}).setdefault(channel_name, []).extend(
        [
            {**deepcopy(sources[r["source_record_id"]]), "reason": r["reason"]}
            for r in payload["excluded"]
        ]
    )
