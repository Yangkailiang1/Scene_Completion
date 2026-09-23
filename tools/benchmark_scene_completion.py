#!/usr/bin/env python3
"""Repeatable, network-free benchmark for the Scene Completion hot paths.

Run from the repository after the optimization commit:
    python3 -B tools/benchmark_scene_completion.py --baseline-revision d2295a4
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_scene_completion import sample_model
from tools.scene_completion import assembly, concerns, review
from tools.scene_completion.schemas import validate_scene_model


def _load_git_module(revision: str, relative_path: str, module_name: str) -> ModuleType:
    source = subprocess.check_output(
        ["git", "show", f"{revision}:{relative_path}"], cwd=ROOT, text=True
    )
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    if spec is None:
        raise RuntimeError(f"cannot create module spec for {module_name}")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "tools.scene_completion"
    sys.modules[module_name] = module
    exec(compile(source, f"{revision}:{relative_path}", "exec"), module.__dict__)
    return module


def _benchmark_model() -> dict[str, Any]:
    base = sample_model()
    base["version"] = "6"
    source_uc = base["use_cases"][0]
    source_interactions = base["interactions"]
    model = copy.deepcopy(base)
    model["use_cases"] = []
    model["interactions"] = []
    for index in range(1, 15):
        use_case = copy.deepcopy(source_uc)
        use_case_id = f"UC-{index:03d}"
        use_case.update({"use_case_id": use_case_id, "use_case_name": f"Benchmark Use Case {index}"})
        model["use_cases"].append(use_case)
        excluded = {"INT-LLM"} if index <= 9 else {"INT-EXT-DB"}
        if index <= 5:
            excluded.add("INT-EXT-CALLER")
        for interaction in source_interactions:
            if interaction["interaction_id"] in excluded:
                continue
            item = copy.deepcopy(interaction)
            item["use_case_id"] = use_case_id
            item["interaction_id"] = f"{use_case_id}-{interaction['interaction_id']}"
            model["interactions"].append(item)
    return validate_scene_model(model, raise_on_error=True)["normalized_model"]


def _median_seconds(operation: Callable[[], Any], repeats: int) -> tuple[float, Any]:
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = operation()
        samples.append(time.perf_counter() - started)
    return statistics.median(samples), result


def _fake_post(_url: str, _api_key: str, body: dict[str, Any], _timeout: float, _retries: int) -> dict[str, Any]:
    text = body["messages"][1]["content"]
    payload = json.loads(text.split("输入数据：", 1)[1])
    return {"choices": [{"message": {"content": json.dumps({
        "items": [{
            "concern_key": item["concern_key"],
            "status": "not_applicable",
            "basis": "固定基准：该合成交换不触发此原子异常。",
            "evidence_types": ["ssd"],
            "findings": [],
            "requirement_impact": "no",
            "subsequent_behavior_impact": "no",
            "environment_coordination_impact": "no",
        } for item in payload["candidates"]]
    }, ensure_ascii=False)}}]}


def _review_once(review_module: ModuleType, model: dict[str, Any], matrix: dict[str, Any], output: Path) -> dict[str, Any]:
    os.environ.setdefault("ECNU_MAX_API_KEY", "benchmark-placeholder")
    return review_module.review_concerns(
        model,
        {"use_cases": []},
        matrix,
        {"base_url": "https://benchmark.invalid/v1", "model": "mock", "max_concurrency": 3, "json_mode": False},
        output,
        post=_fake_post,
    )


def run(revision: str, repeats: int = 3) -> dict[str, Any]:
    old_concerns = _load_git_module(revision, "tools/scene_completion/concerns.py", "tools.scene_completion._benchmark_baseline_concerns")
    old_review = _load_git_module(revision, "tools/scene_completion/review.py", "tools.scene_completion._benchmark_baseline_review")
    model = _benchmark_model()

    baseline_plan_seconds, baseline_matrix = _median_seconds(lambda: old_concerns.plan_concern_matrix(model), repeats)
    optimized_plan_seconds, optimized_matrix = _median_seconds(lambda: concerns.plan_concern_matrix(model), repeats)
    if baseline_matrix["items"] != optimized_matrix["items"]:
        raise AssertionError("candidate matrix differs from baseline; benchmark will not compare unlike results")
    if len(optimized_matrix["items"]) < 1100 or len(optimized_matrix["items"]) > 1200:
        raise AssertionError(f"synthetic fixture drifted from expected scale: {len(optimized_matrix['items'])} candidates")
    # The fixture routes directly from normalized interactions rather than SSD JSON.
    # Use the stable interaction ID as its exchange ID for the batch-review harness.
    for matrix in (baseline_matrix, optimized_matrix):
        for item in matrix["items"]:
            if not item.get("exchange_id"):
                item["exchange_id"] = item.get("interaction_id", "")

    baseline_review_times = []
    optimized_review_times = []
    last_reviewed = None
    with tempfile.TemporaryDirectory(prefix="scene-completion-benchmark-") as tmp:
        temp_root = Path(tmp)
        for iteration in range(repeats):
            baseline_matrix_copy = copy.deepcopy(baseline_matrix)
            baseline_output = temp_root / f"baseline-{iteration}.json"
            started = time.perf_counter()
            _review_once(old_review, model, baseline_matrix_copy, baseline_output)
            baseline_review_times.append(time.perf_counter() - started)
            baseline_reviewed = json.loads(baseline_output.read_text(encoding="utf-8"))

            optimized_matrix_copy = copy.deepcopy(optimized_matrix)
            optimized_output = temp_root / f"optimized-{iteration}.json"
            started = time.perf_counter()
            _review_once(review, model, optimized_matrix_copy, optimized_output)
            optimized_review_times.append(time.perf_counter() - started)
            optimized_reviewed = json.loads(optimized_output.read_text(encoding="utf-8"))
            if [(item.get("concern_key"), item.get("status"), item.get("basis")) for item in baseline_reviewed["items"]] != [(item.get("concern_key"), item.get("status"), item.get("basis")) for item in optimized_reviewed["items"]]:
                raise AssertionError("mock-review judgement matrix differs from baseline")
            last_reviewed = optimized_reviewed

        assert last_reviewed is not None
        assemble_seconds, _ = _median_seconds(
            lambda: assembly.assemble_results(model, last_reviewed, {"findings": []}), repeats
        )

    baseline_review_seconds = statistics.median(baseline_review_times)
    optimized_review_seconds = statistics.median(optimized_review_times)
    return {
        "fixture": {"use_cases": len(model["use_cases"]), "interactions": len(model["interactions"]), "candidates": len(optimized_matrix["items"])},
        "repeats": repeats,
        "median_seconds": {
            "routing_baseline": round(baseline_plan_seconds, 6),
            "routing_optimized": round(optimized_plan_seconds, 6),
            "review_backfill_baseline_mock": round(baseline_review_seconds, 6),
            "review_backfill_optimized_mock": round(optimized_review_seconds, 6),
            "assembly": round(assemble_seconds, 6),
        },
        "speedup_percent": {
            "routing": round((baseline_plan_seconds - optimized_plan_seconds) / baseline_plan_seconds * 100, 2) if baseline_plan_seconds else 0,
            "review_backfill": round((baseline_review_seconds - optimized_review_seconds) / baseline_review_seconds * 100, 2) if baseline_review_seconds else 0,
        },
        "semantic_matrix_equal": True,
        "network_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-revision", default="d2295a4", help="git revision immediately before the performance changes")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error("--repeats must be at least 3")
    print(json.dumps(run(args.baseline_revision, args.repeats), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
