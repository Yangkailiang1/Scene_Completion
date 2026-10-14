# 运行检查、续跑与修复接口

## 模型可用性与并发

先用`check-models --config <配置> --output-dir <检查目录>`探测模型，再用`configure-models --checked-report <available_models.json> --config <原配置> --agent-model <通过ID> --max-concurrency 1 --output-config <运行配置>`保存选择。语义候选可重复指定`--candidate-model`；embedding与独立审查分别用`--include-embedding`、`--include-review`检查。端点目录只作候选，不作成功证明。具体入口及独立embedding配置见[模型配置规则](../.cac/skills/scene-concern-gap/references/model_access.md)。

模型、端点、凭证及执行设置的可用性记录保存在本地。拒绝/鉴权失败进入待配置，不消耗语义修复预算；相同配置在有效期内不反复请求。恢复后用`--refresh`重检。`--max-concurrency`优先于配置，默认1；Agent按客户限制调整共享上限，默认DAG限流降并发并保存`concurrency_status.json`。有效成功产物续跑不为可用性检查新增模型调用。

## 检查当前运行

```bash
python .cac/tools/scene_completion.py check-interaction-run --output-dir <run-dir> --rr-spec-document <rr.md> --sr-spec-document <sr.md>
```

编排结束也会自动生成 `run_checks.json/md`。检查项目包括原文与版本、独立基线、正常模型来源、参与者、数据库服务化、SSD层级与消息、关注点挂载、真实执行证明、批次完整性及可重建的结果集合。

v2的`run_manifest.json`记录当前阶段及完成状态，各阶段worker状态区分缓存复用、完成、失败和延后；检查入口提供`pending_stage`及失败原因。旧协议的`execution_progress`提供批次汇总。失败、过期输入或缺失输出阻止完整发布；未执行批次不能当作未匹配。`structurally_valid`与`formally_accepted`分别表达结构检查及最终验收状态。

## 执行与续跑

v2 默认 `--execution-mode case-dag`；旧阶段编排可显式用 `stage-barrier`。每个用例的正常模型、SSD/组件、参与者、特性、挂载、G和逆向集合各自记录依赖与原执行证明，通过的用例立即向下推进。`case_tasks.json`保存待执行、运行中、通过、修复中、待确认、预算耗尽和过期状态；`progress.json/md`列出未完成用例，`cases/<稳定ID>`保存局部产物和报告。

默认 `--auto-repair bounded --max-repair-rounds 2`，也可 `--auto-repair off`或把上限降到0/1。两轮预算按用例和阶段持久保存；相同失败无进展提前停止。诊断区分格式/引用、模型问题、检查器误判及需用户确认项；定向修复后必须由原校验器和新检查通过。修复只使相关依赖过期。正常/G通道不能读E/GT，E/T各自独立。全局外部调用遵守配置的共享并发上限（默认1），包含修复和embedding；传输重试不增加语义轮数，额度失败保留现场。

用例已有异常通过逆向检查、来源审查和去重后先缓存历史向量；全量历史未齐时不计算推荐排序或正式指标。局部Excel/Markdown提供生成/已有/匹配/缺失，但不冒充项目分母。最终检查验证任务依赖哈希、实际原包与结果、集合一一对应和四项公式；旧结果只有来源、规则及执行身份有效才可导入，保留原ID及哈希。

四类修复命令支持 `--use-case-id <ID>`选择DAG用例；不重置该用例已消耗的自动修复预算。待确认组件/调用绑定 `proposal_id`及证据指纹，批准文件的 `proposal_bindings`为“提案ID → 指纹”映射。历史整图批准仅在其原模型哈希有效时迁移，其他新增项不自动获批。

`scene-pipeline --agent-mode external`执行对应语义包；`packets`仅准备和收集。使用相同输入、后端配置及输出目录重跑，工具复用版本有效的成功结果。每个阶段保存实际Skill、输入、模型、推理配置、执行证明和状态；缓存不能被改标为另一后端。

需要单独执行批次时：

```bash
python .cac/tools/scene_completion.py run-agent-batches --stage-dir <run-dir>/batches/<stage> --sources-index <run-dir>/sources_index.json --config <config.json>
```

使用 `--worker-index`、`--worker-count`分配worker，`--batch-id`可重复指定待执行包。测试阶段使用对应的 `test_sources_index.json`。同一阶段worker运行时不要修复或重写其输入。

批量、抽取与修复入口均支持`--agent-model <ID>`、`--embedding-model <ID>`，优先于配置文件及环境变量。语义API允许配置`qwen38-27b-vl`及其他服务端提供的模型名；`openai-compatible`与旧`ecnu`使用同一兼容接口。Luna子进程的模型名也由配置决定，实际命令、输出和事件仍须验证。最终独立效果审查由`review_model`、`review_runtime`及`review_reasoning_effort`配置，与批量模型选择独立。

