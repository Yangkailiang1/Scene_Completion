"""Compact case-parallel workflow using the shared scheduler and model transport."""

import json
import shutil
import time
from copy import deepcopy
from pathlib import Path

from scene_completion.application import ssd_revision_service as ssd_results
from scene_completion.domain.ssd import matching as ssd_matching
from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.infrastructure import ssd_repository
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.workflow_core import Task


def enabled(ex):
    # Frozen v5 mock packets replay the old task contracts. Real runs and
    # explicit new-format fixture runs use the simplified graph by default.
    default = "legacy" if getattr(ex, "mocks", None) is not None else "ssd"
    return ex.config.get("workflow_mode", default) == "ssd"


def input_directory(ex):
    """Reconstruct frozen uploaded paths, never re-read mutable external inputs."""
    project = getattr(ex, "source_project", ex.root.parent)
    pointer = project / "imports/ssd-input.json"
    if pointer.exists():
        root = (project / read_json(pointer)["path"]).resolve()
        if root.is_relative_to(project.resolve()) and root.is_dir():
            return root
    rows = ex.import_snapshot
    if not any((r.get("behavior_product") or {}).get("kind") == "system_operations" for r in rows):
        return None
    root = (
        (ex.root.parent if getattr(ex, "is_preview", False) else project)
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


def _semantic_available(ex):
    return (
        getattr(ex, "client", None) is not None
        or getattr(ex, "mode", "packets") in {"external", "responses"}
        or getattr(ex, "mocks", None) is not None
    )


def _semantic_cache_identity(ex, stage):
    """A skipped semantic stage is not a completed model analysis.

    Model/account selection remains operational and does not invalidate valid
    analyses; capability, execution provenance and task contracts do.
    """
    if stage not in {"ssd-resolve", "ssd-compare"}:
        return None
    from scene_completion.workflow.semantics import code_version

    task = "ssd-resolve" if stage == "ssd-resolve" else "ssd-semantic-compare"
    return {
        "available": _semantic_available(ex),
        "mode": getattr(ex, "mode", "packets"),
        "mock": getattr(ex, "mocks", None) is not None,
        "artifact_identity": getattr(ex, "artifact_identity", {}),
        "semantic_task": task,
        "semantic_version": code_version(task),
    }


def _review_material(bundle):
    return {
        "steps": bundle.get("steps", []),
        "channels": bundle.get("channels", {}),
        "decisions": [d for d in bundle.get("decisions", []) if d.get("origin") == "manual"],
    }


def _review_identity(ex, cid):
    try:
        effective = ssd_results.editor(ex.root.parent, cid)["bundle"]
        baseline = ssd_results.editor(ex.root.parent, cid, "original")["bundle"]
    except ValueError:
        return None
    material = _review_material(effective)
    return fingerprint(material) if material != _review_material(baseline) else None


def _task(ex, cid, stage, deps, fn, identity=None):
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
                "execution": {"provider": "ssd_case_workflow", "version": ssd_validation.VERSION}
            },
        }

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
                _semantic_cache_identity(ex, stage),
                _review_identity(ex, cid) if stage == "ssd-compare" else None,
            ]
        ),
        execute=execute,
        verify=lambda v: ssd_validation.validate(v["payload"]),
        display_label={
            "ssd-prepare": "建立 SSD 与三方结果",
            "ssd-compare": "比较与发布",
            "ssd-resolve": "处理语义对应",
        }.get(stage, stage),
    )
    ex.scheduler.add(task)
    return task.key


def _compare_pairs(ex, bundle, record):
    """Use the result layer's candidate contract without publishing a baseline."""
    bundle = deepcopy(bundle)
    if not _semantic_available(ex):
        return ssd_validation.validate(bundle)
    candidates = ssd_matching.semantic_candidates(bundle)
    for pair, (a, b) in ssd_matching.PAIRS.items():
        left = {r["id"]: r for r in bundle["channels"][a]["scenarios"]}
        right = {r["id"]: r for r in bundle["channels"][b]["scenarios"]}
        pairs = [
            (left[p["left_id"]], right[p["right_id"]]) for p in candidates if p["pair"] == pair
        ]
        for offset in range(0, len(pairs), 24):
            batch = pairs[offset : offset + 24]
            result, _ = ex.semantic(
                "ssd-semantic-compare",
                {"pair": pair, "pairs": [{"left": x, "right": y} for x, y in batch]},
                record,
            )
            expected = {(x["id"], y["id"]) for x, y in batch}
            actual = {(d["left_id"], d["right_id"]) for d in result["decisions"]}
            if actual != expected or len(actual) != len(result["decisions"]):
                raise ValueError("语义比较必须逐对返回全部候选，不能新增或遗漏")
            bundle.setdefault("decisions", []).extend(
                {
                    **d,
                    "id": "auto-" + fingerprint([pair, d])[:20],
                    "level": "scenario",
                    "pair": pair,
                    "origin": "auto",
                }
                for d in result["decisions"]
            )
    return ssd_validation.validate(bundle)


