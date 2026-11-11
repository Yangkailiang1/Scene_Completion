# 单用例结果契约

`case_analysis.py schema` 输出唯一权威的 `scene-case-analysis-v1` 结构。将 `model.json` 的 `case`、`ssd`、`api_map`、`api_parameters`、`registry` 和 `recommendation_settings` 原样放入草稿。合并三个阶段的 `sources`，按 source ID 去重，保留文件名、原文行号和引用原文。使用已确认的项目规则快照时，提供对应的注册表、推荐设置及历史。默认历史为 `[]`，范围为 `SR`。

- `channels.G/E/GT` 各含 `status`、`source_refs`、`concerns`、`scenarios` 和 `pending`。已确认材料为 `ready`，明确异常尚未完成定位或整理时为 `partial`，缺少材料为 `missing`。原始来源中明确标为待确认的分支列入排除说明。空且已核实的来源仍提供来源引用。G 引用正向来源；E 与 GT 的每个记录至少含一处各自通道的证据，可另引用正向事实。
- 关注点沿用当前注册表 ID、实际交互 ID 和 `sender/receiver/operation/data` 目标。数据项提供 `data_location` 与完整字段路径，操作项以 `operation_index` 区分。同一四元组对象的一个关注点可关联多个独立场景。场景沿用该对象、字段及定位，提供独立触发条件、证据和 `steps`。只有 E 的明示原分支可以申请宽泛覆盖。全局依赖和幂等项留在待补说明。
- 只有清楚声明的约束进入确定场景。区分必填缺失、类型、格式、枚举、上下界和长度。没有具体时间、错误码或后续行为时保留未知。请求与响应各使用自己的字段，未定位字段不改挂到相邻请求。使用 `model.json.interactions` 中实际补全的数据位置、方向和字段名。
- 可推荐的 G 场景选择冻结模式库中启用且适用的 `pattern_id`，并填写有证据的 `confidence`。明示可判定规则使用分值 1，明确声明但值域、范围或落地仍有待验证时使用分值不超过 0.85 并记录依据。把可核对的功能、技术、实际操作、方向或边界写入 `scenario_context`。无适用模式时保留场景及原因。
- `decisions` 包含 `G_E`（G 在左）、`GT_G` 与 `GT_E`（GT 在左）。每个判定使用两端的场景 ID、`full/partial/unmatched` 和理由。匹配必须落在同一实际交互及同一四元组关注点，且核对相同失败条件。只比较所选用例，记录不确定项，不补造对应。
- 将待补和排除原因写进 `pending`。工具生成推荐项 ID 及冻结范围内的关注点和场景指标。导入时服务端重算并核对这两项。导入版在用例结果页显示四元组、异常场景、指标及推荐。来源和结果随版本冻结。
