"""V2 JSON and Excel exporters."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


HEADER_FILL = PatternFill("solid", fgColor="4472C4")
HEADER_FONT = Font(bold=True, size=10, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14, color="1F4E79")
BODY = Alignment(vertical="top", wrap_text=True)
CENTER = Alignment(horizontal="center", vertical="top", wrap_text=True)
THIN = Border(*(Side(style="thin", color="D9E2F3") for _ in range(4)))


def _safe_filename(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", str(value).strip()) or "scene_completion"


def _title(ws, text: str, columns: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=columns)
    ws.cell(1, 1, text).font = TITLE_FONT
    ws.cell(1, 1).alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 24


def _headers(ws, headers: list[str]) -> None:
    for col, header in enumerate(headers, 1):
        cell = ws.cell(3, col, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = THIN


def _format_rows(ws, start: int, rows: list[list[Any]], centered: set[int] | None = None) -> None:
    centered = centered or set()
    for row_index, values in enumerate(rows, start):
        for col, value in enumerate(values, 1):
            cell = ws.cell(row_index, col, value)
            cell.alignment = CENTER if col in centered else BODY
            cell.border = THIN


def _node_labels(bundle: dict[str, Any]) -> dict[str, str]:
    return {node["node_id"]: node["name"] for node in bundle["scene_model"]["system_composition"]["nodes"]}


def _prediction_rows(bundle: dict[str, Any]) -> list[list[Any]]:
    return [[
        item["interaction_id"], item.get("use_case_id") or "", item["source_node"], item["target_node"], item["interaction_message"],
        item["concern"], item["status"], item["basis"], item["exception_desc"], item["prediction_id"],
        "\n".join(f"{i}. {step}" for i, step in enumerate(item["scenario_steps"], 1)), item.get("diagram_paths", ""), item.get("source_location", ""), "", "",
    ] for item in bundle["scenario_catalog"]]


def _write_prediction_workbook(bundle: dict[str, Any], path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "异常预测"
    headers = ["交互ID", "用例ID", "来源对象", "目标对象", "交互消息", "关注点", "适用状态", "判断依据", "异常描述", "预测ID", "场景步骤", "图产物路径", "来源定位", "匹配GT?", "是否合理"]
    _title(ws, f"{bundle['project']} — V2 异常预测（未进行GT评估）", len(headers))
    _headers(ws, headers)
    _format_rows(ws, 4, _prediction_rows(bundle), centered={1, 2, 6, 7, 10, 14, 15})
    widths = [20, 16, 20, 20, 34, 26, 18, 42, 58, 30, 58, 52, 30, 12, 12]
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(headers))}{max(3, ws.max_row)}"
    ws.sheet_view.showGridLines = False
    wb.save(path)


def _write_scenario_sheet(ws, bundle: dict[str, Any]) -> None:
    headers = ["场景ID", "预测ID", "交互ID", "用例ID", "用例名称", "来源对象", "目标对象", "交互消息", "关注点", "适用状态", "判断依据", "异常描述", "场景步骤", "前置条件", "后置条件", "恢复主流程", "图产物路径", "来源定位", "匹配GT?", "是否合理"]
    _title(ws, f"{bundle['project']} — 场景清单（V2，未进行GT评估）", len(headers))
    _headers(ws, headers)
    rows = []
    for item in bundle["scenario_catalog"]:
        rows.append([
            item["scenario_id"], item["prediction_id"], item["interaction_id"], item.get("use_case_id") or "", item.get("use_case_name", ""),
            item["source_node"], item["target_node"], item["interaction_message"], item["concern"], item["status"], item["basis"], item["exception_desc"],
            "\n".join(f"{i}. {step}" for i, step in enumerate(item["scenario_steps"], 1)), item.get("preconditions", ""), item.get("postconditions", ""), item["recovery"], item.get("diagram_paths", ""), item.get("source_location", ""), "", "",
        ])
    _format_rows(ws, 4, rows, centered={1, 2, 3, 4, 9, 10, 19, 20})
    widths = [30, 30, 20, 16, 22, 20, 20, 34, 26, 18, 42, 58, 58, 34, 34, 34, 52, 30, 12, 12]
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(headers))}{max(3, ws.max_row)}"
    ws.sheet_view.showGridLines = False


def _write_matrix_sheet(ws, bundle: dict[str, Any]) -> None:
    headers = ["交互ID", "来源对象", "目标对象", "交互消息", "关注点Key", "关注点", "适用状态", "判断依据", "异常类型", "需求满足影响", "后续行为影响", "环境协调影响", "来源定位"]
    _title(ws, f"{bundle['project']} — 关注点矩阵", len(headers))
    _headers(ws, headers)
    nodes = _node_labels(bundle)
    interaction_map = {item["interaction_id"]: item for item in bundle["scene_model"]["interactions"]}
    rows = []
    for item in bundle["concern_matrix"]:
        interaction = interaction_map[item["interaction_id"]]
        rows.append([
            item["interaction_id"], nodes.get(interaction["from_node"], interaction["from_node"]), nodes.get(interaction["to_node"], interaction["to_node"]), interaction["message"], item["concern_key"], item.get("concern", item["concern_key"]), item["status"], item.get("basis", ""), "\n".join(item.get("exception_types", [])), item.get("requirement_impact", ""), item.get("subsequent_behavior_impact", ""), item.get("environment_coordination_impact", ""), item.get("source_location", interaction.get("source_location", "")),
        ])
    _format_rows(ws, 4, rows, centered={1, 5, 6, 7, 10, 11, 12})
    widths = [20, 20, 20, 34, 38, 26, 18, 42, 40, 18, 18, 18, 30]
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(headers))}{max(3, ws.max_row)}"
    ws.sheet_view.showGridLines = False


def _json_write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def export_workbooks(bundle: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    project = _safe_filename(bundle.get("project", bundle["scene_model"].get("project", "scene_completion")))
    artifacts = {
        "scene_model": output / "scene_model.json",
        "system_composition": output / "system_composition.json",
        "interaction_catalog": output / "interaction_catalog.json",
        "concern_matrix": output / "concern_matrix.json",
        "checkpoint_results": output / "checkpoint_results.json",
        "exception_tree": output / "exception_tree.json",
        "scenario_catalog_json": output / "scenario_catalog.json",
        "diagram_manifest": output / "diagram_manifest.json",
        "review_items": output / "review_items.json",
        "prediction_workbook": output / f"prediction_analysis_{project}.xlsx",
        "scenario_workbook": output / f"scenario_catalog_{project}.xlsx",
    }
    _json_write(artifacts["scene_model"], bundle["scene_model"])
    _json_write(artifacts["system_composition"], bundle["system_composition"])
    _json_write(artifacts["interaction_catalog"], bundle["interaction_catalog"])
    _json_write(artifacts["concern_matrix"], {"version": "2", "items": bundle["concern_matrix"]})
    _json_write(artifacts["checkpoint_results"], bundle["checkpoint_results"])
    _json_write(artifacts["exception_tree"], bundle["exception_tree"])
    _json_write(artifacts["scenario_catalog_json"], bundle["scenario_catalog"])
    _json_write(artifacts["diagram_manifest"], bundle.get("diagram_manifest", {"version": "2", "status": "skipped", "artifacts": []}))
    _json_write(artifacts["review_items"], bundle.get("review_items", []))
    _write_prediction_workbook(bundle, artifacts["prediction_workbook"])
    wb = Workbook()
    ws = wb.active
    ws.title = "场景清单"
    _write_scenario_sheet(ws, bundle)
    matrix_ws = wb.create_sheet("关注点矩阵")
    _write_matrix_sheet(matrix_ws, bundle)
    wb.save(artifacts["scenario_workbook"])
    manifest = {
        "version": "2",
        "project": bundle["project"],
        "scenario_count": len(bundle["scenario_catalog"]),
        "interaction_count": len(bundle["interaction_catalog"]),
        "concern_matrix_count": len(bundle["concern_matrix"]),
        "review_item_count": len(bundle.get("review_items", [])),
        "evaluation": {"ground_truth": False, "precision": None, "recall": None, "f1": None},
        "outputs": {key: str(path) for key, path in artifacts.items()},
    }
    manifest_path = output / "run_manifest.json"
    _json_write(manifest_path, manifest)
    artifacts["manifest"] = manifest_path
    return {key: str(path) for key, path in artifacts.items()}
