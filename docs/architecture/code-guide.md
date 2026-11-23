# 架构与代码导览

用一个合成用例跟读或运行请从[同事材料到离线报告](ssd-walkthrough.md)开始。本页供查阅跨模块依赖。

默认运行入口是交互三方比较流程，业务链路退出当前分析。外部服务在交互中生成后归并，历史链路与架构只读。`compat`保留仍在使用的详细流程、独立分析格式和保存报告能力，不代表恢复v2/v3/v4协议。版本含义见[版本与兼容边界](../reference/versions.md)，唯一文件迁移清单为[module-map.json](module-map.json)。

## 主链与依赖方向

```mermaid
flowchart TD
    Web[frontend / HTTP API] --> App[application 应用服务]
    CLI[CLI] --> App
    App --> Plan[workflow/ssd 阶段编排与实现]
    Plan --> Input[inputs 可复用的结构化解析与文档转换]
    Plan --> Runtime[workflow/runtime 调度适配]
    Runtime --> Core[workflow_core 通用调度]
    Runtime --> Models[models 语义请求与用量]
    Plan --> Domain[domain/ssd 校验、匹配、指标]
    App --> Revision[application/ssd_revision_service 修订与发布]
    Revision --> Domain
    Revision --> Repository[infrastructure/ssd_repository 持久化]
    Plan --> Merge[application/shared_service_service 共用服务发布与修订]
    Merge --> Aggregate[domain/shared_services 确定性归并]
    Merge --> ProjectDomain[domain/project_scopes 匹配与指标复用]
    Merge --> Store[shared_service_results 独立仓储]
    Historical[旧 project_results] --> Merge
    Web --> Report[review/offline/business_report_export 离线报告]
    Report --> Revision
    Legacy[历史审核包预览及应用] --> Revision
```

`application/input_service`组织输入扫描、接纳与监控；`domain/task_extensions`保存任务Schema扩展注册，避免领域层反向依赖分析层；`infrastructure/identity`提供纯指纹计算。`analysis/scenarios/eligibility`协调输入解析和计分资格，纯场景类型规则仍留在`domain/scenario_types.py`。

HTTP与CLI处理参数及响应，应用服务组织用例操作；领域代码决定有效定位、匹配和指标，仓储负责文件、锁与不可变版本。页面与路由不重复实现计分；输入转换不承担报告展示，持久化不负责调用模型。

`serve.py → api/application.create_app → application/project_service.Workbench`装配本地服务。`scene.py → cli/main`使用相同公开能力。`application/execution.Execution`组织执行会话，`workflow/planning.build_pipeline`选择结构化输入或文档抽取路径。

`workflow/ssd/pipeline.py`选择用例、注册依赖并写入流程进度。它复用同一套 SSD 阶段处理结构化输入和 RR／SR 文档抽取结果。阶段定义与语义任务集中在 `workflow/ssd_stages.py`，[结构化输入工作流](../current/structured-input-workflow.md)由它生成。

## 按顺序阅读 SSD

[端到端代码路线](ssd-walkthrough.md)依次列出原件与分件的字段、五个节点的入口和校验、修订与报告，以及合成用例的离线验收。阶段名称、依赖、语义任务以[自动生成的阶段表](../current/structured-input-workflow.md)为准。

`workflow/ssd/` 保存阶段实现。`workflow/ssd_pipeline.py` 和 `analysis/ssd/` 保留旧导入名称，查原模块对应的新文件可用 [module-map.json](module-map.json)。

## 目录职责

| 目录 | 职责与边界 |
|---|---|
| `application/` | 项目、运行配置、执行控制和SSD修订用例；协调业务服务 |
| `domain/`、`domain/ssd/` | 协议、Schema、注册表及SSD校验、匹配、指标；不负责项目文件写入 |
| `workflow/` | `ssd/` 为正式 SSD 各阶段的实现，`runtime/` 为调度适配，`recovery/` 为有限恢复 |
| `workflow_core/` | 通用DAG依赖、并发、暂停、检查点；不放SSD业务规则 |
| `inputs/` | `structured/`结构化材料，`documents/`文档转换，`provenance/`来源索引，及导入采用 |
| `analysis/` | 通用关注点、场景、匹配、评估和交互分析，`ssd/` 保留原导入入口 |
| `models/` | 模型路由、传输、流式、限流、上下文和用量；不改变业务结果版本 |
| `review/` | `offline/` SSD HTML，`handoff/`原业务包，`decisions/`人工决定，`truth/`审核真值 |
| `compat/` | 显式保留的详细流程、独立旧格式与保存报告，见下节 |
| `manager/` | 管理Agent、质量诊断与隔离补丁，仍遵守应用和领域边界 |
| `api/`、`cli/` | HTTP与命令装配；公开URL和参数不因目录迁移改变 |
| `infrastructure/` | 项目存储、事件、进程、资源定位、SSD仓储及项目范围仓储 |

`domain/concern_templates.py` 维护固定参考异常。`workflow/ssd/generate/scenarios.py` 负责 `ssd-generate` 的模型分析与补充校验。业务链路与项目架构结果继续通过历史投影查看。

## 三种兼容职责

| 目录 | 实际用途 | 与SSD主流程的关系 |
|---|---|---|
| `compat/detailed/` | 既有细粒度节点编排及历史mock契约 | 显式兼容执行路径，不作为新主流程的默认入口 |
| `compat/standalone/` | `scene-case-analysis-v1`的准备、校验、导入和既有工件处理 | 保留原G/E/GT和匹配；导入后可发布到共同SSD结果服务 |
| `compat/saved/` | 读取原先保存的报告、图表和指标 | 展示历史事实，不以目录整理为由重算报告 |

这些职责分别维护，不按v9/v10/v11复制源码。独立分析新命令`build`产生`ssd-case-v1`；`schema`、`prepare`、`finalize`保留原独立格式，见[独立分析与保存结果](../current/standalone-and-saved-results.md)。

## 前端

`frontend/src/app`装配项目、工作区及全局状态；`features`按功能拥有页面、API、类型和测试，`shared`只保留跨功能请求、类型与工具，`components/ui`保留基础组件。`features/results/project/`承载业务链路与项目架构的三方对照、依赖表、依赖图和分层指标。

`features/results/ResultsView.tsx`只负责结果入口。`ssd/`包含三方编辑、步骤、修订、来源弹窗、离线回导和局部API/types；`saved/`保留历史及独立导入结果、范围和指标；`shared/`保存被结果页、输入页、节点页或审核页共同使用的产物/对照组件。Markdown阅读器继续由`features/sources`共享。

结果页先读取`ssd-results`，存在共同结果时使用SSD页，否则保留原保存结果页。切换模块不修改请求URL、历史ID、localStorage键、Effect触发或未保存草稿保护。

## 代码、产物与运行数据

`frontend/src`是源码，`web/`是成套构建的网页，`dist/`是本地打包产物。`deployment/windows/`是发布模板，`deployment/experiments/`是历史本机实验脚本，不是通用启动入口。

`.workbench/`、`runs/`、原始文档、账户、额度账本、审核与报告记录不随代码迁移。保存的source ID、任务ID、输入/产物相对路径及公开HTTP/CLI契约保持不变。统一资源位置由`infrastructure/paths.py`解析；开发与发布见[开发约定](development.md)。
