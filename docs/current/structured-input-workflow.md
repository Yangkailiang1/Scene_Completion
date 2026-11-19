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
为 `ssd`（默认），且 `input_directory()` 返回目录，且 `build_structured()` 在该目录下
至少找到一个 `SysOperation.json`。三者任一不满足，不会报错，而是继续走文档抽取分支。

## 单个用例的推进顺序

```
ssd-prepare → ssd-resolve → ssd-generate → ssd-compare
```

用例之间并行，互不阻塞。全部用例完成后，每个用例再触发一次合并阶段。

## 阶段总表

| 阶段 | 页面标签 | 类型 | 对应语义任务 | 依赖 |
|---|---|---|---|---|
| `ssd-prepare` | 建立 SSD 与三方结果 | 脚本（不调用模型） | — | （起点） |
| `ssd-resolve` | 操作判定、约束挂载与独立识别 | 模型调用 | ssd-operation-units、ssd-entity-inference、ssd-entity-classify、ssd-command-classify、ssd-bind、ssd-resolve | ssd-prepare |
| `ssd-generate` | 展开参考异常与业务场景 | 模型调用 | ssd-generate | ssd-resolve |
| `ssd-compare` | 三方比较与发布 | 模型调用＋脚本合并 | ssd-semantic-compare | ssd-generate |
| `shared-services-merge` | 合并共用外部服务（脚本） | 脚本（不调用模型） | — | ssd-compare |

## 逐阶段说明

### `ssd-prepare` · 建立 SSD 与三方结果

- **类型**：脚本（不调用模型）
- **读取**：SysOperation.json；功能树；行为目录；结构化输入快照
- **产出**：用例 steps（发送方·数据·接收方）；G 通道关注点与参考场景；初始发布版本
- **语义任务**：不调用模型
- **依赖**：无（用例起点）

从结构化输入确定性构建步骤与三方结果容器，挂载注册表规则与固定参考异常模板，生成 G 通道，并发布本用例的第一个版本。

### `ssd-resolve` · 操作判定、约束挂载与独立识别

- **类型**：模型调用
- **读取**：正向主成功事件流、功能树实体约束；E/GT 各自的原始记录
- **产出**：CRUD 与实体约束锚点；E/GT 的关注点与具体场景；待确认记录
- **语义任务**：ssd-operation-units、ssd-entity-inference、ssd-entity-classify、ssd-command-classify、ssd-bind、ssd-resolve
- **依赖**：ssd-prepare

实体模式先判定主流程的实际CRUD并处理未能脚本解析的属性约束，再由脚本建立G挂载。E和GT分别根据自己的来源分类，脚本只对齐确认的异常。兼容输入沿用ssd-bind与ssd-resolve。

### `ssd-generate` · 展开参考异常与业务场景

- **类型**：模型调用
- **读取**：G 通道的固定模板场景；正向用例、步骤、对象、接口、实体
- **产出**：每个场景的业务分析；模型补充的适用场景
- **语义任务**：ssd-generate
- **依赖**：ssd-resolve

只针对 G 通道写业务化分析，可补充同一关注点下明确适用且不重复的场景。固定模板全部保留；模型看不到 E 与 GT，不从它们补写答案。

### `ssd-compare` · 三方比较与发布

- **类型**：模型调用＋脚本合并
- **读取**：G/E/GT 全通道场景与关注点；历史机器判定
- **产出**：full/partial/none 判定；发布版本与人工复核结果
- **语义任务**：ssd-semantic-compare
- **依赖**：ssd-generate

复用未变化的机器判定，再对候选对分批判定 full/partial/none，发布机器基线；若检测到人工修订，再独立复核一次。被任一 GT 确认的 G 计为已覆盖。

### `shared-services-merge` · 合并共用外部服务（脚本）

- **类型**：脚本（不调用模型）
- **读取**：全部用例的最新修订；实际外部调用的接收方
- **产出**：shared_service_results/；共用服务三方结果与项目指标
- **语义任务**：不调用模型
- **依赖**：ssd-compare

按实际外部请求的接收方识别服务身份，再按故障类型合并场景，保留每个调用成员的原记录与出处。服务身份无法确认时保留待定位，不按同名强合并。

> 合并阶段 `shared-services-merge` 在上述用例序列全部完成后按用例触发。

## 阶段来源

- 阶段定义与顺序：`src/scene_completion/workflow/ssd_stages.py`
- 执行装配：`src/scene_completion/workflow/ssd_pipeline.py`
- 模型提示词与输出 Schema：`src/scene_completion/domain/ssd_contracts.py`
- 缓存用的语义版本：`src/scene_completion/workflow/task_semantics.json`
