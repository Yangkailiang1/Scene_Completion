"""Readable three-role reports and workbooks, with chapter-level gap lists."""
from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .concerns import CONCERN_DEFINITIONS
from .semantic_backend import write_json


GROUP_LABELS = {
    "common": "通用关注点", "human": "人员交互", "api_data": "接口数据",
    "external_service": "外部服务", "external_database": "外部数据库",
    "external_llm": "外部模型服务", "external_llm_quality": "外部模型输出质量",
    "internal_database": "内部数据库", "internal_service": "内部服务",
    "internal_service_display": "内部展示服务", "internal_service_compute": "内部计算服务",
    "service_display_interaction": "展示与交互服务", "service_query_retrieval": "查询与检索服务",
    "service_resource_mutation": "资源变更服务", "service_analysis_generation": "分析与生成服务",
    "service_release_activation": "发布与激活服务", "service_relation": "服务依赖关系",
    "service_dependency": "内部服务调用依赖",
    "service_workflow": "业务流程取消与中止：检查取消、失败终止及副作用",
    "ar_service_query_read": "实现层查询", "ar_service_command_write": "实现层写操作",
    "ar_service_orchestration": "实现层编排", "ar_service_integration_event": "实现层事件集成",
    "ar_service_publish_activation": "实现层发布激活",
}
CATEGORY_LABELS = {"overall": "全部场景总计", "exception_overall": "异常场景总计",
                   "explicit": "需求明确异常贡献", "concern_derived": "关注点推导异常贡献",
                   "main_success": "主成功场景", "alternative": "可选场景",
                   "unclassified_exception": "未分类异常场景"}
CATEGORY_LABELS.update({"constraint_instantiation": "有原文依据的具体约束实例化",
                        "unreviewed_candidate": "SSD 路由的泛化关注点候选"})
GROUP_LABELS.update({
    "common": "通用关注点：时延与流程执行问题",
    "human": "人员交互：身份、权限和操作约束",
    "api_data": "接口数据：完整性、类型、格式与范围",
    "external_service": "外部服务：边界外调用、协议与结果",
    "external_database": "外部数据库：外部数据访问及质量",
    "external_llm": "外部模型服务：调用、配置与执行",
    "external_llm_quality": "外部模型输出质量：结果有效性与可靠性",
    "internal_database": "内部数据库：资源、字段、事务与幂等",
    "internal_service": "内部服务：本系统服务执行与依赖",
    "internal_service_display": "内部展示服务：展示内容与交互结果",
    "internal_service_compute": "内部计算服务：计算输入与输出",
    "service_display_interaction": "展示与交互服务：内容、输入及用户操作",
    "service_query_retrieval": "查询与检索服务：查询条件与返回资源",
    "service_resource_mutation": "资源变更服务：业务约束、状态与写入",
    "service_analysis_generation": "分析与生成服务：处理条件和生成结果",
    "service_release_activation": "发布与激活服务：发布前提和生效状态",
    "service_relation": "服务依赖关系：调用顺序与资源关联",
    "service_dependency": "内部服务调用依赖：被调用服务可用性",
    "ar_service_query_read": "实现层查询：读取操作与资源结果",
    "ar_service_command_write": "实现层写操作：变更条件与写入结果",
    "ar_service_orchestration": "实现层编排：多步骤执行与关联",
    "ar_service_integration_event": "实现层事件集成：回调与事件处理",
    "ar_service_publish_activation": "实现层发布激活：发布执行与生效",
})
CATEGORY_LABELS.update({
    "overall": "全部场景总计：所有类型按 ID 去重",
    "exception_overall": "异常场景总计：明确异常与关注点异常",
    "explicit": "明确异常保留：直接保留原文分支",
    "concern_derived": "关注点推导异常：具体约束与路由候选",
    "main_success": "主成功场景：完成用例正常目标",
    "alternative": "可选场景：分支条件下的成功路径",
    "unclassified_exception": "未分类异常：尚未对应有效关注点",
})


def category_description(key):
    if key in CONCERN_DEFINITIONS:
        definition = CONCERN_DEFINITIONS[key]
        return f"{definition['label']}：{definition['description']}"
    return GROUP_LABELS.get(key, CATEGORY_LABELS.get(key, key))


def _metric_table(lines, title, values):
    lines += ["", f"## {title}", "", "|类别|关注点说明|漏报率|当前已有完整率|", "|---|---|---|---|"]
    for key, value in values.items():
        lines.append(f"|{key}|{category_description(key)}|{rate_text(value['miss_rate'])}|{rate_text(value['existing_completeness'])}|")


