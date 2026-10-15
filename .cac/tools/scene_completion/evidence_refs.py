"""Packet-local, scope-checked references for exact evidence quotes.

The adapter is presentation-only: it adds a compact source catalog to a copied
packet and expands references in a copied result. Validators still receive the
same literal quote strings and remain responsible for all semantic decisions.
"""
from __future__ import annotations

from copy import deepcopy

from .sources import fingerprint


_SKIP_FIELDS = {"skill", "extraction_skills", "execution_versions", "instructions", "evidence_catalog_format"}
_QUOTE_FIELDS = {"trigger_condition", "failure_mechanism"}
CATALOG_FORMAT = "scoped-quotes-v1"


def _lines(text):
    """Yield nonblank exact source lines without trimming their contents."""
    if not isinstance(text, str):
        return
    for line in text.splitlines():
        if line.strip():
            yield line


def _catalog_entry(quote, scope, ref=None):
    material = {"quote": quote, "scope": scope, "ref": ref}
    return {"id": "EV-" + fingerprint(material)[:16], **material}


def _add(entries, quote, scope, ref=None):
    if not isinstance(quote, str) or not quote.strip():
        return
    entry = _catalog_entry(quote, scope, ref)
    # Identical source material in a different scenario/ref has a different ID.
    if all(existing["id"] != entry["id"] for existing in entries):
        entries.append(entry)


def _walk_input_strings(value, path=()):
    if isinstance(value, str):
        for line in _lines(value):
            yield line, path
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _walk_input_strings(item, path + (i,))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in _SKIP_FIELDS and key != "evidence_catalog":
                yield from _walk_input_strings(item, path + (key,))


def _numbered_section_lines(section):
    """Read source_sections numbered_text as exact source lines + real refs."""
    numbered = section.get("numbered_text")
    if not isinstance(numbered, str):
        return
    for row in numbered.splitlines():
        head, sep, quote = row.partition(": ")
        if not sep or not head.isdigit() or not quote.strip():
            continue
        line = int(head)
        ref = {key: section[key] for key in ("document", "chapter_id") if key in section}
        ref.update(line_start=line, line_end=line)
        yield quote, ref


def _ref_contains_line(refs, line_ref):
    return any(_same_source_ref(ref, line_ref) for ref in (refs if isinstance(refs, list) else []))


def _stage(packet):
    stage = packet.get("stage")
    if isinstance(stage, str):
        return stage
    # Some small hand-built packets omit a top-level stage. Infer only from a
    # unique known input shape; ambiguous inputs fail closed.
    data = packet.get("input", {})
    candidates = []
    if "allowed_inputs" in data:
        candidates.append("diagnosis")
    if "sections" in data and "scenarios" in data and "reviews" not in data:
        candidates.append("interaction-checker-audit")
    if "sections" in data and "exchanges" in data:
        candidates.append("gap-graph-check")
    if "original_scenarios" in data and "units" in data:
        candidates.append("gap-reverse-check")
    if len(candidates) != 1:
        raise ValueError("packet stage is missing or ambiguous")
    return candidates[0]


def _build_catalog(packet, stage):
    data = packet.get("input")
    if not isinstance(data, dict):
        raise ValueError("evidence packet input must be an object")
    entries = []

    if stage == "diagnosis" or stage.endswith("-diagnosis"):
        # Failed outputs are deliberately excluded: diagnosis still needs an
        # original allowed-input quote under its base validator.
        allowed = data.get("allowed_inputs")
        for quote, path in _walk_input_strings(allowed, ("allowed_inputs",)):
            _add(entries, quote, {"kind": "diagnosis_allowed_input", "path": list(path)})
        return entries

    if stage.startswith("gap-reverse-check"):
        units = {u.get("unit_id"): u for u in data.get("units", []) if isinstance(u, dict)}
        originals = {s.get("scenario_id"): s for s in data.get("original_scenarios", []) if isinstance(s, dict)}
        for unit_id, unit in units.items():
            scenario_id = unit.get("source_scenario_id")
            source = originals.get(scenario_id)
            if not source:
                continue
            for field in sorted(_QUOTE_FIELDS):
                for quote in _lines(source.get(field)):
                    _add(entries, quote, {"kind": "reverse_review", "unit_id": unit_id,
                        "scenario_id": scenario_id, "field": field})
        return entries

    if stage == "interaction-checker-audit":
        sections = data.get("sections", [])
        if isinstance(sections, list):
            for section in sections:
                if not isinstance(section, dict):
                    continue
                for quote, ref in _numbered_section_lines(section):
                    _add(entries, quote, {"kind": "source_audit", "section_id": section.get("chapter_id")}, ref)
        return entries

    if stage in {"gap-graph-check", "gap-features"}:
        sections = data.get("sections", [])
        if isinstance(sections, list):
            items = []
            if stage == "gap-features":
                items = [(row, "exchange_id") for row in data.get("exchanges", []) if isinstance(row, dict)]
            else:
                items = ([(row, "exchange_id") for row in data.get("exchanges", []) if isinstance(row, dict)]
                    + [(row, "node_id") for row in data.get("nodes", []) if isinstance(row, dict)])
            for item, id_key in items:
                item_id = item.get(id_key)
                if not isinstance(item_id, str):
                    continue
                item_refs = item.get("source_refs")
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    for quote, ref in _numbered_section_lines(section):
                        if item_refs and not _ref_contains_line(item_refs, ref):
                            continue
                        _add(entries, quote, {"kind": "graph_source", "use_case_id": data.get("use_case_id"),
                            "item_id": item_id, "item_kind": id_key}, ref)
        return entries

    if stage.startswith("gap-normalize-"):
        originals = {s.get("scenario_id"): s for s in data.get("scenarios", []) if isinstance(s, dict)}
        for scenario_id, source in originals.items():
            for field in sorted(_QUOTE_FIELDS):
                for quote in _lines(source.get(field)):
                    _add(entries, quote, {"kind": "normalization_source", "scenario_id": scenario_id, "field": field})
        return entries

    raise ValueError(f"evidence references are not supported for stage {stage!r}")


