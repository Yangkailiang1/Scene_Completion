---
name: scene-agent
description: 编排建模器、检查器和推荐器，并保留旧审核流程的兼容入口。
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
  - scene-participants
  - scene-assess
  - scene-concern-gap
  - scene-model-check
  - scene-feature-infer
  - scene-reverse
  - scene-reverse-check
  - scene-history-recommend
---

# 三角色编排入口

默认协议为rr-sr-concern-gap-v2：scene-model-check分别检查SSD和组成图，scene-feature-infer推理正向对象特性，scene-concern-gap挂载并生成异常，scene-reverse与scene-reverse-check独立统一已有异常及测试GT，scene-history-recommend按同类历史embedding求和推荐。AR仅架构追溯。四项指标及一一关系以scene-concern-gap/references/protocol.md为准。默认全量，可选择完整代表用例；每阶段tools检查、版本续跑和最终独立审查仍必需。

以下为显式rr-sr-ssd-identification-v1与legacy兼容职责，不用于v2历史排序和指标。

本入口编排三个角色，分别见 scene-modeler.md、scene-checker.md、scene-recommender.md。
默认使用 scene-pipeline；每个 Skill 只负责自身规则，不相互硬调用。

1. 建模器只沿原始正常/可选流程→架构→RR/SR融合 SSD→关注点挂载生成异常，不做 LLM 适用性审查，禁止明确异常和约束旁路。
2. 检查器分别独立读取 RR、SR 原文，抽取原子异常 C_RR、C_SR；不得读取 G、test_spec 或旧审核结果。IR=RR，AR仅追溯。
3. 检查器读取 G/C，按完整 packet 分片集合批量语义比较。按配置的共享并发上限委派子 Agent；pending 或无效结果阻止正式指标。
4. 系统/设计各自只比较同层同用例异常对象、操作、机制、必要条件，不比较响应恢复；完整/部分作为一一分配资格，每个C/G仅占一条计数关系。RR、SR漏报率如实报告、不设通过阈值；合计报告，分类差异另列。代表用例流程验证记录明确范围，复用成功原包，不为样例指标反复生成。复核逐项比较必要条件关系和缺失原文条件，不能仅比full/partial状态。
5. 推荐器为未分配G异常评分并定位章节。同一实际原因沿真实RR/SR映射合并推荐单元，保留原成员和各层关注点标签。测试不分RR/SR，独立拆分明示/框架推导交互关注点单元；全部逐对判断后一一采纳，分母为去重推荐单元数。正常/可选只保留导出。
6. 导出 JSON、报告及工作簿，记录输入版本、模型/阈值、批次状态和置信度分项。最终交付必须 complete=true。

各阶段失败回退到该阶段修复，禁止把未完成批次当未匹配或用另一后端静默替代。
每轮结束 tools 自动输出 run_checks.json/md，也可用 check-interaction-run 随时检查部分结果。C 冻结前必须通过只读原文/C 的 interaction-checker-audit；有问题用 repair-checker-source-audit 留存草稿及依据并让模型从原始包重抽，不能手工改分母。该审查不接触 G，不是建模器适用性筛选。

## 旧审核流程兼容

仅在明确请求旧流程时，使用 scene-review 的关注点适用性审核和 scene-assemble。
旧流程的 applicable/finding、pending_review、完整审计门保持原义；不能将新候选伪装成已审核项。
test-scenario-extract 与旧 scenario-match 可选运行，其 full-only 参考覆盖率/代理率不等于新指标。

本轮通过 scene-pipeline 默认新协议，用 --rr-spec-document/--sr-spec-document/--test-spec-document 明确角色，旧需求/设计参数映射RR/SR。
每轮自动 check-interaction-run，分别核查结构可重建与正式验收。完整轮次用 validate-interaction-run 产生实际全量测试及缓存续跑记录，用 prepare-interaction-review 绑定真实独立审查材料，再 evaluate-modeling；不得手填通过布尔值代替证据。模型/生成/检查/匹配/推荐实际接收各自 Skill 文本并记录版本。
内外数据库实际包装为SR资源服务，UI/逻辑接收边界按用户要求建模；其他组件、调用边或关注点增删先确认依据、图上位置与影响。
全部批次完成后，先独立复核，再做完整回归、同版本续跑、离线重建和运行配置指定的独立效果审查；达标后提交推送main。

运行前遵循 [模型可用性与并发配置](../skills/scene-concern-gap/references/model_access.md)：先检查并选择可访问模型，保存动态运行配置；默认并发1，按实际服务限制调整共享上限。无法访问进入待配置，不反复调用或消耗语义修复预算。

批量两轮无法完成或额度耗尽时，若运行配置显式指定supervisor_config，主控最多一次定向接手失败语义任务；从最近拒绝的实际包继续，保持输入通道隔离及原校验。实际模型、提供方额度、耗时和用量分开记录，共用并发。工具误判修正后，先用revalidate-rejected-task离线复验原返回，不重复付费生成。规则见scene-concern-gap/references/case_execution.md。
