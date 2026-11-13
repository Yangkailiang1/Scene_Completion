"""Publication."""

from scene_completion.analysis.diagrams.artifact_exports import export_task
from scene_completion.domain.concern_registry import scoped_execution
from scene_completion.domain.contracts import PROTOCOL
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.workflow.support import safe_case


@scoped_execution
def finish(self):
    from scene_completion.workflow.runtime.pipeline_execution import run_pipeline

    result = run_pipeline(self)
    if self.manifest.get("workflow") == "ssd-case-v1":
        from scene_completion.workflow.ssd_pipeline import finish as finish_ssd

        return finish_ssd(self, result)
    artifact_root = self.root / "artifacts"
    # Keep independently completed task files; failed siblings cannot erase them.
    (self.root / "missing_report.json").unlink(missing_ok=True)
    (self.root / "missing_report.md").unlink(missing_ok=True)
    reports = {}
    evaluations = {}
    cases = {}
    recommendations = {}
    global_results = {}
    records = self.scheduler.state["tasks"]
    for key, record in records.items():
        if key not in self.scheduler.tasks:
            continue
        cid = record.get("case", "shared")
        cases.setdefault(cid, {})[record["stage"]] = record["status"]
        if record["status"] != "passed":
            if record["status"] != "awaiting_review":
                from scene_completion.infrastructure.execution_graph import artifact_folder

                folder = artifact_folder(self.root, key, cid)
                stem = (key if cid == "shared" else key[len(cid) + 1 :]).replace(":", "--")
                for old in folder.glob(stem + ".*"):
                    archive = (
                        self.root
                        / "previous_artifacts"
                        / fingerprint([key, record.get("identity")])[:16]
                        / old.name
                    )
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    old.replace(archive)
            continue
        value = read_json(self.root / record["output_file"])
        stage = value["task"]
        destination = artifact_root / (safe_case(cid) if cid != "shared" else "shared")
        stem = (key if cid == "shared" else key[len(cid) + 1 :]).replace(":", "--")
        export_task(destination, stage, value["payload"], artifact_name=stem)
        write_json(destination / (stem + ".metadata.json"), value.get("metadata", {}))
        if stage == "missing-report":
            reports[cid] = value["payload"]
        if stage == "exception-evaluation":
            evaluations[cid] = value["payload"]
        if stage == "gap-recommend" and cid != "shared":
            recommendations[cid] = value["payload"]
        if stage.startswith("global-") or stage in {
            "business-dependencies",
            "business-entities",
            "business-crud",
            "business-attribute-map",
            "data-dependencies",
        }:
            global_results[
                key if key in {"global-concern-evaluation", "global-scenario-evaluation"} else stage
            ] = value["payload"]
    if "global-concern-evaluation" in global_results:
        global_results["global-concern-compare"] = global_results["global-concern-evaluation"]
    if "global-scenario-evaluation" in global_results:
        global_results["global-scenario-compare"] = global_results["global-scenario-evaluation"]
    if reports or "global-scenario-compare" in global_results:
        from scene_completion.analysis.diagrams.artifact_exports import export_missing_report

        combined = {
            "protocol": PROTOCOL,
            "cases": reports,
            "evaluation": evaluations,
            "global": global_results if "global-scenario-compare" in global_results else {},
            "recommendation": {"enabled": True, "cases": recommendations}
            if self.config.get("scenario_patterns", False)
            else {"enabled": False, "status": "未启用"},
            "evaluation_status": {
                c: "已评测" if c in evaluations else "未评测或任务未完成" for c in reports
            },
        }
        export_missing_report(self.root, combined)
    analysis_stages = {
        "existing-concerns",
        "concern-compare",
        "fused-ssd",
        "rr-ssd",
        "sr-ssd",
        "object-operations",
        "interaction-align",
        "interaction-enrich",
        "concern-match",
        "enriched-view",
        "exception-generate",
        "existing-extract",
        "gap-compare",
        "missing-report",
    }
    analysis = {
        c: all(stages.get(s) == "passed" for s in analysis_stages)
        for c, stages in cases.items()
        if c != "shared"
    }
    global_stages = (
        "business-entities",
        "business-crud",
        "business-attribute-map",
        "data-dependencies",
        "business-dependencies",
        "global-concerns",
        "global-existing-concerns",
        "global-scenarios",
        "global-existing-scenarios",
        "global-concern-compare",
        "global-scenario-compare",
        "global-recommend",
        "global-evaluation",
    )

    def aggregate_stage(stage):
        statuses = [
            r["status"]
            for key, r in records.items()
            if key in self.scheduler.tasks and r.get("case") == "shared" and r.get("stage") == stage
        ]
        if not statuses:
            return "not_created"
        if all(status == "passed" for status in statuses):
            return "passed"
        return next(
            (status for status in statuses if status not in {"passed", "pending"}), "pending"
        )

    global_status = {stage: aggregate_stage(stage) for stage in global_stages}
    # An empty, validated dependency graph has no per-dependency analysis
    # nodes. Report that case as not applicable rather than incomplete.
    no_global_dependencies = global_status[
        "business-dependencies"
    ] == "passed" and not global_results.get("business-dependencies", {}).get("dependencies")
    if no_global_dependencies:
        for stage in global_stages:
            if stage.startswith("global-") and global_status[stage] == "not_created":
                global_status[stage] = "not_applicable"
    if self.config.get("scenario_patterns", False):
        self.manifest["recommendation"] = {
            "enabled": True,
            "status": "已推荐"
            if recommendations and all(c in recommendations for c in reports)
            else "等待缺失比较",
            "case_count": len(recommendations),
        }
    self.manifest.update(
        execution_complete=result["complete"],
        complete=result["complete"]
        and not self.manifest.get("test_import_pending_count", 0)
        and not any(g["status"] == "pending" for g in self.manifest.get("case_correspondence", []))
        and not any(
            m["status"] != "confirmed" for m in self.manifest.get("test_case_correspondence", [])
        ),
        analysis_complete=bool(analysis) and all(analysis.values()),
        analysis_by_case=analysis,
        evaluation_by_case={
            c: s.get("exception-evaluation") == "passed" for c, s in cases.items() if c != "shared"
        },
        global_analysis={
            "complete": all(
                status in {"passed", "not_applicable"} for status in global_status.values()
            ),
            "stages": global_status,
            "evaluation_status": (
                "未评测或任务未完成"
                if global_status["global-evaluation"] != "passed"
                else "已评测"
                if global_results.get("global-evaluation", {})
                .get("metrics", {})
                .get("missing_omission", {})
                .get("status")
                != "未评测"
                else "未评测"
            ),
        },
        tasks={k: r["status"] for k, r in records.items() if k in self.scheduler.tasks},
    )
    if self.supplied_only:
        self.manifest["global_analysis"]["evaluation_status"] = "本轮未运行全局分析"
    write_json(self.root / "run_manifest.json", self.manifest)
    import time

    sessions = read_json(self.root / "execution_sessions.json")
    for session in sessions:
        if session["id"] == self.session_id:
            session.update(
                finished_at=time.time(),
                status="complete"
                if self.manifest["complete"]
                else "complete_with_questions"
                if self.manifest["execution_complete"]
                else "waiting",
            )
    write_json(self.root / "execution_sessions.json", sessions)
    # Diagnostics enqueue only on a fresh completed round. They never block
    # the business pipeline, and old finished runs are not scanned on startup.
    try:
        from scene_completion.manager.quality_runtime import notify_completed

        notify_completed(self.root.parent)
    except Exception as error:
        from scene_completion.infrastructure.execution_events import emit

        emit("quality_enqueue_failed", reason=str(error))
    return self.manifest


