"""Independent checker extraction, semantic matching, and recommendation stages."""
from __future__ import annotations

import math
from pathlib import Path

from .comparison import compare_scenes, scene_map
from .concerns import ACTIVE_CONCERN_KEYS, CONCERN_DEFINITIONS
from .semantic_backend import (collect_packets, cosine, prepare_packets, read_json,
                               scene_text, write_json)
from .sources import (evidence_fragments, fingerprint, source_refs, target_sections,
                      use_case_sections, validate_refs)


def taxonomy() -> list[dict]:
    return [{"key": key, "label": CONCERN_DEFINITIONS[key]["label"],
             "definition": CONCERN_DEFINITIONS[key]["description"]}
            for key in sorted(ACTIVE_CONCERN_KEYS)]


def checker_packets(index: dict, use_cases: list[dict], directory) -> dict:
    payloads = []
    # Only identity/name metadata is shared, never generated/model scenario content.
    identities = {u["use_case_id"]: u.get("use_case_name", u["use_case_id"]) for u in use_cases}
    import re
    for doc in index["documents"]:
        for chapter in doc["chapters"]:
            match = re.search(r"(?:UCG-\d+-UC\d+|UC-\d+)", chapter["title"])
            if match:
                identities.setdefault(match[0], chapter["title"])
    for uc_id, name in sorted(identities.items()):
        sections = use_case_sections(index, uc_id)
        if not sections:
            raise ValueError(f"no source use-case sections: {uc_id}")
        sources = []
        for section in sections:
            doc = next(d for d in index["documents"] if d["document"] == section["document"])
            lines = doc["text"].splitlines()
            sources.append({**section, "numbered_text": "\n".join(
                f"{i}: {lines[i-1]}" for i in range(section["line_start"], section["line_end"] + 1))})
        payloads.append({"use_case_id": uc_id, "use_case_name": name, "sections": sources,
                         "taxonomy": taxonomy()})
    return prepare_packets(directory, "checker", payloads, [
        "Independently extract ALL explicitly described main-success, alternative and exception scenarios from the assigned requirement and design use-case sections.",
        "Do not infer missing exceptions and do not use generated scenarios or test_spec. One main-success scenario per UC; distinct alternative/exception conditions remain atomic.",
        "Merge equivalent descriptions across requirement/design while retaining ALL source citations; preserve distinct outcomes or constraints.",
        "Classify exception concerns independently using the supplied active taxonomy, allowing multiple keys. Main-success and successful alternatives have empty concern_keys. Unknown exceptions use empty keys.",
        "Cite exact source line ranges supporting trigger and expected result; source_refs must lie within assigned sections.",
        "Return covered_section_ids including EVERY assigned chapter_id, even when it adds no scenarios.",
    ], {"covered_section_ids": ["all assigned chapter IDs"],
        "scenarios": [{"name": "specific scenario", "scenario_type": "main_success|alternative|requirement_exception",
                       "preconditions": "explicit or 待需求确认", "trigger": "specific condition",
                       "scenario_steps": ["steps"], "expected_result": "explicit outcome", "recovery": "explicit or 待需求确认",
                       "concern_keys": ["active taxonomy keys"],
                       "source_refs": [{"document": "filename", "line_start": 1, "line_end": 2}]}]})


