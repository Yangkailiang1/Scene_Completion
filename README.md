# Scene Completion

从分层需求、系统架构和交互序列图识别异常场景，比较原文覆盖并推荐待补充场景。Skills定义分析方法，tools负责结构化输入、批次执行、校验、指标和导出。

## 工作流程

1. 读取RR需求spec、SR设计spec及用例定位种子。IR视为RR；保留RR→SR→AR→软件接口的分解关系，AR仅用于实现追溯。
2. 从正常及普通可选流程建立架构、补全有原文依据的参与者，将内外数据库封装为SR资源服务，构建RR/SR融合SSD。
3. **生成器**按真实SSD的交互双方、传输数据、状态和依赖挂载关注点，再具体化异常。每条异常保留消息、交换、挂载和来源引用；正常/可选场景也保留导出。
4. **检查器**独立从系统spec、设计spec抽取RR、SR已有原子异常，分别与同层同用例的生成异常比较。按对象、操作、失败机制及必要条件判断完整/部分/未匹配，响应和恢复不参与覆盖判定；tools执行一一分配。
5. **推荐器**为未分配生成异常评分、定位补充章节。同一实际原因跨RR/SR合并推荐单元，保留原成员及关注点标签。
6. 独立读取测试spec，拆分异常条件单元；推导原因明确标记。测试不按RR/SR分区，与推荐单元一一匹配，计算采纳率。
7. 校验来源、真实SSD锚点、版本、执行证据及批次完整性，输出JSON、章节诊断、架构/依赖/SSD图、Markdown和Excel。

生成器不读取检查器或测试异常补写场景，不通过LLM适用性审查删减候选。正常模型的来源检查用于核实抽取，不是异常候选筛选。

## 安装

使用Python 3.11或更新版本，在项目根目录运行：

```bash
python -m pip install -r requirements.txt
```

需要运行回归时另安装pytest：

```bash
python -m pip install pytest
```

## 准备输入与配置

| 输入 | 用途 |
| --- | --- |
| `--model` | 项目的用例编号、原文定位及系统身份种子，参考 `examples/online_shopping_seed.json` |
| `--rr-spec-document` | 原始RR需求，可重复指定；IR映射为RR |
| `--sr-spec-document` | 原始SR设计，可重复指定；AR描述只提供追溯 |
| `--test-spec-document` | 独立测试spec，可重复指定，不交给生成器或检查器抽取 |
| `--output-dir` | 当前运行目录，保存状态、批次、执行记录及输出 |

默认使用Agent比较和推荐。ECNU配置参考 [rr_sr.config.example.json](rr_sr.config.example.json)，在本地 `.env` 或环境变量中设置 `ECNU_MAX_BASE_URL`、`ECNU_MAX_API_KEY` 和 `ECNU_MAX_MODEL`；模型使用 `ecnu-max`。不提交密钥及运行缓存。

也可使用本地Luna子进程：先完成Codex CLI安装和登录，配置参考 [luna.config.example.json](luna.config.example.json)，增加 `--agent-runtime luna-subprocess`。示例批量使用 `gpt-6-luna/high`，独立效果审查使用 `gpt-6-luna/max`；实际后端及模型身份保存在执行记录中。

## 运行全流程

下面以商城输入说明命令；迁移项目时替换种子和原始文档：

```bash
python .cac/tools/scene_completion.py scene-pipeline --model examples/online_shopping_seed.json --rr-spec-document 在线商城购物系统/系统需求_spec.md --sr-spec-document 在线商城购物系统/功能设计_spec.md --test-spec-document 在线商城购物系统/test_spec.md --agent-mode external --config rr_sr.config.example.json --output-dir output/run
```

Luna运行时改用 `--agent-runtime luna-subprocess --config luna.config.example.json`。`--agent-mode packets`只准备和收集语义包，不主动调用模型。`--requirement-document`、`--design-document`分别兼容映射RR、SR。

首次运行可能因缺少架构确认而暂停，检查 `architecture_proposals.json/md`，确认后用 `--architecture-approval <approval.json>`续跑。补全架构须有原文依据；不为通过检查虚构组件、接口或调用。

默认处理全部用例、全部有效挂载并执行严格来源检查。源文或模型的问题在诊断中保留；执行失败及未完成批次不视为未匹配。

## 续跑与局部运行

使用相同输入、配置和输出目录再次执行原命令，即可复用版本有效的成功批次。模型、Skill、规则或相关输入变化使对应结果过期，不能重标旧模型身份。

- `--checker-input <已核实运行>/existing_scenarios.json`：在来源和抽取规则一致时复用独立检查器基线。
- `--use-case-id <ID>`：显式选择用例，可重复指定；默认不限制。
- `--exchange-local-id <ID>`：局部交互链验证，可重复指定，必须包含真实RR/SR及父调用；保留所选用例的原文异常分母。
- `--comparison-verification final-review`：由最终独立效果审查复核，省去重复全量比较；默认 `all`。
- `--source-quality-gate structural`：仅用于显式代表范围的方法流程验证，保留来源质量否定结论；默认 `strict`。

## 检查、验证与导出

```bash
python .cac/tools/scene_completion.py check-interaction-run --output-dir output/run
python .cac/tools/scene_completion.py validate-interaction-run --output-dir output/run
python .cac/tools/scene_completion.py prepare-interaction-review --output-dir output/run
```

完成真实独立效果审查并保存绑定当前材料的原始结论后运行：

```bash
python .cac/tools/scene_completion.py evaluate-generator --output-dir output/run
```

`check-interaction-run`可检查部分运行，输出 `run_checks.json/md`。`validate-interaction-run`执行完整回归及禁止新模型调用的缓存续跑。流程完成、输入质量和覆盖效果分别报告，不能仅凭 `complete=true`宣告验收。

输出包括生成/已有异常、全部配对决定、指标、推荐、测试采纳、章节诊断及图形；最终工作簿为 `scene_assessment.xlsx`，指标表在“类别”右侧提供中文“关注点说明”。RR、SR和合计分别统计漏报率与异常完整率，并按关注点及大类细化；推荐采纳率按去重推荐单元计算，空分母为null。

## 离线重建

从完整运行导出结果快照，然后在另一目录重建报告，无需再次调用模型：

```bash
python .cac/tools/scene_completion.py export-interaction-snapshot --output-dir output/run --snapshot-file output/snapshot.json
python .cac/tools/scene_completion.py rebuild-interaction-snapshot --snapshot-file output/snapshot.json --output-dir output/rebuilt
```

[示例快照](examples/agent_workflow_smoke/README.md)可直接重建。快照保留可复现结果，不包含私人配置或模型执行缓存；离线重建不冒充新的模型执行验收。

## 开发与方法文件

PowerShell运行回归：

```powershell
$env:PYTHONPATH = '.cac/tools'
python -m pytest -q
```

- 三角色编排与职责： [.cac/agents](.cac/agents/scene-agent.md)。
- 方法入口： [scene-assess](.cac/skills/scene-assess/SKILL.md)。
- 分层输入： [RR/SR输入规范](.cac/skills/scene-extract/references/rr_sr_input_schema.md)。
- 检查与修复接口： [tools说明](docs/rr_sr_tools_checks.md)。
- 逻辑查询返回数据： [来源协议](docs/rr_sr_logical_query_data_policy.md)。

当前运行入口使用Agent后端；旧流程通过 `--protocol legacy`兼容，Embedding/rerank不是当前Agent流程的运行步骤。更多参数使用 `python .cac/tools/scene_completion.py <command> --help`查看。
