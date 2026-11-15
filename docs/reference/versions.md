# 版本与兼容边界

版本描述不同对象，不能按数字大小判断是否应该删除文件或重算项目。

| 标识 | 描述的对象 | 当前处理 |
|---|---|---|
| `scene-workflow-v5` | 项目与任务协议 | 当前运行协议；v2/v3/v4文档与Schema仅作历史记录 |
| `ssd-case-v1` | 共同用例、步骤及三方结果bundle | 默认SSD交互级主流程和新独立build命令输出 |
| `project-scope-v1` | 业务链路或项目架构的依赖/外部服务锚点及三方结果bundle | 三范围主流程的项目级结果；按范围独立修订和计分 |
| `scene-case-analysis-v1` | 原独立分析导入工件 | 仍支持校验/导入；保留提交的G/E/GT与判定，转换到共同结果 |
| `business-adoption-v2` | 三范围业务采纳HTML与反馈 | 当前导出及回导，只允许采纳与意见，按冻结G补GT |
| `coverage-any-confirmed-v2` | 关注点/场景覆盖口径 | full、partial均覆盖；计不同G与GT，允许多对多，保留旧成绩 |
| `ssd-review-v1` | 既有SSD内容修订HTML/JSON | 兼容模块保留；当前业务采纳HTTP入口只接受v2 |
| `project-review-v1` | 既有项目内容修订HTML/JSON | 兼容模块保留；当前采纳入口不用于修改E/G |
| `business-review-v1` | 原业务问题/推荐审核包及反馈 | Windows审核交接能力；与SSD HTML不是同一格式或入口 |
| `two-level-concern-scenario-…`、任务语义标识 | 具体规则、定位或任务语义 | 由现有语义与校验决定复用，不因移动代码而整体升级 |
| v9/v10/v11文档标题 | 当时规则演进及验收里程碑 | 归入历史记录；不是源码目录、包版本或当前成绩 |
| Python/前端包版本 | 软件包发布元数据 | 与运行协议分别维护，不要求数字一致 |
| Git提交、发布标签、VERSION.json | 可交付程序来源 | 用于核对发行包；不能替代项目内规则和来源身份 |

样例文件曾使用的`-v2`、`-v3`后缀也不是协议版本：这些样例内部仍是`scene-case-analysis-v1`。历史样例和验收数字按其原运行条件理解。

## 两种离线审核

当前单文件 HTML 使用 `business-adoption-v2`，一次包含三层差异审核与完整只读参考。业务只修改采纳决定和意见，保存 HTML/JSON 后由研发统一预览和应用；默认选中无冲突项，不自动提交。空审核层仍可浏览完整参考。它不需要 Python、本地服务或模型账号，旧 v2 文件可继续回导。

原Windows审核交接包包含程序与项目审核快照，在review-only服务中回答业务问题、审核推荐，再交回JSON反馈。对应契约和权限仍按原交接服务执行，不能把该包的能力描述用于SSD HTML，也不能把两种反馈直接混用。

## 固定发布路径

[SSD结果契约](../ssd-result-contract.md)保留原路径，因为现有Skill引用它。[v5 Schema](../scene-workflow-v5/schemas/)保留发布目录，字段定义以`domain/schema_definitions.py`及实际校验为准。历史Schema位于`docs/history/scene-workflow-v2|v3|v4/schemas`，不作为当前注册表。

现行使用入口见[文档导航](../README.md)，当前规则边界见[关注点与计分](../current/concern-rules.md)。目录迁移映射集中在[唯一迁移清单](../architecture/module-map.json)。