def checker_validator(index: dict):
    def validate(packet, result):
        payload = packet["input"]
        expected = {s["chapter_id"] for s in payload["sections"]}
        covered = result.get("covered_section_ids", [])
        if not isinstance(covered, list) or set(covered) != expected or len(covered) != len(expected):
            raise ValueError("checker omitted or duplicated source sections")
        scenes = result.get("scenarios")
        if not isinstance(scenes, list) or not scenes:
            raise ValueError("checker needs explicitly extracted scenarios")
        validated, seen = [], set()
        for raw in scenes:
            if not isinstance(raw, dict) or raw.get("scenario_type") not in {"main_success", "alternative", "requirement_exception"}:
                raise ValueError("invalid extracted scenario type")
            for key in ("name", "trigger", "expected_result", "preconditions"):
                if not isinstance(raw.get(key), str) or not raw[key].strip():
                    raise ValueError(f"checker missing {key}")
            if not isinstance(raw.get("scenario_steps"), list) or not raw["scenario_steps"] or any(not isinstance(x, str) or not x.strip() for x in raw["scenario_steps"]):
                raise ValueError("checker missing behavior steps")
            keys = raw.get("concern_keys")
            if not isinstance(keys, list) or any(k not in ACTIVE_CONCERN_KEYS for k in keys) or len(keys) != len(set(keys)):
                raise ValueError("checker returned invalid concern keys")
            if raw["scenario_type"] != "requirement_exception" and keys:
                raise ValueError("nonexception scenes must not carry exception concerns")
            refs = validate_refs(raw.get("source_refs"), index, payload["sections"])
            scene = {k: raw.get(k, "") for k in ("name", "scenario_type", "preconditions", "trigger",
                     "scenario_steps", "expected_result", "recovery", "concern_keys")}
            scene.update({"use_case_id": payload["use_case_id"], "use_case_name": payload["use_case_name"],
                          "source_refs": refs, "target_sections": target_sections(index, payload["use_case_id"])})
            scene["scenario_id"] = "CHK-" + fingerprint([payload["use_case_id"], scene["scenario_type"],
                                                        scene["preconditions"], scene["trigger"],
                                                        scene["scenario_steps"], scene["expected_result"]])[:20]
            if scene["scenario_id"] in seen:
                raise ValueError("checker returned duplicate behavior")
            seen.add(scene["scenario_id"])
            validated.append(scene)
        if sum(s["scenario_type"] == "main_success" for s in validated) != 1:
            raise ValueError("checker must extract one main-success scenario per use case")
        return validated
    return validate


def merge_checker(index: dict, directory, use_cases: list[dict] | None = None) -> dict:
    scenes, status = collect_packets(directory, checker_validator(index))
    if use_cases is not None:
        expected = checker_packets(index, use_cases, Path(directory) / "_expected")
        actual = read_json(Path(directory) / "manifest.json")
        if actual["input_hash"] != expected["input_hash"]:
            status.update({"complete": False, "errors": {"manifest": "checker packet universe differs from source scope"}})
    result = {"schema_version": "three-agent-v1", "role": "checker", "complete": status["complete"],
              "source_hash": fingerprint(index), "batch_status": status,
              "scenario_count": len(scenes), "scenarios": scenes}
    if result["complete"]:
        scene_map(result)
    return result


def match_packets(generated: dict, checker: dict, directory, tile_size: int = 20) -> dict:
    gen, ref = scene_map(generated), scene_map(checker)
    payloads = []
    for uc in sorted({s["use_case_id"] for s in ref.values()} | {s["use_case_id"] for s in gen.values()}):
        gs = [s for s in gen.values() if s["use_case_id"] == uc]
        cs = [s for s in ref.values() if s["use_case_id"] == uc]
        # The entire same-UC cross product is inspected; no similarity prefilter.
        if not gs or not cs:
            continue
        for gi in range(0, len(gs), tile_size):
            for ci in range(0, len(cs), tile_size):
                payloads.append({"use_case_id": uc, "generated": gs[gi:gi+tile_size],
                                 "checker": cs[ci:ci+tile_size]})
    return prepare_packets(directory, "matching", payloads, [
        "Inspect EVERY checker/generated pair in the assigned tile semantically. Return links only for full or partial matches.",
        "full requires the same trigger, core behavior and expected result. partial requires a concrete shared condition/behavior, and must state what is missing.",
        "Sharing a concern label, topic, use-case ID or a main-flow prefix alone is NOT a match. Incompatible outcomes are not matches.",
        "An unreviewed generated candidate can partially match an explicit exception if its specific failure condition aligns; do not invent its response.",
        "Return checked_checker_ids and checked_generated_ids listing EVERY assigned ID even for items having no match.",
    ], {"checked_checker_ids": ["all tile checker IDs"], "checked_generated_ids": ["all tile generated IDs"],
        "matches": [{"checker_scenario_id": "CHK-ID", "generated_scenario_id": "GEN-ID",
                     "status": "full|partial", "evidence": "specific behavior evidence",
                     "missing_behavior": ["required for partial; empty for full"]}]})


