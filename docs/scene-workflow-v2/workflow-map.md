# 工作流与并行关系

共享层：`rr-use-cases`、`sr-use-cases`、`components`、`api-map`、`api-parameters`可并行。`use-case-align`依赖两层用例目录；用例对应明确前不启动融合SSD。

每个confirmed用例组独立执行：

| 任务 | 必须等待 | 可并行与边界 |
|---|---|---|
| fused-ssd | 用例对应、系统组成 | 不读取已有异常；RR/SR正向章节联合输入 |
| rr-ssd / sr-ssd | fused-ssd | 两个投影视图，无额外模型调用 |
| test-operation-project | 本组测试材料 | 仅对象与操作，不含异常或响应 |
| object-operations | 组成、RR视图、测试操作投影 | 能力并集不改变实际SSD操作 |
| interaction-align | fused-ssd及两层视图 | 投影已建步骤对应，不重新猜测 |
| interaction-enrich | 两层视图、组成、对象操作、API两表、步骤对应 | 明确调用类别及内外位置 |
| concern-match / enriched-view | 富化交互和当前注册表 | 按人类/Service调用分配关注点 |
| exception-generate | 正向图表、适用关注点 | 不读取E、GT或比较结果 |
| existing-extract | 对应组的原文已有分支 | 与正向建模独立并行 |
| gap-compare | G与E | 完整语义一一覆盖，直接输出M |
| missing-report | G、E、M及交互关注点 | GT失败不阻止报告 |
| test-ground-truth / exception-evaluation | 独立测试通道及正向约束 / 所需集合 | 明示与框架推导分别报告 |

不同用例组可并行，共享并发上限。待确认用例、失败任务和业务驳回可见，不冒充完成。手动模式审核后继续；自动模式运行后保留审核版本。推荐器恒为未启用。

三角色是职责组织：建模器执行正向模型与G；检查器执行E/GT/比较；推荐器保留停用状态。每个实际语义任务使用独立Deep Agent和虚拟文件系统，DAG保证调度顺序及输入范围。
