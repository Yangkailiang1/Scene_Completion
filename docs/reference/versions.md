# 版本与兼容边界

版本描述不同对象，不能按数字大小判断是否应该删除文件或重算项目。

| 标识 | 描述的对象 | 当前处理 |
|---|---|---|
| `scene-workflow-v5` | 项目与任务协议 | 当前运行协议；v2/v3/v4文档与Schema仅作历史记录 |
| `ssd-case-v1` | 共同用例、步骤及三方结果bundle | 默认SSD主流程和新独立build命令输出 |
| `scene-case-analysis-v1` | 原独立分析导入工件 | 仍支持校验/导入；保留提交的G/E/GT与判定，转换到共同结果 |
| `ssd-review-v1` | SSD差异HTML及JSON反馈 | 新结果页导出/预览/选择应用；浏览器即可离线审核 |
| `business-review-v1` | 原业务问题/推荐审核包及反馈 | Windows审核交接能力；与SSD HTML不是同一格式或入口 |
| `two-level-concern-scenario-…`、任务语义标识 | 具体规则、定位或任务语义 | 由现有语义与校验决定复用，不因移动代码而整体升级 |
| v9/v10/v11文档标题 | 当时规则演进及验收里程碑 | 归入历史记录；不是源码目录、包版本或当前成绩 |
| Python/前端包版本 | 软件包发布元数据 | 与运行协议分别维护，不要求数字一致 |
| Git提交、发布标签、VERSION.json | 可交付程序来源 | 用于核对发行包；不能替代项目内规则和来源身份 |

样例文件曾使用的`-v2`、`-v3`后缀也不是协议版本：这些样例内部仍是`scene-case-analysis-v1`。历史样例和验收数字按其原运行条件理解。

## 两种离线审核

SSD HTML保存审核快照及原始文档，业务修改后下载新HTML或JSON，研发预览差异与版本冲突后选择应用。它不需要Python、本地服务或模型账号。

原Windows审核交接包包含程序与项目审核快照，在review-only服务中回答业务问题、审核推荐，再交回JSON反馈。对应契约和权限仍按原交接服务执行，不能把该包的能力描述用于SSD HTML，也不能把两种反馈直接混用。

## 固定发布路径

[SSD结果契约](../ssd-result-contract.md)保留原路径，因为现有Skill引用它。[v5 Schema](../scene-workflow-v5/schemas/)保留发布目录，字段定义以`domain/schema_definitions.py`及实际校验为准。历史Schema位于`docs/history/scene-workflow-v2|v3|v4/schemas`，不作为当前注册表。

现行使用入口见[文档导航](../README.md)，当前规则边界见[关注点与计分](../current/concern-rules.md)。目录迁移映射集中在[唯一迁移清单](../architecture/module-map.json)。