def matching_validator(packet, result):
    gen = {s["scenario_id"] for s in packet["input"]["generated"]}
    ref = {s["scenario_id"] for s in packet["input"]["checker"]}
    for field, expected in (("checked_generated_ids", gen), ("checked_checker_ids", ref)):
        values = result.get(field)
        if not isinstance(values, list) or set(values) != expected or len(values) != len(expected):
            raise ValueError(f"matching omitted or duplicated {field}")
    links, seen = result.get("matches"), set()
    if not isinstance(links, list):
        raise ValueError("missing matching links")
    for link in links:
        pair = (link.get("checker_scenario_id"), link.get("generated_scenario_id"))
        if pair[0] not in ref or pair[1] not in gen or pair in seen:
            raise ValueError("unknown or duplicate matching pair")
        seen.add(pair)
        if link.get("status") not in {"full", "partial"} or not str(link.get("evidence", "")).strip():
            raise ValueError("matching needs a semantic status and evidence")
        missing = link.get("missing_behavior")
        if (not isinstance(missing, list) or any(not isinstance(x, str) or not x for x in missing)
                or (link["status"] == "partial" and not missing)
                or (link["status"] == "full" and missing)):
            raise ValueError("partial match missing behavioral gaps")
    return links


def merge_matches(generated: dict, checker: dict, directory) -> dict:
    from .matching_audit import audited_matching_validator
    links, status = collect_packets(directory, audited_matching_validator)
    # Reconstruct expected packet universe, detecting a manifest with missing tiles.
    expected_directory = Path(directory) / "_expected"
    expected = match_packets(generated, checker, expected_directory)
    actual = read_json(Path(directory) / "manifest.json")
    if actual["input_hash"] != expected["input_hash"]:
        status.update({"complete": False, "errors": {"manifest": "matching packet universe differs from inputs"}})
    models = set()
    for batch in actual["batches"]:
        path = Path(directory) / "results" / (batch["batch_id"] + ".json")
        if path.exists():
            model = read_json(path).get("semantic_verification", {}).get("model")
            if model:
                models.add(model)
    return {"schema_version": "three-agent-v1", "complete": status["complete"], "backend": "agent",
            "input_hash": fingerprint([generated, checker]), "batch_status": status,
            "verification_models": sorted(models), "matches": links}


def embedding_matches(generated: dict, checker: dict, client, full: float = .85, partial: float = .70) -> dict:
    if not 0 <= partial < full <= 1:
        raise ValueError("need 0 <= partial threshold < full threshold <= 1")
    gs, cs = list(scene_map(generated).values()), list(scene_map(checker).values())
    vectors = client.embeddings([scene_text(s) for s in gs + cs])
    gvec, cvec = vectors[:len(gs)], vectors[len(gs):]
    links = []
    for i, c in enumerate(cs):
        for j, g in enumerate(gs):
            if c["use_case_id"] != g["use_case_id"]:
                continue
            score = cosine(cvec[i], gvec[j])
            if score >= partial:
                status = "full" if score >= full else "partial"
                links.append({"checker_scenario_id": c["scenario_id"], "generated_scenario_id": g["scenario_id"],
                              "status": status, "similarity": score,
                              "evidence": f"Embedding cosine={score:.6f}; uncalibrated thresholds",
                              "missing_behavior": ["相似度处于部分匹配区间，具体行为差异待人工确认"] if status == "partial" else []})
    return {"schema_version": "three-agent-v1", "complete": True, "backend": "embedding",
            "input_hash": fingerprint([generated, checker]), "model": client.model("embedding"),
            "thresholds": {"full": full, "partial": partial, "calibrated": False},
            "matches": links}


def evidence_contexts(candidates: list[dict], index: dict, client=None, rerank: bool = False) -> dict:
    if rerank and client is None:
        raise ValueError("rerank needs a configured semantic client")
    result = {}
    for scene in candidates:
        evidence = evidence_fragments(index, scene["use_case_id"])
        if rerank and evidence:
            vectors = client.embeddings([scene_text(scene)] + [e["text"] for e in evidence])
            ranked = sorted(({**e, "embedding_similarity": cosine(vectors[0], v)}
                             for e, v in zip(evidence, vectors[1:])),
                            key=lambda e: e["embedding_similarity"], reverse=True)[:20]
            evidence = client.rerank(scene_text(scene), ranked)
        result[scene["scenario_id"]] = evidence
    return result


