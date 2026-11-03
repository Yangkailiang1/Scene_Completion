"""Versioned adoption, selection and partial-result merging."""

import time
from copy import deepcopy
from pathlib import Path

from scene_completion.domain.contracts import validate
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.artifact_conversion import cited_payload
from scene_completion.inputs.artifact_recognition import ROOTS as ROOTS
from scene_completion.inputs.artifact_recognition import TASKS as TASKS
from scene_completion.inputs.artifact_recognition import deterministic as deterministic
from scene_completion.inputs.artifact_recognition import role_hint as role_hint
from scene_completion.inputs.artifact_store import LOCK, archive, load, resolve_case, save, snapshot
from scene_completion.inputs.artifact_views import view


def decide(project, iid, body):
    with LOCK:
        index = load(project)
        row = view(project, iid)
        if body.get("expected_revision") != row["revision"]:
            raise ValueError("文件版本已变化，请刷新")
        if body.get("action") in {"enable_behavior", "disable_behavior"}:
            if not row.get("behavior_product"):
                raise ValueError("本文件不是有效行为建模格式")
            from scene_completion.inputs.behavior_imports import VERSION as behavior_version

            if (
                body["action"] == "enable_behavior"
                and row["behavior_product"].get("version") != behavior_version
            ):
                raise ValueError(
                    "行为适配版本已更新，请重新导入同一文件后确认采用；旧版本与报告保留"
                )
            if body.get("dry_run"):
                return {"valid": True, "saved": False}
            archive(project, row)
            if body.get("case_id"):
                row["behavior_product"]["case_ids"] = list(
                    dict.fromkeys(row["behavior_product"]["case_ids"] + [body["case_id"]])
                )
            if body["action"] == "enable_behavior" and not (
                row["behavior_product"].get("case_name") or row["behavior_product"]["case_ids"]
            ):
                raise ValueError("请先确认行为文件对应的用例")
            row["behavior_enabled"] = body["action"] == "enable_behavior"
            row["revision"] += 1
            row["history"].append({"action": body["action"], "at": time.time()})
            write_json(Path(project) / index["items"][iid]["record"], row)
            save(project, index)
            return {"saved": True, "revision": row["revision"]}
        if body.get("action") in {"enable_structure", "disable_structure"}:
            if not row.get("structure_model"):
                raise ValueError("本文件不是RR/SR结构模型")
            if body.get("dry_run"):
                return {"valid": True, "saved": False}
            archive(project, row)
            row["structure_enabled"] = body["action"] == "enable_structure"
            row["revision"] += 1
            row["history"].append({"action": body["action"], "at": time.time()})
            write_json(Path(project) / index["items"][iid]["record"], row)
            save(project, index)
            return {"saved": True, "revision": row["revision"]}
        aid = body.get("artifact_id")
        a = next((a for a in row["artifacts"] if a["id"] == aid), None)
        if a is None:
            raise ValueError("未知目标产物")
        if body.get("action") not in {"accept", "reject"}:
            raise ValueError("请选择接受或拒绝")
        updated = deepcopy(a)
        if "payload" in body and body["action"] == "accept" and body["payload"] != a["payload"]:
            updated["payload"], updated["document"] = cited_payload(
                body["payload"], a["task"], iid + "-" + aid.split(":")[-1], row["name"]
            )
            updated.pop("json_locations", None)
            updated.pop("literal_adapter", None)
        if body.get("case_id"):
            updated["case_hint"] = body["case_id"]
        if body.get("coverage") is not None:
            if body["coverage"] not in {"complete", "partial"}:
                raise ValueError("覆盖范围必须明确为完整或部分")
            updated["coverage"] = body["coverage"]
        if body["action"] == "accept":
            validate(a["task"], updated["payload"])
        updated.update(
            status="accepted" if body["action"] == "accept" else "rejected",
            accepted_partial=updated["coverage"] != "complete",
            replacement_approved=bool(body.get("replace")),
            error=None,
        )
        if body.get("dry_run"):
            return {"valid": True, "saved": False, "artifact": updated}
        archive(project, row)
        a.update(updated)
        row["revision"] += 1
        row["history"].append(
            {
                "action": body["action"],
                "artifact_id": aid,
                "at": time.time(),
                "note": body.get("note", ""),
            }
        )
        write_json(
            Path(project) / index["items"][iid]["record"],
            {k: v for k, v in row.items() if k != "version"},
        )
        save(project, index)
        return {"saved": True, "revision": row["revision"]}


