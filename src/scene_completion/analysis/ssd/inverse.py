"""Independent IR/SR and recovered-test classification and SSD binding.

Only explicit identifiers and conservative literal rules are automated. Unclear
cases retain their full source records for an agent or a human to resolve.
"""

import json
import re
from copy import deepcopy

from scene_completion.domain.ssd.construction import ident, unique


def _field_candidates(step, condition):
    result = []
    for field in step["data"]:
        name = field["name"]
        if re.search(r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])", condition):
            result.append(field)
    return result


def _classification(condition, expected):
    """Return concern family; concrete CRUD kind is selected after locating the step."""
    if re.search(
        r"连接不可达|连接失败|服务不可用|数据库不可用|DATABASE_UNAVAILABLE",
        condition + " " + expected,
        re.I,
    ):
        return "service.base.availability"
    if re.search(
        r"相同.*(?:幂等|Idempotency-Key)|重复.*提交|幂等冲突|同键", condition, re.I
    ) and not re.search(r"缺失|未提供|长度|格式", condition):
        return "crud.idempotency"
    if re.search(r"service[-_]id.*(?:other|其他|越权)|跨服务.*隔离", condition, re.I):
        return "service_relation.data_isolation"
    if re.search(r"级联|删除.*(?:子对象|云端配置).*(?:残留|未删除|未同步)", condition):
        return "global.cascade_operation"
    if re.search(r"前置.*未完成.*后续|顺序颠倒|颠倒.*顺序", condition):
        return "global.call_order"
    if re.search(
        r"跨服务.*(?:不一致|一致性)|一侧成功.*一侧失败|上游.*下游.*(?:旧版本|不一致)", condition
    ):
        return "global.dependency_consistency"
    if re.search(r"Authorization|token|身份|认证", condition, re.I):
        return "human.authentication"
    if re.search(r"无.*权限|没有.*权限|越权|无权|不属于当前(?:顾客|用户|商家)", condition):
        return "human.authorization"
    if re.search(r"version.*(?:不一致|冲突)|并发|版本冲突", condition, re.I):
        return "crud.concurrency"
    if re.search(r"(?:引用|指向|父资源|关联资源).*(?:不存在|已删除|无效)", condition):
        return "api.data.validity"
    if re.search(r"不存在|未找到|NOT_FOUND", condition):
        return "crud.existence"
    if re.search(r"发布前置|待发布.*price", condition):
        return "service.release_activation.prerequisite"
    if re.search(
        r"同名|不可变|原商品|状态|status=|已经是PUBLISHED|业务.*约束|productType=SERVICE.*price",
        condition,
        re.I,
    ):
        return "service.business_attribute_constraint"
    if re.search(r"SQL.*注入|特殊字符", condition, re.I):
        return "database.special_characters"
    if re.search(r"未提供|缺失|遗漏|missing", condition, re.I):
        return "api.data.completeness"
    if re.search(
        r"不是(?:整数|数字|数组|boolean|布尔|字符串)|类型(?:错误|不符)|type error", condition, re.I
    ):
        return "api.data.type"
    if re.search(r"长度|超长", condition):
        return "api.data.length"
    if re.search(r"格式|正则", condition):
        return "api.data.format"
    if re.search(r"大小|字节|\b(?:MB|KB)\b", condition, re.I):
        return "api.data.size"
    if re.search(r"超过|低于|负值|不在.*集合|枚举|越界|范围|大于|小于", condition):
        return "api.data.range"
    return None


