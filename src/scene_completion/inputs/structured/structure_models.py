"""Literal adapters for colleague RR/SR structure_model.json (schema v3).

No LLM or original spec is required to index an already structured catalogue.
The readable projection cites this JSON's pointers, not its unprovided evidence
files. Exception bodies never appear in the positive projection.
"""

import json
from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.structured.recovered_tests import parsed

MARKER = "<!-- colleague-structure-v1 "
CASE_MARKER = "<!-- colleague-case "
BRANCH_MARKER = "- COLLEAGUE_EXCEPTION "


def recognized(value):
    return (
        isinstance(value, dict)
        and isinstance(value.get("scope"), dict)
        and value["scope"].get("model_level") in {"RR", "SR"}
        and isinstance(value.get("entities"), list)
        and isinstance(value.get("relations"), list)
    )


def compile_model(text, name):
    value, _ = parsed(text)
    if not recognized(value):
        return None
    layer = value["scope"]["model_level"]
    entities = {}
    positions = {}
    for n, e in enumerate(value["entities"]):
        if (
            not isinstance(e, dict)
            or not isinstance(e.get("entity_id"), str)
            or not e["entity_id"].strip()
        ):
            raise ValueError("结构模型实体必须有非空entity_id：/entities/" + str(n))
        if e["entity_id"] in entities:
            raise ValueError("结构模型重复entity_id：" + e["entity_id"])
        entities[e["entity_id"]] = e
        positions[e["entity_id"]] = n
    owners = {}
    for r in value["relations"]:
        if r.get("relation_type") != "associated_with_usecase":
            continue
        a, b = r.get("source_entity_id"), r.get("target_entity_id")
        if a not in entities or b not in entities:
            raise ValueError("场景关联引用未知实体")
        if entities[a].get("entity_type") == "use_case":
            a, b = b, a
        if (
            entities[a].get("entity_type") != "scenario"
            or entities[b].get("entity_type") != "use_case"
        ):
            raise ValueError("associated_with_usecase必须关联场景与用例")
        if a in owners and owners[a] != b:
            raise ValueError("场景关联多个用例，需先确认归属：" + a)
        owners[a] = b
    unbound = [
        e["entity_id"]
        for e in entities.values()
        if e.get("entity_type") == "scenario" and e["entity_id"] not in owners
    ]
    if unbound:
        raise ValueError("场景缺少用例关联：" + ", ".join(unbound))
    sid = "import-structure-" + fingerprint([text, name])[:24]
    lines = []
    locations = []

    def emit(s, pointer=None):
        lines.append({"number": len(lines) + 1, "text": s})
        if pointer is not None:
            locations.append({"line": len(lines), "json_pointer": pointer})
        return len(lines)

    def ref(n):
        return {"source_id": sid, "line_start": n, "line_end": n, "quote": lines[n - 1]["text"]}

    def dumps(x):
        return json.dumps(x, ensure_ascii=False, separators=(",", ":"))

    emit(MARKER + dumps({"layer": layer}) + " -->")
    emit("# " + layer + " 结构化需求（同事JSON可读投影）")
    # Metadata/baseline comparison and evidence.quote are deliberately omitted.
    for e in entities.values():
        if e.get("entity_type") in {"scenario", "use_case", "rr_requirement", "sr_requirement"}:
            continue
        safe = {
            k: e[k]
            for k in (
                "entity_id",
                "entity_type",
                "canonical_name",
                "api_key",
                "method",
                "api_path",
                "is_actor",
                "is_external",
            )
            if k in e
        }
        emit("- " + dumps(safe), "/entities/" + str(positions[e["entity_id"]]))
    cases = []
    branches = []
    retained = []
    seen = set()
    for e in entities.values():
        if e.get("entity_type") != "use_case":
            continue
        cid = e.get("use_case_id") or e["entity_id"]
        label = e.get("canonical_name") or e.get("source_name") or cid
        if cid in seen:
            raise ValueError("结构模型重复use_case_id：" + cid)
        seen.add(cid)
        pointer = "/entities/" + str(positions[e["entity_id"]])
        start = emit("## " + cid + "：" + label, pointer)
        actor_ids = e.get("actors") or []
        actors = [
            entities[a].get("canonical_name") or entities[a].get("source_name") or a
            for a in actor_ids
            if isinstance(a, str) and a in entities
        ]
        meta = {"id": cid, "name": label, "goal": label, "actors": actors, "layer": layer}
        mains = [
            s
            for s in entities.values()
            if owners.get(s["entity_id"]) == e["entity_id"]
            and s.get("scenario_kind") == "main_success"
        ]
        if mains:
            meta["goal"] = "；".join(str(s.get("expected_result") or label) for s in mains)
        emit(CASE_MARKER + dumps(meta) + " -->", pointer)
        for s in mains:
            p = "/entities/" + str(positions[s["entity_id"]])
            emit("### 主成功路径 " + s["entity_id"], p)
            for n, step in enumerate(s.get("steps", [])):
                emit(str(step), p + "/steps/" + str(n))
            if s.get("expected_result"):
                emit("成功结果：" + str(s["expected_result"]), p + "/expected_result")
        end = len(lines)
        cases.append(
            {
                **meta,
                "source_ranges": [{"source_id": sid, "start": start, "end": end}],
                "source_refs": [ref(start)],
            }
        )
        emit("### 异常及备选分支（仅已有场景通道）")
        for s in entities.values():
            if (
                owners.get(s["entity_id"]) != e["entity_id"]
                or s.get("scenario_kind") == "main_success"
            ):
                continue
            p = "/entities/" + str(positions[s["entity_id"]])
            kind = s.get("scenario_kind")
            record = {
                "id": layer + "::" + s["entity_id"],
                "case_hint": cid,
                "description": "\n".join(str(x) for x in s.get("steps", []))
                + ("\n预期结果：" + str(s["expected_result"]) if s.get("expected_result") else ""),
                "operation_hint": label,
                "party_hint": "",
            }
            if kind == "exception":
                n = emit(BRANCH_MARKER + dumps(record), p)
                branches.append({**record, "source_refs": [ref(n)]})
            else:
                emit(
                    "- 保留非异常分支 "
                    + dumps(
                        {
                            "id": s["entity_id"],
                            "scenario_kind": kind,
                            "steps": s.get("steps", []),
                            "expected_result": s.get("expected_result"),
                        }
                    ),
                    p,
                )
                retained.append(
                    {"id": s["entity_id"], "case_id": cid, "scenario_kind": kind, "json_pointer": p}
                )
    if not cases:
        raise ValueError("结构模型没有use_case实体，不能作为完整用例目录")
    return {
        "layer": layer,
        "document": {
            "source_id": sid,
            "name": name + " · " + layer + "结构化可读投影.md",
            "channel": "existing",
            "lines": lines,
        },
        "catalogue": {"cases": cases},
        "branches": {"branches": branches},
        "locations": locations,
        "retained": retained,
        "counts": {
            "use_cases": len(cases),
            "main_success": sum(
                e.get("scenario_kind") == "main_success" for e in entities.values()
            ),
            "exceptions": len(branches),
            "non_exception": len(retained),
        },
    }


