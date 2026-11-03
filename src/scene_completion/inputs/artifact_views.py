"""Read-only input inventory and source usage views."""

from pathlib import Path

from scene_completion.infrastructure.storage import read_json
from scene_completion.inputs.artifact_recognition import ROOTS as ROOTS
from scene_completion.inputs.artifact_recognition import TASKS as TASKS
from scene_completion.inputs.artifact_recognition import deterministic as deterministic
from scene_completion.inputs.artifact_recognition import role_hint as role_hint
from scene_completion.inputs.artifact_store import load, snapshot


def provenance_label(value):
    # Historical stored values stay intact; normalize only their visible label.
    return {"同事产物导入": "已有文件输入", "同事产物合并": "已有文件输入（补充合并）"}.get(
        value, value
    )


def purpose(row):
    if row.get("behavior_product"):
        return row["behavior_product"]["label"]
    if row.get("behavior_error"):
        return "行为建模结果（格式待修正，原流程兜底）"
    if row.get("structure_model"):
        return row["structure_model"]["layer"] + "原始文本结构化提取结果"
    kind = row.get("colleague_product", {}).get("format")
    if kind == "api_extraction":
        return "API提取结果"
    if kind == "function_tree":
        return "功能树：业务实体与接口属性"
    return {
        "test": "测试逆向需求场景结果",
        "RR": "RR原始需求文档",
        "SR": "SR原始设计文档",
        "artifact": "结构化分析结果",
    }.get(row.get("role"), "待归类")


def view(project, item=None):
    index = load(project)
    if item:
        if item not in index["items"]:
            raise ValueError("未知导入文件")
        row = read_json(Path(project) / index["items"][item]["record"]) | {
            "index_revision": index["revision"]
        }
        usage = (
            read_json(Path(project) / "imports/usage.json")
            if (Path(project) / "imports/usage.json").exists()
            else {}
        )
        row["usage"] = [v for v in usage.values() if v["file_id"] == item]
        meta_path = Path(project) / "project.json"
        if meta_path.exists() and row.get("role") in {"RR", "SR", "test"}:
            meta = read_json(meta_path)
            sources = meta.get("sources", {}).get(row["role"], [])
            if any(s.get("path") == row["original"] for s in sources):
                row["status"] = "source_active"
                tasks_path = Path(project) / "run/workflow_tasks.json"
                tasks = read_json(tasks_path).get("tasks", {}) if tasks_path.exists() else {}
                from scene_completion.inputs.source_documents import read_project_documents

                source_ids = {
                    d["source_id"]
                    for d in read_project_documents(
                        Path(project),
                        [s for s in sources if s.get("path") == row["original"]],
                        "test" if row["role"] == "test" else "existing",
                    )
                }

                def references(value):
                    if isinstance(value, dict):
                        return value.get("source_id") in source_ids or any(
                            references(v) for v in value.values()
                        )
                    if isinstance(value, list):
                        return any(references(v) for v in value)
                    return False

                for key, value in tasks.items():
                    output = (
                        Path(project) / "run" / value["output_file"]
                        if value.get("output_file")
                        else None
                    )
                    if output and output.is_file() and references(read_json(output)):
                        row["usage"].append(
                            {
                                "node": key,
                                "status": value.get("status"),
                                "file_id": item,
                                "source": row["original"],
                                "revision": row["revision"],
                            }
                        )
                row["source_registered"] = True
        for a in row["artifacts"]:
            if any(
                v["artifact_id"] == a["id"] and v["revision"] == row["revision"]
                for v in row["usage"]
            ):
                a["status"] = "active"
        if row.get("behavior_product"):
            from scene_completion.inputs.behavior_imports import VERSION as behavior_version
            from scene_completion.inputs.behavior_imports import materials

            p = row["behavior_product"]
            row["behavior_upgrade_required"] = p.get("version") != behavior_version
            row["behavior_resolution"] = []
            if row.get("behavior_enabled") and not row["behavior_upgrade_required"]:
                try:
                    materials(
                        snapshot(project),
                        p.get("case_ids", []) + ([p["case_name"]] if p.get("case_name") else []),
                        diagnostics=row["behavior_resolution"],
                    )
                except ValueError as e:
                    row["behavior_resolution"].append({"object": row["name"], "reason": str(e)})
        return {**row, "purpose": purpose(row)}
    return {
        **index,
        "items": [
            {
                **v,
                "id": k,
                "purpose": v.get("purpose") or purpose(read_json(Path(project) / v["record"])),
            }
            for k, v in index["items"].items()
        ],
    }
