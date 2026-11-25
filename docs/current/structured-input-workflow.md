# 结构化输入工作流（自动生成）

本文件由 `tools/render_workflow_doc.py` 从 `src/scene_completion/workflow/ssd_stages.py`
生成，请勿手工编辑。改动阶段说明请改代码后运行：

```sh
python tools/render_workflow_doc.py
```

`make check` 会校验本文件与代码一致。触发条件与分支判定见
[SSD工作流与审核](ssd-case-workflow.md)，语义提示词见 `domain/ssd_contracts.py`。

## 触发条件

结构化输入分支在 `workflow/planning.py::build_pipeline()` 中判定：`workflow_mode`
为 `ssd` 时优先使用建档冻结的输入目录。`authoring_cases.discover()` 同时识别核心
`cases/*/main-success.json`、单件 `authoring-case.json` 和原始 `SysOperation.json`。
同用例优先已编制的核心输入，同优先级多份会在 prepare 报冲突。无结构化入口时继续文档抽取；
发现了用例但指定范围无匹配会报错。

## 单个用例的推进顺序

```
ssd-prepare → ssd-resolve → ssd-generate → ssd-compare
```

用例之间并行。每个用例完成比较后触发对应的共用服务合并节点。

## 阶段总表

| 阶段 | 页面标签 | 类型 | 默认命令模式的语义任务 | 依赖 |
|---|---|---|---|---|
| `ssd-prepare` | 建立 SSD 与三方结果 | 脚本（不调用模型） | — | （起点） |
| `ssd-resolve` | 参与者与操作判定、约束挂载与独立识别 | 模型调用 | ssd-participant-classify、ssd-operation-units、ssd-create-path-roles、ssd-entity-inference、ssd-evidence-classify | ssd-prepare |
| `ssd-generate` | 展开参考异常与业务场景 | 模型调用 | ssd-generate | ssd-resolve |
| `ssd-compare` | 三方比较与发布 | 模型调用＋脚本合并 | ssd-ground-align、ssd-semantic-compare | ssd-generate |
| `shared-services-merge` | 合并共用外部服务（脚本） | 脚本（不调用模型） | — | ssd-compare |

## 逐阶段说明

### `ssd-prepare` · 建立 SSD 与三方结果

- **类型**：脚本（不调用模型）
- **读取**：冻结的核心分件或 SysOperation 与配套材料；关注点注册表
- **产出**：用例 steps（发送方·接收方·操作·数据）；G 通道关注点与参考场景；初始发布版本
- **默认语义任务**：不调用模型
- **依赖**：无（用例起点）

从结构化输入确定性构建步骤与三方结果容器，挂载注册表规则与固定参考异常模板，生成 G 通道，并发布本用例的第一个版本。

### `ssd-resolve` · 参与者与操作判定、约束挂载与独立识别

- **类型**：模型调用
- **读取**：正向主成功事件流、功能树实体约束；E/GT 各自的原始记录
- **产出**：操作单元、CRUD、字段与实体约束挂载；E/GT 各自的来源分类与待定位部分
- **默认语义任务**：ssd-participant-classify、ssd-operation-units、ssd-create-path-roles、ssd-entity-inference、ssd-evidence-classify
- **其他输入配置的语义任务**：ssd-entity-classify、ssd-command-classify、ssd-bind、ssd-resolve
- **依赖**：ssd-prepare

先结合参与者声明和原文引文确认角色。默认命令模式接着判操作单元和 CRUD，再处理未能确定性解析的约束，由脚本建立 G 挂载。E、GT 分别按本方证据分类，在 compare 才对齐最终 G。旧输入按配置使用其他分类或绑定任务。

### `ssd-generate` · 展开参考异常与业务场景

- **类型**：模型调用
- **读取**：G 通道的固定模板场景；正向用例、步骤、对象、接口、实体
- **产出**：每个场景的业务分析；模型补充的适用场景
- **默认语义任务**：ssd-generate
- **依赖**：ssd-resolve

只针对 G 通道写业务化分析，可补充同一关注点下明确适用且不重复的场景。固定模板全部保留；模型看不到 E 与 GT，不从它们补写答案。

### `ssd-compare` · 三方比较与发布

- **类型**：模型调用＋脚本合并
- **读取**：最终 G 与 E、GT 各自的来源分类；候选对、历史判定与人工修订
- **产出**：逐 G 义务的确认覆盖及独立挂载；发布基线与有效修订
- **默认语义任务**：ssd-ground-align、ssd-semantic-compare
- **依赖**：ssd-generate

新版命令模式按最终G分别对齐E与GT，无法对应G的异常再按来源独立挂载。复用未变化的机器判定，再对候选对分批判定。当前口径记录 full/none，旧口径保留 partial。发布机器基线；若检测到人工修订，再独立复核一次。被任一 GT 确认的 G 计为已覆盖。

### `shared-services-merge` · 合并共用外部服务（脚本）

- **类型**：脚本（不调用模型）
- **读取**：全部用例的最新修订；实际外部调用的接收方
- **产出**：shared_service_results/；共用服务三方结果与项目指标
- **默认语义任务**：不调用模型
- **依赖**：ssd-compare

按实际外部请求的接收方识别服务身份，再按故障类型合并场景，保留每个调用成员的原记录与出处。服务身份无法确认时保留待定位，不按同名强合并。

> 合并阶段 `shared-services-merge` 依赖对应的用例比较节点。

## 阶段来源

- 阶段定义与顺序：`src/scene_completion/workflow/ssd_stages.py`
- 执行装配见 `src/scene_completion/workflow/ssd/pipeline.py`
- 字段映射、命令、检查点与报告见[从同事材料到离线报告](../architecture/ssd-walkthrough.md)
- 模型提示词与输出 Schema：`src/scene_completion/domain/ssd_contracts.py`
- 缓存用的语义版本：`src/scene_completion/workflow/task_semantics.json`