def publish_progress(self):
    if self.manifest.get("workflow") == "ssd-case-v1":
        from scene_completion.workflow.ssd_pipeline import progress

        return progress(self)
    ready = getattr(self.scheduler, "resolved_tasks", set())
    cases = {}
    for key, t in self.scheduler.tasks.items():
        if t.case == "shared":
            continue
        cases.setdefault(t.case, {})[t.stage] = (
            key in ready and self.scheduler.state["tasks"].get(key, {}).get("status") == "passed"
        )
    before = self.manifest.get("live_cases", {})
    live = {
        cid: {
            "graphs_ready": all(
                s.get(k, False) for k in ("fused-ssd", "rr-ssd", "sr-ssd", "object-operations")
            ),
            "analysis_ready": all(
                s.get(k, False)
                for k in (
                    "concern-match",
                    "existing-concerns",
                    "concern-compare",
                    "exception-generate",
                    "existing-extract",
                    "missing-report",
                )
            ),
            "recommendation_ready": s.get("gap-recommend", False),
            "evaluation_ready": s.get("exception-evaluation", False),
        }
        for cid, s in cases.items()
    }
    self.manifest.update(
        live_cases=live,
        analysis_by_case={k: v["analysis_ready"] for k, v in live.items()},
        evaluation_by_case={k: v["evaluation_ready"] for k, v in live.items()},
        tasks={
            k: r["status"]
            for k, r in self.scheduler.state["tasks"].items()
            if k in self.scheduler.tasks
        },
    )
    write_json(self.root / "run_manifest.json", self.manifest)
    for cid, v in live.items():
        if before.get(cid) != v:
            self.scheduler.events.append("case_progress", case=cid, **v)
