"""Connect original SR behaviour branches to their supplied SysOperation."""

import json
import re
from collections import defaultdict
from pathlib import PurePosixPath

from scene_completion.inputs.structured.ordered_behaviors import (
    group_path,
    ordered_nodes,
    scenario_kind,
)
from scene_completion.inputs.structured.structure_models import BRANCH_MARKER


def _source_keys(operation):
    yield operation.get("source_key")
    for item in operation.get("realizations", []):
        yield item.get("source_key")
    for field in ("interaction", "action", "system_response"):
        for item in operation.get(field, []):
            yield item.get("source_key")


def _operation_links(operations, branch):
    identity = branch["ID"]
    chunk = branch.get("sourceChunking")
    source_key = branch.get("source_key")
    steps = {step["ref"] for step in branch["Order"]}
    direct, indirect = [], []
    for ident, operation in operations.items():
        if scenario_kind(operation) == "main":
            continue
        keys = {key for key in _source_keys(operation) if isinstance(key, str)}
        realization_ids = {
            item.get("ID") or item.get("id") for item in operation.get("realizations", [])
        }
        if identity in {ident, operation.get("ID"), operation.get("id"), *realization_ids} or (
            source_key and source_key in keys
        ):
            direct.append((ident, operation))
            continue
        same_branch = identity == operation.get("sourceSD")
        scoped_keys = {key for key in keys if chunk and key.partition("::")[0] == chunk}
        if same_branch and (
            scoped_keys
            or (chunk and chunk == operation.get("sourceChunking"))
            or operation.get("scenario_kind") == "exception"
        ):
            indirect.append((ident, operation))
        elif scoped_keys and any(
            row.get("source_node") in steps and row.get("source_key") in scoped_keys
            for field in ("interaction", "action", "system_response")
            for row in operation.get(field, [])
        ):
            indirect.append((ident, operation))
    return direct or indirect


def _anchor(branch, product, fused):
    extension = branch.get("extend_at_main")
    ref = extension.get("after") if isinstance(extension, dict) else None
    if not isinstance(ref, str) or not ref:
        return None, None
    chunk = branch.get("sourceChunking")
    operations = product["raw"]["operations"]
    lines = {line["number"]: line["text"] for line in product["normal_document"]["lines"]}
    targets = {}
    for step in fused["interactions"]:
        if step["layer"] != "SR":
            continue
        fact = json.loads(lines[step["source_refs"][0]["line_start"]])
        row = fact["node"]
        key = row.get("source_key") or operations[fact["operation_id"]].get("source_key") or ""
        origin = key.partition("::")[0]
        # IR origins and SR node IDs can use the same local numbering.
        if chunk and origin != chunk and re.search(r"(?:^|_)(?:IR|SR)(?:_|$)", origin):
            continue
        refs = {row.get("id"), row.get("source_node"), row.get("source_interaction")}
        label = re.match(r"^([A-Za-z]+[0-9]+)[.、:：]\s*", step["operation"]["name"])
        if label:
            refs.add(label[1])
        if ref in refs:
            targets[step["id"]] = fact["operation_id"]
    if len(targets) != 1:
        return ref, None
    return ref, next(iter(targets.items()))


def collect(rows, system_row, fused):
    product = system_row["behavior_product"]
    group = product["context"].get("group_path") or group_path(system_row["name"])
    result = {"documents": [], "branches": [], "pending": [], "inventory": False}
    sources = defaultdict(list)
    for row in rows:
        behavior = row.get("behavior_product") or {}
        path = PurePosixPath((row.get("relative_path") or "").replace("\\", "/"))
        if (
            not row.get("behavior_enabled")
            or behavior.get("kind") != "ordered_scenario"
            or path.parts[-3:-1] != ("behaviour", "SR")
            or group_path(str(path)) != group
            or not behavior.get("scenario_document")
        ):
            continue
        raw = behavior["raw"]
        chunk = raw.get("sourceChunking")
        sources[(chunk if isinstance(chunk, str) else None, raw["ID"])].append((row, str(path)))

    for (_, scenario_id), candidates in sources.items():
        row, path = candidates[0]
        if len({r["hash"] for r, _ in candidates}) > 1:
            result["pending"].append(
                {
                    "file": path,
                    "scenario_id": scenario_id,
                    "reason": "同一SR分支ID存在多个已启用版本",
                }
            )
            continue
        behavior = row["behavior_product"]
        raw = behavior["raw"]
        kind = scenario_kind(raw)
        doc = behavior["scenario_document"]
        line = doc["lines"][0]
        branch = json.loads(line["text"][len(BRANCH_MARKER) :])
        branch["source_refs"] = [
            {
                "source_id": doc["source_id"],
                "line_start": line["number"],
                "line_end": line["number"],
                "quote": line["text"],
            }
        ]
        result["documents"].append(doc)
        if kind in {"alternative", "normal"}:
            branch["scenario_type"] = "optional" if kind == "alternative" else "normal"
            result["branches"].append(branch)
            result["inventory"] = True
            continue
        try:
            ordered_nodes(raw)
        except (ValueError, TypeError, KeyError) as error:
            result["pending"].append(
                {"file": path, "scenario_id": scenario_id, "reason": str(error)}
            )
            continue
        matches = _operation_links(product["raw"]["operations"], raw)
        ref, anchor = _anchor(raw, product, fused)
        identified_exception = kind == "exception" or (
            not raw.get("scenario_kind")
            and len(matches) == 1
            and (
                matches[0][1].get("scenario_kind") == "exception"
                or re.search(r"::exception(?:_\d+)?$", matches[0][1].get("source_key") or "")
            )
        )
        contradictory = any(
            scenario_kind(operation) in {"alternative", "normal"} for _, operation in matches
        )
        if (
            len(matches) > 1
            or contradictory
            or not identified_exception
            or (not matches and not anchor)
        ):
            result["pending"].append(
                {
                    "file": path,
                    "scenario_id": raw["ID"],
                    "reason": "SR分支的异常类型或SysOperation对应ID未能唯一确认",
                }
            )
            continue
        branch["scenario_type"] = "exception"
        branch["behavior_operation_id"] = matches[0][0] if matches else anchor[1]
        if ref:
            branch["behavior_step_id"] = ref
        if anchor:
            branch["behavior_interaction_id"] = anchor[0]
        else:
            result["pending"].append(
                {
                    "file": path,
                    "scenario_id": raw["ID"],
                    "reason": "已对应SysOperation分支，主成功路径锚点尚未唯一定位",
                }
            )
        result["inventory"] = True
        result["branches"].append(branch)
    return result


def bindings(branches):
    result = []
    for branch in branches["branches"]:
        anchor = branch.get("behavior_interaction_id")
        result.append(
            {
                "branch_id": branch["id"],
                "interaction_id": anchor,
                "status": "confirmed" if anchor else "pending",
                "basis": (
                    "SR行为分支扩展锚点ID：" + branch["behavior_step_id"]
                    if anchor
                    else "SR行为分支已对应SysOperation，具体交互待确认"
                ),
                "source_refs": branch["source_refs"],
            }
        )
    return {"bindings": result}
