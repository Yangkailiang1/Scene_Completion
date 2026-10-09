---
name: scene-agent
description: 编排生成器、检查器和推荐器，并保留旧审核流程的兼容入口。
skills:
  - scene-extract
  - scene-ssd
  - dependency-graph
  - scene-review
  - scene-assemble
  - test-scenario-extract
  - scenario-match
  - scene-generate
  - scene-check
  - scene-recommend
---

# 三角色编排入口

本入口编排三个角色，分别见 scene-generator.md、scene-checker.md、scene-recommender.md。
默认使用 scene-pipeline；每个 Skill 只负责自身规则，不相互硬调用。

1. 生成器建立规范模型，校验并生成 RR/SR/AR/fused SSD，保留现有依赖图能力；按关注点路由生成全部候选，不做 LLM 适用性审查。
2. 检查器独立读原始需求/设计用例，生成已有集合 C；抽取阶段不得读取 G、test_spec 或旧审核结果。
3. 检查器读取 G/C，按完整 packet 分片集合批量语义比较。可委派最多三个子 Agent；pending 或无效结果阻止正式指标。
4. 工具按完整和部分匹配计算总指标、具体关注点和大类指标。零分母为 null；各分类独立去重。
5. 推荐器为未匹配 G 场景评分并定位补充章节，保留全量候选。rerank 可选，默认关闭，仅增强推荐。
6. 导出 JSON、报告及工作簿，记录输入版本、模型/阈值、批次状态和置信度分项。最终交付必须 complete=true。

各阶段失败回退到该阶段修复，禁止把未完成批次当未匹配或用另一后端静默替代。

## 旧审核流程兼容

仅在明确请求旧流程时，使用 scene-review 的关注点适用性审核和 scene-assemble。
旧流程的 applicable/finding、pending_review、完整审计门保持原义；不能将新候选伪装成已审核项。
test-scenario-extract 与旧 scenario-match 可选运行，其 full-only 参考覆盖率/代理率不等于新指标。
