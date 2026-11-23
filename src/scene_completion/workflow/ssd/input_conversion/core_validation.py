"""Cross-check serialized core parts against the reconstructed runtime case."""

import json
import stat

from scene_completion.domain.current_scope import COMMAND_PROFILES, STRUCTURED_PROFILES
from scene_completion.domain.ssd.construction import ident
from scene_completion.domain.ssd.interface_fields import (
    INPUT_FIELD_POLICY,
    candidates,
    legacy_name,
    output_only,
)
from scene_completion.infrastructure.storage import io_path

FORMATS = {
    "main-success.json": ("main-success-v1", "main-success-v2"),
    "existing-exceptions.json": ("exception-list-v1", "exception-list-v2"),
    "test-exceptions.json": ("exception-list-v1", "exception-list-v2"),
    "extension-mapping.json": ("extension-mapping-v1", "extension-mapping-v2"),
}


def _load(path):
    return json.loads(io_path(path).read_text(encoding="utf-8-sig"))


def _cross_check(directory, bundle):
    steps = {step["id"]: step for step in bundle["steps"]}
    definitions = bundle["registry"]["definitions"]
    named = bundle.get("interface_field_policy") == INPUT_FIELD_POLICY
    entities = {e["id"]: {a["name"] for a in e.get("attributes", [])} for e in bundle["entities"]}

    def mount(row, location):
        step = steps.get(row.get("step_id"))
        if not step or row.get("target") not in {"sender", "entity", "receiver", "data"}:
            raise ValueError(location + " 未绑定有效步骤或目标")
        if row.get("concern_key") not in definitions:
            raise ValueError(location + " 关注点无效")
        if (
            bundle.get("analysis_profile") not in STRUCTURED_PROFILES
            and row.get("failure_step_id")
            and row["failure_step_id"] not in steps
        ):
            raise ValueError(location + " 实际失败步骤无效")
        if (
            row["target"] == "entity"
            and row.get("entity_id")
            and row.get("attribute") not in entities.get(row["entity_id"], set())
        ):
            raise ValueError(location + " 实体属性不存在")
        param = row.get("parameter")
        if param and named:
            if main.get("interface_field_policy") == INPUT_FIELD_POLICY and (
                not param.get("command_id") or "location" in param or "direction" in param
            ):
                raise ValueError(location + " 接口参数需使用 command_id 和 name")
            if (
                not output_only(row.get("condition"))
                and len(candidates(bundle, step["id"], row, include_conflicted=True)) != 1
            ):
                raise ValueError(
                    location + " 接口字段不存在或同名字段无法唯一对应，请明确 parameter.command_id"
                )
        elif param:
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

    directory = io_path(directory)
    main = _load(directory / "main-success.json")
    if main.get("analysis_profile") in STRUCTURED_PROFILES:
        from scene_completion.domain.ssd_contracts import CRUD

        architecture_file = directory.parent.parent / "architecture.json"
        for file in [
            architecture_file,
            *(directory / name for name in (*FORMATS, "source-map.json")),
        ]:
            try:
                if not stat.S_ISREG(file.stat().st_mode):
                    raise ValueError("核心分件应为文件：" + file.name)
            except (FileNotFoundError, NotADirectoryError) as error:
                raise ValueError("缺少核心分件：" + file.name) from error
            except OSError as error:
                raise ValueError(f"无法读取核心分件 {file.name}：{error.strerror}") from error
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
        if main["analysis_profile"] in COMMAND_PROFILES:
            if main.get("command_bindings") != bundle["command_bindings"]:
                raise ValueError("SR 命令主挂载与输入步骤不一致")
            for row in main["steps"]:
                step = steps[row["id"]]
                saved_command = row["operation"].get("command_id")
                observed_command = step["operation"].get("command_id")
                legacy_occurrence = saved_command and saved_command == step.get("call_command_id")
                if saved_command != observed_command and not legacy_occurrence:
                    raise ValueError("步骤命令编号与来源不一致：" + row["id"])
            supplied = main.get("data_obligations", [])
            if named:
                matches = {
                    (step["id"], field["command_id"], field["name"]): field["id"]
                    for step in bundle["steps"]
                    for field in step["data"]
                }
                if main.get("interface_field_policy") == INPUT_FIELD_POLICY:
                    actual = {
                        (r["step_id"], r["command_id"], r["name"]): r["field_id"] for r in supplied
                    }
                    valid = (
                        actual == matches
                        and len(actual) == len(supplied)
                        and all("location" not in r and "direction" not in r for r in supplied)
                    )
                elif main.get("interface_field_policy"):
                    valid = False
                else:
                    # Old exports could omit a field whose transport location was unknown.
                    # The function tree restores it; still check every old row's identity.
                    legacy = {(step, cid, legacy_name(name)) for step, cid, name in matches}
                    valid = len({r["field_id"] for r in supplied}) == len(supplied) and all(
                        (r["step_id"], r["command_id"], legacy_name(r["name"])) in legacy
                        and r["field_id"]
                        == ident(
                            "command-field",
                            bundle["case"]["id"],
                            r["command_id"],
                            r.get("location"),
                            r["name"],
                        )
                        for r in supplied
                    )
            else:
                obligations = {
                    (step["id"], field["id"], field["command_id"], field["location"], field["name"])
                    for step in bundle["steps"]
                    for field in step["data"]
                }
                actual = {
                    (r["step_id"], r["field_id"], r["command_id"], r["location"], r["name"])
                    for r in supplied
                }
                valid = actual == obligations and len(actual) == len(supplied)
            if not valid:
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
            return {
                (
                    *(row.get(key) for key in binding_fields),
                    *(
                        tuple((row.get("parameter") or {}).get(k) for k in ("command_id", "name"))
                        if named
                        else ()
                    ),
                )
                for row in rows
            }

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