def model_layer(document):
    if not document.get("source_id", "").startswith("import-structure-"):
        return None
    row = next((r for r in document["lines"] if r["text"].startswith(MARKER)), None)
    return json.loads(row["text"][len(MARKER) : -4])["layer"] if row else None


def catalogue(documents, layer):
    if not documents or any(model_layer(d) != layer for d in documents):
        return None
    cases = []
    for d in documents:
        lines = d["lines"]
        head = None
        markers = []
        for r in lines:
            if r["text"].startswith("## "):
                head = r
            if r["text"].startswith(CASE_MARKER):
                markers.append((head, r, json.loads(r["text"][len(CASE_MARKER) : -4])))
        for head, row, meta in markers:
            if head is None:
                raise ValueError("结构化用例缺少标题定位")
            stop = next(
                (
                    r["number"]
                    for r in lines
                    if r["number"] > row["number"]
                    and (r["text"].startswith("## ") or r["text"].startswith("### 异常及备选"))
                ),
                max(r["number"] for r in lines) + 1,
            )
            end = max(r["number"] for r in lines if head["number"] <= r["number"] < stop)
            cases.append(
                {
                    **meta,
                    "source_ranges": [
                        {"source_id": d["source_id"], "start": head["number"], "end": end}
                    ],
                    "source_refs": [
                        {
                            "source_id": d["source_id"],
                            "line_start": head["number"],
                            "line_end": head["number"],
                            "quote": head["text"],
                        }
                    ],
                }
            )
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("多个结构文件包含重复用例ID，请选择当前版本")
    return {"cases": cases}


def existing_branches(documents):
    if not documents or any(model_layer(d) is None for d in documents):
        return None
    branches = []
    for d in documents:
        for r in d["lines"]:
            if r["text"].startswith(BRANCH_MARKER):
                b = json.loads(r["text"][len(BRANCH_MARKER) :])
                branches.append(
                    {
                        **b,
                        "source_refs": [
                            {
                                "source_id": d["source_id"],
                                "line_start": r["number"],
                                "line_end": r["number"],
                                "quote": r["text"],
                            }
                        ],
                    }
                )
    return {"branches": branches}


def imported_sources(rows):
    """Only complete, uniquely chosen layer snapshots can replace a catalogue.

    Multiple versions stay visible but require an explicit selection; never use
    the newest filename/timestamp as authority.
    """
    result = {}
    for layer in ("RR", "SR"):
        selected = [
            r
            for r in rows
            if r.get("structure_model", {}).get("layer") == layer
            and r.get("structure_enabled", True)
        ]
        if len(selected) > 1:
            raise ValueError(layer + "结构模型存在多个版本，请在导入页停用非当前版本")
        if selected:
            result[layer] = deepcopy(selected[0]["structure_model"]["document"])
    return result