def selections(project, task, case=None, frozen=None):
    if task not in TASKS:
        return []
    out = []
    for row in snapshot(project) if frozen is None else frozen:
        for a in row["artifacts"]:
            if a["task"] != task or a["status"] not in {"candidate", "accepted", "active"}:
                continue
            hint = a.get("case_hint")
            if case and resolve_case(project, hint) != case:
                continue
            if not case and hint:
                continue
            if a["coverage"] != "complete" and not a["accepted_partial"]:
                continue
            out.append(
                {
                    **a,
                    "file_id": row["id"],
                    "file_revision": row["revision"],
                    "file_name": row["name"],
                }
            )
    return out


def identity(project, task, case=None):
    return (
        fingerprint(
            [
                {k: a[k] for k in ("id", "payload", "coverage", "file_revision")}
                for a in selections(project, task, case)
            ]
        )
        if task in TASKS
        else None
    )


def documents(project, task, case=None):
    return [a["document"] for a in selections(project, task, case)]


def candidate(project, task, case, inputs, existing=None, parts=None):
    from scene_completion.analysis.validation import validate_result
    from scene_completion.infrastructure.execution_events import emit

    values = [p for p in parts or selections(project, task, case) if p["task"] == task]
    if not values:
        return None
    # Conflicting full artifacts are not resolved by timestamp or filename.
    full = [v for v in values if v["coverage"] == "complete"]

    def facts(v):
        if isinstance(v, dict):
            return {k: facts(x) for k, x in v.items() if k != "source_refs"}
        if isinstance(v, list):
            return [facts(x) for x in v]
        return v

    if len({fingerprint(facts(v["payload"])) for v in full}) > 1:
        emit("import_blocked", reason="多个完整产物冲突，需选择当前版本")
        return None
    if not full:
        return None
    selected = deepcopy(full[-1])
    if task == "api-parameters" and inputs.get("interface"):
        selected["payload"]["apis"] = [
            a for a in selected["payload"]["apis"] if a["id"] == inputs["interface"]["id"]
        ]
        if not selected["payload"]["apis"]:
            return None
    if existing and not selected.get("replacement_approved"):
        emit("import_blocked", reason="已有成功产物，替换需确认")
        return None
    check = deepcopy(inputs)
    for layer in ("RR", "SR"):
        if layer in check:
            check[layer] += [v["document"] for v in values]
    check["import-documents"] = [v["document"] for v in values]
    try:
        validate_result(task, selected["payload"], check)
    except ValueError as e:
        emit("import_blocked", file_id=selected["file_id"], reason=str(e))
        return None
    emit(
        "result_reused",
        provider="colleague_import",
        file_id=selected["file_id"],
        artifact_id=selected["id"],
    )
    return deepcopy(selected["payload"]), {
        "provider": "colleague_import",
        "file_id": selected["file_id"],
        "artifact_id": selected["id"],
        "revision": selected["file_revision"],
        "file_name": selected["file_name"],
    }


def fragments_for(project, task, case=None, frozen=None):
    tasks = [task] + (["rr-ssd", "sr-ssd"] if task == "fused-ssd" else [])
    rows = [a for t in tasks for a in selections(project, t, case, frozen)]
    if task == "fused-ssd" and case:
        for row in rows:
            row["payload"] = deepcopy(row["payload"])
            for i in row["payload"].get("interactions", []):
                i["case_id"] = case
    return rows


