"""Task Registration."""

from copy import deepcopy

from scene_completion.analysis.concern_hierarchy import resolve_matches
from scene_completion.analysis.exception_generation import (
    attach_provenance,
    data_exceptions,
    deduplicate,
    pending_rules,
    query_exceptions,
    service_exceptions,
    storage_exceptions,
)
from scene_completion.analysis.interaction_enrichment import resource_metadata
from scene_completion.analysis.normal_rules import documented_normal_tolerance
from scene_completion.analysis.test_alignment import exact_alignment, known_catalogue
from scene_completion.analysis.validation import validate_result
from scene_completion.domain.concern_registry import scoped_execution
from scene_completion.domain.contracts import (
    PROTOCOL,
    SCHEMAS,
    TASKS,
    registry,
    schema,
)
from scene_completion.domain.scenario_types import normal_replay_record
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.ordered_behaviors import fused_candidate
from scene_completion.review.reviews import REVIEW_TASKS
from scene_completion.workflow.scheduler import Task, TaskBlocked, TaskRejected
from scene_completion.workflow.semantics import code_version, component_version
from scene_completion.workflow.support import analysis_settings, payload
from scene_completion.workflow.task_context import generation_matches


@scoped_execution
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
    static = static or {}
    if verify_derivation and (transform is None or task in REVIEW_TASKS and not skip_review):
        raise ValueError("derived validation requires an unreviewed deterministic task")
    from scene_completion.inputs.artifact_imports import fragments_for
    from scene_completion.inputs.external_interfaces import REVISION, inventory

    external_contract = key in {
        f"{layer}-external-api-{stage}"
        for layer in ("rr", "sr")
        for stage in ("context", "map", "index")
    }

    imported = fragments_for(self.root.parent, task, case, self.import_snapshot)
    if transform and task == "fused-ssd":
        imported = []
    if task == "business-entities" and key != "business-entities":
        imported = []
    if transform and key in {
        "api-map",
        "api-parameters",
        "rr-api-parameters",
        "sr-api-parameters",
        "external-api-map",
        "external-api-index",
        "external-api-parameters",
    }:
        imported = []
    elif api_scope is not None:
        from scene_completion.inputs.api_layers import scoped_imports

        imported = scoped_imports(imported, api_scope)
    previous = self.scheduler.state["tasks"].get(key, {})
    if imported and previous.get("status") == "passed" and previous.get("output_file"):
        old = (
            read_json(self.root / previous["output_file"]).get("metadata", {}).get("execution", {})
        )
        imported = [
            a
            for a in imported
            if a.get("replacement_approved")
            or old.get("artifact_id") == a["id"]
            and old.get("revision") == a["file_revision"]
        ]
    import_identity = fingerprint(imported) if imported else None
    from scene_completion.workflow.node_repair import repair_revision as supplied_repair_revision

    supplied_repair = supplied_repair_revision(self.root, key)
    review_identity = fingerprint(
        [
            self.reviews.execution_identity,
            code_version(task),
            *([REVISION] if external_contract else []),
            schema(task) if task in SCHEMAS else None,
            self.conversations.revision(key),
            import_identity,
            *([supplied_repair] if supplied_repair else []),
        ]
    )

    def inputs_for(dependencies, *, legacy_crud=False):
        values = {k: payload(v) for k, v in dependencies.items()}
        result = build(values) if build else deepcopy(static)
        if imported:
            result = deepcopy(result)
            result["import-documents"] = [p["document"] for p in imported]
            result["imported-fragments"] = [
                {k: p[k] for k in ("task", "payload", "coverage")} for p in imported
            ]
            if task == "fused-ssd":
                for layer in ("RR", "SR"):
                    result[layer] += [
                        p["document"]
                        for p in imported
                        if p["task"] in {"fused-ssd", layer.lower() + "-ssd"}
                    ]
        from scene_completion.review.review_questions import materials

        confirmation = materials(self.root.parent, key)
        if confirmation:
            result = deepcopy(result)
            result["review-documents"] = confirmation
            if "normal-documents" in result:
                result["normal-documents"] += [
                    {k: d[k] for k in ("source_id", "name", "channel", "lines")}
                    for d in confirmation
                    if d["channel"] == "normal"
                ]
        if task == "business-crud" and (crud := result.pop("_crud_scope", None)) is not None:
            aliases, legacy_aliases, locations = crud
            if legacy_crud:
                from scene_completion.inputs.colleague_formats import scoped_entities

                result["business-entities"] = scoped_entities(
                    result["business-entities"], legacy_aliases
                )
            else:
                from scene_completion.analysis.crud_scope import project

                result = project(result, aliases, locations)
        return result

    def execute(dependencies, record):
        inputs = inputs_for(dependencies)
        reviewed = (
            self.reviews.cached(key, task, inputs, review_identity)
            if task in REVIEW_TASKS and not skip_review and not supplied_repair
            else None
        )
        from scene_completion.inputs.artifact_imports import candidate as imported_candidate

        imported_result = (
            imported_candidate(
                self.root.parent,
                task,
                case,
                inputs,
                existing=record.get("previous_success"),
                parts=imported,
            )
            if imported and task not in {"rr-ssd", "sr-ssd"}
            else None
        )
        if imported_result is not None:
            value, proof = imported_result
        elif reviewed is not None:
            value = reviewed
            proof = {"reviewed": True}
        elif (
            task == "fused-ssd"
            and transform is None
            and (native := fused_candidate(self.import_snapshot, inputs)) is not None
        ):
            value = native
            proof = {
                "provider": "ordered_behavior_import",
                "reason": "已验证系统操作、参与者及Order转换；未重复调用融合SSD模型",
            }
        elif transform:
            value = transform(inputs)
            proof = {}
        elif (
            task == "api-map"
            and inputs.get("interface-scope", {}).get("boundary") == "external"
            and not inventory(inputs)
        ):
            value = {"services": []}
            proof = {
                "provider": "external_interface_inventory",
                "reason": "本层未声明可抽取外部接口",
            }
        elif (
            task == "use-case-extract"
            and (
                structured := __import__(
                    "scene_completion.inputs.structure_models", fromlist=["catalogue"]
                ).catalogue(inputs["documents"], inputs["layer"])
            )
            is not None
        ):
            value = structured
            proof = {
                "provider": "colleague_structure",
                "source_ids": [d["source_id"] for d in inputs["documents"]],
                "reason": "同事结构化JSON用例实体与主成功路径，保留原用例身份；未调用模型重复抽取",
            }
        elif (
            task == "existing-branches"
            and (
                structured := __import__(
                    "scene_completion.inputs.structure_models", fromlist=["existing_branches"]
                ).existing_branches(inputs["existing-documents"])
            )
            is not None
        ):
            value = structured
            proof = {
                "provider": "colleague_structure",
                "source_ids": [d["source_id"] for d in inputs["existing-documents"]],
                "reason": "仅scenario_kind=exception进入E分支；主成功和备选保留查看，不作为异常",
            }
        elif (
            task == "test-inventory"
            and (known := known_catalogue(inputs["test-documents"])) is not None
        ):
            value = known
            proof = {
                "provider": "explicit_test_structure",
                "reason": "按原文明示字段/EXT标签整理，不改变场景类型",
            }
        elif (
            task == "exception-scope"
            and (
                scope_review := __import__(
                    "scene_completion.review.scope_reviews", fromlist=["reviewed"]
                ).reviewed(self.root.parent, key, inputs)
            )
            is not None
        ):
            value, proof = scope_review, {"provider": "human_scope_review"}
        elif (
            task == "interaction-normalize"
            and (
                literal := __import__(
                    "scene_completion.analysis.atomic_steps", fromlist=["literal_plan"]
                ).literal_plan(inputs["candidate"])
            )
            is not None
        ):
            value, proof = (
                literal,
                {
                    "provider": "validated_literal_order",
                    "reason": "逐条核对已提供的结构化定义、双方、顺序和返回对应；混合或歧义仍走模型审查",
                },
            )
        elif task == "exception-scope" and not inputs["source-records"]:
            value, proof = {"units": []}, {"provider": "empty_exception_source"}
        elif task == "test-case-align" and (aligned := exact_alignment(inputs)) is not None:
            value = aligned
            proof = {"provider": "explicit_case_identifiers"}
        elif task == "test-ground-truth" and documented_normal_tolerance(inputs):
            value = {"scenarios": [], "pending": []}
            proof = {
                "provider": "documented_normal_tolerance",
                "reason": "本测试明确为可选容错且预期允许隐藏/缺省，不违反约定，不进入异常GT；测试原文保存在任务输入",
            }
        elif (
            task in {"global-scenarios", "global-existing-scenarios", "global-test-scenarios"}
            and not inputs["identified-concerns"]["matches"]
        ):
            # Scene expansion cannot invent a concern that its independent
            # recognition channel did not identify. Carry questions forward.
            value = {
                "scenarios": [],
                "pending": deepcopy(inputs["identified-concerns"].get("pending", [])),
            }
            proof = {
                "provider": "no_identified_global_concerns",
                "reason": "本通道未识别全局关注点，不调用模型扩写场景；未决事项保留",
            }
        elif task == "test-supplement" and not any(
            not r["concern_key"].startswith("api.data.") for r in inputs["normal-rules"]["rules"]
        ):
            value = {"tests": []}
            proof = {
                "provider": "independent_positive_contract_tests",
                "reason": "明确字段约束和服务可用性由独立测试工具补全，不读取G/E",
            }
        elif (
            task == "existing-extract"
            and "bindings" in inputs
            and not any(b["status"] == "confirmed" for b in inputs["bindings"]["bindings"])
        ):
            value = {"scenarios": []}
            proof = {
                "provider": "unconfirmed_branch",
                "reason": "没有已确认的异常交互绑定；保留待确认分支，不调用模型补造",
            }
        elif (
            task in {"test-concerns", "test-ground-truth"}
            and (source := normal_replay_record(inputs)) is not None
        ):
            value = {
                ("matches" if task == "test-concerns" else "scenarios"): [],
                "pending": [],
                "excluded": [
                    {
                        "original_id": source["id"],
                        "scenario_type": "normal",
                        "reason": "原始表标为异常，但触发仅相同幂等键正常重试、预期返回已有且不重复创建；不计关注点或异常场景",
                        "source_refs": source["source_refs"],
                    }
                ],
            }
            proof = {"provider": "documented_normal_replay"}
        elif (
            task in {"existing-extract", "test-ground-truth"}
            and "identified-concerns" in inputs
            and not any(
                m.get("status") == "applicable" for m in inputs["identified-concerns"]["matches"]
            )
        ):
            source = inputs.get("test-documents", inputs.get("existing-documents", []))
            pending = deepcopy(inputs["identified-concerns"].get("pending", []))
            excluded = deepcopy(inputs["identified-concerns"].get("excluded", []))
            if not pending and not excluded:
                pending = [
                    {
                        "interaction_id": "unbound",
                        "object": "待定位对象",
                        "concern_key": "未识别",
                        "reason": "本片异常来源尚未识别到确定关注点，场景细化暂缓；未将其视为正常或已覆盖",
                        "source_refs": [
                            {
                                "source_id": d["source_id"],
                                "line_start": r["number"],
                                "line_end": r["number"],
                                "quote": r["text"],
                            }
                            for d in source
                            for r in d["lines"]
                            if r["text"].strip()
                        ],
                    }
                ]
            value = {"scenarios": [], "pending": pending, "excluded": excluded}
            proof = {"provider": "awaiting_identified_concerns"}
        elif (
            task == "exception-generate"
            and not generation_matches(inputs)
            and not self.conversations.revision(key)
        ):
            value = {"scenarios": [], "pending": []}
            proof = {
                "provider": "deterministic_rule_coverage",
                "reason": "没有额外适用语义规则；字段/查询/可用性等由独立工具生成，不额外调用模型",
            }
        elif task in {"gap-compare", "semantic-compare", "global-scenario-match"} and (
            not inputs["left"] or not inputs["right"]
        ):
            value, proof = (
                {
                    "decisions": [],
                    **({"missing": deduplicate(inputs["left"])} if task == "gap-compare" else {}),
                },
                {},
            )
        else:
            value, proof = self.semantic(semantic_task or task, inputs, record)
        if proof.get("provider") == "colleague_structure":
            proof["source_files"] = [
                {"file_id": row["id"], "name": row["name"], "revision": row["revision"]}
                for row in self.import_snapshot
                if row.get("structure_model", {}).get("document", {}).get("source_id")
                in proof["source_ids"]
                or (row.get("behavior_product", {}).get("scenario_document") or {}).get("source_id")
                in proof["source_ids"]
            ]
        input_document_ids = {
            doc.get("source_id")
            for k in ("RR", "SR", "normal-documents", "existing-documents")
            for doc in inputs.get(k, [])
            if isinstance(doc, dict)
        }
        behavior_sources = [
            {
                "file_id": row["id"],
                "name": row["name"],
                "revision": row["revision"],
                "artifact_id": "behavior-input",
            }
            for row in self.import_snapshot
            if row.get("behavior_enabled")
            and any(
                doc and doc.get("source_id") in input_document_ids
                for doc in (
                    row.get("behavior_product", {}).get("normal_document"),
                    row.get("behavior_product", {}).get("scenario_document"),
                )
            )
        ]
        if behavior_sources:
            proof["input_sources"] = behavior_sources
        candidate = deepcopy(value)
        try:
            if imported and imported_result is None:
                from scene_completion.inputs.artifact_imports import merge

                value = merge(task, value, imported)
                proof["import_sources"] = [
                    {
                        "file_id": p["file_id"],
                        "name": p["file_name"],
                        "revision": p["file_revision"],
                        "artifact_id": p["id"],
                    }
                    for p in imported
                ]
            if task == "api-parameters":
                from scene_completion.inputs.api_parameters import canonical_contract

                value = canonical_contract(value)
            if task == "existing-branches":
                from scene_completion.analysis.branch_evidence import complete
                from scene_completion.domain.scenario_types import filter_branches

                value = filter_branches(complete(value, inputs))
            if task == "test-supplement":
                from scene_completion.analysis.test_supplement import mechanical_tests

                value["tests"] = list(
                    {
                        fingerprint(t): t
                        for t in value["tests"] + mechanical_tests(inputs)["tests"]
                    }.values()
                )
            if task == "use-case-align" and self.mocks is None:
                from scene_completion.analysis.use_cases import canonical_correspondence

                value = canonical_correspondence(value, inputs)
            if task == "normal-rules":
                for rule in value["rules"]:
                    rule["id"] = (
                        "normal-" + fingerprint({k: v for k, v in rule.items() if k != "id"})[:20]
                    )
            if task == "components":
                from scene_completion.inputs.component_facts import normalize_externality

                value = normalize_externality(value)
            if task == "existing-bind":
                from scene_completion.analysis.failure_units import normalize_bindings

                value = normalize_bindings(value, inputs)
            if task == "business-crud" and not transform:
                if self.mocks is None:
                    from scene_completion.analysis.crud_review import validate_reviews

                    validate_reviews(value, inputs)
                if scope := inputs.get("crud-entity-scope"):
                    from scene_completion.analysis.crud_scope import record_pending

                    value = record_pending(value, scope, case)
            if task in {"existing-concerns", "test-concerns"}:
                from scene_completion.analysis.concern_alignment import recognize

                value = recognize(inputs, value, inverse=True)
            if task == "concern-match":
                if self.mocks is None:
                    from scene_completion.analysis.recognition_coverage import validate_coverage

                    validate_coverage(value, inputs)
                resolved = resolve_matches(inputs, value["matches"])
                value["matches"] = resolved["matches"]
                value["pending"] = list(
                    {fingerprint(v): v for v in value["pending"] + resolved["pending"]}.values()
                )
            if (
                task in {"exception-generate", "existing-extract", "test-ground-truth"}
                and "pattern-applicability" not in inputs
            ):
                from scene_completion.analysis.normal_rules import normalize_scenarios

                value = normalize_scenarios(value, inputs, truth=task == "test-ground-truth")
                if task == "exception-generate":
                    from scene_completion.analysis.normal_rules import rule_exceptions

                    value["scenarios"] = deduplicate(
                        attach_provenance(
                            inputs,
                            value["scenarios"]
                            + data_exceptions(inputs)
                            + query_exceptions(inputs)
                            + service_exceptions(inputs)
                            + storage_exceptions(inputs)
                            + rule_exceptions(inputs),
                        )
                    )
                    value["pending"] = list(
                        {
                            fingerprint(x): x for x in value["pending"] + pending_rules(inputs)
                        }.values()
                    )
                else:
                    value["scenarios"] = deduplicate(value["scenarios"])
            if task == "existing-extract" and "fused-ssd" in inputs:
                from scene_completion.analysis.inverse_alignment import expand_inverse

                value = expand_inverse(value, inputs)
            if task == "test-ground-truth" and "fused-ssd" in inputs:
                from scene_completion.analysis.inverse_alignment import expand_truth

                value = expand_truth(value, inputs)
                from scene_completion.analysis.failure_units import normalize_test_assertions

                value = normalize_test_assertions(value, inputs)
            if task in {"test-ground-truth", "existing-extract"}:
                from scene_completion.analysis.failure_units import normalize_inverse_units

                value = normalize_inverse_units(value, inputs)
            if (
                task in {"test-ground-truth", "existing-extract", "exception-generate"}
                and "pattern-applicability" not in inputs
            ):
                from scene_completion.domain.scenario_types import filter_scenarios

                value = filter_scenarios(value, inputs, task)
            if self.config.get("scenario_patterns", False) and task in {
                "existing-extract",
                "test-ground-truth",
                "test-additional-truth",
            }:
                from scene_completion.analysis.scenario_patterns import inverse_metadata

                value = inverse_metadata(
                    value,
                    inputs,
                    analysis_settings(self.pattern_settings),
                    truth=task == "test-ground-truth",
                )
            from scene_completion.infrastructure.execution_events import phase

            phase("validating")
            if task in {"exception-generate", "existing-extract", "test-ground-truth"}:
                from scene_completion.analysis.concern_alignment import bind_scenarios

                identified = (
                    inputs.get("concern-match")
                    if task == "exception-generate"
                    else inputs.get("identified-concerns")
                )
                if identified is not None:
                    value = bind_scenarios(value, inputs, identified, gate=True)
            if task in SCHEMAS:
                validate_result(task, value, inputs)
        except ValueError as exc:
            rejection = (
                self.root
                / "agent_rejections"
                / (fingerprint([key, inputs, candidate, str(exc), "postprocess"]) + ".json")
            )
            write_json(
                rejection,
                {
                    "task": task,
                    "node_key": key,
                    "input_hash": fingerprint(inputs),
                    "payload": candidate,
                    "error": str(exc),
                    "identity_error": getattr(exc, "identity_details", None),
                },
            )
            raise TaskRejected(
                {
                    "error": str(exc),
                    "phase": "postprocess",
                    "rejected_output": str(rejection.relative_to(self.root)),
                    "identity_error": getattr(exc, "identity_details", None),
                }
            ) from exc
        if reviewed is None and not skip_review:
            self.reviews.propose(key, task, inputs, value, review_identity)
        meta = {
            "logic_version": code_version(task),
            "input_hash": fingerprint(inputs),
            "source_channel": "task-scoped",
            "execution": proof,
        }
        if task == "components":
            meta.update(resource_metadata(value))
        return {"protocol": PROTOCOL, "task": task, "payload": value, "metadata": meta}

    def verify(value):
        if value.get("protocol") != PROTOCOL or value.get("task") != task:
            raise ValueError("wrong task/protocol result")
        dependencies = {
            dep: read_json(self.root / self.scheduler.state["tasks"][dep]["output_file"])
            for dep in deps
        }
        actual = inputs_for(dependencies)
        saved_hash = value.get("metadata", {}).get("input_hash")
        if saved_hash != fingerprint(actual):
            if "crud-entity-scope" not in actual or saved_hash != fingerprint(
                inputs_for(dependencies, legacy_crud=True)
            ):
                raise ValueError("cached task input changed")
            if self.mocks is None:
                from scene_completion.analysis.crud_review import validate_reviews

                validate_reviews(value["payload"], actual)
            from scene_completion.analysis.crud_scope import record_pending

            if (
                record_pending(deepcopy(value["payload"]), actual["crud-entity-scope"], case)
                != value["payload"]
            ):
                raise ValueError("cached CRUD result requires unresolved entity scope review")
        # Re-run schema checks on cache reads, not just initial responses.
        if task in SCHEMAS:
            validate_result(task, value["payload"], actual)
        if verify_derivation:
            # Schema validity does not prove a saved tool aggregate was derived
            # correctly. Recompute this bounded, pure transform from validated
            # dependencies; invalid old aggregates are rebuilt without recalling
            # the successful upstream model tasks or trusting a code hash.
            expected = transform(deepcopy(actual))
            if fingerprint(expected) != fingerprint(value["payload"]):
                raise ValueError(
                    "deterministic artifact differs from its current dependencies; "
                    "rebuild this tool task, preserve valid upstream model outputs"
                )

    from scene_completion.workflow.node_repair import repair_revision

    version = {
        "cache_contract": "producer-independent-v1",
        "protocol": PROTOCOL,
        "code": code_version(task),
        "schema": fingerprint(schema(task)) if task in SCHEMAS else None,
        "static": fingerprint(static),
        "identity": self.artifact_identity,
        "imports": import_identity,
        "guidance_revision": self.conversations.revision(key),
        "review_revision": self.reviews.revision(key),
        "cases": [case] if case else [],
        "registry": registry()["hash"]
        if task
        in {
            "existing-concerns",
            "test-concerns",
            "concern-compare",
            "concern-evaluation",
            "normal-rules",
            "concern-match",
            "exception-generate",
            "existing-extract",
            "test-ground-truth",
            "gap-compare",
            "semantic-compare",
            "enriched-view",
            "missing-report",
            "exception-evaluation",
        }
        else None,
    }
    from scene_completion.review.review_questions import materials

    if task == "exception-scope":
        from scene_completion.review.scope_reviews import revision

        version["scope_review"] = revision(self.root.parent, key)
    if confirmation := materials(self.root.parent, key):
        version["business_confirmation"] = fingerprint(confirmation)
    if revision := repair_revision(self.root, key):
        version["external_repair"] = revision
    if self.config.get("scenario_patterns", False) and task in {
        "pattern-applicability",
        "existing-extract",
        "test-ground-truth",
        "test-additional-truth",
        "gap-recommend",
    }:
        version["pattern_settings_hash"] = (
            self.pattern_settings["hash"]
            if task == "gap-recommend"
            else analysis_settings(self.pattern_settings)["hash"]
        )
    if self.config.get("scenario_patterns", False) and task == "gap-recommend":
        version.update(
            history_hash=fingerprint(self.recommendation_history),
            recommendation_run=self.session_id,
        )
    if external_contract:
        version["external_declarations"] = REVISION
    if imported:
        version["import_logic"] = component_version("artifact-imports")
    self.scheduler.add(
        Task(
            key,
            case or "shared",
            task,
            tuple(deps),
            version=version,
            execute=execute,
            repair=execute,
            verify=verify,
        )
    )
    self.scheduler.tasks[key].attempt_identity = fingerprint(
        {
            k: v
            for k, v in self.config.items()
            if k not in {"run_root", "cache_dir", "priority_cases", "supplement_tests"}
        }
    )
    self.scheduler.tasks[key].recoverable = bool(
        self.mode == "external"
        and self.mocks is None
        and not transform
        and task not in {"gap-compare", "semantic-compare"}
    )