def prepare_packet(packet):
    """Return a deep-copied packet with a small, stage-scoped evidence catalog.

    Catalog entries bind an exact source line/field to its provenance and
    allowed stage scope. Existing catalog data is replaced rather than trusted.
    """
    result = deepcopy(packet)
    if not isinstance(result, dict) or not isinstance(result.get("input"), dict):
        raise ValueError("evidence packet must contain an input object")
    stage = _stage(result)
    result["input"]["evidence_catalog"] = _build_catalog(result, stage)
    result["input"]["evidence_catalog_format"] = CATALOG_FORMAT
    return result


def _row_references(parent, key):
    if not isinstance(parent, dict):
        return []
    if key == "failure_evidence_quote":
        refs = parent.get("failure_source_refs")
    elif key in {"contract_evidence_quote", "positive_evidence_quote"}:
        refs = parent.get("contract_source_refs")
    else:
        refs = parent.get("source_refs")
    return refs if isinstance(refs, list) else []


def _same_source_ref(left, right):
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    if left.get("document") != right.get("document"):
        return False
    a0, a1 = left.get("line_start"), left.get("line_end")
    b0, b1 = right.get("line_start"), right.get("line_end")
    return all(isinstance(x, int) and not isinstance(x, bool) for x in (a0, a1, b0, b1)) and a0 <= b0 <= b1 <= a1


def _graph_exchange(packet, supplied_id):
    exchanges = [row for row in packet["input"].get("exchanges", []) if isinstance(row, dict)]
    exact = [row for row in exchanges if row.get("exchange_id") == supplied_id]
    if len(exact) == 1:
        return exact[0]
    aliases = [row for row in exchanges if row.get("local_id") == supplied_id]
    return aliases[0] if len(aliases) == 1 else None


def _entry_allowed(entry, stage, parent, quote_key, packet, exchange_scope=None):
    scope = entry["scope"]
    if scope["kind"] == "diagnosis_allowed_input":
        return stage == "diagnosis" or stage.endswith("-diagnosis")
    if scope["kind"] == "reverse_review":
        data = packet["input"]
        units = {u.get("unit_id"): u for u in data.get("units", []) if isinstance(u, dict)}
        unit = units.get(parent.get("unit_id")) if isinstance(parent, dict) else None
        return (stage.startswith("gap-reverse-check") and quote_key == "evidence_quote"
            and unit is not None and unit.get("source_scenario_id") == scope["scenario_id"])
    if scope["kind"] in {"source_audit", "graph_source"}:
        if stage == "interaction-checker-audit":
            if scope["kind"] != "source_audit":
                return False
            scenario_ids = {row.get("scenario_id") for row in packet["input"].get("scenarios", []) if isinstance(row, dict)}
            if not isinstance(parent, dict):
                return False
            if parent.get("scenario_id") is not None and parent.get("scenario_id") not in scenario_ids:
                return False
            if parent.get("scenario_id") is None and parent.get("layer_use_case_id") != packet["input"].get("use_case_id"):
                return False
        elif stage not in {"gap-graph-check", "gap-features"} or scope["kind"] != "graph_source":
            return False
        elif stage == "gap-graph-check":
            if not isinstance(parent, dict):
                return False
            row_id = parent.get("id")
            node_ids = {row.get("node_id") for row in packet["input"].get("nodes", []) if isinstance(row, dict)}
            exchange = _graph_exchange(packet, row_id) if parent.get("kind") == "ssd" else None
            if row_id in node_ids:
                if scope.get("item_id") != row_id or scope.get("item_kind") != "node_id":
                    return False
            elif exchange:
                if scope.get("item_id") != exchange.get("exchange_id") or scope.get("item_kind") != "exchange_id":
                    return False
            else:
                return False
        elif not isinstance(parent, dict) or parent.get("exchange_id") not in {
            row.get("exchange_id") for row in packet["input"].get("exchanges", []) if isinstance(row, dict)
        }:
            if stage != "gap-features" or exchange_scope not in {
                row.get("exchange_id") for row in packet["input"].get("exchanges", []) if isinstance(row, dict)
            }:
                return False
        if stage == "gap-features" and exchange_scope not in {
            row.get("exchange_id") for row in packet["input"].get("exchanges", []) if isinstance(row, dict)
        }:
            return False
        if stage == "gap-features" and scope.get("item_id") != exchange_scope:
            return False
        refs = _row_references(parent, quote_key)
        return any(_same_source_ref(ref, entry.get("ref")) for ref in refs)
    if scope["kind"] == "normalization_source":
        if not stage.startswith("gap-normalize-") or quote_key != "evidence_quote":
            return False
        items = {row.get("source_scenario_id") for row in packet["input"].get("scenarios", []) if isinstance(row, dict)}
        sid = parent.get("source_scenario_id") if isinstance(parent, dict) else None
        return sid == scope["scenario_id"] or sid in items and sid == scope["scenario_id"]
    return False


