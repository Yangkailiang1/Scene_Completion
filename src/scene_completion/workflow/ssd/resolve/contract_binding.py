"""Forward-only missing-contract assistance; API identity remains optional."""

import re
from copy import deepcopy

from scene_completion.analysis.project_scopes.pipeline import documents_and_lines
from scene_completion.domain.ssd.construction import ident, unique
from scene_completion.workflow.ssd.generate.fixed import generate_g
from scene_completion.workflow.ssd.generate.scenarios import _positive


def prepare(bundle):
    steps = [
        s
        for s in bundle["steps"]
        if s.get("kind") != "action"
        and (
            not s.get("api_id")
            and any(not f.get("type") and not f.get("constraints") for f in s.get("data", []))
            or not s["operation"].get("kinds")
            and s.get("direction") == "request"
            and re.search(r"\bPOST\s+", s["operation"].get("name", ""), re.I)
        )
    ]
    if not steps:
        return None, None
    _, lines = documents_and_lines([bundle])
    maps = {"steps": {}, "fields": {}, "apis": {}, "lines": {}}
    context = {"case": deepcopy(bundle["case"]), "steps": [], "apis": [], "positive_lines": []}
    for n, step in enumerate(steps, 1):
        sid = f"S{n:02d}"
        maps["steps"][sid] = step["id"]
        row = _positive(step)
        row["id"] = sid
        for field in row.get("data", []):
            fid = f"F{len(maps['fields']) + 1:03d}"
            maps["fields"][fid] = field["id"]
            field["id"] = fid
        context["steps"].append(row)
    for n, api in enumerate(bundle.get("apis", []), 1):
        aid = f"A{n:02d}"
        maps["apis"][aid] = api["id"]
        row = _positive(api)
        row["id"] = aid
        context["apis"].append(row)
    for n, line in enumerate(lines, 1):
        lid = f"L{n:04d}"
        maps["lines"][lid] = line
        context["positive_lines"].append({"id": lid, "text": line["text"]})
    return context, maps


def validate_result(value, inputs):
    steps = {s["id"]: s for s in inputs["steps"]}
    apis = {a["id"]: a for a in inputs["apis"]}
    refs = {r["id"] for r in inputs["positive_lines"]}
    for row in (
        value["operations"] + value["field_links"] + value["field_definitions"] + value["pending"]
    ):
        if row["step_id"] not in steps:
            raise ValueError("字段定位引用未知步骤")
    for row in value["operations"]:
        existing = steps[row["step_id"]]["operation"].get("kinds", [])
        if existing and set(existing) != set(row["kinds"]):
            raise ValueError("不能改写已有明确或人工CRUD")
    for row in value["field_links"] + value["field_definitions"]:
        step = steps[row["step_id"]]
        if row["field_id"] not in {f["id"] for f in step.get("data", [])}:
            raise ValueError("不能关联其他步骤或新增字段")
        if "api_id" in row:
            if row["api_id"] not in apis or not any(
                f["name"] == row["name"] and f.get("location") == row["location"]
                for f in apis[row["api_id"]].get("fields", [])
            ):
                api = apis.get(row["api_id"], {})
                declared = [f"{f.get('location')}.{f['name']}" for f in api.get("fields", [])]
                raise ValueError(
                    f"字段约束必须来自已声明接口属性：{row['api_id']}中不存在"
                    f"{row['location']}.{row['name']}。允许属性：{declared}。"
                    "不要将RR凭证字段冒充SR接口属性；无对应属性时删除此field_links项，"
                    "有准确正向L原文依据则使用field_definitions，无依据则写pending。"
                )
            storage = (
                next(f for f in step["data"] if f["id"] == row["field_id"]).get("location")
                == "storage"
            )
            if storage != (row["location"] == "storage") or (
                not storage and (row["location"] == "response") != (step["direction"] == "return")
            ):
                raise ValueError("请求、响应与存储字段不能串挂")
        elif not row["source_ref_ids"] or not set(row["source_ref_ids"]) <= refs:
            raise ValueError(
                f"字段定义必须引用本次正向原文：{row['step_id']}/{row['field_id']}缺少有效L编号。"
                "未知字段不要在field_definitions中输出空占位行，删除该行并只在pending说明缺口。"
            )
    return value


def apply_result(bundle, context, maps, value):
    validate_result(value, context)
    steps = {s["id"]: s for s in bundle["steps"]}
    apis = {a["id"]: a for a in bundle.get("apis", [])}
    for row in value["operations"]:
        operation = steps[maps["steps"][row["step_id"]]]["operation"]
        if not operation.get("kinds"):
            operation.update(kinds=row["kinds"], kinds_source="semantic")
    for row in value["field_links"] + value["field_definitions"]:
        step = steps[maps["steps"][row["step_id"]]]
        field = next(f for f in step["data"] if f["id"] == maps["fields"][row["field_id"]])
        if "api_id" in row:
            aid = maps["apis"][row["api_id"]]
            prop = next(
                f
                for f in apis[aid]["fields"]
                if f["name"] == row["name"] and f.get("location") == row["location"]
            )
            source = deepcopy(prop)
            field.setdefault("contract_links", []).append(
                {"api_id": aid, "name": row["name"], "location": row["location"]}
            )
        else:
            source = deepcopy(row)
            source["source_refs"] = [
                {
                    "document_id": maps["lines"][i]["document_id"],
                    "start_line": maps["lines"][i]["line"],
                    "end_line": maps["lines"][i]["line"],
                    "quote": maps["lines"][i]["text"],
                    "kind": "origin",
                }
                for i in row["source_ref_ids"]
            ]
        if not field.get("type"):
            field["type"] = source.get("data_type", source.get("type"))
        if field.get("required") is None:
            field["required"] = source.get("required")
        field["source_refs"] = unique(field.get("source_refs", []) + source.get("source_refs", []))
        field["constraints"] = unique(
            field.get("constraints", [])
            + [
                {**c, "source_refs": c.get("source_refs") or source.get("source_refs", [])}
                for c in source.get("constraints", [])
            ]
        )
    bundle["contract_binding_pending"] = [
        {
            "id": ident("contract-gap", bundle["case"]["id"], maps["steps"][r["step_id"]]),
            "step_id": maps["steps"][r["step_id"]],
            "reason": r["reason"],
        }
        for r in value["pending"]
    ]
    bundle["channels"]["G"] = generate_g(bundle)
    return bundle
