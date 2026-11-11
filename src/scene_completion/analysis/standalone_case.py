"""Material preparation and reporting for the standalone case-analysis skill."""

import base64
import json
from copy import deepcopy
from pathlib import Path

from scene_completion.analysis.imported_case_results import prepare
from scene_completion.analysis.interaction_enrichment import display_parameters
from scene_completion.analysis.interaction_identity import canonical_fused
from scene_completion.analysis.scenario_patterns import normalize_settings
from scene_completion.domain.concern_registry import default_registry
from scene_completion.infrastructure.storage import fingerprint, write_json
from scene_completion.inputs.colleague_formats import function_product
from scene_completion.inputs.input_bundles import discover_material
from scene_completion.inputs.recovered_tests import catalogue
from scene_completion.inputs.source_documents import evidence_refs
from scene_completion.inputs.supplied_api import contracts_for_cases


def _selected(preview, accepted, selector):
    hits = []
    for cid, entry in accepted.items():
        product = entry["row"]["behavior_product"]
        group = entry["group"]
        aliases = {
            cid,
            product["case_name"],
            *group["rr_ids"],
            *group["sr_ids"],
            *product["case_ids"],
        }
        if selector in aliases:
            hits.append((cid, entry, aliases))
    if len(hits) == 1:
        return hits[0]
    reasons = [
        row["reason"]
        for row in preview["supplied_cases"]["cases"]
        if selector in {row["name"], row["case_id"]}
    ]
    raise ValueError("目标用例没有唯一通过校验的SSD。" + " ".join(reasons))


def _text(file):
    return base64.b64decode(file["content_base64"]).decode("utf-8-sig")


def _scope_lines(document, material):
    source_id = document["source_id"]
    lines = {
        n
        for r in evidence_refs(material)
        if r["source_id"] == source_id
        for n in range(r["line_start"], r["line_end"] + 1)
    }
    return {**document, "lines": [row for row in document["lines"] if row["number"] in lines]}


def _positive(preview, files, cid, entry, aliases):
    row = entry["row"]
    product = row["behavior_product"]
    ssd = entry["fused"]
    behavior = {**product["normal_document"], "name": row["relative_path"]}
    sources = [behavior]
    file_index = {f["role"]: f for f in preview["files"] if f["role"] != "behavior"}
    definitions = []
    entities = []
    pending = []
    if "function_tree" in files:
        item = file_index["function_tree"]
        tree = function_product(
            json.loads(_text(files["function_tree"])), item["hash"][:24], item["name"]
        )
        contract_doc = {**tree["interface_document"], "name": item["path"] + " · SR接口依据"}
        definitions = [(api, contract_doc) for api in tree["interface_declarations"]]
        entity_rows = tree["artifacts"][0]["payload"]["entities"]
        for entity in entity_rows:
            attributes = [
                attr
                for attr in entity["attributes"]
                if aliases.intersection(attr["case_ids"] + attr["case_names"])
            ]
            refs = [
                r
                for r in entity["source_refs"]
                if json.loads(r["quote"])["case_id"] in aliases
                or json.loads(r["quote"])["case_name"] in aliases
            ]
            if refs or attributes:
                entities.append({**entity, "attributes": attributes, "source_refs": refs})
        if entities:
            sources.append(
                _scope_lines(
                    {**tree["document"], "name": item["path"] + " · 业务属性依据"}, entities
                )
            )
    else:
        pending.append("未提供功能树，SR接口契约及其字段约束待补。")
    mapping, _, contracts, documents, api_pending = contracts_for_cases(definitions, {cid: entry})
    parameters = {"apis": [api for api, _ in contracts.values()]}
    for doc in {d["source_id"]: d for d in documents.values()}.values():
        sources.append(_scope_lines(doc, [mapping, parameters]))
    material = {"api-map": mapping, "api-parameters": parameters}
    enriched = display_parameters(canonical_fused(ssd, material), material)
    interactions = enriched["interactions"]
    pending.extend(p["reason"] for p in enriched.get("pending", []))
    paths = [row["relative_path"]] + [
        file_index[key]["path"] for key in ("RR", "SR", "function_tree") if key in file_index
    ]
    group_path = Path(row["relative_path"]).parent
    paths += [
        f["path"]
        for f in preview["files"]
        if f["role"] == "behavior"
        and Path(f["path"]).parent == group_path
        and Path(f["path"]).name.casefold() == "ssd.json"
    ]
    return {
        "case": {"id": cid, "name": product["case_name"], "source_ids": [behavior["source_id"]]},
        "used_files": paths,
        "ssd": ssd,
        "api_map": mapping,
        "api_parameters": parameters,
        "interactions": interactions,
        "business_entities": entities,
        "sources": sources,
        "registry": default_registry(),
        "recommendation_settings": normalize_settings(),
        "pending": pending + api_pending,
    }


def _existing(entry):
    facts = entry["existing"]
    status = "ready" if facts["inventory"] else "missing"
    if facts["pending"]:
        status = "partial"
    sources = [
        {
            **doc,
            "name": str(
                Path(entry["row"]["relative_path"]).parent / "behaviour" / "SR" / doc["name"]
            ),
        }
        for doc in facts["documents"]
    ]
    return {
        "status": status,
        "records": facts["branches"],
        "sources": sources,
        "source_refs": evidence_refs(facts["branches"]),
        "pending": [f"{row['file']} · {row['reason']}" for row in facts["pending"]]
        + (["未提供该用例的有效 SR 原文异常来源。"] if status == "missing" else []),
    }


