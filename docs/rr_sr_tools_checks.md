# 运行检查、续跑与修复接口

## 检查当前运行

```bash
python .cac/tools/scene_completion.py check-interaction-run --output-dir <run-dir> --rr-spec-document <rr.md> --sr-spec-document <sr.md>
```

编排结束也会自动生成 `run_checks.json/md`。检查项目包括原文与版本、独立基线、正常模型来源、参与者、数据库服务化、SSD层级与消息、关注点挂载、真实执行证明、批次完整性及可重建的结果集合。

`execution_progress`区分有效、无效、失败、延后和待执行批次，只统计当前manifest。失败、过期输入或缺失输出阻止完整发布；未执行批次不能当作未匹配。`structurally_valid`与`formally_accepted`分别表达结构检查及最终验收状态。

## 执行与续跑

`scene-pipeline --agent-mode external`执行对应语义包；`packets`仅准备和收集。使用相同输入、后端配置及输出目录重跑，工具复用版本有效的成功结果。每个阶段保存实际Skill、输入、模型、推理配置、执行证明和状态；缓存不能被改标为另一后端。

需要单独执行批次时：

```bash
python .cac/tools/scene_completion.py run-agent-batches --stage-dir <run-dir>/batches/<stage> --sources-index <run-dir>/sources_index.json --config <config.json>
```

使用 `--worker-index`、`--worker-count`分配worker，`--batch-id`可重复指定待执行包。测试阶段使用对应的 `test_sources_index.json`。同一阶段worker运行时不要修复或重写其输入。

## 来源诊断与修复

正常模型和独立检查器分别依据自己的原文检查；正常模型修复不接受C或测试条件作为生成依据。

| 命令 | 用途 |
| --- | --- |
| `diagnose-generator-model` | 定位正常模型的结构、角色、字段和父调用错误 |
| `diagnose-normal-source-audit` | 定位来源审查的引句、清单完整性及输出结构错误 |
| `repair-generator-model-origins` | 根据实际来源拒绝或指定源文发现，从原始正常流程包重新抽取 |
| `retry-normal-source-audit` | 原文复核确认审查误判后，重审指定来源审查包，不改变正常模型 |
| `repair-checker-source-audit` | 对尚未冻结的被拒绝检查器草稿，从原始来源包重抽 |

这些命令均要求 `--output-dir <run-dir>`。诊断可在worker结束后加 `--prepare-retry`记录来源绑定的提示；它不代填语义结论。指定发现的修复使用 `--source-review-file <review.json>`和重复的 `--source-finding-id <ID>`，文件必须绑定实际原包、当前模型及精确原文引句。修复入口保留旧结果和拒绝依据，只改所选包；之后仍需完成当前来源检查。

固定检查器使用 `--checker-input <reviewed-run>/existing_scenarios.json`导入。工具核验原文、分类、实际抽取规则、独立执行记录及来源核验；原文或抽取规则变化不能复用旧分母。冻结后的基线不原地手工修复。

## 局部范围与质量模式

默认全量处理、`source-quality-gate=strict`、`comparison-verification=all`。

局部验证通过 `--use-case-id <ID>`明确选择业务范围；交互链可再重复指定 `--exchange-local-id <RR或SR本地ID>`。工具要求真实层级、全部父调用及所选链的全部有效挂载，原文分母不删减。测试读取所选业务的全部相关记录，不按RR/SR分区。

`--source-quality-gate structural`仅允许显式代表范围，保留真实来源审查的否定结论，不能标为质量通过。SSD真实来源、锚点、挂载、执行证明和结果完整性仍须有效。`--comparison-verification final-review`省去重复全量比较，但最终独立审查仍执行。

## 验证与效果审查

完整流程后依次运行：

```bash
python .cac/tools/scene_completion.py validate-interaction-run --output-dir <run-dir>
python .cac/tools/scene_completion.py prepare-interaction-review --output-dir <run-dir>
```

第一步运行全仓库pytest并保存JUnit、命令、日志和代码/测试版本，再执行禁止模型调用及网络访问的真实缓存续跑，核对全部输入、结果和指标前后相同。

第二步生成 `effect_review_materials.json`，绑定原文、模型、SSD、挂载、G/C、来源检查、比较、推荐、测试及执行批次。由实际 `gpt-6-luna/max`独立审查，保存 `effect_review_raw.json`和 `effect_review.json`；记录材料/结果哈希、真实agent身份、逐领域理由、证据文件及未解决发现。领域包括纯SSD生成、层级、关注点、原子条件、异常机制、分母、采纳、缺口、参与者、映射、一一分配及测试推导。

审查完成后：

```bash
python .cac/tools/scene_completion.py evaluate-generator --output-dir <run-dir>
python .cac/tools/scene_completion.py check-interaction-run --output-dir <run-dir>
```

验收工具重新核验回归、续跑、结果及真实审查绑定，不接受手填通过布尔值。输入质量、覆盖指标和流程验收分别报告。

## 离线导出与重建

```bash
python .cac/tools/scene_completion.py export-interaction-snapshot --output-dir <run-dir> --snapshot-file <snapshot.json>
python .cac/tools/scene_completion.py rebuild-interaction-snapshot --snapshot-file <snapshot.json> --output-dir <rebuilt-dir>
```

导出先复验完整原运行，仅保存源文、模型、SSD、挂载、异常及比较决定等可复现数据，不包含密钥、私人配置或执行缓存。重建不调用模型，重新核实SSD、挂载、比较全集、一一分配及结果哈希，导出JSON、Markdown、图和Excel；标记 `execution_evidence_verified=false`，不继承原运行验收状态。

详细参数使用 `<command> --help`查看；运行及配置入口见[项目README](../README.md)。
