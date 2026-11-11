"""Public commands for the scene-workflow-v5 protocol."""

import argparse
import json
from pathlib import Path

from scene_completion.analysis.evaluation import UNITS, accuracy
from scene_completion.analysis.interaction_enrichment import capability_union
from scene_completion.domain.contracts import TASKS, packet
from scene_completion.infrastructure.storage import read_json, write_json
from scene_completion.inputs.source_documents import read_documents
from scene_completion.workflow.engine import Execution, build_pipeline, payload
from scene_completion.workflow_core import run_lock


def client_for(config, root, env_file=None):
    from scene_completion.models.http_transport import load_ecnu_env_file
    from scene_completion.models.model_configuration import referenced_env_keys

    if env_file and Path(env_file).exists():
        load_ecnu_env_file(env_file, referenced_env_keys(config))
    config = dict(config)
    config.setdefault("cache_dir", str(root / "model_cache"))
    if config.get("agent_runtime") == "deepagents":
        from scene_completion.models.deepagents_client import DeepAgentsClient

        config["run_root"] = str(root)
        config.setdefault("indexed_context", True)
        return DeepAgentsClient(config)
    if config.get("agent_runtime") == "luna-subprocess":
        from scene_completion.models.native_client import NativeClient

        config.update(native_run_root=str(root), native_run_dir=str(root / "native"))
        return NativeClient(config)
    from scene_completion.models.model_client import SemanticClient

    return SemanticClient(config)


def parser():
    p = argparse.ArgumentParser(
        description="Scene workflow: isolated inputs, layered concerns, bounded execution"
    )
    sub = p.add_subparsers(dest="command", required=True)
    pipe = sub.add_parser("pipeline")
    pipe.add_argument("--rr-spec-document", action="append", required=True)
    pipe.add_argument("--sr-spec-document", action="append", required=True)
    pipe.add_argument("--ar-spec-document", action="append", default=[])
    pipe.add_argument("--test-spec-document", action="append", default=[])
    pipe.add_argument("--use-case-id", action="append")
    pipe.add_argument("--extraction-truth", help="JSON map of task/case:task to manual GT payload")
    pipe.add_argument("--review-mode", choices=("manual", "auto"), default="auto")
    pipe.add_argument(
        "--adjudications", help="JSON map to input-bound confirmed semantic extraction decisions"
    )
    pipe.add_argument(
        "--no-supplement-tests",
        action="store_true",
        help="仅用原始异常测试计分，不补充独立异常测试",
    )
    task = sub.add_parser("task")
    task.add_argument("--task", choices=TASKS, required=True)
    task.add_argument("--input-json", required=True)
    for a in (pipe, task):
        a.add_argument("--output-dir", required=True)
        a.add_argument("--agent-mode", choices=("packets", "external"), default="packets")
        a.add_argument("--responses-dir")
        a.add_argument("--config")
        a.add_argument("--env-file", default=".env")
        a.add_argument("--max-repair-rounds", type=int, choices=(0, 1, 2), default=2)
    score = sub.add_parser("score-extraction")
    score.add_argument("--task", choices=UNITS, required=True)
    for name in ("extracted", "truth", "output"):
        score.add_argument("--" + name, required=True)
    score.add_argument(
        "--decisions",
        help="input-bound semantic decisions (or explicit reviewed JSON decision list)",
    )
    draw = sub.add_parser("render-composition")
    draw.add_argument("--input-json", required=True)
    draw.add_argument("--output-svg", required=True)
    check = sub.add_parser("check-run")
    check.add_argument("--run-dir", required=True)
    return p


def unwrap(v):
    if isinstance(v, dict) and "protocol" in v:
        return payload(v)
    return v


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "render-composition":
        from scene_completion.analysis.composition_drawing import render_composition
        from scene_completion.domain.contracts import validate

        value = unwrap(read_json(args.input_json))
        validate("components", value)
        render_composition(value, args.output_svg)
        return 0
    if args.command == "score-extraction":
        value = accuracy(
            args.task,
            unwrap(read_json(args.extracted)),
            unwrap(read_json(args.truth)),
            read_json(args.decisions) if args.decisions else None,
        )
        write_json(args.output, value)
        return 0
    if args.command == "check-run":
        from scene_completion.workflow.run_inspection import inspect_run

        result = inspect_run(Path(args.run_dir))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 2
    independent = args.command == "task"
    if independent:
        inputs = read_json(args.input_json)
    else:
        groups = [
            {str(Path(p).resolve()) for p in paths}
            for paths in (
                args.rr_spec_document,
                args.sr_spec_document,
                args.ar_spec_document,
                args.test_spec_document,
            )
        ]
        if sum(len(group) for group in groups) != len(set().union(*groups)):
            raise ValueError("RR/SR/AR/test must be distinct files")
        rr = read_documents(args.rr_spec_document, "existing")
        sr = read_documents(args.sr_spec_document, "existing")
        ar = read_documents(args.ar_spec_document, "existing")
        tests = read_documents(args.test_spec_document, "test")
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if independent:
        from scene_completion.domain.concern_registry import default_registry, registry_scope

        with registry_scope(
            read_json(root / "registry_override.json")
            if (root / "registry_override.json").exists()
            else default_registry()
        ):
            packet(args.task, inputs)
    config = read_json(args.config) if args.config else {}
    if not independent:
        config.update(
            review_mode=args.review_mode,
            supplement_tests=not args.no_supplement_tests,
            scenario_patterns=True,
        )
    with run_lock(root):
        deterministic = independent and args.task in {"object-operations", "gap-recommend"}
        client = (
            client_for(config, root, args.env_file)
            if args.agent_mode == "external" and not deterministic
            else None
        )
        ex = Execution(
            root,
            mode=args.agent_mode,
            client=client,
            config=getattr(client, "config", config),
            responses_dir=args.responses_dir,
            case_ids=getattr(args, "use_case_id", None),
            max_rounds=args.max_repair_rounds,
        )
        if independent:
            transform = (
                capability_union
                if args.task == "object-operations"
                else (lambda d: {"enabled": False, "status": "未启用"})
                if args.task == "gap-recommend"
                else None
            )
            ex.add(args.task, args.task, static=inputs, transform=transform)
        else:
            build_pipeline(
                ex,
                rr,
                sr,
                tests,
                read_json(args.extraction_truth) if args.extraction_truth else None,
                read_json(args.adjudications) if args.adjudications else None,
                ar=ar,
            )
        result = ex.finish()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["complete"] else 2