def _locate(bundle, record, family):
    steps = bundle["steps"]
    raw = record.get("raw", {})
    note = str(raw.get("note") or "")
    direct = raw.get("step_id") or raw.get("interaction_id") or raw.get("behavior_interaction_id")
    candidates = [s for s in steps if s["id"] == direct] if direct else []
    if direct and not candidates:
        candidates = [s for s in steps if direct in s.get("aliases", [])]
    if not candidates and not direct:
        after = (raw.get("extend_at_main") or {}).get("after")
        candidates = [step for step in steps if after and step["id"] == after]
    if not candidates:
        # Match complete IDs, never a shorter request prefix inside DB-REQ.
        ids = re.findall(r"交互\s*([A-Za-z0-9_-]+)", note)
        candidates = [s for s in steps if s["id"] in ids]
    after = (raw.get("extend_at_main") or {}).get("after")
    failure = re.search(r"失败于步骤\s*([RS]\d+)", note)
    label = failure[1] if failure else after
    local = [s for s in steps if label and label in s.get("aliases", []) and s["kind"] == "action"]
    if family == "crud.idempotency":
        actions = [s for s in candidates if s["kind"] == "action"] or local
        if len(actions) == 1 and not actions[0]["operation"].get("kinds"):
            validator = actions[0]
            inbound = [
                s
                for s in steps
                if s["kind"] != "action"
                and s["direction"] == "request"
                and s["receiver"]["id"] == validator["receiver"]["id"]
                and s.get("layer") == validator.get("layer")
                and s.get("order", 0) < validator.get("order", 0)
                and set(s["operation"].get("kinds", [])) & {"create", "update", "delete"}
            ]
            if len(inbound) == 1:
                return inbound[0]
    field_family = family and family.startswith("api.data.")
    business = family in {
        "service.business_attribute_constraint",
        "crud.concurrency",
        "crud.existence",
        "service.release_activation.prerequisite",
        "database.special_characters",
    }
    if business and len(local) == 1 and local[0]["receiver"].get("technology") == "database":
        return local[0]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates and label:
        candidates = [s for s in steps if label in s.get("aliases", [])]
        if len(candidates) == 1 and candidates[0]["kind"] != "action":
            return candidates[0]
    own_ids = {n.get("id") for n in raw.get("interaction", [])}
    own = [s for s in steps if s["id"] in own_ids and s["kind"] != "action"]
    layer = record.get("layer")
    if layer:
        own = [s for s in own if s["layer"] == layer]
    if field_family:
        response = "成功响应" in record["condition"] or "response." in record["condition"]
        relevant = [
            s
            for s in own
            if (s["direction"] == "return") == response
            and _field_candidates(s, record["condition"])
        ]
        if len(relevant) == 1:
            return relevant[0]
        if len(local) == 1:
            # A local validator refers back to the actual message it validates.
            validator = local[0]
            relevant = [
                s
                for s in own
                if s["direction"] == "request"
                and s["receiver"]["id"] == validator["receiver"]["id"]
                and _field_candidates(s, record["condition"])
            ]
            if len(relevant) == 1:
                return relevant[0]
    if family == "service.base.availability":
        relevant = [
            s
            for s in own
            if s["direction"] == "request" and s["receiver"]["name"] in record["condition"]
        ]
        if len(relevant) == 1:
            return relevant[0]
    if family and (family.startswith("human.") or family.startswith("service_relation.")):
        relevant = [
            s
            for s in own
            if s["direction"] == "request"
            and (s["sender"]["type"] == "human") == family.startswith("human.")
        ]
        if len(relevant) == 1:
            return relevant[0]
    if len(candidates) == 1 and not field_family:
        return candidates[0]
    if business and len(local) == 1:
        return local[0]
    return None


TARGETS = {"sender": "sender", "data": "data", "receiver": "receiver", "entity": "data"}


def _target_of(record):
    """Supplied mounts name the data object ``entity``; the SSD calls it ``data``."""
    return TARGETS.get(str(record.get("target") or "").strip().lower())


def _entity_attribute(bundle, step, record, names=()):
    declared_entity = record.get("entity_id")
    declared_attribute = record.get("attribute")
    allowed = {declared_entity} if declared_entity else set(step["entity_ids"])
    matches = [
        (entity["id"], attribute["name"])
        for entity in bundle.get("entities", [])
        if entity["id"] in allowed
        for attribute in entity.get("attributes", [])
        if (
            attribute["name"] == declared_attribute
            or not declared_attribute
            and attribute["name"] in names
        )
    ]
    return matches[0] if len(set(matches)) == 1 else (None, None)