def _reuse_machine_decisions(ex, bundle, semantic_identity):
    """Reuse unchanged pairs across human edits or a newly published preparation."""

    def semantic_record(record):
        if record is None:
            return None
        # Citation repairs change provenance, not the judged failure. Keep all
        # other fields strict so conditions, outcomes and bindings invalidate.
        return {key: value for key, value in record.items() if key != "source_refs"}

    bundle = deepcopy(bundle)
    try:
        # One state snapshot keeps the current and previous machine baselines
        # together. prepare publishes its fresh bundle before compare, so the
        # most recent analyzed machine result can now be previous_baseline.
        state = ssd_repository.state(ex.root.parent, bundle["case"]["id"])
    except ValueError:
        return bundle
    existing = {
        (d["level"], d["pair"], d["left_id"], d["right_id"]) for d in bundle.get("decisions", [])
    }
    for baseline in (state["baseline"], state.get("previous_baseline")):
        if not baseline or baseline.get("semantic_comparison_identity") != semantic_identity:
            continue
        for decision in baseline.get("decisions", []):
            identity = (
                decision["level"],
                decision["pair"],
                decision["left_id"],
                decision["right_id"],
            )
            if identity in existing or decision.get("origin") != "auto":
                continue
            a, b = ssd_matching.PAIRS[decision["pair"]]
            kind = "scenarios" if decision["level"] == "scenario" else "concerns"
            unchanged = all(
                semantic_record(
                    next((r for r in bundle["channels"][channel][kind] if r["id"] == ident), None)
                )
                == semantic_record(
                    next((r for r in baseline["channels"][channel][kind] if r["id"] == ident), None)
                )
                and any(r["id"] == ident for r in bundle["channels"][channel][kind])
                for channel, ident in ((a, decision["left_id"]), (b, decision["right_id"]))
            )
            if unchanged:
                bundle.setdefault("decisions", []).append(deepcopy(decision))
                existing.add(identity)
    return bundle


def _compare(ex, bundle, record):
    """Publish machine analysis, then independently review the effective human version."""
    from scene_completion.workflow.semantics import code_version

    semantic_identity = {
        "logic": code_version("ssd-compare"),
        **_semantic_cache_identity(ex, "ssd-compare"),
    }
    machine = _reuse_machine_decisions(ex, bundle, semantic_identity)
    machine = _compare_pairs(ex, machine, record)
    machine["semantic_comparison_identity"] = semantic_identity
    snapshot = ssd_results.publish(ex.root.parent, machine)
    effective = snapshot["bundle"]
    if _semantic_available(ex) and _review_material(effective) != _review_material(machine):
        reviewed = _compare_pairs(ex, effective, record)
        if reviewed.get("decisions", []) != effective.get("decisions", []):
            try:
                ssd_results.save_revision(
                    ex.root.parent,
                    machine["case"]["id"],
                    {
                        "base_revision": snapshot["revision"],
                        "bundle": reviewed,
                        "reason": "自动复核人工修订的未决场景对应",
                    },
                )
            except ssd_results.RevisionConflict as conflict:
                from scene_completion.workflow_core import TaskBlocked

                # Do not cache this stage as complete: even an unrelated note
                # edit can conflict while leaving the semantic signature intact.
                raise TaskBlocked(
                    "pending",
                    {
                        "review_conflict": conflict.current_revision,
                        "reason": "人工修订已更新，重新运行可复核剩余对应",
                    },
                ) from conflict
    return machine