def _resolve(value, packet, stage, catalog, exchange_scope=None, feature_item=False, result_root=False):
    if isinstance(value, list):
        return [_resolve(item, packet, stage, catalog, exchange_scope, feature_item, False) for item in value]
    if isinstance(value, dict):
        local_scope = exchange_scope
        if stage == "gap-features" and feature_item:
            expected = {row.get("exchange_id") for row in packet["input"].get("exchanges", []) if isinstance(row, dict)}
            exchange_id = value.get("exchange_id")
            local_scope = exchange_id if exchange_id in expected else None
        ref_keys = [key for key in value if key.endswith("_quote_ref")]
        out = {}
        for key, item in value.items():
            if key in ref_keys:
                continue
            child_is_feature_item = stage == "gap-features" and result_root and key == "items"
            out[key] = _resolve(item, packet, stage, catalog, local_scope, child_is_feature_item, False)
        if not ref_keys:
            return out
        for ref_key in ref_keys:
            quote_key = ref_key[:-4]  # evidence_quote_ref -> evidence_quote
            if quote_key not in {"evidence_quote", "failure_evidence_quote"}:
                raise ValueError("unsupported evidence quote reference field")
            spec = value[ref_key]
            if not isinstance(spec, dict) or set(spec) != {"evidence_id"}:
                raise ValueError(f"{ref_key} must contain only evidence_id")
            evidence_id = spec.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id:
                raise ValueError(f"{ref_key} requires a nonempty evidence_id")
            entry = catalog.get(evidence_id)
            if entry is None:
                raise ValueError("unknown packet-local evidence ID")
            if not _entry_allowed(entry, stage, value, quote_key, packet, local_scope):
                raise ValueError("evidence ID is outside this result item's source scope")
            current = value.get(quote_key)
            if quote_key in value and current != entry["quote"]:
                raise ValueError("explicit evidence quote does not match its reference")
            out[ref_key] = deepcopy(spec)
            out[quote_key] = entry["quote"]
        return out
    return deepcopy(value)


def expand_result(packet, raw):
    """Expand exact quote references on a copied result, preserving the refs.

    The accepted forms are ``{"evidence_quote_ref":{"evidence_id":"EV-..."}}``
    and the field-specific ``failure_evidence_quote_ref`` for source-audit
    failure clauses. The original packet and raw result are never changed, and
    no decision/status field is interpreted or rewritten.
    """
    stage = _stage(packet)
    existing_format = packet.get("input", {}).get("evidence_catalog_format")
    if existing_format is None and "evidence_catalog" in packet.get("input", {}):
        if _contains_reference(raw):
            raise ValueError("legacy evidence catalog is not a scoped quote catalog")
        return deepcopy(raw)
    if existing_format is not None and existing_format != CATALOG_FORMAT:
        raise ValueError("unsupported evidence catalog format")
    if existing_format == CATALOG_FORMAT:
        prepared = packet
        expected = _build_catalog(packet, stage)
        if prepared["input"]["evidence_catalog"] != expected:
            raise ValueError("packet evidence catalog does not match its source inputs")
    else:
        prepared = prepare_packet(packet)
    catalog_rows = prepared["input"].get("evidence_catalog")
    if not isinstance(catalog_rows, list):
        raise ValueError("packet evidence catalog must be a list")
    catalog = {}
    for row in catalog_rows:
        if (not isinstance(row, dict) or set(row) != {"id", "quote", "scope", "ref"}
                or not isinstance(row.get("id"), str) or not isinstance(row.get("quote"), str)):
            raise ValueError("packet evidence catalog entry is malformed")
        if row["id"] in catalog:
            raise ValueError("packet evidence catalog has duplicate IDs")
        catalog[row["id"]] = row
    return _resolve(raw, packet, stage, catalog, result_root=True)


def _contains_reference(value):
    if isinstance(value, dict):
        return any(key.endswith("_quote_ref") or _contains_reference(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_reference(item) for item in value)
    return False
