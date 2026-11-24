"""Deterministic core input tools used by the CLI and coding agents."""

import hashlib
from pathlib import Path

from scene_completion.domain.current_scope import STRUCTURED_PROFILES
from scene_completion.domain.ssd.validation import validate
from scene_completion.infrastructure.storage import fingerprint, io_path, logical_path, write_json
from scene_completion.inputs.structured.authoring_cases import discover
from scene_completion.workflow.ssd.input_conversion.case_builder import (
    _input_root,
    build_cases,
    case_identity,
    recovered_test_claims,
)
from scene_completion.workflow.ssd.input_conversion.core_files import write_core
from scene_completion.workflow.ssd.input_conversion.core_validation import (
    FORMATS as FORMATS,
)
from scene_completion.workflow.ssd.input_conversion.core_validation import (
    _cross_check,
    _load,
)

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
            "failure_step_hint",
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
    test_claims = recovered_test_claims(root, entries)
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
                        root,
                        [case["id"]],
                        case_files=[file],
                        generate=False,
                        profile=profile,
                        test_claims=test_claims,
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
        if gap.get("case_match_gap"):
            yield _issue("pending", gap["reason"], case_id=case_id, candidates=gap["candidates"])
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
                **{key: row[key] for key in ("candidates", "conflicting_case_ids") if key in row},
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
        if name == "architecture.json" and "kind" in patch["set"]:
            row["kind_override"] = patch["set"]["kind"]
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

    root, output = _input_root(directory), io_path(destination).resolve()
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
        "output": str(logical_path(output)),
        "input_hash": input_hash,
        "issues": issues + validation["issues"],
    }


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
