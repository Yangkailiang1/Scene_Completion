# 结构护栏

本页说明当前代码结构的已知债务、自动检查的边界，以及什么改动算结构变更、什么算语义变更。触发这次治理的原因、诊断数据见
[架构与代码导览](code-guide.md) 与 `tools/check_architecture.py` 的注释。

## 两条自动检查

| 检查 | 命令 | 失败含义 |
|---|---|---|
| 分层方向 | `make arch` | 出现未登记的反向依赖 |
| 流程文档一致 | `make docs` | 改了 `ssd_stages.py` 却没重新生成文档 |

两者都在 `make check` 与 CI 中运行。

## 分层方向

包的依赖方向写在 `tools/check_architecture.py` 的 `ALLOWED`。要点：

- `domain` 是最内层，不得依赖同层的其他包。
- `infrastructure` 只允许依赖 `domain` 与 `workflow_core`。
- `compat` 只能被上层单向调用，不得反向依赖主链。

当前存在 **6 条已登记的历史反向依赖**，集中在两处：

1. `infrastructure/worker_runtime.py` 启动与停止 worker 时需要上层服务（3 条）。
2. `infrastructure/execution_graph.py` 与 `execution_progress.py` 作为只读视图，聚合了上层数据（3 条）。

另有一条例外：9 个 `domain` 模块共用 `infrastructure/identity.py` 的纯函数指纹助手。正确做法是把它移到 `domain`，但那会改动发布缓存身份所用的导入路径，所以集中登记为一条豁免，而不是散落九条。

**登记不等于批准。** 新增反向依赖必须在 `KNOWN_REVERSE_EDGES` 写下原因；能移动依赖就应该移动。

## 结构化输入工作流的可读性契约

阶段定义、顺序、读写内容、对应的语义任务集中写在
`src/scene_completion/workflow/ssd_stages.py`。页面标签从那里取，
[结构化输入工作流](../current/structured-input-workflow.md) 也由它生成。

`tests/unit/test_ssd_stages.py` 锁死以下事实：

- 五个阶段恰好是 `ssd-prepare → ssd-resolve → ssd-generate → ssd-compare` 加合并阶段；
- 每个阶段都声明类型、依赖、读取、产出与说明；
- 声明的语义任务必须存在于 `workflow/task_semantics.json`；
- 流水线里不得再出现写死的标签字符串；
- 生成文档与代码一致。

## 结构变更与语义变更的边界

这一区分决定了能否安全地重跑历史项目。

| 改动 | 类型 | 是否影响缓存身份 |
|---|---|---|
| 移动文件、改名、拆模块、调整目录 | 结构 | 否 |
| 改页面标签、补文档、加检查脚本 | 结构 | 否 |
| 改阶段读写内容、换挂载规则、改判定口径 | 语义 | 是，必须更新 `task_semantics.json` |
| 改 Schema、改产物字段 | 语义 | 是 |

结构变更后必须证明语义零改动：

```sh
git diff --stat -- src/scene_completion/workflow/task_semantics.json
git diff --stat -- src/scene_completion/domain/schema_definitions.py
git diff --stat -- src/scene_completion/domain/ssd_contracts.py
git diff --stat -- src/scene_completion/analysis/ssd/
git diff --stat -- src/scene_completion/domain/ssd/
```

以上应为空 diff。

## 待消除的债务

按收益排序，均未在本轮执行：

1. 把 `infrastructure/identity.py` 移进 `domain`，消除那条例外。
2. 让 `worker_runtime` 通过注入而非直接导入上层服务。
3. 拆分 `models/clients/deepagents_client.py`（1461 行）与
   `inputs/provenance/indexed_context.py`（1285 行）。
4. `compat/detailed/` 的旧编排与新流水线并存，需要明确停用计划。
