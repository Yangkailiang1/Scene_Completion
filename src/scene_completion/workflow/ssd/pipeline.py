"""Select cases, register SSD stage dependencies and publish workflow progress."""

import shutil
import time
from pathlib import Path

from scene_completion.application import ssd_revision_service as ssd_results
from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.infrastructure.storage import fingerprint, io_path, read_json, write_json
from scene_completion.workflow.ssd.compare.stage import _compare, _review_identity
from scene_completion.workflow.ssd.generate.stage import _generate
from scene_completion.workflow.ssd.resolve.stage import _resolve
from scene_completion.workflow.ssd.shared.semantic_execution import _semantic_cache_identity
from scene_completion.workflow.ssd.shared_services.stage import _project_scopes
from scene_completion.workflow.ssd_stages import label as stage_label
from scene_completion.workflow_core import Task


def enabled(ex):
    # Frozen v5 mock packets replay the old task contracts. Real runs and
    # explicit new-format fixture runs use the simplified graph by default.
    default = "legacy" if getattr(ex, "mocks", None) is not None else "ssd"
    return ex.config.get("workflow_mode", default) == "ssd"


def input_directory(ex):
    """Reconstruct frozen uploaded paths, never re-read mutable external inputs."""
    project = io_path(getattr(ex, "source_project", ex.root.parent)).resolve()
    pointer = project / "imports/ssd-input.json"
    if pointer.exists():
        root = (project / read_json(pointer)["path"]).resolve()
        if root.is_relative_to(project.resolve()) and root.is_dir():
            return root
    rows = ex.import_snapshot
    if not any((r.get("behavior_product") or {}).get("kind") == "system_operations" for r in rows):
        return None
    root = (
        (io_path(ex.root.parent) if getattr(ex, "is_preview", False) else project)
        / "imports/ssd-inputs"
        / fingerprint(rows)
    )
    for row in rows:
        rel = Path(row.get("relative_path") or row["name"])
        original = (project / row["original"]).resolve()
        if rel.is_absolute() or ".." in rel.parts or not original.is_relative_to(project.resolve()):
            continue
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
    meta = read_json(project / "project.json") if (project / "project.json").exists() else {}
    for items in meta.get("sources", {}).values():
        for row in items:
            original = project / row["path"]
            if original.is_file() and original.suffix.lower() in {".md", ".markdown"}:
                shutil.copy2(original, root / Path(row["name"]).name)
    return root


def _task(ex, cid, stage, deps, fn, identity=None, *, verify_payload=None):
    from scene_completion.infrastructure.code_retry import revision as code_retry_revision
    from scene_completion.workflow.recovery.node_repair import repair_revision
    from scene_completion.workflow.semantics import code_version

    if getattr(ex, "is_preview", False):
        key = cid + ":" + stage
        ex.add(key, stage, deps, case=cid, transform=lambda d: d)
        return key

    def execute(values, record):
        values = {k: v.get("payload", v) for k, v in values.items()}
        result = fn(values, record)
        return {
            "task": stage,
            "payload": result,
            "metadata": {
                "execution": {
                    "provider": "ssd_case_workflow",
                    "version": ssd_validation.VERSION,
                    "semantic_batches": record.get("semantic_sources", {}),
                }
            },
        }

    def verify(value):
        bundle = ssd_validation.validate(value["payload"])
        if verify_payload:
            verify_payload(bundle)

    task = Task(
        key=cid + ":" + stage,
        case=cid,
        stage=stage,
        deps=tuple(deps),
        version=fingerprint(
            [
                ssd_validation.VERSION,
                code_version(stage),
                stage,
                identity,
                ex.registry_snapshot,
                repair_revision(ex.root, cid + ":" + stage),
                _semantic_cache_identity(ex, stage),
                _review_identity(ex, cid) if stage == "ssd-compare" else None,
            ]
            + (
                ["code_retry", code_retry_revision(ex.root, cid + ":" + stage)]
                if code_retry_revision(ex.root, cid + ":" + stage)
                else []
            )
            + (
                [ex.conversations.revision(cid + ":" + stage)]
                if getattr(ex, "conversations", None)
                and ex.conversations.revision(cid + ":" + stage)
                else []
            )
        ),
        execute=execute,
        verify=verify,
        # Labels live in workflow/ssd_stages.py so the page, the generated
        # documentation and this pipeline cannot drift apart.
        display_label=stage_label(stage),
    )
    ex.scheduler.add(task)
    return task.key


def _tail(ex, cid, prepare):
    resolved = _task(ex, cid, "ssd-resolve", [prepare], lambda d, r: _resolve(ex, d[prepare], r))
    generated = _task(
        ex, cid, "ssd-generate", [resolved], lambda d, r: _generate(ex, d[resolved], r)
    )
    _task(ex, cid, "ssd-compare", [generated], lambda d, r: _compare(ex, d[generated], r))