def _diagnostic_values(item):
    # Accept structured values unchanged; JSON and the extra-detail column retain
    # any additional diagnostic fields supplied by the pipeline.
    fields = (("source_refs", "source", "source_location"), ("trigger", "exception", "exception_description"),
              ("concern_keys", "concern_key"), ("subject_node_id", "node_id", "node"),
              ("relation_id", "edge_id", "edge"), ("candidate_id", "candidate_ids"),
              ("status",), ("reason",), ("suggestion", "recommendation"))
    return [next((item[k] for k in aliases if k in item), "") for aliases in fields]


def ref_text(ref: dict) -> str:
    return f"{ref['document']} → {' → '.join(ref['heading_path'])}（{ref['line_start']}-{ref['line_end']}行）"


def target_text(scene: dict) -> str:
    step = scene.get("source_step_index") or scene.get("anchor_step_index")
    anchor = f" → {scene.get('use_case_id', '用例未定位')} / " + (f"步骤 {step}" if step else "用例级（步骤未定位）")
    targets = scene.get("recommendation_target_sections", scene.get("target_sections", {}))
    prefix = "建议补充（检查范围）：" if "recommendation_target_sections" in scene else ""
    lines = [prefix + f"{doc}: " + ("；".join(ref_text(r) + anchor for r in refs) if refs else "章节关联缺失")
             for doc, refs in targets.items()]
    lines.extend("设计证据关联：" + f"{doc}: " + ("；".join(ref_text(r) + anchor for r in refs) if refs else "章节关联缺失")
                 for doc, refs in scene.get("related_design_sections", {}).items())
    return "\n".join(lines)


def rate_text(metric: dict) -> str:
    return f"{metric['numerator']}/{metric['denominator']} = {metric['rate']:.2%}" if metric["rate"] is not None else "不可计算（分母为0）"