def _supplied(output, bundle, channel_name, step, record, condition, expected, refs):
    """Validate a supplied mount against the positive step, field and entity indexes."""
    from scene_completion.domain.ssd.construction import add_concern, add_scenario

    target = _target_of(record)
    parameter = record.get("parameter") or {}
    entity, attribute, field = None, None, None
    if record.get("target") == "entity":
        entity, attribute = _entity_attribute(bundle, step, record)
        if not entity or declared_entity_mismatch(step, entity):
            return False
    elif parameter or target == "data":
        name = parameter.get("name") or record.get("field_name")
        location = parameter.get("location")
        direction = parameter.get("direction")
        if isinstance(name, str) and not location and "." in name:
            location, _, name = name.partition(".")
        if direction and direction not in {
            step["direction"],
            "response" if step["direction"] == "return" else "request",
            "storage" if location == "storage" else None,
        }:
            return False
        fields = [
            field
            for field in step["data"]
            if field["name"] == name and (not location or field["location"] == location)
        ]
        if len(fields) != 1:
            return False
        field, target = fields[0], "data"
    if not target:
        return False
    concern = add_concern(
        output,
        bundle,
        channel_name,
        step,
        record["concern_key"],
        target,
        field=field,
        entity=entity,
        attribute=attribute,
        condition=condition,
        refs=refs,
    )
    if not concern:
        return False
    scene = add_scenario(output, concern, condition, expected, refs, record["id"])
    if record.get("extension_id"):
        scene["extension_id"] = record["extension_id"]
    if record.get("failure_step_id"):
        scene["failure_step_id"] = record["failure_step_id"]
    return True


def declared_entity_mismatch(step, entity):
    return bool(step["entity_ids"] and entity not in step["entity_ids"])


