"""Semantic Executor."""

from copy import deepcopy

from scene_completion.analysis.exception_generation import (
    data_exceptions,
    pending_rules,
    query_exceptions,
    service_exceptions,
    storage_exceptions,
)
from scene_completion.analysis.validation import validate_result
from scene_completion.domain.contracts import PROTOCOL, packet
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.workflow.scheduler import TaskBlocked, TaskRejected


def semantic(self, task, inputs, record):
    p = packet(task, inputs, [record["case"]] if record.get("case") not in (None, "shared") else [])
    from scene_completion.infrastructure.execution_events import context

    _, event_context = context()
    p["node_key"] = event_context.get("task_key", task)
    from scene_completion.infrastructure.execution_events import emit
    from scene_completion.models.usage_audit import context_summary

    emit("context_prepared", task=task, context=context_summary(inputs))
    p["skill_text"] = self.skill_text(task)
    if task == "exception-generate":
        # These are derived only from this task's positive inputs. They are
        # not E/GT, previous G, or semantic answers from another channel.
        from scene_completion.analysis.normal_rules import rule_exceptions

        p["tool_rule_coverage"] = {
            "data": data_exceptions(inputs),
            "query": query_exceptions(inputs),
            "availability": service_exceptions(inputs),
            "storage": storage_exceptions(inputs),
            "normal_rules": rule_exceptions(inputs),
            "pending": pending_rules(inputs),
        }
        p["tool_rule_instruction"] = (
            "工具会合并上述确定性候选。模型只需返回其他有具体正常规则支持的双方/操作异常，可返回空scenarios；不要改写字段规则或编造后续行为。"
        )
    if task == "concern-match":
        p["tool_rule_instruction"] = (
            "本任务独立识别本片四要素对象上的适用具体关注点，明示字段约束须逐项返回证据。注册表只是候选；已确认的人类调用身份/权限、外部服务可用性由工具策略保底。不得填写policy_id，不编造认证机制；未知规则写pending，不输出具体场景。幂等性由全局C/U/D任务处理。"
        )
        if inputs.get("recognition_scope") == "data":
            p["tool_rule_instruction"] = (
                "本片仅识别实际接口数据字段的关注点；不输出双方、操作或业务关注点。这些由独立片处理。已声明字段检查须逐项识别并引用证据，工具不会补入G。"
            )
    if record.get("rounds"):
        p["repair"] = {
            "failure": record.get("failure"),
            "round": record["rounds"],
            "rule": "仅修复本任务；不读取其他通道。",
        }
        candidate = (record.get("failure") or {}).get("rejected_output")
        if candidate:
            path = (self.root / candidate).resolve()
            if path.is_relative_to(self.root.resolve()) and path.is_file():
                previous = read_json(path)
                if (
                    previous.get("task") == task
                    and previous.get("node_key") == p["node_key"]
                    and previous.get("input_hash") == fingerprint(inputs)
                ):
                    p["repair"]["candidate"] = previous["payload"]
                    if previous.get("review_questions") is not None:
                        p["repair"]["review_questions"] = previous["review_questions"]
                    if previous.get("candidate_format") == "model":
                        p["repair"]["candidate_format"] = "model"
                    p["repair"]["rule"] = (
                        "候选尚未通过校验。只定向修复列出的错误，保留有据且合法的部分；所有字段仍须重新满足Schema、当前指导与原文引用。"
                    )
    p["batch_id"] = fingerprint({k: v for k, v in p.items() if k != "batch_id"})
    batch = p["batch_id"]
    write_json(self.root / "packets" / (batch + ".json"), p)
    from scene_completion.workflow.node_repair import read_repair

    repaired = read_repair(self.root, p, self.conversations.revision(p["node_key"]))
    if repaired is not None:
        validate_result(task, repaired["payload"], inputs)
        emit(
            "result_reused",
            provider="external_code_agent_repair",
            revision=repaired["revision"],
            reason="外部修复通过输入、Schema及来源校验",
        )
        return deepcopy(repaired["payload"]), {
            "provider": "external_code_agent_repair",
            "revision": repaired["revision"],
            "note": repaired["note"],
        }
    if self.mode == "external" and self.mocks is None:
        from scene_completion.workflow.positive_reuse import find

        reused = find(self.root, task, inputs, p["case_ids"], p["skill_text"])
        if reused:
            value, source = reused
            emit(
                "result_reused",
                **source,
                reason="unchanged positive source/contract/Skill; actual scope and evidence revalidated",
            )
            return value, {"provider": "verified_positive_reuse", **source}
    semantic_identity = fingerprint(
        {
            "task": task,
            "input": inputs,
            "skill": p["skill_text"],
            "schema": p["output_schema"],
            "endpoint": self.identity["endpoint_hash"],
            "model": self.identity["model"],
            "guidance": self.conversations.revision(p["node_key"]),
        }
    )
    cached_response = self.root / "semantic_responses" / (semantic_identity + ".json")
    if (
        self.mode == "external"
        and self.mocks is None
        and cached_response.exists()
        and not record.get("rounds")
    ):
        cached = read_json(cached_response)
        try:
            from scene_completion.workflow.semantic_reuse import replay

            replayed = replay(self.root, cached, task, inputs)
            validate_result(task, replayed, inputs)
        except (ValueError, KeyError, TypeError):
            pass
        else:
            emit(
                "result_reused",
                source_file=str(cached_response.relative_to(self.root)),
                reason="相同语义输入、Schema、Skill、模型及指导；重新执行工具规范化",
            )
            return replayed, {
                "semantic_response_reused": True,
                "original_execution": cached.get("proof"),
            }
    if (
        self.mode == "external"
        and self.mocks is None
        and task
        in {
            "concern-match",
            "existing-concerns",
            "test-concerns",
            "existing-extract",
            "test-ground-truth",
        }
    ):
        from scene_completion.workflow.semantic_reuse import identity as reuse_identity
        from scene_completion.workflow.semantic_reuse import index as reuse_index

        if not hasattr(self, "_semantic_seeds"):
            self._semantic_seeds = reuse_index(
                self.root,
                self.identity["model"],
                self.identity["endpoint_hash"],
                self.conversations,
            )
        projected = reuse_identity(
            task,
            inputs,
            p["skill_text"],
            p["output_schema"],
            self.identity["model"],
            self.identity["endpoint_hash"],
            self.conversations.revision(p["node_key"]),
        )
        seed = self._semantic_seeds.get(projected)
        if seed:
            cached = read_json(seed)
            try:
                from scene_completion.workflow.semantic_reuse import replay

                value = replay(self.root, cached, task, inputs)
                validate_result(task, value, inputs)
            except (ValueError, KeyError, TypeError):
                pass
            else:
                emit(
                    "result_reused",
                    source_file=str(seed.relative_to(self.root)),
                    reason="同一识别输入及相同或明确审计兼容的Skill；已重新规范化及校验，不重复调用模型",
                )
                return value, {
                    "semantic_response_reused": True,
                    "tool_only_reprocessing": True,
                    "original_execution": cached.get("proof"),
                }
    raw = None
    if self.mocks is not None:
        value = self.mocks.get(record.get("stage"), self.mocks.get(task))
        if value is None:
            raise TaskBlocked("pending", {"mock_missing": task})
        raw = value(p) if callable(value) else deepcopy(value)
    elif self.responses_dir and (self.responses_dir / (batch + ".json")).exists():
        envelope = read_json(self.responses_dir / (batch + ".json"))
        if (
            envelope.get("protocol") != PROTOCOL
            or envelope.get("batch_id") != batch
            or envelope.get("task") != task
        ):
            raise TaskRejected(
                {"error": "external result is not bound to this protocol/task/input"}
            )
        raw = envelope["payload"]
    elif self.mode == "external":
        if not self.client:
            raise ValueError("external mode needs a configured semantic client")
        try:
            if task in {"gap-compare", "semantic-compare"}:
                from scene_completion.analysis.comparison_batches import compare_in_batches

                raw = compare_in_batches(
                    p,
                    self.client,
                    self.root,
                    self.conversations.revision(p["node_key"]),
                    call=lambda child: (
                        self.client.agent(child)
                        if hasattr(self.client, "post")
                        else self.gate.call(self.client.agent, child)
                    ),
                )
            elif record.get("recovery_dispatch"):
                from scene_completion.workflow.node_recovery import generate

                raw = generate(self, p, record)
            else:
                raw = (
                    self.client.agent(p)
                    if hasattr(self.client, "post")
                    else self.gate.call(self.client.agent, p)
                )
        except ValueError as exc:
            diagnostic = getattr(exc, "response_diagnostic", None)
            if diagnostic:
                attempt = self.root / "attempts" / batch / (str(record.get("rounds", 0)) + ".json")
                write_json(
                    attempt, {"task": task, "protocol": PROTOCOL, "rejected_response": diagnostic}
                )
                raise TaskRejected(
                    {"error": str(exc), "rejected_output": str(attempt.relative_to(self.root))}
                ) from exc
            raise
    else:
        raise TaskBlocked(
            "pending", {"packet": str(self.root / "packets" / (batch + ".json")), "batch_id": batch}
        )
    if not isinstance(raw, dict):
        raise TaskRejected({"error": "model result must be a JSON object"})
    proof = {k: raw[k] for k in ("execution_model_evidence", "native_execution") if k in raw}
    value = {k: v for k, v in raw.items() if k not in proof}
    if inputs.get("imported-fragments"):
        from scene_completion.inputs.artifact_imports import merge

        value = merge(task, value, inputs["imported-fragments"])
    if task == "api-map":
        from scene_completion.inputs.http_interfaces import normalize_mapping

        value = normalize_mapping(value)
    if task == "api-parameters":
        from scene_completion.inputs.api_documents import complete_success_responses

        value = complete_success_responses(value, inputs)
    attempt = self.root / "attempts" / batch / (str(record.get("rounds", 0)) + ".json")
    write_json(attempt, {"task": task, "protocol": PROTOCOL, "payload": value, "execution": proof})
    try:
        validate_result(task, value, inputs)
        if task in {"rr-ssd", "sr-ssd"} and any(inputs.values()) and not value["interactions"]:
            raise ValueError(
                "nonempty positive document requires real SSD interactions, not an empty successful result"
            )
        if task == "components" and any(inputs.values()) and not value["components"]:
            raise ValueError("nonempty RR/SR requires evidenced components")
        scope = p["case_ids"]
        if scope and task in {
            "rr-ssd",
            "sr-ssd",
            "exception-generate",
            "existing-extract",
            "test-ground-truth",
        }:
            records = value.get("interactions", value.get("scenarios", []))
            if any(r["case_id"] not in scope for r in records):
                raise ValueError("result outside selected case scope")
            if task in {"rr-ssd", "sr-ssd"} and set(scope) != {r["case_id"] for r in records}:
                raise ValueError("selected SSD cases incomplete")
    except ValueError as exc:
        raise TaskRejected(
            {"error": str(exc), "rejected_output": str(attempt.relative_to(self.root))}
        ) from exc
    if self.mode == "external" and self.mocks is None:
        write_json(
            cached_response, {"identity": semantic_identity, "payload": value, "proof": proof}
        )
    return value, proof
