---
name: scenario-match
description: 依据需求行为证据匹配参考测试场景与生成场景，并计算覆盖率及自动采纳代理率。
title: Scenario Match
version: 1.0.0
---

# Scenario Match

Agent 对每个参考测试场景与生成场景判断 `full`、`partial` 或 `unmatched`，写入可解释证据；工具校验所有 ID 和状态并计算指标。仅完整匹配计入覆盖率；部分匹配单独报告。自动采纳代理率表示至少匹配一个参考测试场景的生成场景比例，不是人工审核采纳率。允许一对多/多对一关系，但禁止重复链接和未知 ID。

输入：`reference_test_scenarios.json`、生成场景目录的 `test_scenarios.json`、Agent 的匹配 JSON。运行 `score-scenario-matches` 输出带分子、分母、比例和未匹配清单的报告。字段见 `references/matching.md`。本 Skill 不调用其他 Skill。