def recognize_records(bundle, records, channel_name):
    """Independent conservative fallback; unresolved records remain reviewable."""
    from scene_completion.domain.ssd.construction import (
        add_concern,
        add_scenario,
        channel,
        pending,
    )

    output = channel()
    output["project_records"] = []
    from scene_completion.domain.concern_registry import default_registry
    from scene_completion.domain.current_scope import current_registry

    definitions = current_registry(bundle.get("registry") or default_registry())["definitions"]
    from scene_completion.domain.current_scope import STRUCTURED_PROFILES

    if bundle.get("analysis_profile") in STRUCTURED_PROFILES:
        for record in records:
            row = pending(
                record["id"],
                record["condition"],
                record["source_refs"],
                step_id=record.get("step_ref"),
                reason=record.get("reason") or "等待独立识别",
                original=record,
                needs_semantic=True,
            )
            output["pending"].append(row)
        return output
    for record in records:
        condition, expected, refs = (
            record["condition"],
            record.get("expected", ""),
            record["source_refs"],
        )
        rid = record["id"]
        if record.get("scenario_type") in {"normal", "main", "alternative", "optional"}:
            continue
        if record.get("scenario_type") == "out_of_scope":
            continue
        if record.get("status") == "pending" or record.get("scenario_type") == "pending":
            output["pending"].append(
                pending(
                    rid,
                    condition,
                    refs,
                    step_id=record.get("step_ref"),
                    reason=record.get("reason") or "异常类型或具体条件待确认",
                    original=record,
                    needs_semantic=record.get("needs_semantic", False),
                )
            )
            continue
        if record.get("step_ref") and record.get("concern_key"):
            # The supplied case already mounted this failure on a step and a
            # concern; only identities and wording are re-checked here.
            step = next((s for s in bundle["steps"] if s["id"] == record["step_ref"]), None)
            if step is None:
                output["pending"].append(
                    pending(rid, condition, refs, reason="原步骤已移除，请重新挂载")
                )
                continue
            if not _supplied(output, bundle, channel_name, step, record, condition, expected, refs):
                output["pending"].append(
                    pending(
                        rid,
                        condition,
                        refs,
                        reason="关注点或字段不能唯一挂载，请核对步骤、对象和字段",
                    )
                )
            continue
        if record.get("scenario_type") == "pending" or re.search(
            r"待确认|待澄清|不能判定", expected + " " + str(record.get("raw", {}).get("note", ""))
        ):
            output["pending"].append(
                pending(
                    rid,
                    condition,
                    refs,
                    reason="异常类型或具体条件待确认",
                    needs_semantic=False,
                    original=record,
                )
            )
            continue
        family = _classification(condition, expected)
        scope = definitions.get(family, {}).get("scope")
        if scope in {"business_chain", "architecture"}:
            located = _locate(bundle, record, family)
            output["project_records"].append(
                {
                    **deepcopy(record),
                    "case_id": bundle["case"]["id"],
                    "key": family,
                    "scope": scope,
                    "channel": channel_name,
                    "step_id": located["id"] if located else None,
                }
            )
            continue
        step = _locate(bundle, record, family)
        if not step or not family:
            output["pending"].append(
                pending(
                    rid,
                    condition,
                    refs,
                    reason="需要确认交互对象或关注点分类",
                    needs_semantic=True,
                    original=record,
                )
            )
            continue
        kinds = step["operation"].get("kinds", [])
        kind = next((k for k in kinds if k in {"create", "read", "update", "delete"}), None)
        if family == "crud.existence":
            family = (
                "service.query_retrieval.resource_existence"
                if kind == "read"
                else f"service.crud.{kind}.resource_existence"
                if kind
                else None
            )
        elif family == "crud.concurrency":
            family = (
                f"service.crud.{kind}.concurrency_consistency"
                if kind in {"create", "update", "delete"}
                else None
            )
        elif family == "crud.idempotency":
            family = (
                f"service.crud.{kind}.idempotency"
                if kind in {"create", "update", "delete"}
                else None
            )
        occurrence = step
        if family and family.startswith("human.") and step["kind"] == "action":
            triggers = [
                candidate
                for candidate in bundle["steps"]
                if candidate["kind"] == "interaction"
                and candidate["direction"] == "request"
                and candidate["sender"]["type"] == "human"
                and candidate["order"] < step["order"]
            ]
            if len(triggers) == 1:
                step = triggers[0]
        if (
            family in {"human.authentication", "human.authorization"}
            and step["sender"]["type"] == "service"
        ):
            family = family.replace("human.", "service_relation.")
        if not family:
            output["pending"].append(
                pending(
                    rid,
                    condition,
                    refs,
                    reason="实际 CRUD 操作尚未确定",
                    needs_semantic=True,
                    original=record,
                )
            )
            continue
        target = "sender" if family.startswith("human.") else "receiver"
        fields = [None]
        attributes = [
            a["name"]
            for e in bundle.get("entities", [])
            if e["id"] in step["entity_ids"]
            for a in e.get("attributes", [])
            if re.search(r"(?<![\w.])" + re.escape(a["name"]) + r"(?!\w)", condition)
        ]
        entity, attribute = _entity_attribute(bundle, step, record, attributes)
        if family.startswith("api.data."):
            target = "data"
            fields = _field_candidates(step, condition)
            if not fields and entity and attribute:
                fields = [None]
            if len(fields) != 1:
                output["pending"].append(
                    pending(
                        rid,
                        condition,
                        refs,
                        reason="字段不能唯一定位，需拆分失败条件或确认字段",
                        needs_semantic=True,
                        original=record,
                    )
                )
                continue
        elif family == "service.business_attribute_constraint" and step["direction"] == "return":
            target = "sender"
        if not family.startswith("api.data.") and family != "service.business_attribute_constraint":
            entity, attribute = None, None
        for field in fields:
            concern = add_concern(
                output,
                bundle,
                channel_name,
                step,
                family,
                target,
                field=field,
                entity=None if field else entity,
                attribute=None if field else attribute,
                condition=condition,
                refs=refs,
            )
            if concern:
                concern["scope"] = "interaction"
                scene = add_scenario(output, concern, condition, expected, refs, rid)
                scene["scope"] = "interaction"
                if occurrence["id"] != step["id"]:
                    scene["failure_step_id"] = occurrence["id"]
            else:
                output["pending"].append(
                    pending(
                        rid,
                        condition,
                        refs,
                        reason="当前关注点体系没有对应分类",
                        needs_semantic=True,
                        original=record,
                    )
                )
    return output


def _provided(bundle, row, channel_name):
    supplied_id = row.get("id")
    sid = (
        supplied_id
        if re.fullmatch(r"(?:E|GT)-scenario-[a-f0-9]{24}", str(supplied_id))
        and supplied_id.startswith(channel_name + "-")
        else ident(channel_name + "-scenario", bundle["case"]["id"], "supplied", supplied_id)
    )
    return {
        **row,
        "id": sid,
        "original_id": row.get("id"),
        "scenario_type": row.get("scenario_kind") or row.get("status") or "exception",
        "raw": row,
    }