def _truth(preview, files, aliases):
    empty = {
        "status": "missing",
        "records": [],
        "sources": [],
        "source_refs": [],
        "pending": ["未提供可唯一对应到本用例的原始异常测试。"],
    }
    if "test" not in files:
        return empty
    item = next(f for f in preview["files"] if f["role"] == "test")
    source = {
        "source_id": "case-test-" + item["hash"][:24],
        "name": item["path"],
        "channel": "test",
        "lines": [
            {"number": n, "text": line}
            for n, line in enumerate(_text(files["test"]).splitlines(), 1)
        ],
    }
    value = catalogue(source)
    if not value:
        return empty
    cases = [c for c in value["cases"] if c["source_case_id"] in aliases]
    if not cases:
        cases = [c for c in value["cases"] if c["name"] in aliases]
    if len(cases) != 1:
        return empty
    case = cases[0]
    records = [r for r in value["records"] if r["case_id"] == case["id"]]
    pending = [
        r["测试ID"] + " · 测试分支类型待确认" for r in records if r["scenario_type"] == "pending"
    ]
    return {
        "status": "ready",
        "records": records,
        "sources": [_scope_lines(source, [case, records])],
        "source_refs": case["source_refs"],
        "pending": pending,
    }


def input_phase(input_dir, selector, phase):
    preview, files, accepted = discover_material(directory=str(Path(input_dir).resolve()))
    cid, entry, aliases = _selected(preview, accepted, selector)
    relevant = {"model": {"RR", "SR", "function_tree"}, "existing": set(), "test": {"test"}}[phase]
    issues = [issue["reason"] for issue in preview["issues"] if issue.get("role") in relevant]
    if issues:
        raise ValueError("输入用途待确认。" + " ".join(issues))
    if phase == "model":
        return _positive(preview, files, cid, entry, aliases)
    if phase == "existing":
        return _existing(entry)
    return _truth(preview, files, aliases)


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def finalize(bundle, output):
    value = prepare(bundle)
    p = value["payloads"]
    meta = value["metadata"]
    evaluation = value["scoped_evaluation"]
    recommendation = p["gap-recommend"]
    bundle = {
        **deepcopy(bundle),
        "recommendation_ids": [s["id"] for s in recommendation["Q"]],
        "metrics": meta["metrics"],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "case-analysis.json", bundle)
    lines = [
        f"# {meta['case']['name']}（{meta['case']['id']}）",
        "",
        f"指标范围为 {meta['scope']}。规则快照为 `{meta['registry_hash']}`。",
        "",
        "| 交互 | 发送方 | 接收方 | 操作 | 数据字段与约束 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i in p["enriched-view"]["interactions"]:
        fields = [
            ".".join((f["location"], f["name"]))
            + " "
            + json.dumps(
                {
                    k: v
                    for k, v in f.items()
                    if k in {"data_type", "required", "default"} and v is not None
                }
                | {"constraints": [(r["kind"], r["value"]) for r in f["constraints"]]},
                ensure_ascii=False,
            )
            for f in i["data"]["sequence"]
        ]
        cells = [
            i["id"],
            i["sender"]["name"],
            i["receiver"]["name"],
            i["operation"]["name"],
            "、".join(fields),
        ]
        lines.append("| " + " | ".join(map(_cell, cells)) + " |")
    for channel in ("G", "E", "GT"):
        stage = {"G": "exception-generate", "E": "existing-extract", "GT": "test-ground-truth"}[
            channel
        ]
        lines += ["", f"## {channel}（{meta['channels'][channel]}）", "", "关注点"]
        lines += [
            f"- `{m['interaction_id']}` · {m['target']} · {m['object']} · {m['concern_key']}"
            for m in p[stage]["matches"]
        ]
        lines += ["", "异常场景"]
        lines += [
            f"- `{s['id']}` · `{s['interaction_id']}` · {s['steps']['trigger']}"
            for s in p[stage]["scenarios"]
        ]
    lines += ["", "## 缺失报告与推荐", ""]
    lines += [
        f"- M · `{s['id']}` · {s['steps']['trigger']}" for s in p["missing-report"].get("M", [])
    ]
    if not p["missing-report"]:
        lines.append("- 待补材料。")
    lines += [f"- Q · `{s['id']}` · {s['steps']['trigger']}" for s in recommendation["Q"]]
    lines += ["", "## 评测指标", ""]
    labels = {
        "missing_exception_miss_rate": "关注点缺失异常漏报率",
        "generation_validity": "关注点生成有效率",
        "recommendation_adoption": "推荐 GT 命中率（采纳率）",
        "recommendation_false_positive": "推荐误报率",
        "critical_missing_recall": "关键缺失召回率",
    }
    for name, score in evaluation.get("metrics", {}).items():
        display = (
            f"{score['value']:.2f}%（{score['numerator']}/{score['denominator']}）"
            if score.get("value") is not None
            else score["status"]
        )
        lines.append(f"- {labels.get(name, name)} · {display}")
    for key, label in (("baseline", "推荐前 M"), ("recommended", "推荐后 Q")):
        comparison = evaluation.get("recommendation_comparison", {}).get(key, {})
        for name, score in comparison.get("metrics", {}).items():
            lines.append(
                f"- {label} · {labels.get(name, name)} · {score['numerator']}/{score['denominator']} · {score['status']}"
            )
    if not evaluation:
        lines.append("未评测。")
    lines += ["", "## 匹配判定", ""]
    for purpose, decisions in bundle["decisions"].items():
        lines += [
            f"- {purpose} · `{d['left_id']}` → `{d['right_id']}` · {d['status']} · {d['reason']}"
            for d in decisions
        ]
    lines += ["", "## 待补材料与证据", ""]
    lines += [f"- {note}" for note in meta["pending"]]
    lines += [
        f"- {doc['channel']} · {doc['name']} · `{doc['source_id']}`" for doc in bundle["sources"]
    ]
    (output / "case-analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {**meta, "id": fingerprint(bundle), "metrics": evaluation.get("metrics", {})}