def _resolve(ex, bundle, record):
    bundle = deepcopy(bundle)
    for channel in ("G", "E", "GT"):
        pending = [p for p in bundle["channels"][channel]["pending"] if p.get("needs_semantic")]
        if not pending or not _semantic_available(ex):
            continue
        # Each invocation has just its own source records and shared positive anchors.
        inputs = {
            "case": bundle["case"],
            "steps": bundle["steps"],
            "apis": deepcopy(bundle.get("apis", [])),
            "entities": deepcopy(bundle.get("entities", [])),
            "channel": channel,
            "records": pending,
            "registry": ex.registry_snapshot,
        }
        result, _ = ex.semantic("ssd-resolve", inputs, record)
        allowed = {p["id"] for p in pending}
        resolved = set(result["resolved_ids"])
        if not resolved <= allowed:
            raise ValueError("语义识别引用了本通道以外的记录")
        if any(
            not any(c["source_record_id"] == ident for c in result["concerns"])
            or not any(s["source_record_id"] == ident for s in result["scenarios"])
            for ident in resolved
        ):
            raise ValueError("已解决的来源必须同时保留关注点和具体场景，不能提交空结果丢弃来源")
        for row in result["concerns"] + result["scenarios"]:
            if row.get("source_record_id") not in resolved:
                raise ValueError("语义结果必须绑定本次输入来源")
            source = next(p for p in pending if p["id"] == row["source_record_id"])
            row["source_refs"] = deepcopy(source.get("source_refs", []))
        bundle["channels"][channel]["concerns"].extend(result["concerns"])
        bundle["channels"][channel]["scenarios"].extend(result["scenarios"])
        bundle["channels"][channel]["pending"] = [
            p for p in bundle["channels"][channel]["pending"] if p["id"] not in resolved
        ]
    return ssd_validation.validate(bundle)


def _tail(ex, cid, prepare):
    resolved = _task(ex, cid, "ssd-resolve", [prepare], lambda d, r: _resolve(ex, d[prepare], r))
    _task(ex, cid, "ssd-compare", [resolved], lambda d, r: _compare(ex, d[resolved], r))


def build_structured(ex, directory):
    from scene_completion.analysis.ssd.pipeline import build_cases, case_identity, generate_g

    directory = Path(directory)
    files = sorted(directory.rglob("SysOperation.json"))
    if not files:
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
    for file in files:
        try:
            raw = json.loads(file.read_text(encoding="utf-8-sig"))
            case = case_identity(file, directory, raw)
        except (ValueError, UnicodeError):
            case = case_identity(file, directory, {})
        cid, name = case["id"], case["name"]
        aliases = {cid, name}
        # Legacy G-nnn grouping is a UI alias only, never an SSD object identity.
        for group in alias_groups:
            if cid in group.get("rr_ids", []) + group.get("sr_ids", []):
                aliases.add(group["id"])
        if ex.case_ids and not aliases.intersection(ex.case_ids):
            continue
        selected.append(cid)

        def prepare(_, record, cid=cid, file=file):
            bundles = build_cases(directory, [cid], case_files=[file])
            if len(bundles) != 1:
                raise ValueError("当前用例没有唯一可用的 SysOperation")
            bundle = ssd_validation.validate(bundles[0])
            bundle["registry"] = deepcopy(ex.registry_snapshot)
            bundle["channels"]["G"] = generate_g(bundle)
            ssd_results.publish(ex.root.parent, bundle)
            return bundle

        identity = [
            (str(p.relative_to(directory)), fingerprint(p.read_bytes().hex()))
            for p in source_files
            if p.is_relative_to(file.parent)
            or not any(p.is_relative_to(other.parent) for other in files)
        ]
        key = _task(ex, cid, "ssd-prepare", [], prepare, identity)
        _tail(ex, cid, key)
    if not selected:
        raise ValueError("指定用例不在当前结构化输入中")
    ex.manifest["ssd_cases"] = selected
    ex.scheduler.priority_cases = selected
    return True


def build_from_documents(
    ex, rr, sr, tests, catalogue, groups, test_catalogue=None, test_alignment=None
):
    """Build SSD cases from shared document extraction and source branches."""
    from scene_completion.analysis.interactions.use_cases import select_documents
    from scene_completion.analysis.ssd.pipeline import generate_g
    from scene_completion.inputs.documents.source_documents import normal_projection
    from scene_completion.inputs.documents.ssd_adapter import normalize_extracted_case
    from scene_completion.workflow.runtime.task_context import ssd_context

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
            bundle = normalize_extracted_case(
                {"id": cid, "name": name},
                d[fk],
                d["api-parameters"],
                d["business-entities"],
                d[bk],
                ts,
                docs,
            )
            bundle["registry"] = deepcopy(ex.registry_snapshot)
            bundle["channels"]["G"] = generate_g(bundle)
            ssd_results.publish(ex.root.parent, bundle)
            return bundle

        key = _task(
            ex,
            cid,
            "ssd-prepare",
            [fused_key, branches_key, "api-parameters", "business-entities"],
            prepare,
        )
        _tail(ex, cid, key)
    ex.manifest["ssd_cases"] = selected


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
        for stage in ("ssd-compare", "ssd-resolve", "ssd-prepare"):
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
    pending = sum(c["pending_count"] for c in summary["cases"])
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
        global_analysis={"complete": False, "evaluation_status": "本轮未运行全局分析"},
        recommendation={"enabled": False},
        metrics=summary["metrics"],
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