def partitioned(self, key, task, deps, build, case):
    """Expand after inputs validate; each child has its own review/cache/retry."""
    from scene_completion.workflow.task_partitions import merge_parts, split_task

    def waiting(d):
        raise TaskBlocked("dependency_wait", {"reason": "等待子任务展开"})

    self.add(key, task, deps, build=build, transform=waiting, case=case)
    self.scheduler.tasks[key].deferred = True

    def expand():
        inputs = build(
            {
                d: payload(read_json(self.root / self.scheduler.state["tasks"][d]["output_file"]))
                for d in deps
            }
        )
        units = split_task(task, inputs)
        children = []
        for unit, part in units:
            child = key + "--part-" + fingerprint(unit)[:10]
            children.append(child)
            inherited = {
                m["detail"].get("parent_message_id") for m in self.conversations.list(child)
            }
            for message in self.conversations.list(key):
                if message["kind"] == "guidance" and message["id"] not in inherited:
                    self.conversations.append(
                        child,
                        "guidance",
                        message["text"],
                        {"parent_message_id": message["id"], "parent_task": key},
                    )
            self.add(
                child, task, deps, static=part, build=lambda d, part=part: deepcopy(part), case=case
            )
            self.scheduler.tasks[child].display_label = (
                TASKS.get(task, ("", task))[1] + " · " + unit
            )
        self.scheduler.tasks.pop(key)
        self.add(
            key,
            task,
            tuple(children) or deps,
            build=lambda d, inputs=inputs: inputs,
            transform=lambda d, children=children: merge_parts(
                task,
                [
                    payload(read_json(self.root / self.scheduler.state["tasks"][c]["output_file"]))
                    for c in children
                ],
            ),
            case=case,
            skip_review=True,
        )

    self.partitions.append((tuple(deps), expand))