def merge(task, generated, parts):
    """Keep imported facts; combine missing records without fuzzy ID guessing."""
    value = deepcopy(generated)

    def union(a, b):
        if a == b or b is None:
            return deepcopy(a)
        if a is None:
            return deepcopy(b)
        if isinstance(a, dict) and isinstance(b, dict):
            return {k: union(a.get(k), b.get(k)) for k in a.keys() | b.keys()}
        if isinstance(a, list) and isinstance(b, list):
            return list({fingerprint(x): deepcopy(x) for x in a + b}.values())
        raise ValueError("同一导入身份具有不同字段值，需确认：" + str(a)[:80] + " / " + str(b)[:80])

    def combine(rows, extra, key):
        found = {key(r): r for r in rows}
        for r in extra:
            if key(r) in found:
                item = deepcopy(r)
                if {"kind", "value", "status"} <= item.keys():
                    item["id"] = found[key(r)]["id"]
                found[key(r)] = union(found[key(r)], item)
            else:
                found[key(r)] = deepcopy(r)
        return list(found.values())

    for part in parts:
        other = part["payload"]
        if task == "api-map":
            for service in other["services"]:
                target = next((s for s in value["services"] if s["name"] == service["name"]), None)
                if target is None:
                    value["services"].append(deepcopy(service))
                    continue
                target["interfaces"] = combine(
                    target["interfaces"],
                    service["interfaces"],
                    lambda a: (a.get("method"), a.get("address"))
                    if a.get("address")
                    else ("id", a["id"]),
                )
                target["source_refs"] = union(target["source_refs"], service["source_refs"])
        elif task == "api-parameters":
            for api in other["apis"]:
                target = next((a for a in value["apis"] if a["id"] == api["id"]), None)
                if target is None:
                    value["apis"].append(deepcopy(api))
                    continue
                for k in ("name", "address"):
                    target[k] = union(target.get(k), api.get(k))
                target["source_refs"] = union(target["source_refs"], api["source_refs"])
                for param in api["parameters"]:
                    known = next(
                        (
                            p
                            for p in target["parameters"]
                            if (p["name"], p["location"]) == (param["name"], param["location"])
                        ),
                        None,
                    )
                    if known is None:
                        target["parameters"].append(deepcopy(param))
                        continue
                    for k in ("name", "location", "default"):
                        known[k] = union(known.get(k), param.get(k))
                    if known.get("data_type") is None:
                        known["data_type"] = param.get("data_type")
                    elif (
                        param.get("data_type") is not None
                        and known["data_type"] != param["data_type"]
                    ):
                        known["constraints"].append(
                            {
                                "id": "import-type-"
                                + fingerprint(
                                    [param["name"], param["location"], param["data_type"]]
                                )[:20],
                                "kind": "type",
                                "value": param["data_type"],
                                "status": "explicit",
                                "source_refs": param["source_refs"],
                            }
                        )
                    known["required"] = (
                        True
                        if known.get("required") is True or param.get("required") is True
                        else union(known.get("required"), param.get("required"))
                    )
                    known["source_refs"] = union(known["source_refs"], param["source_refs"])
                    known["constraints"] = combine(
                        known["constraints"],
                        param["constraints"],
                        lambda c: (c["kind"], fingerprint(c["value"]), c["status"]),
                    )
        elif task == "fused-ssd":
            value["interactions"] = combine(
                value["interactions"], other.get("interactions", []), lambda x: x["id"]
            )
            if part["task"] == "fused-ssd":
                value["rr_sr_links"] = combine(
                    value["rr_sr_links"], other.get("rr_sr_links", []), lambda x: x["rr_id"]
                )
        elif task == "business-entities":
            from scene_completion.analysis.domain_model import merge_entities

            value = merge_entities([value, other])
        else:
            root = next(iter(ROOTS[task])) if task not in {"components"} else "components"
            identity_key = "name" if task == "object-operations" else "id"
            value[root] = combine(value[root], other[root], lambda x: x[identity_key])
            if task == "components":
                value["relations"] = union(value.get("relations", []), other.get("relations", []))
    return value


def record_use(project, key, proof):
    if (
        proof.get("provider") not in {"colleague_import", "colleague_structure"}
        and not proof.get("import_sources")
        and not proof.get("input_sources")
    ):
        return
    with LOCK:
        path = Path(project) / "imports/usage.json"
        data = read_json(path) if path.exists() else {}
        if proof.get("provider") == "colleague_structure":
            for source in proof.get("source_files", []):
                data[key + "::" + source["file_id"]] = {
                    "node": key,
                    **proof,
                    **source,
                    "artifact_id": "structure-model",
                    "at": time.time(),
                }
        elif proof.get("provider") == "colleague_import":
            data[key] = {"node": key, **proof, "at": time.time()}
        for source in proof.get("import_sources", []):
            data[key + "::" + source["artifact_id"]] = {
                "node": key,
                "provider": "colleague_partial",
                **source,
                "at": time.time(),
            }
        for source in proof.get("input_sources", []):
            data[key + "::behavior::" + source["file_id"]] = {
                "node": key,
                "provider": "behavior_input",
                "mode": "basis",
                **source,
                "at": time.time(),
            }
        write_json(path, data)