def existing_channel(bundle, case_dir, sources, supplied=(), raw=None):
    from scene_completion.inputs.structured.ordered_behaviors import scenario_kind

    records = [_provided(bundle, row, "E") for row in supplied]
    candidates = []
    from scene_completion.domain.current_scope import STRUCTURED_PROFILES

    entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
    for layer in () if entity_only else ("IR", "SR"):
        for path in sorted((case_dir / "behaviour" / layer).glob("*.json")):
            branch = json.loads(path.read_text(encoding="utf-8-sig"))
            candidates.append((layer, path, "", branch))
    for key, branch in (raw or {}).get("operations", {}).items():
        pointer = "/operations/" + key.replace("~", "~0").replace("/", "~1")
        layer = "IR" if str(branch.get("source_layer") or "").upper() in {"IR", "RR"} else "SR"
        candidates.append((layer, case_dir / "SysOperation.json", pointer, branch))

    for layer, path, pointer, branch in candidates:
        kind = scenario_kind(branch)
        if (
            kind == "main"
            or not branch.get("guard")
            or (not entity_only and kind in {"normal", "alternative", "optional"})
        ):
            continue
        responses = [
            n.get("message")
            for n in branch.get("system_response", []) + branch.get("interaction", [])
            if n.get("message")
            and (n in branch.get("system_response", []) or n.get("direction") == "return")
        ]
        outcome = responses or [n["content"] for n in branch.get("action", []) if n.get("content")]
        expected = "；".join(dict.fromkeys(outcome))
        if (
            not entity_only
            and isinstance(branch.get("resume_at_main"), dict)
            and not any(
                re.search(r"HTTP\s*[45]\d{2}|返回\s*[A-Z]+_[A-Z_]+|拒绝|失败", value)
                for value in outcome
            )
        ):
            continue
        original_id = branch.get("ID") or path.stem
        records.append(
            {
                "id": ident("E-scenario", bundle["case"]["id"], layer, original_id),
                "original_id": original_id,
                "condition": branch["guard"],
                "expected": expected,
                "source_refs": sources.refs(branch, sources.add(path), pointer),
                "layer": "RR" if layer == "IR" else "SR",
                "scenario_type": kind or "exception",
                "failure_step_id": branch.get("failure_step_id")
                or (None if entity_only else (branch.get("extend_at_main") or {}).get("after")),
                "failure_step_hint": branch.get("failure_step_hint"),
                "raw": branch,
            }
        )

    def normalize(value):
        return re.sub(r"\s+", "", value or "")

    if entity_only:
        return recognize_records(bundle, records, "E")

    merged = {}
    for record in records:
        raw = record["raw"]
        code = re.search(r"_SC_EX_(.+)$", record["original_id"] or "")
        anchor = record.get("step_ref") or (raw.get("extend_at_main") or {}).get("after")
        expected = record.get("expected") or ""
        responses = [
            line for line in expected.split("；") if re.match(r"返回\s*HTTP\s*[45]\d{2}", line)
        ]
        terminal = "；".join(responses) if code and responses else expected
        error = re.search(
            r"\b(?:ORDER_|PRODUCT_|NAME_|DATABASE_|INVALID_|AUTH_|STATE_)[A-Z_]+", terminal
        )
        certain = code or (error and anchor)
        key = (
            code[1] if code else (error[0] if certain else ""),
            normalize(record["condition"]),
            (error[0] if error and anchor and not code else normalize(terminal)),
            "" if code else str(anchor or ""),
            record.get("target"),
            record.get("entity_id"),
            record.get("attribute"),
        )
        previous = merged.get(key)
        if previous is None:
            merged[key] = record
            continue

        # Prefer a separately authored SR branch over a fused copy that has lost
        # its local branch markers or explicit step citations.
        def score(item):
            return (
                item.get("layer") == "SR",
                any(
                    not (ref.get("json_pointer") or "").startswith("/operations/")
                    for ref in item["source_refs"]
                ),
                bool(
                    _locate(
                        bundle, item, _classification(item["condition"], item.get("expected", ""))
                    )
                ),
            )

        primary = deepcopy(record if score(record) > score(previous) else previous)
        primary["source_refs"] = unique(previous["source_refs"] + record["source_refs"])
        merged[key] = primary

    def occurrence(record):
        after = (record["raw"].get("extend_at_main") or {}).get("after")
        return (
            after,
            normalize(record["condition"]),
            record.get("target"),
            record.get("entity_id"),
            record.get("attribute"),
        )

    concrete = {}
    for record in merged.values():
        anchor = occurrence(record)
        if anchor[0] and record.get("expected"):
            concrete.setdefault(anchor, []).append(record)
    retained = []
    for record in merged.values():
        # Attach a partial branch only when its explicit occurrence and condition
        # uniquely identify an outcome supplied by another layer.
        complete = concrete.get(occurrence(record), [])
        if not record.get("expected") and len(complete) == 1:
            complete[0]["source_refs"] = unique(complete[0]["source_refs"] + record["source_refs"])
            continue
        retained.append(record)
    return recognize_records(bundle, retained, "E")


