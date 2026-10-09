"""Trace exception coverage to concrete checks, components and accepted links."""
from __future__ import annotations

from .concerns import CONCERN_DEFINITIONS


def coverage_diagnostics(generated, checker, matches):
    gen = {s["scenario_id"]: s for s in generated["scenarios"]}
    diagnostics = []
    for c in checker["scenarios"]:
        if c["scenario_type"] != "requirement_exception":
            continue
        links = [m for m in matches["matches"] if m["checker_scenario_id"] == c["scenario_id"]
                 and m["status"] in {"full", "partial"} and gen[m["generated_scenario_id"]]["scenario_type"]
                 in {"requirement_exception", "concern_derived_exception"}]
        derived = [m for m in links if gen[m["generated_scenario_id"]].get("generation_status") != "explicit"]
        explicit = [m for m in links if gen[m["generated_scenario_id"]].get("generation_status") == "explicit"]
        matched = [gen[m["generated_scenario_id"]] for m in links]
        same_uc = [s for s in gen.values() if s["use_case_id"] == c["use_case_id"]
                   and s["scenario_type"] == "concern_derived_exception"]
        routed = [s for s in same_uc if set(c["concern_keys"]) & set(s["concern_keys"])]
        if derived:
            reason, suggestion = "关注点已实例化并通过语义匹配", "保留当前具体检查与来源"
        elif explicit:
            reason, suggestion = "明确分支已覆盖，关注点推导尚未覆盖", "将该异常涉及的正常约束与检查对象进一步实例化"
        elif not c["concern_keys"]:
            reason, suggestion = "已有异常未分类，需核实体系表达能力", "独立核实原文；评估是否需新增关注点"
        elif not routed:
            reason, suggestion = "现有关注点未路由到所属用例", "依据依赖和检查步骤补齐组件/调用边与挂载"
        else:
            reason, suggestion = "存在同类候选但具体条件/行为尚未覆盖", "核实对象和失败机制、候选具体化及逐对判定"
        # An explicit match must not hide the independently routed candidates
        # whose missing behavior or unconfirmed check location still needs work.
        relevant = list({s["scenario_id"]: s for s in [*matched, *routed]}.values())
        accepted_ids = {s["scenario_id"] for s in matched}
        proposals = [s["mount_proposal"] for s in relevant if s.get("mount_proposal")]
        if proposals:
            owners = sorted({n for p in proposals for n in p["components"]})
            suggestion += "；SSD 挂载待确认，关联用例既有实现组件：" + "、".join(owners)
        diagnostics.append({
            "checker_scenario_id": c["scenario_id"], "use_case_id": c["use_case_id"],
            "source_refs": c["source_refs"], "exception": c["name"], "trigger": c["trigger"],
            "business_operation": c.get("use_case_name", c["use_case_id"]),
            "failure_condition_evidence": c["trigger"], "existing_behavior_steps": c["scenario_steps"],
            "existing_expected_result": c["expected_result"],
            "concern_keys": c["concern_keys"],
            "concern_descriptions": [CONCERN_DEFINITIONS[k]["label"] for k in c["concern_keys"]],
            "node_id": sorted({s.get("subject_node_id") for s in relevant if s.get("subject_node_id")}),
            "edge_id": sorted({s.get("exchange_id") for s in relevant if s.get("exchange_id")}),
            "candidate_ids": sorted({s.get("candidate_id") for s in relevant if s.get("candidate_id")}),
            "routed_generated_ids": [s["scenario_id"] for s in routed],
            "unmatched_routed_generated_ids": [s["scenario_id"] for s in routed if s["scenario_id"] not in accepted_ids],
            "matched_generated_ids": [m["generated_scenario_id"] for m in links],
            "matched_statuses": [m["status"] for m in links],
            "explicit_covered": bool(explicit), "concern_covered": bool(derived),
            "constraint_instantiation_covered": any(gen[m["generated_scenario_id"]].get("generation_status")
                == "constraint_instantiation" for m in derived),
            "generic_routing_covered": any(gen[m["generated_scenario_id"]].get("generation_status")
                == "unreviewed_candidate" for m in derived),
            "unclassified_in_checker": not c["concern_keys"],
            "unmapped_check_ids": [s["scenario_id"] for s in relevant if s.get("trace_mapping_status") == "needs_confirmation"],
            "suggested_check_locations": proposals,
            "status": "covered" if links else "unmatched", "reason": reason, "suggestion": suggestion,
            "semantic_evidence": [m["evidence"] for m in links],
            "missing_behavior": [{"generated_scenario_id": m["generated_scenario_id"],
                                  "gaps": m["missing_behavior"]} for m in links if m["status"] == "partial"],
        })
    return diagnostics
