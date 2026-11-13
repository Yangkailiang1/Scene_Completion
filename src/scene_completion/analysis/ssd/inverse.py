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
        return "global.idempotency"
    if re.search(r"service[-_]id.*(?:other|其他|越权)|跨服务.*隔离", condition, re.I):
        return "service_relation.data_isolation"
    if re.search(r"Authorization|token|身份|认证", condition, re.I):
        return "human.authentication"
    if re.search(r"无.*权限|没有.*权限|越权|无权", condition):
        return "human.authorization"
    if re.search(r"version.*(?:不一致|冲突)|并发|版本冲突", condition, re.I):
        return "crud.concurrency"
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
    if not candidates:
        # Match complete IDs, never a shorter request prefix inside DB-REQ.
        ids = re.findall(r"交互\s*([A-Za-z0-9_-]+)", note)
        candidates = [s for s in steps if s["id"] in ids]
    after = (raw.get("extend_at_main") or {}).get("after")
    failure = re.search(r"失败于步骤\s*([RS]\d+)", note)
    label = failure[1] if failure else after
    local = [s for s in steps if label and label in s.get("aliases", []) and s["kind"] == "action"]
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


def recognize_records(bundle, records, channel_name):
    """Independent conservative fallback; unresolved records remain reviewable."""
    from scene_completion.domain.ssd.construction import add_concern, add_scenario, channel, pending

    output = channel()
    for record in records:
        condition, expected, refs = (
            record["condition"],
            record.get("expected", ""),
            record["source_refs"],
        )
        rid = record["id"]
        if record.get("scenario_type") in {"normal", "main", "alternative", "optional"}:
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
        if family and family.startswith("global."):
            output["pending"].append(
                pending(
                    rid,
                    condition,
                    refs,
                    reason="全局关注点留待后续，本轮不计分",
                    needs_semantic=False,
                    original=record,
                )
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
        if family.startswith("api.data."):
            target = "data"
            fields = _field_candidates(step, condition)
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
        entity = (
            step["entity_ids"][0]
            if family == "service.business_attribute_constraint"
            and len(step.get("entity_ids", [])) == 1
            else None
        )
        for field in fields:
            concern = add_concern(
                output,
                bundle,
                channel_name,
                step,
                family,
                target,
                field=field,
                entity=entity,
                condition=condition,
                refs=refs,
            )
            if concern:
                add_scenario(output, concern, condition, expected, refs, rid)
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


def existing_channel(bundle, case_dir, sources):
    records = []
    for layer in ("IR", "SR"):
        for path in sorted((case_dir / "behaviour" / layer).glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            if raw.get("scenario_kind") in {"main", "normal", "alternative", "optional"}:
                continue
            if not raw.get("guard"):
                continue
            name = sources.add(path)
            expected = "；".join(
                n.get("message", "")
                for n in raw.get("interaction", [])
                if n.get("direction") == "return"
            )
            records.append(
                {
                    "id": ident(
                        "E-scenario", bundle["case"]["id"], layer, raw.get("ID") or path.stem
                    ),
                    "original_id": raw.get("ID") or path.stem,
                    "condition": raw["guard"],
                    "expected": expected,
                    "source_refs": sources.refs(raw, name),
                    "layer": "RR" if layer == "IR" else "SR",
                    "scenario_type": raw.get("scenario_kind", "exception"),
                    "raw": raw,
                }
            )
    merged = {}
    for record in records:
        code = re.search(r"_SC_EX_(.+)$", record["original_id"])
        key = ("id", code[1]) if code else ("condition", re.sub(r"\s+", "", record["condition"]))
        previous = merged.get(key)
        if previous is None:
            merged[key] = record
        else:
            # The SR realization supplies the concrete target. Both source
            # layers remain attached, even where their prose differs.
            primary = deepcopy(record if record["layer"] == "SR" else previous)
            primary["source_refs"] = unique(previous["source_refs"] + record["source_refs"])
            primary["source_records"] = previous.get("source_records", [previous["raw"]]) + [
                record["raw"]
            ]
            merged[key] = primary
    return recognize_records(bundle, list(merged.values()), "E")


def test_channel(bundle, sources):
    from scene_completion.domain.ssd.construction import channel, pending

    path = sources.root / "recovered_usecases.json"
    if not path.exists():
        result = channel()
        result["pending"].append(
            pending(
                ident("GT-missing", bundle["case"]["id"]),
                "未提供 recovered_usecases.json",
                needs_semantic=False,
            )
        )
        return result
    name = sources.add(path, "test")
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = (
        raw
        if isinstance(raw, list)
        else raw.get("usecases", raw.get("use_cases", raw.get("cases", [])))
    )
    found = [
        (n, c)
        for n, c in enumerate(cases)
        if c.get("id") == bundle["case"]["id"] or c.get("name") == bundle["case"]["name"]
    ]
    if len(found) != 1:
        result = channel()
        result["pending"].append(
            pending(
                ident("GT-case", bundle["case"]["id"]),
                "测试用例无法唯一对应",
                [sources.ref(name)],
                needs_semantic=True,
            )
        )
        return result
    n, case = found[0]
    prefix = (
        ""
        if isinstance(raw, list)
        else "/" + next(k for k in ("usecases", "use_cases", "cases") if k in raw)
    )
    records = []
    for en, extension in enumerate(case.get("extensions", [])):
        note = str(extension.get("note", ""))
        kind = extension.get("scenario_type") or (
            "alternative" if re.search(r"成功备选|正常备选", note) else "exception"
        )
        pointer = f"{prefix}/{n}/extensions/{en}"
        refs = [sources.ref(name, pointer, kind="test")]
        # These are test-source references. Requirement context in a note never
        # becomes test evidence; it is only used to locate the SSD object.
        records.append(
            {
                "id": ident("GT-scenario", bundle["case"]["id"], extension.get("id") or pointer),
                "condition": extension.get("condition") or "",
                "expected": extension.get("expected_result") or "",
                "source_refs": refs,
                "scenario_type": kind,
                "raw": extension,
            }
        )
    return recognize_records(bundle, records, "GT")
