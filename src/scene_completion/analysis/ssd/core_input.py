"""Deterministic core input tools used by the CLI and coding agents."""

import hashlib
import json
from pathlib import Path

from scene_completion.analysis.ssd.core_export import write_core
from scene_completion.analysis.ssd.pipeline import _input_root, build_cases, case_identity
from scene_completion.domain.current_scope import COMMAND_PROFILES, STRUCTURED_PROFILES
from scene_completion.domain.ssd.validation import validate
from scene_completion.infrastructure.storage import fingerprint, write_json
from scene_completion.inputs.structured.authoring_cases import discover

FORMATS = {
    "main-success.json": ("main-success-v1", "main-success-v2"),
    "existing-exceptions.json": ("exception-list-v1", "exception-list-v2"),
    "test-exceptions.json": ("exception-list-v1", "exception-list-v2"),
    "extension-mapping.json": ("extension-mapping-v1", "extension-mapping-v2"),
}
PATCHES = {
    "architecture.json": ("elements", "id", {"kind", "technology"}),
    "main-success.json": (
        "steps",
        "id",
        {"sender", "receiver", "parent_id", "api_ref", "operation", "declared_fields"},
    ),
    "existing-exceptions.json": (
        "exceptions",
        "id",
        {
            "step_id",
            "failure_step_id",
            "target",
            "entity_id",
            "attribute",
            "parameter",
            "concern_key",
            "status",
            "reason",
            "anchor",
            "scenario_kind",
        },
    ),
    "extension-mapping.json": ("items", "extension_id", {"kind", "reason", "bindings"}),
}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _relative(root, path):
    file = (root / path).resolve()
    if not file.is_relative_to(root) or not file.is_file():
        raise ValueError("引用不在输入目录内，或文件不存在：" + str(path))
    return file


def _fingerprint(root):
    return fingerprint(
        [
            (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(root.rglob("*"))
            if path.is_file()
            and path.resolve().is_relative_to(root)
            and path.suffix.lower() in {".json", ".md", ".markdown", ".xlsx"}
            and not any(part.startswith(".") for part in path.relative_to(root).parts)
        ]
    )


def _issue(kind, reason, **location):
    return {"kind": kind, "reason": reason, **location}


def _read_cases(root, selections, profile=None):
    entries = list(discover(root, case_identity))
    selected = set(selections or [])
    seen = set()
    issues, bundles = [], []
    for file, case, error in entries:
        if selected and not selected.intersection(case.values()):
            continue
        seen.update(case.values())
        if not error:
            try:
                bundle = validate(
                    build_cases(
                        root, [case["id"]], case_files=[file], generate=False, profile=profile
                    )[0]
                )
            except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
                error = str(exc)
        if error:
            issues.append(
                _issue(
                    "blocking", error, case_id=case["id"], file=file.relative_to(root).as_posix()
                )
            )
        else:
            bundles.append(bundle)
    for unknown in sorted(selected - seen):
        issues.append(_issue("blocking", "找不到用例", case_id=unknown))
    if not entries and not issues:
        issues.append(_issue("blocking", "未找到结构化用例"))
    return bundles, issues


def _needs(bundle):
    case_id = bundle["case"]["id"]
    if bundle.get("analysis_profile") in STRUCTURED_PROFILES:
        entities = {e["id"] for e in bundle["entities"]}
        if not entities:
            yield _issue("pending", "功能树未找到唯一用例的实体约束", case_id=case_id)
        for step in bundle["steps"]:
            gaps = set(step["entity_ids"]) - entities
            if gaps:
                yield _issue(
                    "pending",
                    "交互实体在功能树缺少定义",
                    case_id=case_id,
                    step_id=step["id"],
                    entities=sorted(gaps),
                )
            if step.get("participant_gaps"):
                yield _issue(
                    "pending", "行为模型缺少参与者声明", case_id=case_id, step_id=step["id"]
                )
    for api in bundle.get("apis", []):
        if not api.get("path_conflicts"):
            continue
        for step in bundle["steps"]:
            if not step.get("api_id") and api["id"] in step["operation"]["name"]:
                yield _issue(
                    "pending",
                    "接口编号对应多个路径",
                    case_id=case_id,
                    step_id=step["id"],
                    api_id=api["id"],
                    candidates=api["path_conflicts"],
                    qualified_candidates=api.get("qualified_candidates", []),
                    evidence=api["source_refs"],
                )
    for gap in bundle.get("pending", []):
        if gap.get("command_gap"):
            yield _issue(
                "pending",
                gap["reason"],
                case_id=case_id,
                command_id=gap["command_id"],
                evidence=gap["source_refs"],
            )
    if bundle.get("gt_source_available") is False:
        yield _issue("unassessed", "该用例缺少可对齐的 GT", case_id=case_id)
    for channel in ("E", "GT"):
        for row in bundle["channels"][channel]["pending"]:
            yield _issue(
                "pending",
                row.get("reason") or row["condition"],
                case_id=case_id,
                channel=channel,
                id=row["id"],
                step_id=row.get("step_id"),
                condition=row["condition"],
                evidence=row.get("source_refs", []),
            )


def inspect(directory, cases=None, *, profile=None):
    root = _input_root(directory)
    if not root.is_dir():
        raise ValueError("输入目录不存在")
    bundles, issues = _read_cases(root, cases, profile)
    return {
        "version": "core-input-inspection-v1",
        "input_hash": _fingerprint(root),
        "cases": [bundle["case"] for bundle in bundles],
        "issues": issues + [issue for bundle in bundles for issue in _needs(bundle)],
    }


def _evidence(root, entry):
    file = _relative(root, entry["file"])
    if "json_pointer" in entry:
        value = _load(file)
        pointer = entry["json_pointer"]
        if not isinstance(pointer, str) or pointer and not pointer.startswith("/"):
            raise ValueError("无效 JSON Pointer")
        for raw in pointer.split("/")[1:]:
            key = raw.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) and key.isdecimal() else value[key]
        return
    text = file.read_text(encoding="utf-8-sig").splitlines()
    start, end, quote = entry["start_line"], entry["end_line"], entry["quote"]
    if not (
        1 <= start <= end <= len(text)
        and quote.strip()
        and quote in "\n".join(text[start - 1 : end])
    ):
        raise ValueError("补充引用的行号或引文不吻合")