def test_channel(bundle, sources, *, supplied=(), mapping=None, mapping_source=None):
    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, STRUCTURED_PROFILES
    from scene_completion.domain.ssd.construction import channel, pending
    from scene_completion.inputs.structured.case_names import candidates as case_candidates

    entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
    supplied_records = [_provided(bundle, row, "GT") for row in supplied]
    mapped = (mapping or {}).get("items", [])
    requested_path = (mapping or {}).get("source") or "recovered_usecases.json"
    path = (sources.root / requested_path).resolve()
    if not path.is_relative_to(sources.root.resolve()):
        raise ValueError("测试来源超出输入目录")
    if not path.exists() and not supplied and not mapped:
        result = channel()
        result["pending"].append(
            pending(
                ident("GT-missing", bundle["case"]["id"]), "未提供测试来源", needs_semantic=False
            )
        )
        bundle["gt_source_available"] = False
        return result
    name, case, prefix = None, {}, ""
    if path.exists():
        name = sources.add(path, "test")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            cases = value
        else:
            key = next((k for k in ("usecases", "use_cases", "cases") if k in value), "usecases")
            cases, prefix = value.get(key, []), "/" + key
        source_id = (mapping or {}).get("source_uc_id") or bundle["case"]["id"]
        if bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE:
            found = case_candidates(
                cases,
                bundle["case"]["name"],
                bundle.get("case_entity"),
                explicit_id=(mapping or {}).get("source_uc_id"),
            )
        else:
            found = [(i, row) for i, row in enumerate(cases) if row.get("id") == source_id]
            if not found and not (mapping or {}).get("source_uc_id"):
                found = [
                    (i, row)
                    for i, row in enumerate(cases)
                    if row.get("name") == bundle["case"]["name"]
                ]
        if len(found) == 1:
            index, case = found[0]
            prefix += f"/{index}"
        elif not supplied and not mapped:
            result = channel()
            result["pending"].append(
                pending(
                    ident("GT-case", bundle["case"]["id"]),
                    "测试用例无法唯一对应",
                    [sources.ref(name)],
                    reason="测试用例无法唯一对应",
                    candidates=[row.get("id") for _, row in found],
                )
            )
            bundle["gt_source_available"] = False
            return result

    records = []
    mapped_ids = {row["extension_id"] for row in mapped}
    supplied_by_extension = {}
    for row in supplied_records:
        extension = row.get("extension_id")
        if extension in mapped_ids:
            supplied_by_extension.setdefault(extension, []).append(row)
        else:
            records.append(row)
    extensions = case.get("extensions", [])
    indexed = {extension.get("id"): (i, extension) for i, extension in enumerate(extensions)}
    locations = {e.get("id"): e for e in case.get("evidence_locations", [])}

    def refs_for(extension, index):
        if name is None or index is None:
            return []
        refs = [sources.ref(name, f"{prefix}/extensions/{index}", kind="test")]
        for evidence in extension.get("evidence", []):
            label = re.split(r"[:：]", str(evidence), maxsplit=1)[0].strip()
            if label in locations:
                location = locations[label]
                actual = sources.test_evidence(location)
                refs.extend(
                    actual
                    or [
                        sources.ref(
                            name, f"{prefix}/extensions/{index}", kind="test", origin=location
                        )
                    ]
                )
        return unique(refs)

    for mount_index, mount in enumerate(mapped):
        eid = mount["extension_id"]
        index, extension = indexed.get(eid, (None, {}))
        for binding in mount["bindings"]:
            row = {**extension, **binding}
            if entity_only and binding.get("kind") == "pending":
                row = {**binding, **extension}
            condition = (
                binding.get("condition")
                or extension.get("condition")
                or mount.get("condition")
                or ""
            )
            expected = (
                binding.get("expected")
                or extension.get("expected_result")
                or mount.get("expected")
                or ""
            )
            fields = (
                "step_ref",
                "target",
                "entity_id",
                "attribute",
                "field_name",
                "parameter",
                "concern_key",
            )
            provided = supplied_by_extension.get(eid, [])
            equivalent = [
                item
                for item in provided
                if all(not item.get(key) or item.get(key) == binding.get(key) for key in fields)
                and item["condition"] == condition
                and item["expected"] == expected
            ]
            kind = row.get("kind") or "pending"
            reason = row.get("reason")
            if provided and not equivalent and kind == "exception":
                kind, reason = "pending", "测试异常与扩展挂载不一致"
            if kind == "exception" and not (binding.get("step_ref") and binding.get("concern_key")):
                kind, reason = "pending", reason or "测试扩展缺少确定挂载"
            rid = ident(
                "GT-scenario", bundle["case"]["id"], eid, *[row.get(k) for k in fields], condition
            )
            if len(equivalent) == 1:
                rid = equivalent[0]["id"]
            mapping_refs = []
            if mapping_source:
                mapping_path, mapping_prefix = mapping_source
                mapping_name = sources.add(
                    mapping_path, "test" if mapping_prefix == "" else "intermediate"
                )
                mapping_refs = [
                    sources.ref(mapping_name, f"{mapping_prefix}/items/{mount_index}", kind="test")
                ]
            records.append(
                {
                    **row,
                    "id": rid,
                    "original_id": eid,
                    "extension_id": eid,
                    "condition": condition,
                    "expected": expected,
                    "scenario_type": kind,
                    "reason": reason,
                    "source_refs": unique(
                        refs_for(extension, index)
                        + mapping_refs
                        + [r for item in equivalent for r in item["source_refs"]]
                    ),
                    "raw": extension,
                }
            )
    for index, extension in enumerate(extensions):
        eid = extension.get("id")
        if eid in mapped_ids or any(row.get("extension_id") == eid for row in supplied_records):
            continue
        note = str(extension.get("note", ""))
        kind = extension.get("scenario_type") or (
            "alternative" if re.search(r"成功备选|正常备选", note) else "exception"
        )
        records.append(
            {
                "id": ident("GT-scenario", bundle["case"]["id"], eid or index),
                "original_id": eid,
                "extension_id": eid,
                "condition": extension.get("condition") or "",
                "expected": extension.get("expected_result") or "",
                "source_refs": refs_for(extension, index),
                "scenario_type": kind,
                "raw": extension,
            }
        )
    bundle["gt_source_available"] = bool(
        case or ((mapping or {}).get("source_available") is not False and (supplied or mapped))
    )
    bundle["test_source_case_id"] = case.get("id") or (mapping or {}).get("source_uc_id")
    bundle["test_source_path"] = path.relative_to(sources.root).as_posix() if name else None
    result = recognize_records(bundle, records, "GT")
    pending_by_id = {item["id"]: item for item in result["pending"]}
    excluded = {item["id"] for item in result.get("project_records", [])}
    bundle["test_import_records"] = [
        {
            **{
                k: row.get(k)
                for k in (
                    "id",
                    "original_id",
                    "scenario_type",
                    "step_ref",
                    "reason",
                    "source_refs",
                    "condition",
                    "expected",
                )
            },
            **({"scenario_type": "out_of_scope"} if row["id"] in excluded else {}),
            **(
                {"needs_semantic": True}
                if pending_by_id.get(row["id"], {}).get("needs_semantic")
                else {}
            ),
        }
        for row in records
    ]
    return result
