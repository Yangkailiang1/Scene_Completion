"""Resolve the business entities eligible for one CRUD task from positive evidence."""

import json
import re
import unicodedata
from collections import defaultdict

from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.source_documents import documents_in, evidence_refs, validate_evidence


def normalized(text):
    return unicodedata.normalize("NFKC", str(text)).casefold().strip()


def structured_fact(text):
    if text.lstrip().startswith("{"):
        try:
            fact = json.loads(text)
        except ValueError:
            return {}
        if isinstance(fact, dict):
            return fact
    return {}


def case_labels(fact):
    # A title is a fallback only when the fact has no explicit use-case ID.
    label = fact.get("case_id") or fact.get("case_name")
    return {normalized(label)} if label else set()


def operation_refs(interaction):
    return interaction.get("source_refs", []) + evidence_refs(interaction.get("operation", {}))


def operation_text(interaction):
    operation = interaction.get("operation", {})
    yield operation.get("name", "")
    for step in operation.get("sequence", []):
        if isinstance(step, str):
            yield step
        elif isinstance(step, dict):
            yield step.get("name", "")


def project(inputs, case_aliases, locations):
    catalogue = inputs["business-entities"]["entities"]
    aliases = {normalized(a) for a in case_aliases}
    docs = documents_in(inputs["normal-documents"])
    interactions = inputs["fused-ssd"]["interactions"]
    service_names = {
        normalized(i.get(side, {}).get("name", ""))
        for i in interactions
        for side in ("sender", "receiver")
    }
    lookup = defaultdict(set)
    explicit = set()
    known_refs = {}
    ref_entities = defaultdict(set)
    for entity in catalogue:
        eid = entity["id"]
        identities = {normalized(eid), normalized(entity["name"])} - {""}
        for label in identities:
            lookup[label].add(eid)
        if any(
            aliases.intersection(
                normalized(x) for x in (a.get("case_ids") or a.get("case_names", []))
            )
            for a in entity["attributes"]
        ):
            explicit.add(eid)
        refs = {}
        for ref in entity["source_refs"] + evidence_refs(entity["attributes"]):
            ref_id = fingerprint(ref)
            refs[ref_id] = ref
            ref_entities[ref_id].add(eid)
            fact = structured_fact(ref["quote"])
            if case_labels(fact) & aliases and normalized(fact.get("entity", "")) in identities:
                explicit.add(eid)
        known_refs[eid] = refs

    labels = sorted(lookup, key=lambda label: (-len(label), label))
    patterns = {
        label: re.compile(
            r"(?<![a-z0-9_.-])" + re.escape(label) + r"(?![a-z0-9_.-])"
            if label.isascii()
            else re.escape(label)
        )
        for label in labels
    }
    inferred = set()
    ambiguous = defaultdict(set)
    local_refs = defaultdict(dict)

    def mentions(text, ref=None, interaction_id=None):
        # Parameter tables and service/actor declarations establish other
        # objects. Their names are not entity-operation evidence.
        if re.match(
            r"^\s*(?:\||(?:participant|actor|service)\s|(?:服务名称|所属服务|参与者)[：:])",
            text,
            re.I,
        ):
            return
        fact = structured_fact(text)
        cases = case_labels(fact)
        if cases and not cases & aliases:
            return
        if cases and fact.get("entity"):
            candidates = lookup.get(normalized(fact["entity"]), set())
            if len(candidates) == 1:
                eid = next(iter(candidates))
                explicit.add(eid)
                if ref is not None:
                    local_refs[eid].setdefault(ref["source_id"], ref)
            return
        if fact:
            return  # JSON key/value mentions alone do not establish an entity.
        source = normalized(text)
        spans = []
        for label in labels:
            for match in patterns[label].finditer(source):
                a, b = match.span()
                if label in service_names and not (
                    re.search(r"(?:业务实体|实体|entity)\s*$", source[:a])
                    or re.match(r"\s*(?:业务实体|实体|entity)", source[b:])
                ):
                    continue
                if any(lo <= a and b <= hi for lo, hi in spans):
                    continue
                spans.append((a, b))
                candidates = lookup[label]
                preferred = candidates & explicit
                if len(preferred or candidates) != 1:
                    ambiguous[label].add(interaction_id or "")
                    continue
                eid = next(iter(preferred or candidates))
                inferred.add(eid)
                if ref is not None:
                    local_refs[eid].setdefault(ref["source_id"], ref)

    # Collect explicit document facts first so they can disambiguate name matches.
    for doc in docs:
        for row in doc["lines"]:
            fact = structured_fact(row["text"])
            if case_labels(fact) & aliases and fact.get("entity"):
                mentions(row["text"])
    for doc in docs:
        for row in doc["lines"]:
            n = row["number"]
            mentions(
                row["text"],
                {
                    "source_id": doc["source_id"],
                    "line_start": n,
                    "line_end": n,
                    "quote": row["text"],
                },
            )
    for interaction in interactions:
        for text in operation_text(interaction):
            mentions(text, interaction_id=interaction["id"])

    selected = explicit | inferred
    entities = []
    for entity in catalogue:
        eid = entity["id"]
        if eid not in selected:
            continue
        identities = {normalized(eid), normalized(entity["name"])}
        refs = {fingerprint(r): r for r in local_refs[eid].values()}
        explicit_refs = []
        for ref_id, ref in known_refs[eid].items():
            fact = structured_fact(ref["quote"])
            if (
                case_labels(fact) & aliases
                and normalized(fact.get("entity", "")) in identities
                and len(ref_entities[ref_id]) == 1
            ):
                explicit_refs.append((ref_id, ref, "name" in fact and "rules" not in fact))
        # Imported attributes establish scope but their repeated constraints
        # belong to the entity catalogue, not this classification request.
        identity_refs = [(key, ref) for key, ref, identity in explicit_refs if identity]
        if identity_refs:
            refs.update(identity_refs)
        elif not refs and explicit_refs:
            key, ref, _ = explicit_refs[0]
            refs[key] = ref
        entities.append(
            {
                "id": eid,
                "name": entity["name"],
                "attributes": [],
                "business_rules": [],
                "source_refs": list(refs.values()),
            }
        )
    used = {(r["source_id"], r["line_start"]) for e in entities for r in e["source_refs"]}
    source_locations = [
        {"source_id": sid, "line": line, **locations[(sid, line)]}
        for sid, line in sorted(used)
        if (sid, line) in locations
    ]
    return {
        **inputs,
        "normal-documents": docs,
        "business-entities": {"entities": entities, "pending": []},
        "crud-entity-scope": {
            "project_entities": len(catalogue),
            "explicit_entities": sorted(explicit),
            "missing_entities": not selected,
            "ambiguous_names": sorted(ambiguous),
            "ambiguous_interactions": {
                label: sorted(i for i in ids if i) for label, ids in sorted(ambiguous.items())
            },
            "source_locations": source_locations,
        },
    }