def _apply(root, output, overrides, input_hash):
    if (
        overrides.get("version") != "core-input-overrides-v1"
        or overrides.get("input_hash") != input_hash
    ):
        raise ValueError("补充文件版本无效，或输入已变化")
    folders = {
        _load(path)["case"]["id"]: path.parent for path in output.glob("cases/*/main-success.json")
    }
    saved, touched = [], set()
    for patch in overrides.get("patches", []):
        name = patch["file"]
        if name not in PATCHES:
            raise ValueError("该文件不接受补充：" + str(name))
        container, identity, allowed = PATCHES[name]
        folder = output if name == "architecture.json" else folders[patch["case_id"]]
        file = folder / name
        value = _load(file)
        key = (file, patch["id"])
        if (
            key in touched
            or not patch.get("evidence")
            or not patch["set"]
            or set(patch["set"]) - allowed
        ):
            raise ValueError("补充重复、缺证据，或字段不允许修改：" + str(patch["id"]))
        touched.add(key)
        for ref in patch["evidence"]:
            _evidence(root, ref)
        rows = [row for row in value[container] if row.get(identity) == patch["id"]]
        if len(rows) != 1:
            raise ValueError("补充引用了不存在或不唯一的 ID：" + str(patch["id"]))
        row = rows[0]
        row.update(patch["set"])
        if name == "extension-mapping.json":
            if row.get("kind") == "exception" and not row.get("bindings"):
                raise ValueError("已确认的测试异常必须提供具体挂载")
            gt_file = folder / "test-exceptions.json"
            gt = _load(gt_file)
            by_binding = {
                fingerprint(
                    [
                        b.get(key)
                        for key in (
                            "step_id",
                            "target",
                            "entity_id",
                            "attribute",
                            "parameter",
                            "concern_key",
                            "condition",
                        )
                    ]
                )[:24]: b
                for b in row.get("bindings", [])
                if row.get("kind") == "exception"
            }
            gt["exceptions"] = [
                r for r in gt["exceptions"] if r.get("extension_id") != row["extension_id"]
            ]
            gt["exceptions"].extend(
                {
                    **binding,
                    "id": "GT-scenario-"
                    + fingerprint([patch["case_id"], row["extension_id"], key])[:24],
                    "extension_id": row["extension_id"],
                    "status": "active",
                }
                for key, binding in by_binding.items()
            )
            write_json(gt_file, gt)
        write_json(file, value)
        saved.append(patch)
    if saved:
        write_json(output / "accepted-overrides.json", {"input_hash": input_hash, "patches": saved})