模型切换不重标旧结果；默认只复用当前模型的缓存。确需复用历史实际模型时，在配置明确列出`allowed_cached_models`，保留原执行身份。新API批次记录端点指纹，端点改变时重新执行；向量按端点/模型/文本隔离。输入/工具版本变化仍阻止旧结果冒充当前正式验收。

## 来源诊断与修复

v2图检查、特性推理、生成及G/E/T逆向检查分别保存语义包；只有同一通道的材料进入输入。正常模型修复不接受E或测试GT作为依据。已有异常的来源抽取与逆向检查是独立阶段。

语义对应worker提供与严格校验一致的证据格式提示。接受关系必须覆盖每条必要条件，并引用原句；部分缺口不能用解释代替原条件。同一实际交互若同时声称“原因相同、条件兼容”却判为未匹配，工具拒绝并要求重新核验，不能依据成功复用、返回结果或处理失败措辞区分异常身份。工具不自动把拒绝项改成匹配。

强化校验后被拒绝的旧缓存执行会保存在阶段`attempts`中，再执行真实重判；旧拒绝及新执行均纳入复验材料。只重跑无效批次，其他成功结果和向量继续复用。

| 命令 | 用途 |
| --- | --- |
| `diagnose-generator-model` | 定位正常模型的结构、角色、字段和父调用错误 |
| `diagnose-normal-source-audit` | 定位来源审查的引句、清单完整性及输出结构错误 |
| `repair-generator-model-origins` | 根据实际来源拒绝或指定源文发现，从原始正常流程包重新抽取 |
| `retry-normal-source-audit` | 原文复核确认审查误判后，重审指定来源审查包，不改变正常模型 |
| `repair-checker-source-audit` | 对尚未冻结的被拒绝检查器草稿，从原始来源包重抽 |
| `repair-gap-generation` | 仅将逆向检查实际拒绝的G条目按既有SSD挂载重新具体化，不读取E或T；保留其他成功条目及原顺序 |
| `repair-gap-reverse` | 用 `--collection G/E/T`及 `--unit-id`，只在同一独立通道重提取被拒绝的逆向单元，不修改原文基线或其他成功单元 |

这些命令均要求 `--output-dir <run-dir>`。诊断可在worker结束后加 `--prepare-retry`记录来源绑定的提示；它不代填语义结论。指定发现的修复使用 `--source-review-file <review.json>`和重复的 `--source-finding-id <ID>`，文件必须绑定实际原包、当前模型及精确原文引句。修复入口保留旧结果和拒绝依据，只改所选包；之后仍需完成当前来源检查。

固定检查器使用 `--checker-input <reviewed-run>/existing_scenarios.json`导入。工具核验原文、分类、实际抽取规则、独立执行记录及来源核验；原文或抽取规则变化不能复用旧分母。冻结后的基线不原地手工修复。

## 局部范围与质量模式

v2默认全量处理及严格图锚点检查。`--use-case-id`选择完整代表用例，`--reuse-run`导入字节及来源版本一致的成功抽取；不使用旧逐对比较或评分作为v2结果。

`--source-quality-gate`控制旧v1的额外正常模型来源审查门禁。v2仅保留此兼容配置记录：实际图锚点错误始终阻断，完整性遗漏/未知契约始终保留质量诊断，选项不切换新图检查语义。流程验收不代表全部输入质量问题已解决。

测试读取所选业务的全部相关异常，不按RR/SR分区，按交互和具体因果关注点统一粒度。AR仅架构追溯。无法映射的异常保留在集合及报告，不当作未执行批次。

历史排名仅使用M和已逆向检查的E，不读取T。保存相似度明细、文本/模型指纹和随机种子；成功向量复用。无历史每类最多10条固定种子抽样，有历史按每类TopN选取，跨类去重。所有未入选M仍导出。

## 验证与效果审查

完整流程后依次运行：

```bash
python .cac/tools/scene_completion.py validate-interaction-run --output-dir <run-dir>
python .cac/tools/scene_completion.py prepare-interaction-review --output-dir <run-dir>
```

第一步运行全仓库pytest并保存JUnit、命令、日志和代码/测试版本，再执行禁止模型调用及网络访问的真实缓存续跑，核对全部输入、结果和指标前后相同。

第二步生成 `effect_review_materials.json`，绑定原文、模型、SSD、挂载、G/C、来源检查、比较、推荐、测试及执行批次。由运行清单指定的模型及推理设置独立审查，保存 `effect_review_raw.json`和 `effect_review.json`；记录材料/结果哈希、真实agent身份、逐领域理由、证据文件及未解决发现。v2审查领域包括纯SSD生成、AR仅追溯、图检查、对象特性、逆向原子条件、异常机制、GT推导、四项分母、历史排序、TopN抽样、一一分配及范围续跑。

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
