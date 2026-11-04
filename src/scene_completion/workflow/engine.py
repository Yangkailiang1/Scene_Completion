"""Execution session and public workflow assembly entry points."""

from pathlib import Path

from scene_completion.domain.contracts import PROTOCOL
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.workflow import publication, semantic_executor, task_registration
from scene_completion.workflow.case_pipeline import _build_cases as _build_cases
from scene_completion.workflow.planning import build_pipeline as build_pipeline
from scene_completion.workflow.scheduler import (
    CallGate,
    Scheduler,
)
from scene_completion.workflow.semantics import code_version as code_version
from scene_completion.workflow.support import analysis_settings as analysis_settings
from scene_completion.workflow.support import payload as payload
from scene_completion.workflow.support import safe_case as safe_case
from scene_completion.workflow.support import skill_path


class Execution:
    def __init__(
        self,
        root,
        *,
        mode="packets",
        client=None,
        responses_dir=None,
        mocks=None,
        config=None,
        case_ids=None,
        auto_repair="bounded",
        max_rounds=2,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        from scene_completion.review.project_review import project_registry

        self.registry_snapshot = project_registry(self.root.parent)
        self.mode, self.client, self.responses_dir, self.mocks = (
            mode,
            client,
            Path(responses_dir) if responses_dir else None,
            mocks,
        )
        self.config = config or getattr(client, "config", {}) or {}
        self.case_ids = case_ids or []
        self.evaluation_scope = "all"
        from scene_completion.inputs.artifact_imports import snapshot

        self.import_snapshot = snapshot(self.root.parent)
        from scene_completion.analysis.scenario_patterns import normalize_settings
        from scene_completion.domain.concern_registry import registry_scope

        with registry_scope(self.registry_snapshot):
            self.pattern_settings = (
                normalize_settings(read_json(self.root / "pattern_settings_used.json"))
                if (self.root / "pattern_settings_used.json").exists()
                else normalize_settings()
            )
        self.recommendation_history = (
            read_json(self.root / "recommendation_history_used.json")
            if (self.root / "recommendation_history_used.json").exists()
            else []
        )
        from scene_completion.review.node_conversations import Conversations
        from scene_completion.review.reviews import Reviews

        self.conversations = Conversations(self.root)
        self.reviews = Reviews(self.root, self.config.get("review_mode", "auto"))
        self.expand_pipeline = None
        self.expand_api = None
        self.partitions = []
        if self.config.get("structured_output", "json_object") not in {
            "json_object",
            "json_schema",
        }:
            raise ValueError("structured_output must be json_object or configured json_schema")
        operational = {
            "priority_cases",
            "supplement_tests",
            "max_concurrency",
            "max_endpoint_concurrency",
        }
        self.identity = {
            "mode": "mock" if mocks is not None else mode,
            "model": client.model("agent") if client else None,
            "config_hash": fingerprint(
                {k: v for k, v in self.config.items() if k not in operational}
            ),
            "endpoint_hash": fingerprint(getattr(client, "base_url", None)),
        }
        self.artifact_identity = {"mode": self.identity["mode"]}
        self.reviews.execution_identity = fingerprint(self.artifact_identity)
        manifest = self.root / "run_manifest.json"
        previous = read_json(manifest) if manifest.exists() else None
        if previous and (
            previous.get("run_scope", []) != self.case_ids
            or previous.get(
                "supplement_tests", any(":test-expanded" in k for k in previous.get("tasks", {}))
            )
            != bool(self.config.get("supplement_tests", False))
        ):
            import shutil
            import time

            archive = self.root / "report_versions" / ("scope-" + str(time.time_ns()))
            archive.mkdir(parents=True, exist_ok=True)
            for name in (
                "missing_report.json",
                "missing_report.md",
                "run_manifest.json",
                "workflow_tasks.json",
                "workflow_graph.json",
            ):
                if (self.root / name).exists():
                    shutil.copy2(self.root / name, archive / name)
        if previous and previous.get("protocol") != PROTOCOL:
            raise ValueError("different protocol: use a new run directory")
        if (
            any((self.root / n).exists() for n in ("case_tasks.json", "workflow_tasks.json"))
            and not previous
        ):
            raise ValueError("unbound/legacy scheduler cache requires a separate run directory")
        if (
            previous
            and previous.get("execution_identity", {}).get("mode") == "mock"
            and mocks is None
        ):
            raise ValueError("mock results cannot be promoted into a real run")
        used = self.root / "registry_used" / (self.registry_snapshot["hash"] + ".json")
        if not used.exists():
            write_json(used, self.registry_snapshot)
        if (
            previous
            and previous.get("registry_hash")
            and previous["registry_hash"] != self.registry_snapshot["hash"]
        ):
            import shutil
            import time

            archive = (
                self.root
                / "report_versions"
                / (previous["registry_hash"][:16] + "-" + str(time.time_ns()))
            )
            for name in (
                "missing_report.json",
                "missing_report.md",
                "run_manifest.json",
                "workflow_tasks.json",
                "workflow_graph.json",
            ):
                source = self.root / name
                if source.exists():
                    archive.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, archive / name)
        if (
            previous
            and self.config.get("scenario_patterns", False)
            and previous.get("pattern_settings_hash") != self.pattern_settings["hash"]
        ):
            import shutil
            import time

            archive = (
                self.root
                / "report_versions"
                / (
                    "patterns-"
                    + str(previous.get("pattern_settings_hash", "legacy"))[:16]
                    + "-"
                    + str(time.time_ns())
                )
            )
            for name in (
                "missing_report.json",
                "missing_report.md",
                "run_manifest.json",
                "workflow_tasks.json",
                "workflow_graph.json",
            ):
                source = self.root / name
                if source.exists():
                    archive.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, archive / name)
        from scene_completion.analysis.normal_rules import RULESET_VERSION

        if (
            previous
            and previous.get("ruleset_version")
            and previous["ruleset_version"] != RULESET_VERSION
        ):
            import shutil
            import time

            archive = (
                self.root
                / "report_versions"
                / ("rules-" + previous["ruleset_version"] + "-" + str(time.time_ns()))
            )
            archive.mkdir(parents=True, exist_ok=True)
            from scene_completion.analysis.result_views import ResultView

            old_metrics = ResultView(self.root.parent).metrics()
            write_json(
                archive / "metrics_summary.json",
                {
                    k: old_metrics.get(k)
                    for k in ("metrics", "ruleset_version", "matching_version", "cases", "test_set")
                },
            )
            for name in (
                "missing_report.json",
                "missing_report.md",
                "run_manifest.json",
                "workflow_tasks.json",
                "workflow_graph.json",
            ):
                if (self.root / name).exists():
                    shutil.copy2(self.root / name, archive / name)
        self.manifest = {
            "protocol": PROTOCOL,
            "complete": False,
            "execution_identity": self.identity,
            "registry_hash": self.registry_snapshot["hash"],
            "registry_version": self.registry_snapshot["version"],
            "recommendation": {"enabled": False, "status": "未启用"},
            "formal": False,
        }
        self.manifest["ruleset_version"] = RULESET_VERSION
        self.manifest.update(
            run_scope=self.case_ids,
            supplement_tests=bool(self.config.get("supplement_tests", False)),
        )
        self.manifest["evaluation_version"] = RULESET_VERSION
        from scene_completion.analysis.concern_alignment import VERSION

        self.manifest["matching_version"] = VERSION
        if self.config.get("scenario_patterns", False):
            self.manifest.update(
                pattern_settings_hash=self.pattern_settings["hash"],
                pattern_library_version=self.pattern_settings["library"]["version"],
                recommendation={"enabled": True, "status": "等待缺失集合M"},
            )
        self.manifest["artifact_cache_contract"] = "producer-independent-v1"
        write_json(manifest, self.manifest)
        self.scheduler = Scheduler(
            self.root,
            concurrency=self.config.get("max_concurrency", 1),
            auto_repair=auto_repair,
            max_rounds=max_rounds,
        )
        import time

        self.session_id = fingerprint([time.time_ns(), str(self.root)])[:20]
        self.recovery_epoch = (
            previous.get("recovery_epoch", self.session_id)
            if previous and not previous.get("execution_complete")
            else self.session_id
        )
        self.manifest["recovery_epoch"] = self.recovery_epoch
        from scene_completion.workflow.node_recovery import eligible

        self.scheduler.can_recover = lambda t, r: bool(
            getattr(t, "recoverable", False)
            and eligible(self.root.parent, t.stage, r, self.recovery_epoch)
        )
        sessions = (
            read_json(self.root / "execution_sessions.json")
            if (self.root / "execution_sessions.json").exists()
            else []
        )
        sessions.append(
            {
                "id": self.session_id,
                "started_at": time.time(),
                "finished_at": None,
                "status": "running",
            }
        )
        write_json(self.root / "execution_sessions.json", sessions)
        self.gate = CallGate(
            self.config.get("max_concurrency", 1),
            adaptive=self.config.get("adaptive_concurrency", True),
            on_change=lambda s: write_json(self.root / "concurrency_status.json", s),
            pause_file=self.root / "pause_requested.json",
        )
        prior_limit = self.root / "concurrency_status.json"
        if prior_limit.exists():
            import time

            prior = read_json(prior_limit)
            if prior.get("configured_max") == self.gate.limit:
                self.gate.effective_limit = min(self.gate.limit, prior["effective_max"])
                self.gate.retry_not_before = time.monotonic() + max(
                    0.0, min(300.0, prior.get("not_before_unix", 0) - time.time())
                )
        # Reuse the existing request-level gate, cooldown and token-budget code.
        if client and hasattr(client, "post"):
            client.shared_call_gate = self.gate
            original = client.post
            client.post = lambda *a, **k: self.gate.call(original, *a, **k)

    def semantic(self, task, inputs, record):
        return semantic_executor.semantic(self, task, inputs, record)

    def skill_text(self, task):
        return skill_path(task).read_text(encoding="utf8")

    def add(
        self,
        key,
        task,
        deps=(),
        static=None,
        build=None,
        transform=None,
        semantic_task=None,
        case=None,
        skip_review=False,
        api_scope=None,
        verify_derivation=False,
    ):
        return task_registration.add(
            self,
            key,
            task,
            deps,
            static,
            build,
            transform,
            semantic_task,
            case,
            skip_review,
            api_scope,
            verify_derivation,
        )

    def partitioned(self, key, task, deps, build, case):
        return task_registration.partitioned(self, key, task, deps, build, case)

    def finish(self):
        return publication.finish(
            self,
        )

    def publish_progress(self):
        return publication.publish_progress(
            self,
        )