def recommendation_packets(report: dict, index: dict, directory, client=None, rerank: bool = False) -> dict:
    if report.get("complete") is not True:
        raise ValueError("recommendations need complete matching metrics")
    candidates = report["overall"]["unmatched_generated_scenarios"]
    contexts = evidence_contexts(candidates, index, client, rerank)
    # Reuse individually grounded scores when a changed match set moves a candidate
    # into a different batch. Candidate, evidence and enhancement must be identical.
    cache = {}
    root = Path(directory)
    for old_packet_path in (root / "packets").glob("*.json"):
        old = read_json(old_packet_path)
        result_path = root / "results" / old_packet_path.name
        if not result_path.exists():
            continue
        try:
            raw = read_json(result_path)
            if raw.get("input_hash") != old.get("input_hash") or raw.get("batch_id") != old.get("batch_id"):
                continue
            if fingerprint({k: v for k, v in old.items() if k not in {"input_hash", "batch_id"}}) != old["input_hash"]:
                continue
            scores = {s["scenario_id"]: s for s in recommendation_validator(index)(old, raw)}
            for s in old["input"]["candidates"]:
                key = fingerprint([s, old["input"]["evidence"][s["scenario_id"]], old["input"]["rerank"]])
                score = scores[s["scenario_id"]]
                from .support_audit import check_support
                if score.get("support_verification"):
                    check_support(old, score)
                if key not in cache or (score.get("support_verification") and not cache[key].get("support_verification")):
                    cache[key] = score
        except (ValueError, KeyError, TypeError):
            continue
    keys = {s["scenario_id"]: fingerprint([s, contexts[s["scenario_id"]], rerank]) for s in candidates}
    payloads = []
    for known in (True, False):
        group = [s for s in candidates if (keys[s["scenario_id"]] in cache) == known]
        payloads.extend({"candidates": group[i:i+8], "evidence": {
            s["scenario_id"]: contexts[s["scenario_id"]] for s in group[i:i+8]}, "rerank": rerank}
            for i in range(0, len(group), 8))
    manifest = prepare_packets(directory, "recommendation", payloads, [
        "Score EVERY candidate, retaining low-support candidates. These candidates already have no full or partial match.",
        "support_score (0..1): 0=no relevant evidence; .25=only generic topic; .5=specific interface/SSD context; .75=explicit constraint supports failure mechanism; 1=direct verifiable evidence. Relevance alone is not logical support.",
        "missing_score (0..1) measures how clearly this behavior is not explicitly described in assigned source sections; explain ambiguity or conflicting descriptions.",
        "Use evidence in supplied order (reranked when enabled). Cite supplied source_ref objects. Never invent limits, error codes or recovery policies.",
        "Return exactly one item per candidate with concrete reasons, evidence_refs and both scores. Empty evidence_refs is allowed only with support_score=0.",
    ], {"items": [{"scenario_id": "GEN-ID", "support_score": .5, "missing_score": .8,
                  "basis": "specific rationale", "evidence_refs": [{"document": "filename", "line_start": 1, "line_end": 2}]}]})
    for batch, payload in zip(manifest["batches"], payloads):
        if all(keys[s["scenario_id"]] in cache for s in payload["candidates"]):
            packet = read_json(root / "packets" / (batch["batch_id"] + ".json"))
            result = {**batch, "items": [cache[keys[s["scenario_id"]]] for s in payload["candidates"]],
                      "reused_candidate_scores": True}
            recommendation_validator(index)(packet, result)
            write_json(root / "results" / (batch["batch_id"] + ".json"), result)
    return manifest


