"""Content-based discovery of the five agreed inputs; no model calls or code execution."""

import base64
import json
import os
from pathlib import Path

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.colleague_formats import format_of
from scene_completion.inputs.recovered_tests import json_cases, parsed
from scene_completion.inputs.structure_models import recognized

ROLES = ("RR", "SR", "function_tree", "api_extraction", "test")
LABELS = {
    "RR": "RR原始文本结构化提取结果",
    "SR": "SR原始文本结构化提取结果",
    "function_tree": "功能树：业务实体与接口属性",
    "api_extraction": "API提取结果",
    "test": "测试逆向需求场景结果",
}
TARGETS = {
    "RR": ["rr-use-cases", "<用例>:existing-branches"],
    "SR": ["sr-use-cases", "<用例>:existing-branches"],
    "function_tree": [
        "business-entities",
        "<用例>:business-crud（提供依据）",
        "business-attribute-map（提供依据）",
        "<用例>:interaction-enrich（精确字段补充）",
    ],
    "api_extraction": ["接口映射及参数契约（仅已有文件模式使用 SR）"],
    "test": [
        "test-inventory",
        "test-case-align",
        "<用例>:test-concerns",
        "<用例>:test-ground-truth",
    ],
}
EXCLUDED = {"node_modules", ".git", "python", "data", ".workbench", "run", "imports", "__pycache__"}


def identify(text):
    value, _ = parsed(text)
    if recognized(value):
        return value["scope"]["model_level"]
    kind = format_of(value)
    if kind:
        return kind
    from scene_completion.inputs.behavior_imports import format_of as behavior_format

    if behavior_format(value):
        return "behavior"
    try:
        json_cases(text)
        return "test"
    except (ValueError, IndexError, RecursionError):
        return None


def discover(*, directory=None, paths=None, files=None):
    preview, contents, _ = discover_material(directory=directory, paths=paths, files=files)
    return preview, contents