def excerpt_of(ref, allowed):
    """A bounded page of a trusted quote retains its original source coordinates."""
    return bool(ref["quote"].strip()) and any(
        ref["source_id"] == source["source_id"]
        and ref["line_start"] == source["line_start"]
        and ref["line_end"] == source["line_end"]
        and ref["quote"] in source["quote"]
        for source in allowed
    )


def validate_operations(value, inputs):
    docs = documents_in(inputs["normal-documents"])
    interactions = {i["id"]: i for i in inputs["fused-ssd"]["interactions"]}
    for row in value["rows"]:
        related = [interactions[row["interaction_id"]]]
        related.extend(
            interactions[i] for i in row.get("delegate_interaction_ids", []) if i in interactions
        )
        refs = [r for i in related for r in operation_refs(i)]
        for citation in row["source_refs"]:
            if excerpt_of(citation, refs):
                break
            try:
                validate_evidence(citation, docs)
            except ValueError:
                continue
            break
        else:
            raise ValueError(
                "CRUD operation requires a current use-case or actual operation citation; "
                f"entity identity alone is insufficient: {row['interaction_id']}"
            )


def record_pending(value, scope, case):
    entries = [
        (interaction or case, "同名业务实体归属待确认：" + name)
        for name in scope["ambiguous_names"]
        for interaction in scope["ambiguous_interactions"].get(name, []) or [None]
    ]
    if scope["missing_entities"]:
        entries.append((case, "当前用例未定位到业务实体，需确认实体归属"))
    uncertain = {i for ids in scope["ambiguous_interactions"].values() for i in ids} - {
        row["interaction_id"] for row in value["rows"]
    }
    for review in value.get("reviews", []):
        if review["interaction_id"] in uncertain:
            review["decision"] = "pending"
            review["basis"] = "当前操作提及多个同名业务实体，归属需确认"
    pending = value["pending"]
    for obj, reason in entries:
        entry = {"object": obj, "reason": reason, "source_refs": []}
        if entry not in pending:
            pending.append(entry)
    return value