def build_structured(ex, directory):
    from scene_completion.domain.concern_registry import default_registry
    from scene_completion.domain.current_scope import current_registry

    ex.registry_snapshot = current_registry(
        getattr(ex, "registry_snapshot", None) or default_registry()
    )
    from scene_completion.inputs.structured import authoring_cases
    from scene_completion.workflow.ssd.input_conversion.case_builder import (
        _input_root,
        case_identity,
    )
    from scene_completion.workflow.ssd.prepare import stage as prepare_stage
    from scene_completion.workflow.ssd.prepare.snapshot import verify_core_snapshot

    directory = _input_root(directory)
    entries = list(authoring_cases.discover(directory, case_identity))
    if not entries:
        return False
    source_files = [p for p in sorted(directory.rglob("*")) if p.is_file()]
    ex.manifest.update(
        workflow="ssd-case-v1",
        evaluation_scope="all",
        test_supplement_enabled=False,
        recommendation={"enabled": False},
    )
    selected = []
    from scene_completion.inputs.structured.supplied_cases import inspect_cases

    alias_groups = inspect_cases(ex.import_snapshot)[2] if ex.import_snapshot else []
    for file, case, problem in entries:
        cid, name = case["id"], case["name"]
        aliases = {cid, name}
        # Legacy G-nnn grouping is a UI alias only, never an SSD object identity.
        for group in alias_groups:
            if cid in group.get("rr_ids", []) + group.get("sr_ids", []):
                aliases.add(group["id"])
        if ex.case_ids and not aliases.intersection(ex.case_ids):
            continue
        selected.append(cid)

        def prepare(_, record, cid=cid, file=file, problem=problem):
            return prepare_stage.structured(ex, directory, cid, file, problem)

        identity = [
            (str(p.relative_to(directory)), fingerprint(p.read_bytes().hex()))
            for p in source_files
            if p.is_relative_to(file.parent)
            or not any(p.is_relative_to(other.parent) for other, _, _ in entries)
        ]
        key = _task(
            ex,
            cid,
            "ssd-prepare",
            [],
            prepare,
            identity,
            verify_payload=lambda bundle: verify_core_snapshot(ex.root, bundle),
        )
        _tail(ex, cid, key)
    if not selected:
        raise ValueError("指定用例不在当前结构化输入中")
    ex.manifest["ssd_cases"] = selected
    ex.scheduler.priority_cases = selected
    _project_scopes(ex, selected)
    return True


def build_from_documents(
    ex, rr, sr, tests, catalogue, groups, test_catalogue=None, test_alignment=None
):
    """Build SSD cases from shared document extraction and source branches."""
    from scene_completion.analysis.interactions.use_cases import select_documents
    from scene_completion.domain.concern_registry import default_registry
    from scene_completion.domain.current_scope import current_registry
    from scene_completion.inputs.documents.source_documents import normal_projection
    from scene_completion.workflow.runtime.task_context import ssd_context
    from scene_completion.workflow.ssd.prepare import stage as prepare_stage

    ex.registry_snapshot = current_registry(
        getattr(ex, "registry_snapshot", None) or default_registry()
    )
    ex.manifest.update(workflow="ssd-case-v1", recommendation={"enabled": False})
    selected = []
    for group in groups:
        if group["status"] != "confirmed":
            continue
        cid = group["id"]
        selected.append(cid)
        rr_docs = select_documents(
            rr, [c for c in catalogue["RR"] if c["id"] in group["rr_ids"]], catalogue["RR"]
        )
        sr_docs = select_documents(
            sr, [c for c in catalogue["SR"] if c["id"] in group["sr_ids"]], catalogue["SR"]
        )
        from scene_completion.inputs.structured.behavior_imports import materials

        aliases = (
            group["rr_ids"]
            + group["sr_ids"]
            + [
                c["name"]
                for c in catalogue["RR"] + catalogue["SR"]
                if c["id"] in group["rr_ids"] + group["sr_ids"]
            ]
        )
        behavior = materials(ex.import_snapshot, aliases)
        existing_docs = rr_docs + sr_docs + behavior["existing"]
        rr_docs = rr_docs + behavior["RR"]
        sr_docs = sr_docs + behavior["SR"]
        context_key = cid + ":ssd-context"
        fused_key = cid + ":fused-ssd"
        branches_key = cid + ":existing-branches"
        ex.add(
            context_key,
            "ssd-context",
            ("components",),
            case=cid,
            static={
                "RR": normal_projection(rr_docs),
                "SR": normal_projection(sr_docs),
                "case-group": group,
            },
            build=lambda d, r=rr_docs, s=sr_docs, g=group: {
                "RR": normal_projection(r),
                "SR": normal_projection(s),
                "components": d["components"],
                "case-group": g,
            },
            transform=ssd_context,
        )
        ex.add(
            fused_key,
            "fused-ssd",
            (context_key,),
            case=cid,
            build=lambda d, key=context_key: d[key],
        )
        ex.add(
            branches_key,
            "existing-branches",
            case=cid,
            static={"existing-documents": existing_docs},
        )
        name = next(
            (
                c["name"]
                for c in catalogue["SR"] + catalogue["RR"]
                if c["id"] in group["sr_ids"] + group["rr_ids"]
            ),
            cid,
        )
        case_tests = tests
        if test_catalogue is not None and test_alignment is not None:
            from scene_completion.analysis.matching.test_alignment import as_records, scoped_tests

            scoped, cat = scoped_tests(test_catalogue, test_alignment, tests, cid)
            case_tests = as_records(cat, scoped)

        def prepare(
            d,
            record,
            cid=cid,
            name=name,
            fk=fused_key,
            bk=branches_key,
            docs=[{**d, "role": "RR"} for d in rr]
            + [{**d, "role": "SR"} for d in sr]
            + [{**d, "role": "test", "channel": "test"} for d in tests],
            ts=case_tests,
        ):
            return prepare_stage.extracted(
                ex,
                {"id": cid, "name": name},
                d[fk],
                d["api-parameters"],
                d["business-entities"],
                d[bk],
                ts,
                docs,
            )

        key = _task(
            ex,
            cid,
            "ssd-prepare",
            [fused_key, branches_key, "api-parameters", "business-entities"],
            prepare,
        )
        _tail(ex, cid, key)
    ex.manifest["ssd_cases"] = selected
    _project_scopes(ex, selected)