def discover_material(*, directory=None, paths=None, files=None):
    """Return private bytes separately from the serializable preview.

    Explicit paths belong to the server host; browser File objects use bytes.
    Different versions of one role never silently win by filename or order.
    """
    if sum(x is not None for x in (directory, paths, files)) != 1:
        raise ValueError("请选择文件夹、五份绝对路径或上传文件中的一种")
    candidates = []
    ignored = []
    if directory is not None:
        root = Path(directory).expanduser()
        if not root.is_absolute() or not root.is_dir() or root == Path(root.anchor):
            raise ValueError("请指定专用输入文件夹的绝对路径")
        if (root / ".git").exists() or (root / "serve.py").exists():
            raise ValueError("不能扫描程序仓库，请选择材料文件夹")
        for parent, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in EXCLUDED
                and not (Path(parent) / d).is_symlink()
            ]
            for name in names:
                p = Path(parent) / name
                if name.startswith(".") or p.suffix.lower() != ".json" or p.is_symlink():
                    continue
                candidates.append((str(p.relative_to(root)), p, None))
                if len(candidates) > 1000:
                    raise ValueError("JSON文件过多，请缩小输入目录")
    elif paths is not None:
        if not isinstance(paths, dict) or set(paths) - set(ROLES):
            raise ValueError("路径清单仅接受RR、SR、function_tree、api_extraction、test")
        for role, path in paths.items():
            if not isinstance(path, str) or not path.strip():
                raise ValueError(role + "必须指定非空绝对路径")
            p = Path(path).expanduser()
            if (
                not p.is_absolute()
                or not p.is_file()
                or p.is_symlink()
                or p.suffix.lower() != ".json"
            ):
                raise ValueError(role + "必须是现有JSON文件的绝对路径")
            candidates.append((p.name, p, role))
    else:
        if (
            not isinstance(files, list)
            or len(files) > 1000
            or any(not isinstance(f, dict) for f in files)
        ):
            raise ValueError("上传文件列表无效或超过1000份")
        for f in files:
            name = str(f.get("relative_path") or f.get("name", "")).replace("\\", "/")
            parts = Path(name).parts
            if (
                ".." in parts
                or name.startswith("/")
                or any(x.startswith(".") or x in EXCLUDED for x in parts)
            ):
                continue
            if Path(name).suffix.lower() != ".json":
                ignored.append(
                    {"name": name, "reason": "仅接入约定的五类JSON，不读取Skill或报告作为任务指令"}
                )
                continue
            candidates.append((name, f, None))
    selected = {}
    issues = []
    behaviors = []
    invalid_behavior_rows = []
    for display, source, expected in candidates:
        if isinstance(source, Path):
            if source.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("文件超过20MB：" + display)
            raw = source.read_bytes()
            name = source.name
        else:
            raw = (
                base64.b64decode(source["content_base64"], validate=True)
                if source.get("content_base64")
                else str(source.get("content", "")).encode("utf8")
            )
            name = Path(display).name
            if len(raw) > 20 * 1024 * 1024:
                raise ValueError("文件超过20MB：" + display)
        named_ssd = name.casefold() == "sysoperation.json" and "行为模型" in Path(display).parts
        try:
            role = identify(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeError, IndexError, RecursionError) as error:
            if expected:
                raise ValueError(display + "无法识别：" + str(error)) from error
            if named_ssd:
                invalid_behavior_rows.append(
                    {
                        "id": fingerprint([display, raw.hex()])[:24],
                        "name": name,
                        "relative_path": display,
                        "behavior_error": "JSON 读取失败",
                    }
                )
            else:
                ignored.append({"name": display, "reason": "JSON格式无效或不是约定材料"})
            continue
        if role is None:
            if expected:
                raise ValueError(display + "不属于约定的五类格式")
            if named_ssd:
                invalid_behavior_rows.append(
                    {
                        "id": fingerprint([display, raw.hex()])[:24],
                        "name": name,
                        "relative_path": display,
                        "behavior_error": "缺少用例或系统操作定义",
                    }
                )
            else:
                ignored.append(
                    {
                        "name": display,
                        "reason": "非约定格式（如AR、融合模型或一致性报告），本次不接入",
                    }
                )
            continue
        if expected and expected != role:
            raise ValueError(display + "声明用途" + expected + "与实际结构" + role + "不同")
        digest = fingerprint(raw.hex())
        if role == "behavior":
            if any(
                p.lower()
                in {"inputs", "history", "backup", "backups", "archive", "archives", "versions"}
                for p in Path(display).parts[:-1]
            ):
                ignored.append(
                    {
                        "name": display,
                        "reason": "行为生成输入/历史备份不与当前outputs混用；请显式选择需要的当前输出版本",
                    }
                )
                continue
            behaviors.append(
                {
                    "path": display,
                    "name": name,
                    "value": json.loads(raw.decode("utf-8-sig")),
                    "raw": raw,
                    "hash": digest,
                }
            )
            continue
        record = {
            "role": role,
            "label": LABELS[role],
            "name": name,
            "path": display,
            "hash": digest,
            "bytes": len(raw),
            "target_nodes": TARGETS[role],
        }
        if role in selected:
            if selected[role][0]["hash"] != digest:
                issues.append(
                    {
                        "role": role,
                        "reason": "同一用途存在多个不同版本，请手动指定绝对路径",
                        "files": [selected[role][0]["path"], display],
                    }
                )
            else:
                ignored.append({"name": display, "reason": "同内容副本，按内容哈希去重"})
            continue
        selected[role] = (record, raw)
    rows = [selected[r][0] for r in ROLES if r in selected]
    missing = [r for r in ROLES if r not in selected]
    extras = {}
    from scene_completion.inputs.behavior_imports import compile_product, context_for

    supplied_rows = invalid_behavior_rows
    for b in behaviors:
        context = context_for(b["path"], behaviors)
        key = "behavior:" + fingerprint([b["path"], b["hash"]])[:20]
        try:
            product = compile_product(b["value"], key.split(":")[1], b["name"], context)
            error = None
        except (ValueError, TypeError, KeyError) as e:
            product = None
            error = str(e)
        label = product["label"] if product else "行为建模结果（待修正）"
        targets = product["target_nodes"] if product else []
        if product and product["kind"] == "ordered_scenario":
            if product["layer"] == "SR" and product.get("scenario_document"):
                label = "SR原文分支（按ID对应SysOperation）"
            else:
                label = "行为参考文件"
                targets = []
        record = {
            "role": "behavior",
            "label": label,
            "name": b["name"],
            "path": b["path"],
            "hash": b["hash"],
            "bytes": len(b["raw"]),
            "target_nodes": targets,
            "case_name": product["case_name"] if product else context.get("case_name"),
            "counts": product["counts"] if product else {},
            "coverage": "partial",
            "error": error,
        }
        rows.append(record)
        supplied_rows.append(
            {
                "id": key,
                "name": b["name"],
                "relative_path": b["path"],
                "hash": b["hash"],
                "behavior_product": product,
                "behavior_error": error,
                "behavior_enabled": True,
            }
        )
        extras[key] = {
            "name": b["name"],
            "relative_path": b["path"],
            "behavior_context": context,
            "content_base64": base64.b64encode(b["raw"]).decode(),
        }
    from scene_completion.inputs.structure_models import compile_model
    from scene_completion.inputs.supplied_cases import inspect_cases

    if supplied_rows:
        for layer in ("RR", "SR"):
            if layer in selected:
                entry, raw = selected[layer]
                try:
                    supplied_rows.append(
                        {"structure_model": compile_model(raw.decode("utf-8-sig"), entry["name"])}
                    )
                except ValueError as error:
                    issues.append({"role": layer, "reason": str(error)})
    supplied_preview, accepted = {"cases": [], "accepted": []}, {}
    if supplied_rows:
        supplied_preview, _, _, accepted = inspect_cases(supplied_rows)
    if supplied_preview["accepted"]:
        from scene_completion.inputs.colleague_formats import function_interfaces
        from scene_completion.inputs.supplied_api import contracts_for_cases

        if api := selected.pop("api_extraction", None):
            ignored.append(
                {
                    "name": api[0]["path"],
                    "reason": "已有SSD模式从功能树读取SR接口和字段约束",
                }
            )
        rows = [row for row in rows if row["role"] != "api_extraction"]
        issues = [issue for issue in issues if issue["role"] != "api_extraction"]
        missing = [role for role in missing if role != "api_extraction"]
        for row in rows:
            if row["role"] == "function_tree":
                row["target_nodes"] = [
                    "business-entities",
                    "api-map（SR）",
                    "api-index（SR）",
                    "api-parameters（SR）",
                    "<用例>:interaction-enrich",
                ]
        definitions = []
        if tree := selected.get("function_tree"):
            record, raw = tree
            try:
                parsed_tree = function_interfaces(
                    json.loads(raw.decode("utf-8-sig")), record["hash"][:24], record["name"]
                )
                definitions = [
                    (declaration, parsed_tree["interface_document"])
                    for declaration in parsed_tree["interface_declarations"]
                ]
            except (ValueError, TypeError, KeyError) as error:
                issues.append({"role": "function_tree", "reason": str(error)})
        try:
            _, _, contracts, _, api_pending = contracts_for_cases(definitions, accepted)
        except (ValueError, TypeError, KeyError) as error:
            issues.append({"role": "function_tree", "reason": str(error)})
        else:
            supplied_preview.update(sr_interface_count=len(contracts), sr_api_pending=api_pending)
    preview = {
        "supplied_cases": supplied_preview,
        "version": "five-input-bundle-v1",
        "files": rows,
        "missing": missing,
        "issues": issues,
        "ignored": ignored,
        "valid": not issues,
        "complete": not missing and not issues,
        "model_calls": 0,
    }
    preview["preview_hash"] = fingerprint(
        {"files": rows, "missing": missing, "issues": issues, "supplied_cases": supplied_preview}
    )
    return (
        preview,
        {
            **{
                r: {"name": record["name"], "content_base64": base64.b64encode(raw).decode()}
                for r, (record, raw) in selected.items()
            },
            **extras,
        },
        accepted,
    )


