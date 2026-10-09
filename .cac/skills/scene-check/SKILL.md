---
name: scene-check
description: 独立从需求与设计用例抽取已有场景，批量语义匹配并统计关注点覆盖。
---

# 场景检查

先只读原始用例章节及分类注册表，抽取完整已有集合 C；再读生成集合 G 比较。
抽取保留所有来源、基本/备选/异常行为；不得用 test_spec 或生成候选代替原文。
异常可多标签，主成功/成功替代路径不强行归类；不能分类的异常单列。

默认 Agent packet 模式，可开最多三个子 Agent。按 packet 合同返回全部已检查 ID；
用 run-agent-batches 可将子 Agent 分工的 packet 交给 ECNU 语义模型处理。
接受的匹配须再经逐对语义复核，逐字引用双方触发条件并保存完整决策；直接填写的提案也须通过 worker 复核。
共享 CLI 负责 ID、批次哈希、完整性、引用和指标校验，不做规则语义匹配。
另一后端是 embedding，阈值必须在输出中记录为未校准参数。

详细操作与指标协议见 references/three_roles.md。本 Skill 不调用其他 Skill。