def progress(ex):
    statuses = ex.scheduler.state["tasks"]
    cases = {}
    for cid in ex.manifest.get("ssd_cases", []):
        ready = statuses.get(cid + ":ssd-prepare", {}).get("status") == "passed"
        complete = statuses.get(cid + ":ssd-compare", {}).get("status") == "passed"
        cases[cid] = {
            "graphs_ready": ready,
            "analysis_ready": ready,
            "evaluation_ready": complete,
            "recommendation_ready": False,
        }
    ex.manifest.update(
        live_cases=cases,
        analysis_by_case={c: v["analysis_ready"] for c, v in cases.items()},
        evaluation_by_case={c: v["evaluation_ready"] for c, v in cases.items()},
        tasks={k: v["status"] for k, v in statuses.items() if k in ex.scheduler.tasks},
    )
    write_json(ex.root / "run_manifest.json", ex.manifest)


def finish(ex, result):
    # Republish verified cached outputs too, so review state and scheduler cache agree.
    for cid in ex.manifest.get("ssd_cases", []):
        compare_record = ex.scheduler.state["tasks"].get(cid + ":ssd-compare", {})
        if compare_record.get("failure", {}).get("review_conflict"):
            # _compare already published the verified machine baseline before
            # the concurrent review conflict. Do not roll it back to prepare.
            continue
        for stage in ("ssd-compare", "ssd-generate", "ssd-resolve", "ssd-prepare"):
            record = ex.scheduler.state["tasks"].get(cid + ":" + stage, {})
            if (
                record.get("status") == "passed"
                and cid + ":" + stage in ex.scheduler.resolved_tasks
            ):
                ssd_results.publish(
                    ex.root.parent, read_json(ex.root / record["output_file"])["payload"]
                )
                break
    progress(ex)
    summary = ssd_results.index(ex.root.parent)
    from scene_completion.application import shared_service_service

    shared_service_service.publish(ex.root.parent)
    project_summary = shared_service_service.index(ex.root.parent)
    pending = sum(c["pending_count"] for c in summary["cases"])
    pending += sum(s.get("pending_count", 0) for s in project_summary["scopes"])
    pending += ex.manifest.get("test_import_pending_count", 0)
    pending += sum(
        g.get("status") != "confirmed" for g in ex.manifest.get("case_correspondence", [])
    )
    pending += sum(
        g.get("status") != "confirmed" for g in ex.manifest.get("test_case_correspondence", [])
    )
    ex.manifest.update(
        execution_complete=result["complete"],
        complete=result["complete"] and not pending,
        analysis_complete=result["complete"],
        pending_count=pending,
        global_analysis={
            "complete": False,
            "enabled": False,
            "scopes": [],
        },
        shared_services=project_summary["scopes"],
        recommendation={"enabled": False},
        metrics=project_summary["metrics"]["overall"]["concern"],
        metrics_by_scope=project_summary["metrics"],
    )
    write_json(ex.root / "run_manifest.json", ex.manifest)
    path = ex.root / "execution_sessions.json"
    sessions = read_json(path)
    for session in sessions:
        if session["id"] == ex.session_id:
            session.update(
                finished_at=time.time(),
                status="complete"
                if ex.manifest["complete"]
                else "complete_with_questions"
                if result["complete"]
                else "waiting",
            )
    write_json(path, sessions)
    return ex.manifest
