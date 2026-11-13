"""Replay positive scenario tools against frozen recognized concerns, without LLM calls.

This writes a separate diagnostic, never rewrites a project or claims that new
scenes have been semantically evaluated against the existing E/GT decisions.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scene_completion.analysis.evaluation.scenario_losses import summarize
from scene_completion.analysis.interactions.interaction_enrichment import (
    actual_context,
    basic_views,
    bind_resource_services,
)
from scene_completion.analysis.matching.concern_alignment import VERSION, definite, recognize
from scene_completion.analysis.recommendation.scenario_patterns import applicability, generated
from scene_completion.compat.saved.result_views import ResultView
from scene_completion.domain.contracts import validate
from scene_completion.infrastructure.storage import fingerprint, write_json
from scene_completion.inputs.documents.api_documents import case_parameters


def replay(project, cases=None):
    view = ResultView(project)
    result = {
        "version": VERSION,
        "mode": "offline-positive-tool-replay",
        "model_calls": 0,
        "official_metrics_recomputed": False,
        "cases": [],
    }
    for cid in cases or [c["id"] for c in view.cases()]:
        prior = view.payload(cid + ":exception-generate")
        enriched = view.payload(cid + ":enriched-view")
        matches = view.payload(cid + ":concern-match")
        if not enriched or not matches:
            result["cases"].append({"case_id": cid, "status": "缺少冻结正向产物"})
            continue
        material = {
            k: view.payload(
                k if k in {"components", "api-map", "api-parameters"} else cid + ":" + k
            )
            for k in ("components", "api-map", "api-parameters", "normal-rules", "rr-ssd", "sr-ssd")
        }
        inputs = bind_resource_services(material)
        inputs.update(basic_views(enriched))
        inputs["api-parameters"] = case_parameters(inputs, enriched)
        inputs.update({"enriched-interactions": actual_context(enriched), "concern-match": matches})
        inputs["business-entities"] = view.payload("business-entities")
        inputs["business-crud"] = view.payload(cid + ":business-crud")
        valid, rejected = [], []
        for row in matches.get("matches", []):
            try:
                valid.extend(recognize(inputs, {"matches": [row]}, relocate=False)["matches"])
            except ValueError as error:
                rejected.append(
                    {
                        "binding_id": row.get("binding_id"),
                        "interaction_id": row["interaction_id"],
                        "concern_key": row["concern_key"],
                        "error": str(error),
                    }
                )
        inputs["concern-match"] = {"matches": valid, "pending": []}
        matrix = applicability(inputs)
        value = generated(matrix)
        validate("pattern-applicability", matrix)
        validate("exception-generate", value)
        represented = {bid for s in value["scenarios"] for bid in s.get("concern_binding_ids", [])}
        gaps = [
            {k: row.get(k) for k in ("binding_id", "interaction_id", "object", "concern_key")}
            for bid, row in definite(inputs["concern-match"]).items()
            if bid not in represented
        ]
        evaluation = view.payload(cid + ":exception-evaluation")
        evaluation = evaluation.get("original_evaluation", evaluation)
        scoped = view.scoped(cid, evaluation, evaluation.get("concern_level", {}))
        result["cases"].append(
            {
                "case_id": cid,
                "status": "工具重放通过，语义重验未执行",
                "frozen_input_hash": fingerprint(inputs),
                "before": dict(Counter(s["concern_key"] for s in prior.get("scenarios", []))),
                "after": dict(Counter(s["concern_key"] for s in value["scenarios"])),
                "represented_scene_links": dict(
                    Counter(
                        k
                        for s in value["scenarios"]
                        for k in set(s.get("concern_origins", [s["concern_key"]]))
                    )
                ),
                "recognized_without_scene": gaps,
                "recognition_repairs_required": rejected,
                "new_scenarios": value,
                "saved_report_diagnostic": summarize(scoped),
                "normalization_exclusions": matrix["excluded"],
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    project, output = Path(args.project).resolve(), Path(args.output).resolve()
    if output.is_relative_to(project):
        parser.error("replay output must be outside the source project")
    report = replay(project, args.case)
    write_json(output, report)
    print(
        json.dumps(
            {
                "cases": len(report["cases"]),
                "model_calls": 0,
                "official_metrics_recomputed": False,
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
