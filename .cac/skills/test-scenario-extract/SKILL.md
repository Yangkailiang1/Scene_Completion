---
name: test-scenario-extract
description: 将 test_spec.md 中有来源的测试场景解析为稳定 ID 的结构化参考测试集。
title: Test Scenario Extract
version: 1.0.0
---

# Test Scenario Extract

仅负责读取 `test_spec.md` 并将每条测试场景解析到 `reference_test_scenarios.json`；不得修改生成侧 `test_scenarios.json`。保持测试场景编号、用例/需求/API 关联、场景类型、前置条件、触发条件、目标、预期结果和来源定位。缺字段或重复 ID 时显式失败，不推断缺失测试行为。

使用 `python .cac/tools/scene_completion.py extract-test-scenarios --input test_spec.md --output reference_test_scenarios.json`，再运行 `validate-test-scenarios`。格式见 `references/format.md`。本 Skill 不调用其他 Skill。
