"""Freeze completed acceptance evidence; never archive secrets or model caches."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

from verify_online_shopping import pack_stage, verify, validate_replay
from verify_demo import compact
from scene_completion.comparison import compare_scenes
from scene_completion.role_cli import run_evaluate, validate_execution_models
from scene_completion.matching_audit import validate_native_review_binding, exclude_native_rejections
from scene_completion.semantic_backend import read_json, write_json
from scene_completion.three_roles import merge_matches


def snapshot(prepared, run, baseline, output):
    """Publish a verified fresh tree, preserving the previous tree on failure."""
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and any(output.iterdir()) and not (output / "evaluation.json").exists():
        raise ValueError("snapshot output is a nonempty unmanaged directory")
    with tempfile.TemporaryDirectory(prefix="online-shopping-snapshot-", dir=output.parent) as directory:
        temporary = Path(directory).resolve()
        if temporary.parent != output.parent or temporary == output:
            raise ValueError("snapshot staging directory escaped the requested parent")
        staged, previous = temporary / output.name, temporary / "previous-snapshot"
        build_snapshot(prepared, run, baseline, staged)
        if output.exists():
            output.rename(previous)
        try:
            staged.rename(output)
        except Exception:
            if previous.exists():
                previous.rename(output)
            raise
        shutil.copy2(temporary / "online_shopping_model.json", output.parent / "online_shopping_model.json")


def build_snapshot(prepared, run, baseline, output):
    prepared, run, baseline, output = map(Path, (prepared, run, baseline, output))
    _, code = run_evaluate(SimpleNamespace(output_dir=str(run)))
    if code:
        raise ValueError("cannot publish an unaccepted run")
    validate_replay(run)
    output.mkdir(parents=True, exist_ok=True)
    preparation = read_json(prepared / "run_manifest.json")
    if not preparation.get("complete") or preparation.get("agent_model") != "ecnu-max":
        raise ValueError("generator preparation must record the completed ecnu-max run")
    write_json(output / "preparation_manifest.json", preparation)
    shutil.copy2(Path(__file__).parent / "online_shopping_seed.json", output / "generator_seed.json")
    validate_execution_models(prepared / "batches" / "generator-model")
    if (run.parent / "round_history").exists():
        shutil.copytree(run.parent / "round_history", output / "round_history", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("_expected", ".scene_cache", "__pycache__", "*.pyc", ".env", "*.local.json"))
    native_reviews = []
    for stage, prefix in (("matching", "luna_review"), ("matching-recovery", "luna_recovery")):
        if (run / "batches" / stage / "native_review.json").exists():
            validate_native_review_binding(run / "batches" / stage)
            packet_name = "luna_review_packet.json" if stage == "matching" else "luna_recovery_packet.json"
            result_name = "luna_review_results.json" if stage == "matching" else "luna_recovery_results.json"
            native_reviews.append({"stage": stage, "packet": read_json(run.parent / packet_name),
                                   "review": read_json(run / "batches" / stage / "native_review.json")})
            for filename in (packet_name, result_name):
                if filename == result_name and read_json(run.parent / filename) != native_reviews[-1]["review"]:
                    raise ValueError("human-readable native result differs from applied review")
                shutil.copy2(run.parent / filename, output / filename)
            for segment in native_reviews[-1]["review"].get("review_segments", []):
                filename = Path(segment["file"]).name
                shutil.copy2(run.parent / filename, output / filename)
    if not any(r["stage"] == "matching" for r in native_reviews):
        raise ValueError("acceptance snapshot requires complete native matching review")
    for stage, packet_name in (("matching", "baseline_luna_review_packet.json"),
                               ("matching-recovery", "baseline_recovery_luna_review_packet.json")):
        directory = baseline / "batches" / stage
        if not (directory / "manifest.json").exists():
            continue
        validate_native_review_binding(directory)
        native_reviews.append({"stage": "baseline-matching" if stage == "matching" else "baseline-recovery",
            "packet": read_json(run.parent / packet_name), "review": read_json(directory / "native_review.json")})
    write_json(output / "native_reviews.json", native_reviews)
    checker = read_json(run / "existing_scenarios.json")
    fixed_c = {**checker, "scenarios": [s for s in checker["scenarios"]
                                     if s["scenario_type"] == "requirement_exception"],
               "scope": "frozen_requirement_exceptions"}
    fixed_c["scenario_count"] = len(fixed_c["scenarios"])
    old_g = read_json(baseline / "generated_scenarios.json")
    old_matches = merge_matches(old_g, fixed_c, baseline / "batches" / "matching")
    if (baseline / "batches" / "matching-recovery" / "manifest.json").exists():
        subset = read_json(baseline / "recovery_checker.json")
        recovered = merge_matches(old_g, subset, baseline / "batches" / "matching-recovery")
        if not recovered["complete"]:
            raise ValueError("baseline recovery comparison is incomplete")
        links = {(m["checker_scenario_id"], m["generated_scenario_id"]): m for m in old_matches["matches"]}
        links.update({(m["checker_scenario_id"], m["generated_scenario_id"]): m for m in
                      exclude_native_rejections(recovered["matches"], baseline / "batches" / "matching")})
        old_matches["matches"] = list(links.values())
        write_json(output / "baseline" / "recovery_checker.json", subset)
    if not old_matches["complete"]:
        raise ValueError("baseline comparison is incomplete")
    old_metrics = compare_scenes(old_g, fixed_c, old_matches)
    for name, value in (("generated_scenarios", old_g), ("existing_scenarios", fixed_c),
                        ("scenario_matches", old_matches), ("metrics_summary", compact(old_metrics))):
        write_json(output / "baseline" / (name + ".json"), value)
    for filename in ("scene_model.json", "generated_scenarios.json", "existing_scenarios.json",
                     "sources_index.json", "checker_sources_index.json", "scenario_matches.json",
                     "recommendations.json", "run_manifest.json", "evaluation.json", "coverage_diagnostics.json",
                     "architecture_changes.json", "architecture_evidence_review.json", "concern_placements.md", "architecture_calls.svg",
                     "system_composition.json", "system_composition.svg", "report.md", "scene_assessment.xlsx"):
        shutil.copy2(run / filename, output / filename)
    if (run / "replay_verification.json").exists():
        shutil.copy2(run / "replay_verification.json", output / "replay_verification.json")
    if (run.parent / "final_effect_review.md").exists():
        shutil.copy2(run.parent / "final_effect_review.md", output / "final_effect_review.md")
    write_json(output / "metrics_summary.json", compact(read_json(run / "metrics.json")))
    write_json(output / "diagram_manifest.json", read_json(run / "diagrams" / "diagram_manifest.json"))
    for folder in ("diagrams", "dependencies"):
        for source in (run / folder).rglob("*"):
            if source.is_file() and source.suffix in {".svg", ".puml", ".json", ".md", ".dot"}:
                target = output / folder / source.relative_to(run / folder)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    evidence = {"generator-model": pack_stage(prepared / "batches" / "generator-model"),
                "pipeline": {d.name: pack_stage(d) for d in (run / "batches").iterdir()
                             if d.is_dir() and (d / "manifest.json").exists()},
                "baseline-matching": pack_stage(baseline / "batches" / "matching")}
    if (baseline / "batches" / "matching-recovery" / "manifest.json").exists():
        evidence["baseline-recovery"] = pack_stage(baseline / "batches" / "matching-recovery")
    # Compact JSON avoids repeating indentation in thousands of quoted source lines.
    (output / "batch_evidence.json").write_text(json.dumps(evidence, ensure_ascii=False,
                                                         separators=(",", ":")), encoding="utf-8")
    shutil.copy2(prepared / "scene_model.json", output.parent / "online_shopping_model.json")
    verify(output)
    metrics = read_json(run / "metrics.json")
    final_miss, old_miss = metrics["exception_overall"]["miss_rate"], old_metrics["exception_overall"]["miss_rate"]
    details = metrics["concern_method_details"]
    components = read_json(run / "architecture_changes.json")["added_documented_components"]
    architecture = read_json(run / "architecture_changes.json")
    if not architecture.get("evidence_review_complete"):
        raise ValueError("architecture source claims require complete independent evidence review")
    generated = read_json(run / "generated_scenarios.json")
    constraints = [s for s in generated["scenarios"] if s.get("generation_status") == "constraint_instantiation"]
    pending_mounts = sum(bool(s.get("mount_proposal")) for s in constraints)
    derived_gaps = metrics["generation_contributions"]["concern_derived"]["missing_scenarios"]
    text = ["# 在线商城购物系统：需求专用异常覆盖验收", "",
        "检查器仅独立抽取原始需求，固定 37 条异常；生成器使用原始需求与设计，未读取检查器或参考测试集。",
        "生成输入由 ecnu-max 按 scene-generate Skill 批量抽取，工具保留全部场景和关注点候选。", "",
        f"- 优化前（同一 C）：{old_miss['numerator']}/{old_miss['denominator']} = {old_miss['rate']:.2%}。",
        f"- 优化后：{final_miss['numerator']}/{final_miss['denominator']} = {final_miss['rate']:.2%}，严格低于 5%。",
        f"- 全部生成场景：{len(generated['scenarios'])}；检查器全部场景：{len(checker['scenarios'])}。",
        f"- 优化前关注点推导覆盖：{old_metrics['generation_contributions']['concern_derived']['matched_checker_count']}/37；明确分支保留覆盖：{old_metrics['generation_contributions']['explicit']['matched_checker_count']}/37。",
        f"- 关注点推导覆盖：{metrics['generation_contributions']['concern_derived']['matched_checker_count']}/37；明确分支保留覆盖：{metrics['generation_contributions']['explicit']['matched_checker_count']}/37。",
        *[f"- 关注点方法 {key} 覆盖：{len(value['matched_checker_ids'])}/37。" for key, value in details.items()], "",
        "来源约束实例化与泛化 SSD 路由分开统计；泛化候选多不等于具体异常覆盖充分。两类贡献可重叠，不能相加。",
        "明确分支保留也能降低总体漏报，因此评估关注点方法时必须同时看推导贡献，不能只看总体。历史需求与设计联合分母的 55.67% 不作为此次优化前数值。",
        f"当前关注点体系能给全部 37 条需求异常归类，但推导集合尚有 {len(derived_gaps)} 条未获匹配；总体达标不表示关注点自动推导已完全覆盖。",
        f"{len(constraints)} 条来源约束中，{pending_mounts} 条暂未对应精确 SSD 交换，保留组件责任方、业务步骤与待确认挂载建议；这些不冒充已经实施的检查。",
        "每项关注点及大类的分子、分母、章节、分类差异和未挂载位置见报告与工作簿。", "",
        "## 修正依据", "",
        "内部服务可用性与流程取消分别增加关注点；现有幂等和业务约束需具体化到请求键、对象、操作与时间参照点。",
        "需求中的时间倒序与设计中的时间范围分别保留；成功返回的重复请求也生成幂等约束实例。",
        "多依赖 SSD 分别建模数据库、内部/外部服务与回调。人类交互和实现返回保留证据，不作为新增服务调用。",
        f"架构抽取关联 {len(architecture['calls'])} 条：{architecture['confirmed_call_count']} 条原文明示、{architecture['pending_call_count']} 条待确认，以实线/虚线区分。生成输入及 SSD 保留全部抽取候选，不能将未确认的模型关联当作实际调用。",
        f"有原文依据的业务组件补充：{'、'.join(n['name'] for n in components) or '无'}。表节点为逻辑资源，资源服务为分析抽象，均不表示新增部署。", "",
        "## 复核与重放", "",
        "逐对 ECNU 判定及独立语义复核记录保存在 batch_evidence.json；原生 gpt-6-luna / max 全量接受关系复核保存在 native_reviews.json。",
        "固定检查器抽取批次早于模型身份记录；保持其场景内容与 37 条分母，另以 ecnu-max 独立核实来源分类。生成输入、分类、匹配与推荐记录实际 ecnu-max 批次身份。",
        "round_history 保留未达标轮次和已识别误拒的诊断历史；这些中间值不作为正式前后对照。",
        "推荐全部展示，0.7×支持度+0.3×缺失度；评分不是真实正确概率。rerank 默认关闭，历史增强对照另见上级 README。", "",
        "```bash", "python examples/verify_online_shopping.py",
        "python examples/verify_online_shopping.py --output-dir examples/results/replayed_online", "```", "",
        "以上无需联网或密钥，重算固定分母、全部匹配和分类指标，验证原始批次、生成集合、评分与原生复核输入绑定。", "",
        "[完整报告](report.md) · [工作簿](scene_assessment.xlsx) · [逐条诊断](coverage_diagnostics.json) · [检查挂载](concern_placements.md) · [实际调用图](architecture_calls.svg)", ""]
    (output / "README.md").write_text("\n".join(text), encoding="utf-8")
    review = ["# 关注点体系与漏报原因诊断", "",
        "## 结论与同口径对照", "",
        f"固定原始需求异常 37 条，总体漏报由 {old_miss['rate']:.2%} 降至 {final_miss['rate']:.2%}。",
        "总体覆盖包含明确异常保留，不能据此宣称关注点自动推导已覆盖全部异常。",
        f"推导贡献为 {metrics['generation_contributions']['concern_derived']['matched_checker_count']}/37，"
        f"具体来源约束覆盖 {len(details['constraint_instantiation']['matched_checker_ids'])}/37，"
        f"泛化路由候选覆盖 {len(details['unreviewed_candidate']['matched_checker_ids'])}/37；三者各自去重，贡献可重叠。", "",
        "原先 55.67% 使用需求与设计混合的 97 个已有场景，和本轮需求专用 37 个异常分母不同。"
        "本轮重新比较旧 G 与固定 C，不能把口径变化当作算法改进。", "",
        "## 为什么泛化生成不能充分覆盖已有异常", "",
        "- 单一依赖选择会让数据库调用遮蔽支付、物流及内部服务调用，本轮以有来源的多依赖交换分别路由。",
        "- 泛化候选只给出类型，缺少具体字段、对象、状态、幂等键和事件时间参照；本轮独立抽取 139 条原文约束进行实例化。",
        "- 原先取消支付仍携带支付成功步骤、无效类目分支仍携带合法类目选择，导致与需求行为矛盾；修正分支路径与前后置条件上下文。",
        "- 时间倒序与时间范围、重复支付请求与重复回调、业务幂等与数据库重复写入属于不同机制；逐对复核防止用泛化相似描述冒充覆盖。", "",
        "## 关注点与组件是否需要增加", "",
        "此次补充内部依赖可用性和流程取消/中止两个关注点。现有分类能表达固定需求 37 条异常，"
        "其余缺口优先调整提取、具体化及检查位置，不再增加同义分类。",
        f"新增有文档依据的业务组件仅为 {'、'.join(n['name'] for n in components) or '无'}；"
        "其余为已有组件关联、逻辑表资源与分析抽象，不能当作新增部署服务。",
        f"保存 {len(architecture['calls'])} 条抽取关联，其中 {architecture['confirmed_call_count']} 条原文明示、"
        f"{architecture['pending_call_count']} 条证据不足而以虚线标为待确认。"
        "PaymentService、LogisticsService 调用及事件回调分别保留；幂等检查需绑定具体请求或事件，不能仅放在数据库写入上。", "",
        "## 尚未获得推导匹配的 6 条需求异常", "",
        "下列建议是诊断后的后续优化位置，不是新增原文事实，也未回填到本轮生成器输入。",
        "|用例与需求行号|已有异常|已有分类|建议检查位置及具体化|", "|---|---|---|---|"]
    advice = {
        "UCG-001-UC001": "ProductDisplayService / ProductCatalogService 查询返回处：区分空列表与服务故障，保留空列表及提示行为。",
        "UCG-002-UC002": "PaymentAdapter 支付交互取消分支：停止成功副作用并保持 WAIT_PAY；不等同于支付服务不可用。",
        "UCG-003-UC004": "RefundService → PaymentService 退款提交边：明确失败对象和退款操作，保存待处理退款单及异步重试。",
        "UCG-004-UC001": "MerchantProductService 创建前身份/资质校验：实例化资质失效及重新认证，不只检查权限类型。",
        "UCG-004-UC002": "MerchantProductService 图片接收/校验位置：分清格式与大小限制，拒绝对应图片；未知数值限制仍待确认。",
        "UCG-004-UC003": "MerchantProductService 库存价格输入校验：区分 sale_price 与库存范围，保留提示修正价格；不预设新数值边界。",
    }
    for s in derived_gaps:
        refs = "；".join(f"{r['document']}:{r['line_start']}-{r['line_end']}" for r in s["source_refs"])
        review.append("|" + "|".join([f"{s['use_case_id']} / {refs}", s["name"],
            "、".join(s["concern_keys"]), advice.get(s["use_case_id"], "依据原文核实具体约束与检查位置")]) + "|")
    review += ["", "## 挂载与指标的边界", "",
        f"{len(constraints)} 条来源约束中 {pending_mounts} 条没有精确对应 SSD 交换。已保存检查对象、原文步骤、"
        "现有实现责任方和待确认挂载建议；不以相邻交换猜测实际检查位置，也不虚构新组件。",
        f"接受关系中有 {len(metrics['classification_discrepancies'])} 条两端标签差异；分类指标只计两端共同归类的关系，"
        "因此总异常漏报为零不表示每类指标为零。全部差异保留在指标、报告和工作簿中。", "",
        "建议下一轮优先补局部业务检查与实现层交换的明确映射，再从原始文档独立生成；保持固定 C、严格行为判定及分项贡献。", "",
        "[逐条需求诊断](coverage_diagnostics.json) · [有来源的调用图](architecture_calls.svg) · [检查挂载清单](concern_placements.md)", ""]
    (output / "optimization_review.md").write_text("\n".join(review), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--baseline-dir", required=True)
    parser.add_argument("--output-dir", default=str(Path(__file__).parent / "online_shopping_demo"))
    args = parser.parse_args()
    snapshot(args.prepared_dir, args.run_dir, args.baseline_dir, args.output_dir)


if __name__ == "__main__":
    main()
