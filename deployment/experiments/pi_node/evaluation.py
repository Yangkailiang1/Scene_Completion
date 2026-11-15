"""Independent source-backed review and conservative paired decisions."""

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json

COUNT_FIELDS = ("omissions", "wrong_bindings", "unsupported_additions", "invalid_citations")


def public_result(path):
    value = read_json(path)
    value.pop("execution_model_evidence", None)
    return value


def submit_review(root, path):
    value = read_json(path)
    review_id = value.get("review_id")
    mapping = read_json(root / "blinding-private.json")
    execution = next((k for k, v in mapping.items() if v == review_id), None)
    if execution is None:
        raise ValueError("Unknown blinded review identity")
    result_path = root / "executions" / execution / "result.json"
    summary = read_json(result_path.parent / "summary.json")
    if value.get("input_hash") != summary["input_hash"] or value.get("result_hash") != fingerprint(
        public_result(result_path)
    ):
        raise ValueError("Review is bound to a different input/result")
    rubric = value.get("rubric", {})
    if value.get("reviewed") is not True or type(rubric.get("business_correct")) is not bool:
        raise ValueError("Review must explicitly judge business correctness")
    for key in COUNT_FIELDS:
        if type(rubric.get(key)) is not int or rubric[key] < 0:
            raise ValueError("Review counts must be nonnegative integers: " + key)
    if not value.get("source_checks") or any(
        not isinstance(r, dict) or not r.get("location") or not r.get("finding")
        for r in value["source_checks"]
    ):
        raise ValueError("Review requires explicit source locations and findings")
    for key in ("template_completeness", "match_accuracy"):
        score = rubric.get(key)
        required = (
            key == "template_completeness"
            and summary["task"] == "ssd-generate"
            or key == "match_accuracy"
            and summary["task"] == "ssd-semantic-compare"
        )
        if score is None and not required:
            continue
        if (
            not isinstance(score, dict)
            or any(type(score.get(k)) is not int for k in ("passed", "total"))
            or not 0 <= score["passed"] <= score["total"]
            or score["total"] < 1
        ):
            raise ValueError("Review score must supply passed/total: " + key)
    target = root / "reviews" / (review_id + ".json")
    if target.exists() and read_json(target) != value:
        old = read_json(target)
        write_json(root / "review-history" / (fingerprint(old) + ".json"), old)
    write_json(target, value)
    return {"status": "reviewed", "review_id": review_id, "production_results_modified": False}


def qualified(review):
    rubric = review["rubric"]
    return rubric["business_correct"] and not any(rubric[k] for k in COUNT_FIELDS)


def compare(pairs, root, mapping):
    totals = {
        arm: {
            "deliveries": 0,
            "first_submission_passes": 0,
            "qualified": 0,
            "sent_requests": 0,
            "reported_tokens": 0,
            "elapsed_seconds": 0,
            "repair_attempts": 0,
            "business_errors": 0,
        }
        for arm in ("A", "B")
    }
    eligible = 0
    for pair in pairs:
        if not pair["provider_comparable"]:
            continue
        reviewed = {}
        for arm in ("A", "B"):
            row = pair[arm]
            execution = pair["executions"][arm]
            path = root / "reviews" / (mapping[execution] + ".json")
            if row["status"] == "delivered" and not path.exists():
                break
            reviewed[arm] = read_json(path) if path.exists() else None
        if len(reviewed) != 2:
            continue
        eligible += 1
        for arm in ("A", "B"):
            row, out = pair[arm], totals[arm]
            out["deliveries"] += row["status"] == "delivered"
            out["first_submission_passes"] += row["first_submission_passed"]
            for key in ("sent_requests", "reported_tokens", "elapsed_seconds", "repair_attempts"):
                out[key] += row[key]
            if reviewed[arm]:
                out["qualified"] += qualified(reviewed[arm])
                out["business_errors"] += sum(reviewed[arm]["rubric"][k] for k in COUNT_FIELDS)
    for values in totals.values():
        values["tokens_per_qualified_result"] = (
            values["reported_tokens"] / values["qualified"] if values["qualified"] else None
        )
        values["delivery_rate"] = values["deliveries"] / eligible if eligible else None
        values["first_submission_rate"] = (
            values["first_submission_passes"] / eligible if eligible else None
        )
    if eligible != 2:
        return {
            "recommendation": "证据不足",
            "reason": "需两轮同模型配对及独立业务审核",
            "eligible_pairs": eligible,
            "totals": totals,
        }
    a, b = totals["A"], totals["B"]
    quality_win = b["qualified"] > a["qualified"] and b["business_errors"] <= a["business_errors"]
    efficiency_win = (
        b["qualified"] == a["qualified"] == 2
        and b["business_errors"] == a["business_errors"]
        and (
            b["reported_tokens"] <= 0.8 * a["reported_tokens"]
            and b["elapsed_seconds"] <= 1.1 * a["elapsed_seconds"]
            or b["elapsed_seconds"] <= 0.8 * a["elapsed_seconds"]
            and b["reported_tokens"] <= 1.1 * a["reported_tokens"]
        )
    )
    return {
        "recommendation": "适合试用 Pi" if quality_win or efficiency_win else "保持当前实现",
        "reason": "小样本观察：质量改善或合格率相同且成本/耗时降低至少20%"
        if quality_win or efficiency_win
        else "未观察到足以替换现有实现的收益，质量相当时保留当前实现",
        "eligible_pairs": eligible,
        "totals": totals,
        "generalized_superiority_claim": False,
    }
