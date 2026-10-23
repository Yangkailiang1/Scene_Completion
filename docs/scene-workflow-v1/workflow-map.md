# 方法与程序流程对照

| 顺序 | 方法 | 程序入口/输出 | 隔离边界 |
| --- | --- | --- | --- |
| 1 | RR/SR输入、正向材料 | source_documents.current_projection / normal_projection | 已有异常不进正向通道；原文不修改 |
| 2 | 共享组成/API两表 | workflow.build_pipeline共享任务 | 无测试和历史产物 |
| 3 | 每用例RR/SR基础SSD | rr-ssd / sr-ssd | 先抽取，不依赖能力表 |
| 4 | 对象能力汇总 | 内部test-operation-project → capability_union | 测试仅操作投影，不新增交互 |
| 5 | 交互补全 | interaction-align → enrich | 有据统一名称、组成位置、能力、接口；RR/SR对应未知待确认 |
| 6 | 关注点匹配 | concern-match → enriched-view | 预定义57项，双方及数据；本次操作决定适用性 |
| 7 | 异常生成G | exception-generate、data_exceptions、query_exceptions | 不看E/GT；请求/返回分离、字段/约束原子化，未知待确认 |
| 8 | 已有异常E | existing-extract | 独立当前文档已有分支 |
| 9 | 缺失比较M | gap-compare直接输出decisions+missing | 仅G/E，full语义一一对应；partial不覆盖 |
| 10 | 缺失报告 | missing-report → JSON / Markdown | 独立于GT失败，汇总交互、关注点、异常步骤、已有覆盖和缺失原因 |
| 11 | 测试异常GT与评测 | test-ground-truth、semantic-compare、exception-evaluation | 测试描述/框架/正常约束，无G反馈；明示与推导单列 |
| 12 | 人工抽取GT计分 | extraction-evaluation / score-extraction | 六项可选GT，Acc；不混用测试异常GT |
| 13 | 推荐 | gap-recommend | 未启用，无Q、历史检索、排序或随机回退 |

实际入口集中在`cli.py`四条命令。流程实现为固定依赖DAG，每用例case字段独立；共享提取失败影响所有需要它的用例，但某用例SSD/GT失败不阻塞其他用例。

当前组成直接读RR/SR；不新增架构图或依赖图抽取任务。本轮保持现有模型传输和持久化执行方式，未迁移Deep Agents，也没有真实模型稳定性对照结论。