def _cell(value):
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    # Model/source content is data, never an Excel formula.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _sheet(wb, title, headers, rows):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="305496")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for row in rows:
        ws.append([_cell(v) for v in row])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for column in ws.columns:
        ws.column_dimensions[column[0].column_letter].width = 25 if len(headers) > 6 else 38
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def export_reports(output, generated, checker, matches, metrics, recommendations):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    for name, value in (("generated_scenarios", generated), ("existing_scenarios", checker),
                        ("scenario_matches", matches), ("metrics", metrics), ("recommendations", recommendations)):
        write_json(root / f"{name}.json", value)
    overall = metrics["overall"]
    headline = metrics.get("exception_overall", overall)
    lines = ["# 三 Agent 异常场景补全评估" if "exception_overall" in metrics else "# 三 Agent 场景评估", "",
             f"- 异常漏报率：{rate_text(headline['miss_rate'])}" if "exception_overall" in metrics else f"- 漏报率：{rate_text(headline['miss_rate'])}",
             f"- 当前已有完整率（{'异常生成场景' if 'exception_overall' in metrics else '全部生成场景'}口径）：{rate_text(headline['existing_completeness'])}",
             "- 当前已有完整率按 G 去重：至少匹配一个已有场景的生成场景数 / 生成场景总数；与按 C 计算的需求覆盖率分开解读。",
             f"- 匹配后端：{matches['backend']}；推荐后端：{recommendations['backend']}；rerank：{recommendations['rerank']}",
             "- 完整与部分匹配均计重合；分类分别去重，数量不可直接相加。",
             "- 推荐评分未经概率校准；候选不代表已证实的产品缺陷。"]
    if "exception_overall" in metrics:
        lines += [f"- 全部场景对照漏报率：{rate_text(overall['miss_rate'])}；完整率：{rate_text(overall['existing_completeness'])}。"]
    if "acceptance" in metrics:
        acceptance = metrics["acceptance"]
        lines += [f"- 异常漏报率验收：{'通过' if acceptance['passed'] else '未通过'}；要求严格低于5%、异常分母大于0且匹配输入完整。"]
    if (root / "architecture_changes.json").exists():
        architecture = json.loads((root / "architecture_changes.json").read_text(encoding="utf-8"))
        lines += [f"- 架构抽取关联：{len(architecture['calls'])} 条；原文明示 {architecture.get('confirmed_call_count', 0)} 条；"
                  f"待确认 {architecture.get('pending_call_count', len(architecture['calls']))} 条。实线与虚线分开，不把待确认关联写成实际调用。",
                  "- [架构证据复核](architecture_evidence_review.json) · [调用与待确认关联图](architecture_calls.svg) · [关注点检查挂载](concern_placements.md)。"]
        constraints = [s for s in generated["scenarios"] if s.get("generation_status") == "constraint_instantiation"]
        lines += [f"- 来源约束 {len(constraints)} 条，其中 {sum(bool(s.get('mount_proposal')) for s in constraints)} 条尚无精确 SSD 交换，"
                  "保留已有实现责任方与待确认检查建议，不能视为已经实施的检查。"]
    coverage = metrics.get("classification_coverage", {})
    for role, values in coverage.items():
        lines.append(f"- {role} 显式异常标签覆盖：{values['classified_count']}/{values['explicit_exception_count']}；"
                     f"未分类 {len(values['unclassified_ids'])} 项。未分类异常只计入总计及未分类桶，分类指标依赖标签覆盖。")
    if "generation_contributions" in metrics:
        _metric_table(lines, "明确异常与关注点推导贡献", metrics["generation_contributions"])
        for key, value in metrics["generation_contributions"].items():
            lines += [f"- {category_description(key)}：覆盖已有异常 {value['matched_checker_count']} 项；"
                      f"独占 {value['exclusive_checker_count']} 项（{'、'.join(value['exclusive_checker_ids']) or '无'}）；"
                      f"共享 {value['shared_checker_count']} 项（{'、'.join(value['shared_checker_ids']) or '无'}）。",
                      f"  覆盖已有异常 ID：{'、'.join(value['matched_checker_ids']) or '无'}。"]
        gaps = metrics["generation_contributions"]["concern_derived"]["missing_scenarios"]
        lines += ["", "## 关注点推导尚未覆盖的已有异常", "",
                  "总体覆盖包含明确分支保留。下列项目仅表示推导集合未获完整或部分匹配，不能据此宣称必须新增分类。",
                  "|需求章节|已有异常|现有关注点|", "|---|---|---|"]
        for scene in gaps:
            values = ["；".join(ref_text(r) for r in scene.get("source_refs", [])),
                      scene.get("trigger", scene.get("name", "")),
                      "；".join(category_description(k) for k in scene.get("concern_keys", []))]
            lines.append("|" + "|".join(v.replace("|", "\\|").replace("\n", "<br>") for v in values) + "|")
        if not gaps:
            lines.append("|无|推导集合已覆盖全部已有异常|—|")
    for field, title in (("concern_method_details", "关注点方法贡献细分（来源约束与泛化候选）"),
                         ("by_concern_exception", "各关注点异常指标"), ("by_group_exception", "各大类异常指标"),
                         ("by_concern", "各关注点全部场景对照指标"), ("by_group", "各大类全部场景对照指标"),
                         ("special_categories", "主成功、可选与未分类指标")):
        if field in metrics:
            _metric_table(lines, title, metrics[field])
    for title, status in (("完整匹配", "full"), ("部分匹配与缺少行为", "partial")):
        lines += ["", f"## {title}", ""]
        for m in matches["matches"]:
            if m["status"] == status:
                lines += [f"- {m['checker_scenario_id']} ↔ {m['generated_scenario_id']}：{m['status']}。"
                          f"{m['evidence']} 缺少行为：{'；'.join(m.get('missing_behavior', [])) or '无'}"]
    lines += ["", f"## 分类差异（{len(metrics['classification_discrepancies'])} 条）", "",
              "两端标签独立标注；分类重合只计算两端共同归类的关系。以下差异不改变总体行为匹配。",
              "|已有场景|生成场景|匹配|检查器关注点|生成器关注点|章节|", "|---|---|---|---|---|---|"]
    gen_by_id = {s["scenario_id"]: s for s in generated["scenarios"]}
    checker_by_id = {s["scenario_id"]: s for s in checker["scenarios"]}
    discrepancy_rows = []
    for link in metrics["classification_discrepancies"]:
        c, g = checker_by_id[link["checker_scenario_id"]], gen_by_id[link["generated_scenario_id"]]
        c_keys, g_keys = c.get("concern_keys", []), g.get("concern_keys", [])
        c_refs = "；".join(ref_text(r) for r in c.get("source_refs", []))
        g_refs = "；".join(ref_text(r) for r in g.get("source_refs", []))
        values = [c["scenario_id"], g["scenario_id"], link["status"],
                  "；".join(category_description(k) + f" ({k})" for k in c_keys) or "未归类",
                  "；".join(category_description(k) + f" ({k})" for k in g_keys) or "未归类", c_refs]
        lines.append("|" + "|".join(v.replace("|", "\\|").replace("\n", "<br>") for v in values) + "|")
        discrepancy_rows.append([c["scenario_id"], g["scenario_id"], link["status"], c_keys, g_keys,
                                values[3], values[4], c["trigger"], g["trigger"], c_refs, g_refs, link["evidence"]])
    lines += ["", "## 生成器漏报", ""]
    for s in headline["missing_scenarios"]:
        lines += [f"### {s['scenario_id']}：{s['name']}", "", s["trigger"], "",
                  *[ref_text(ref) for ref in s.get("source_refs", [])], ""]
    lines += ["", "## 关注点挂载", "", "|角色|场景ID|关注点说明|节点|边或交换|候选|", "|---|---|---|---|---|---|"]
    attachment_rows = []
    for role, scenes in (("生成器", generated["scenarios"]), ("检查器", checker["scenarios"])):
        for s in scenes:
            for key in s.get("concern_keys", []) or [""]:
                description = category_description(key) if key else "未分类（未挂载关注点）"
                node = s.get("subject_node_id", "")
                edge = s.get("relation_id") or s.get("exchange_id") or s.get("interaction_id", "")
                attachment_rows.append([role, s["scenario_id"], s["use_case_id"], s["scenario_type"], key, description,
                                        s.get("concern_subject", ""), node, edge, s.get("candidate_id", ""),
                                        s.get("generation_status", ""), "\n".join(ref_text(r) for r in s.get("source_refs", []))])
                lines.append(f"|{role}|{s['scenario_id']}|{description}|{node}|{edge}|{s.get('candidate_id', '')}|")
    diagnostics = metrics.get("coverage_diagnostics", [])
    lines += ["", "## 覆盖诊断", ""]
    if diagnostics:
        lines += ["|来源|异常|关注点|节点|边|候选|状态|原因|建议|", "|---|---|---|---|---|---|---|---|---|"]
        for diagnostic in diagnostics:
            lines.append("|" + "|".join(str(_cell(v)).replace("|", "\\|").replace("\n", "<br>") for v in _diagnostic_values(diagnostic)) + "|")
    else:
        lines.append("未提供覆盖诊断记录。")
    for title, scenes in (("全部生成场景", generated["scenarios"]), ("全部已有场景", checker["scenarios"])):
        lines += ["", f"## {title}", ""]
        for s in scenes:
            lines += [f"### {s['scenario_id']}：{s.get('name', '')}", "",
                      f"用例：{s['use_case_id']}；类型：{s['scenario_type']}；关注点：{'、'.join(s.get('concern_keys', [])) or '未分类'}",
                      f"触发：{s['trigger']}", f"步骤：{'；'.join(s['scenario_steps'])}", f"预期结果：{s['expected_result']}",
                      *[ref_text(r) for r in s.get("source_refs", [])], ""]
    lines += ["", "## 按章节查看未匹配场景与补充建议", ""]
    for s in recommendations["items"]:
        lines += [f"### {s['scenario_id']}：{s['name']}", "",
                  f"推荐评分：{s['confidence']:.4f}；支持度：{s['support_score']:.4f}；缺失度：{s['missing_score']:.4f}；等级：{s['priority']}",
                  "", target_text(s), "", f"建议补充：{s['trigger']}", "", s["basis"], ""]
    (root / "report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    wb = Workbook()
    wb.remove(wb.active)
    metric_rows = []
    sections = []
    if "exception_overall" in metrics:
        sections.append(("异常总计", {"exception_overall": headline}))
    for field, label in (("generation_contributions", "生成贡献"), ("concern_method_details", "关注点方法细分"),
                         ("by_concern_exception", "异常关注点"),
                         ("by_group_exception", "异常大类")):
        if field in metrics:
            sections.append((label, metrics[field]))
    sections += [("总计", {"overall": overall}), ("关注点", metrics["by_concern"]),
                 ("大类", metrics["by_group"]), ("特殊类型", metrics["special_categories"])]
    for level, rows in sections:
        for key, row in rows.items():
            metric_rows.append([level, key, category_description(key), row["checker_count"], row["generated_count"],
                                row["miss_rate"]["numerator"], row["miss_rate"]["denominator"], row["miss_rate"]["rate"],
                                row["existing_completeness"]["numerator"], row["existing_completeness"]["denominator"],
                                row["existing_completeness"]["rate"], row.get("matched_checker_ids", []),
                                row.get("exclusive_checker_count"), row.get("exclusive_checker_ids", []),
                                row.get("shared_checker_count"), row.get("shared_checker_ids", [])])
    metric_ws = _sheet(wb, "指标", ["粒度", "类别", "关注点说明", "已有场景数", "生成场景数", "漏报分子", "漏报分母", "漏报率",
                         "完整率分子", "完整率分母", "当前已有完整率", "匹配已有场景ID", "独占覆盖数", "独占覆盖ID",
                         "共享覆盖数", "共享覆盖ID"], metric_rows)
    metric_headers = {cell.value: cell.column for cell in metric_ws[1]}
    for title in ("漏报率", "当前已有完整率"):
        for row in metric_ws.iter_rows(min_row=2, min_col=metric_headers[title], max_col=metric_headers[title]):
            row[0].number_format = "0.00%"
    for cell in metric_ws[1]:
        metric_ws.column_dimensions[cell.column_letter].width = 48 if cell.value == "关注点说明" else 36 if cell.value == "类别" or cell.value.endswith("ID") else 18
    metric_ws.row_dimensions[1].height = 36
    for row in metric_ws.iter_rows(min_row=2):
        lines = 1
        for cell in row[1:3]:
            width = metric_ws.column_dimensions[cell.column_letter].width - 2
            display_width = sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
                                for char in str(cell.value or ""))
            lines = max(lines, math.ceil(display_width / width))
        metric_ws.row_dimensions[row[0].row].height = max(32, lines * 15 + 6)
    for title, scenes in (("生成场景", generated["scenarios"]), ("已有场景", checker["scenarios"]),
                           ("生成器漏报", headline["missing_scenarios"])):
        _sheet(wb, title, ["ID", "用例", "类型", "名称", "前置条件", "触发", "步骤", "预期结果", "恢复", "后置条件", "关注点", "证据章节", "补充章节"],
               [[s["scenario_id"], s["use_case_id"], s["scenario_type"], s.get("name"), s.get("preconditions"), s["trigger"],
                 s["scenario_steps"], s["expected_result"], s.get("recovery"), s.get("postconditions"), s.get("concern_keys"),
                 "\n".join(ref_text(r) for r in s.get("source_refs", [])), target_text(s)] for s in scenes])
    _sheet(wb, "关注点挂载", ["角色", "场景ID", "用例", "类型", "关注点", "关注点说明", "关注对象", "节点",
                              "边或交换", "候选", "生成状态", "证据章节"], attachment_rows)
    _sheet(wb, "覆盖诊断", ["来源", "异常", "关注点", "节点", "边", "候选", "状态", "原因", "建议", "完整记录"],
           [[*_diagnostic_values(item), item] for item in diagnostics])
    _sheet(wb, "匹配关系", ["已有场景", "生成场景", "状态", "依据", "缺少行为"],
           [[m["checker_scenario_id"], m["generated_scenario_id"], m["status"], m["evidence"], m.get("missing_behavior", [])]
            for m in matches["matches"]])
    _sheet(wb, "分类差异", ["已有场景", "生成场景", "匹配状态", "检查器编码", "生成器编码", "检查器关注点说明",
                            "生成器关注点说明", "检查器触发", "生成器触发", "需求章节", "生成证据章节", "行为匹配依据"], discrepancy_rows)
    for title, status in (("完整匹配", "full"), ("部分匹配", "partial")):
        _sheet(wb, title, ["已有场景", "生成场景", "状态", "依据", "缺少行为"],
               [[m["checker_scenario_id"], m["generated_scenario_id"], m["status"], m["evidence"], m.get("missing_behavior", [])]
                for m in matches["matches"] if m["status"] == status])
    _sheet(wb, "推荐", ["ID", "用例", "名称", "评分", "支持度", "缺失度", "等级", "依据", "补充章节", "证据", "rerank"],
           [[s["scenario_id"], s["use_case_id"], s["name"], s["confidence"], s["support_score"],
             s["missing_score"], s["priority"], s["basis"], target_text(s), s.get("evidence_refs"),
             recommendations["rerank"]] for s in recommendations["items"]])
    wb.save(root / "scene_assessment.xlsx")
    wb.close()
    return {"report": str(root / "report.md"), "workbook": str(root / "scene_assessment.xlsx")}