def convert(directory, destination, cases=None, overrides=None, *, profile=None):
    from tempfile import TemporaryDirectory

    root, output = _input_root(directory), Path(destination).resolve()
    if not root.is_dir():
        raise ValueError("输入目录不存在")
    if output.exists() or output.is_relative_to(root):
        raise ValueError("输出须为输入目录之外的新目录")
    input_hash = _fingerprint(root)
    bundles, issues = _read_cases(root, cases, profile)
    if not bundles:
        return {"output": None, "input_hash": input_hash, "case_ids": [], "issues": issues}
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as staging:
        core = Path(staging) / "core"
        report = write_core(root, core, bundles)
        if overrides:
            _apply(root, core, _load(Path(overrides)), input_hash)
        validation = validate_core(core)
        if not validation["valid"]:
            return {
                **report,
                "output": None,
                "input_hash": input_hash,
                "issues": issues + validation["issues"],
            }
        core.rename(output)
    return {
        **report,
        "output": str(output),
        "input_hash": input_hash,
        "issues": issues + validation["issues"],
    }


def _cross_check(directory, bundle):
    steps = {step["id"]: step for step in bundle["steps"]}
    definitions = bundle["registry"]["definitions"]
    entities = {e["id"]: {a["name"] for a in e.get("attributes", [])} for e in bundle["entities"]}

    def mount(row, location):
        step = steps.get(row.get("step_id"))
        if not step or row.get("target") not in {"sender", "entity", "receiver", "data"}:
            raise ValueError(location + " 未绑定有效步骤或目标")
        if row.get("concern_key") not in definitions or (
            row.get("failure_step_id") and row["failure_step_id"] not in steps
        ):
            raise ValueError(location + " 关注点或实际失败步骤无效")
        if (
            row["target"] == "entity"
            and row.get("entity_id")
            and row.get("attribute") not in entities.get(row["entity_id"], set())
        ):
            raise ValueError(location + " 实体属性不存在")
        param = row.get("parameter")
        if param:
            direction = "response" if param.get("direction") == "return" else param.get("direction")
            if not any(
                f["name"] == param.get("name")
                and f["location"] == param.get("location")
                and (
                    f.get("direction")
                    or (
                        "storage"
                        if f["location"] == "storage"
                        else "response"
                        if step["direction"] == "return"
                        else "request"
                    )
                )
                == direction
                for f in step["data"]
            ):
                raise ValueError(location + " 接口字段或方向不存在")

    main = _load(directory / "main-success.json")
    if main.get("analysis_profile") in STRUCTURED_PROFILES:
        from scene_completion.domain.ssd_contracts import CRUD

        architecture_file = directory.parent.parent / "architecture.json"
        parties = {p["id"]: p for p in _load(architecture_file)["elements"]}
        roles = {"external_actor", "external_service", "internal_service"}
        for step in main["steps"]:
            if step.get("declared_fields") or (
                step.get("data") and main["analysis_profile"] not in COMMAND_PROFILES
            ):
                raise ValueError("实体模式不接受接口字段分析产物")
            if not set(step["operation"].get("crud", [])) <= set(CRUD):
                raise ValueError("CRUD 包含非 CRUD 操作")
            if any(
                parties.get(step[role], {}).get("kind") not in roles
                for role in ("sender", "receiver")
            ):
                raise ValueError("四元组引用了不存在或类型无效的参与者：" + step["id"])
            if {ref["entity"] for ref in step.get("entity_refs", [])} - set(step["entities"]):
                raise ValueError("实体引用证据与四元组实体不一致：" + step["id"])
        if any(not (directory / name).is_file() for name in (*FORMATS, "source-map.json")):
            raise ValueError("实体模式缺少核心分件")
        if main["analysis_profile"] in COMMAND_PROFILES:
            if main.get("command_bindings") != bundle["command_bindings"]:
                raise ValueError("SR 命令主挂载与输入步骤不一致")
            for row in main["steps"]:
                if row["operation"].get("command_id") != steps[row["id"]]["operation"].get(
                    "command_id"
                ):
                    raise ValueError("步骤命令编号与来源不一致：" + row["id"])
            obligations = {
                (step["id"], field["id"], field["command_id"], field["location"], field["name"])
                for step in bundle["steps"]
                for field in step["data"]
            }
            supplied = main.get("data_obligations", [])
            actual = {
                (r["step_id"], r["field_id"], r["command_id"], r["location"], r["name"])
                for r in supplied
            }
            if actual != obligations or len(actual) != len(supplied):
                raise ValueError("SR 数据义务清单与已声明接口不一致")
        mapping = _load(directory / "extension-mapping.json")
        gt = _load(directory / "test-exceptions.json")
        by_extension = {row["extension_id"]: row for row in mapping["items"]}
        binding_fields = (
            "step_id",
            "target",
            "entity_id",
            "attribute",
            "concern_key",
            "condition",
            "expected",
        )

        def bound_rows(rows):
            return {tuple(row.get(key) for key in binding_fields) for row in rows}

        if len(by_extension) != len(mapping["items"]):
            raise ValueError("扩展 ID 重复")
        for ext, item in by_extension.items():
            bindings = item.get("bindings", [])
            active = [
                r
                for r in gt["exceptions"]
                if r.get("extension_id") == ext and r.get("status") == "active"
            ]
            if (item["kind"] == "exception") != bool(bindings) or bound_rows(
                bindings
            ) != bound_rows(active):
                raise ValueError("GT 与扩展映射的确认绑定不一致：" + ext)
        if any(row.get("extension_id") not in by_extension for row in gt["exceptions"]):
            raise ValueError("测试异常缺少对应扩展")
    for name, versions in FORMATS.items():
        file = directory / name
        if not file.is_file():
            continue
        value = _load(file)
        if value.get("version") not in versions:
            raise ValueError(name + " 版本无效")
        if name in {"existing-exceptions.json", "test-exceptions.json"}:
            identities = [row["id"] for row in value.get("exceptions", [])]
            if len(set(identities)) != len(identities):
                raise ValueError(name + " 的异常 ID 重复")
            for row in value.get("exceptions", []):
                if row.get("status", "active") == "active" and row.get("scenario_kind") not in {
                    "normal",
                    "alternative",
                    "out_of_scope",
                }:
                    mount(row, name + "/" + row["id"])
        if name == "extension-mapping.json":
            for row in value.get("items", []):
                if row.get("kind") == "exception" and row.get("status", "active") != "pending":
                    for binding in row.get("bindings") or [row]:
                        mount(binding, name + "/" + row["extension_id"])


def validate_core(directory, cases=None):
    root = _input_root(directory)
    bundles, issues = _read_cases(root, cases)
    files = {
        case["id"]: file.parent
        for file, case, error in discover(root, case_identity)
        if not error and file.name == "main-success.json"
    }
    for bundle in bundles:
        cid = bundle["case"]["id"]
        if cid not in files:
            issues.append(_issue("blocking", "找不到分件主成功文件", case_id=cid))
            continue
        try:
            _cross_check(files[cid], bundle)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            issues.append(_issue("blocking", str(exc), case_id=cid))
    return {
        "valid": not any(issue["kind"] == "blocking" for issue in issues),
        "cases": [bundle["case"] for bundle in bundles],
        "issues": issues + [issue for bundle in bundles for issue in _needs(bundle)],
    }