def validate_files(files):
    # Validate every decoded format before writing, not halfway through a batch.
    for role, f in files.items():
        raw = base64.b64decode(f["content_base64"])
        text = raw.decode("utf-8-sig")
        if role.startswith("behavior:"):
            # Invalid optional behavior remains visible and falls back. It must
            # not prevent adopting the five original authoritative sources.
            continue
        if role in {"RR", "SR"}:
            from scene_completion.inputs.structure_models import compile_model

            compile_model(text, f["name"])
        elif role in {"function_tree", "api_extraction"}:
            from scene_completion.inputs.colleague_formats import convert

            product = convert(json.loads(text), fingerprint(raw.hex())[:24], f["name"])
            from scene_completion.domain.contracts import validate

            for a in product["artifacts"]:
                validate(a["task"], a["payload"])
        else:
            from scene_completion.inputs.test_sources import preview_sources

            if not preview_sources([{"name": f["name"], "content": text}])["valid"]:
                raise ValueError("测试文件未通过预览")


def apply(
    service, project, preview, files, *, expected_hash=None, adopt_partial=False, replace=False
):
    import scene_completion.inputs.artifact_imports as imports
    from scene_completion.api.inputs import accept_source
    from scene_completion.infrastructure.worker_runtime import read_job

    project = Path(project)
    if not preview["valid"]:
        raise ValueError("用途存在多个候选，请先解决导入预览问题")
    if not files:
        raise ValueError("未找到约定的五类输入文件")
    if expected_hash and expected_hash != preview["preview_hash"]:
        raise ValueError("文件内容或选择已变化，请重新预览")
    if project.name in service.active or read_job(project).get("status") == "running":
        raise ValueError("当前执行中，五文件采用需等本轮结束；不覆盖在途结果")
    validate_files(files)
    result = imports.receive(project, list(files.values()))
    rows = {r["id"]: r for r in imports.snapshot(project)}
    for (role, f), received in zip(files.items(), result["received"]):
        row = rows[received["id"]]
        if role.startswith("behavior:"):
            if adopt_partial and row.get("behavior_product"):
                imports.decide(
                    project,
                    row["id"],
                    {"action": "enable_behavior", "expected_revision": row["revision"]},
                )
            continue
        if role in {"RR", "SR"} and not row.get("structure_enabled", True):
            imports.decide(
                project,
                row["id"],
                {"action": "enable_structure", "expected_revision": row["revision"]},
            )
        elif role == "test":
            meta = read_json(project / "project.json")
            digest = fingerprint(base64.b64decode(f["content_base64"]).hex())
            if not any(
                s.get("path") == row["original"]
                or fingerprint((project / s["path"]).read_bytes().hex()) == digest
                for s in meta["sources"]["test"]
            ):
                accept_source(
                    service,
                    project,
                    row,
                    {"role": "test", "expected_revision": row["revision"], "replace": replace},
                )
        elif adopt_partial or replace:
            for artifact in row["artifacts"]:
                if artifact["error"]:
                    continue
                if artifact["coverage"] == "partial" and not adopt_partial:
                    continue
                current = imports.view(project, row["id"])
                imports.decide(
                    project,
                    row["id"],
                    {
                        "action": "accept",
                        "expected_revision": current["revision"],
                        "artifact_id": artifact["id"],
                        "replace": replace,
                    },
                )
    record = {
        "preview_hash": preview["preview_hash"],
        "files": preview["files"],
        "adopt_partial": adopt_partial,
        "replace": replace,
        "received": result["received"],
        "model_calls": 0,
    }
    write_json(project / "imports/bundles" / (preview["preview_hash"] + ".json"), record)
    return {
        **preview,
        "saved": True,
        "received": result["received"],
        "next": "未启动模型；显式执行时复用已校验产物，只补缺项",
    }
