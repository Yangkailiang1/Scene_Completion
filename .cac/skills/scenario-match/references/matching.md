# 匹配关系与指标格式

Agent 提交 `{ "matches": [...] }`，每条关系包含 `test_scenario_id`、`generated_scenario_id`、`match_status`（`full`/`partial`/`unmatched`）和非空 `evidence`。多对多允许；完全重复关系拒绝。所有 ID 必须存在。

- 测试场景覆盖率 = 至少有一条 `full` 关系的不同参考测试场景数 / 参考测试场景总数。
- 自动采纳代理率 = 至少被一个 `full` 测试场景匹配的不同生成场景数 / 生成场景总数。
- partial 单独报告，不计入上述分子。两个分母为 0 时比例为 `null`。

第二项只是测试匹配的自动代理指标，不表示人工接受或质量审批。
