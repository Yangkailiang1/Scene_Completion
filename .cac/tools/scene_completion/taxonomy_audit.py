"""Independently verify classification claims, without changing checker behavior."""
from .sources import fingerprint

VERSION = "requirement-taxonomy-proof-v1"


def context(packet, result):
    return {"input": packet["input"], "proposed_items": result.get("items")}


def validate_verdicts(packet, verdicts):
    expected = {s["scenario_id"]: s for s in packet["input"]["scenarios"]}
    allowed = {t["key"] for t in packet["input"]["taxonomy"]}
    if not isinstance(verdicts, list) or len(verdicts) != len(expected):
        raise ValueError("taxonomy verification omitted checker scenes")
    seen, items = set(), []
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            raise ValueError("taxonomy verification verdict must be an object")
        sid = verdict.get("scenario_id")
        if sid not in expected or sid in seen:
            raise ValueError("taxonomy verification has unknown/duplicate scene")
        if verdict.get("trigger_quote") != expected[sid]["trigger"]:
            raise ValueError("taxonomy verification trigger quote belongs to another scene")
        seen.add(sid)
        assessments = verdict.get("assessments")
        if not isinstance(assessments, list):
            raise ValueError("taxonomy verification needs explicit key assessments")
        keys = set()
        for assessment in assessments:
            if (not isinstance(assessment, dict) or assessment.get("key") not in allowed or
                    assessment["key"] in keys or type(assessment.get("supported")) is not bool or
                    not isinstance(assessment.get("reason"), str) or not assessment["reason"].strip()):
                raise ValueError("invalid taxonomy key assessment")
            keys.add(assessment["key"])
        items.append({"scenario_id": sid,
                      "concern_keys": sorted(a["key"] for a in assessments if a["supported"]),
                      "reason": verdict.get("reason"), "source_refs": verdict.get("source_refs")})
    return items


def audited_taxonomy_validator(index):
    from .checker_taxonomy import taxonomy_validator
    validate = taxonomy_validator(index)
    def audited(packet, result):
        items = validate(packet, result)
        proof = result.get("classification_verification")
        if not isinstance(proof, dict) or proof.get("version") != VERSION:
            raise ValueError("taxonomy labels require independent source-only verification")
        proposed = proof.get("proposed_items")
        validate(packet, {"items": proposed})
        if proof.get("input_hash") != fingerprint(context(packet, {"items": proposed})):
            raise ValueError("stale taxonomy verification")
        verdicts = proof.get("verdicts")
        if validate(packet, {"items": validate_verdicts(packet, verdicts)}) != items:
            raise ValueError("taxonomy labels differ from verified decisions")
        proposed_keys = {row["scenario_id"]: set(row["concern_keys"]) for row in proposed}
        for verdict in verdicts:
            if not proposed_keys[verdict["scenario_id"]] <= {a["key"] for a in verdict["assessments"]}:
                raise ValueError("taxonomy verification omitted a proposed key")
        return items
    return audited


def verify_taxonomy(packet, result, client, index):
    from .checker_taxonomy import taxonomy_validator
    validate = taxonomy_validator(index)
    validate(packet, result)
    try:
        audited_taxonomy_validator(index)(packet, result)
        return result
    except ValueError:
        pass
    proposed = result.get("classification_verification", {}).get("proposed_items", result["items"])
    generator = packet["stage"] == "generator-taxonomy"
    request = {"stage": "generator-taxonomy-verification" if generator else "checker-taxonomy-verification", "input": context(packet, {"items": proposed}),
        "instructions": [
            ("Independently verify EACH frozen requirement exception and EVERY proposed classification key against the original requirement and taxonomy. No G, design or tests are available." if not generator else
             "Verify every supplied explicit branch/source constraint label against the supplied original requirement/design and taxonomy. No C, matches, tests or applicability decisions are provided. Preserve every scene's ID, behavior and count."),
            "Copy its complete trigger verbatim. Return every scenario_id exactly once. Do not change behavior, IDs, or the denominator.",
            "For each proposed key return supported true/false and a reason; add an omitted key only if its definition directly expresses the specific failure mechanism.",
            "Do not retain a key that your rationale excludes. A duplicate valid callback is not an external contract/format violation. Business qualification/permit expiry is not automatically an expired login token.",
            "Do not infer database implementation or cross-service consistency from a business entity alone. Internal service failures are not third-party calls. A timeout label needs a timeout condition.",
            "Resource/state/business-rule failures can be expressed by existing definitions. Empty keys mean a genuine remaining taxonomy gap, with an explanation.",
            "Selected concern_keys are derived ONLY from supported assessments. Cite exact assigned requirement lines and explain the final classification.",
        ], "output_contract": {"verdicts": [{"scenario_id": "each frozen ID", "trigger_quote": "exact complete trigger",
            "assessments": [{"key": "each proposed key, plus evidenced additions", "supported": True,
                              "reason": "specific mechanism and definition"}],
            "reason": "final classification rationale", "source_refs": [{"document": "requirement filename",
                                                                          "line_start": 1, "line_end": 2}]}]}}
    error = None
    for _ in range(2):
        if error: request["validation_feedback"] = error
        try:
            verdicts = client.agent(request).get("verdicts")
            items = validate(packet, {"items": validate_verdicts(packet, verdicts)})
            verified = {**result, "items": items, "classification_verification": {
                "version": VERSION, "input_hash": fingerprint(context(packet, {"items": proposed})),
                "proposed_items": proposed, "verdicts": verdicts, "model": client.model("agent")}}
            audited_taxonomy_validator(index)(packet, verified)
            return verified
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
    raise ValueError("taxonomy verification failed: " + str(error))