def recommendation_validator(index: dict):
    def validate(packet, result):
        expected = {s["scenario_id"] for s in packet["input"]["candidates"]}
        items, seen = result.get("items"), set()
        if not isinstance(items, list):
            raise ValueError("missing recommendations")
        validated = []
        for raw in items:
            sid = raw.get("scenario_id")
            if sid not in expected or sid in seen:
                raise ValueError("unknown or duplicate recommendation")
            seen.add(sid)
            for key in ("support_score", "missing_score"):
                score = raw.get(key)
                if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError("invalid recommendation score")
            if not isinstance(raw.get("basis"), str) or not raw["basis"].strip():
                raise ValueError("recommendation needs rationale")
            refs = raw.get("evidence_refs")
            if not isinstance(refs, list):
                raise ValueError("missing evidence_refs")
            allowed = [e["source_ref"] for e in packet["input"]["evidence"][sid]]
            if refs:
                try:
                    refs = validate_refs(refs, index, allowed)
                except ValueError as exc:
                    raise ValueError(f"{sid}: {exc}; copy only this candidate's supplied source_ref objects") from exc
            elif raw["support_score"] != 0:
                raise ValueError("positive support requires source evidence")
            validated.append({**raw, "evidence_refs": refs,
                              "ranked_evidence": packet["input"]["evidence"][sid]})
        if seen != expected:
            raise ValueError("recommendation batch omitted candidates")
        return validated
    return validate


def finish_recommendations(report: dict, items: list[dict], backend: str, rerank: bool, complete: bool) -> dict:
    candidates = {s["scenario_id"]: s for s in report["overall"]["unmatched_generated_scenarios"]}
    ids = [i["scenario_id"] for i in items]
    if complete and (len(ids) != len(set(ids)) or set(ids) != set(candidates)):
        raise ValueError("recommendation set differs from unmatched generated set")
    rows = []
    for item in items:
        confidence = .7 * item["support_score"] + .3 * item["missing_score"]
        rows.append({**candidates[item["scenario_id"]], **item, "confidence": confidence,
                     "confidence_kind": "heuristic_recommendation_score_not_probability",
                     "priority": "high" if confidence >= .75 else "medium" if confidence >= .5 else "needs_confirmation"})
    rows.sort(key=lambda r: (-r["confidence"], r["scenario_id"]))
    return {"schema_version": "three-agent-v1", "complete": complete, "backend": backend,
            "rerank": rerank, "weights": {"support": .7, "missing": .3},
            "input_hash": report["input_hash"], "recommendation_count": len(rows), "items": rows}


def merge_recommendations(report: dict, index: dict, directory, rerank: bool = False) -> dict:
    from .support_audit import audited_recommendation_validator
    items, status = collect_packets(directory, audited_recommendation_validator(index))
    manifest = read_json(Path(directory) / "manifest.json")
    for batch in manifest["batches"]:
        packet = read_json(Path(directory) / "packets" / (batch["batch_id"] + ".json"))
        if packet["input"]["rerank"] != rerank:
            raise ValueError("recommendation batch rerank configuration differs")
    result = finish_recommendations(report, items, "agent", rerank, status["complete"])
    result["batch_status"] = status
    return result


def embedding_recommendations(report: dict, checker: dict, index: dict, client, rerank=False) -> dict:
    candidates = report["overall"]["unmatched_generated_scenarios"]
    existing = list(scene_map(checker).values())
    existing_vectors = client.embeddings([scene_text(s) for s in existing])
    contexts = evidence_contexts(candidates, index, client, rerank)
    items = []
    for scene in candidates:
        evidence = contexts[scene["scenario_id"]]
        vectors = client.embeddings([scene_text(scene)] + ([] if rerank else [e["text"] for e in evidence]))
        same_uc = [v for s, v in zip(existing, existing_vectors) if s["use_case_id"] == scene["use_case_id"]]
        nearest = max((cosine(vectors[0], v) for v in same_uc), default=0)
        if rerank:
            scores = [e["rerank_score"] for e in evidence]
        else:
            scores = [cosine(vectors[0], v) for v in vectors[1:]]
            evidence = [{**e, "embedding_similarity": score} for e, score in zip(evidence, scores)]
        best = max(range(len(scores)), key=lambda i: scores[i]) if scores else None
        support = scores[best] if best is not None else 0
        items.append({"scenario_id": scene["scenario_id"], "support_score": support,
                      "missing_score": 1 - nearest, "nearest_existing_similarity": nearest,
                      "evidence_refs": [evidence[best]["source_ref"]] if best is not None else [],
                      "ranked_evidence": sorted(evidence, key=lambda e: e.get("rerank_score", e.get("embedding_similarity", 0)), reverse=True),
                      "basis": "证据相关度代理（非逻辑证明）与已有场景距离的加权评分"})
    return finish_recommendations(report, items, "embedding", rerank, True)
