# Scene Completion

从分层需求、系统架构和交互序列图识别异常关注点，逆向统一原文已有异常并推荐缺失场景。默认协议为`rr-sr-concern-gap-v2`；Skills定义方法，tools负责批次、结构校验、规范化集合、一一对应和导出。

## 工作流程

1. 读取RR系统需求、SR设计spec及AR材料。IR视为RR；未单独提供AR文件时，从SR文档中的AR描述保留实现追溯。
2. 语义抽取正常/普通可选流程、系统组成与原文已有异常。两个输出通道独立，已有异常不进入生成器。
3. 检查融合SSD和系统组成图，再从SSD构造主成功场景、从正向组成与交互推理对象特性。保留RR请求、SR展开及逐层返回；AR不参与异常挂载，内外数据库封装为SR资源服务。
4. 根据主成功交互和对象/数据/依赖特性挂载注册关注点，生成原子异常G；不进行异常适用性筛选。
5. 独立逆向已有异常E和测试异常T，统一到用例、实际交互、关注点、具体原因及必要条件，经过逆向检查器。宽泛异常测试拆成不同因果触发单元，并标记框架推导；正常条目不展开异常。
6. 各通道先复核同一交互、对象、原因下的条件差异：普通操作前提的不同描述可合并为同一异常，额外因果条件必须分开；保留全部原条件和标签。再按规范化身份及同交互/关注点内的语义核验一一对应，形成缺失集合M=G−E；未映射异常单列，不删除或强行分类。
7. M中的每条候选与同关注点的全部唯一历史E做embedding，原始余弦相似度求和。每类少于10条全选，否则选min(N,max(10,ceil(10%×N)))；无历史时固定种子随机取最多10条。跨类选中异常去重形成R，全部M仍在缺失报告中保留。
8. 以客户测试spec作为临时GT，计算漏报率、生成有效率、推荐采纳率及推荐误报率，分别提供总计、关注点和大类结果；输出JSON、Markdown、Excel及图。

匹配只比较异常对象、操作、机制及必要条件，响应和恢复不参与。测试GT不进入生成器或历史embedding库。正常模型来源检查不是异常候选筛选。

完整和部分匹配均可参与一一分配及集合交集计数；部分匹配必须识别同一具体原因，并提供缺少的必要条件原句。普通主题相同不算部分匹配，全部逐对决定保留供检查。

重复请求、回调或事件的幂等重放按异常触发条件处理，即使正确预期是复用已有结果且不重复执行；不能因为处理成功便改成普通可选流程。普通取消或正常选择仍保留为可选。

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
| `--test-spec-document` | 独立测试spec，可重复指定；经逆向细粒度化形成临时GT |
| `--ar-spec-document` | 可选独立AR材料，可重复指定；仅架构追溯，不分析AR交互 |
| `--output-dir` | 当前运行目录，保存状态、批次、执行记录及输出 |

默认使用Agent抽取、检查和语义核验，推荐使用历史embedding排序。ECNU配置参考 [rr_sr.config.example.json](rr_sr.config.example.json)，在本地 `.env` 或环境变量中设置 `ECNU_MAX_BASE_URL`、`ECNU_MAX_API_KEY` 和 `ECNU_MAX_MODEL`，以及文本embedding模型 `ECNU_EMBEDDING_TEXT`；生成/检查模型使用 `ecnu-max`。不提交密钥及运行缓存。

也可使用本地Luna子进程：先完成Codex CLI安装和登录，配置参考 [luna.config.example.json](luna.config.example.json)，增加 `--agent-runtime luna-subprocess`。示例批量使用 `gpt-6-luna/high`，独立效果审查使用 `gpt-6-luna/max`；实际身份保存在执行记录中。Luna只处理语义包，历史推荐仍调用ECNU embedding；可用 `--embedding-config <config.json>`提供独立embedding地址/密钥环境变量/模型配置。

## 运行全流程

下面以商城输入说明命令；迁移项目时替换种子和原始文档：

```bash
python .cac/tools/scene_completion.py scene-pipeline --model examples/online_shopping_seed.json --rr-spec-document 在线商城购物系统/系统需求_spec.md --sr-spec-document 在线商城购物系统/功能设计_spec.md --test-spec-document 在线商城购物系统/test_spec.md --agent-mode external --config rr_sr.config.example.json --output-dir output/run
```

Luna运行时改用 `--agent-runtime luna-subprocess --config luna.config.example.json`。`--agent-mode packets`只准备和收集语义包，不主动调用模型。`--requirement-document`、`--design-document`分别兼容映射RR、SR。

首次运行可能因缺少架构确认而暂停，检查 `architecture_proposals.json/md`，确认后用 `--architecture-approval <approval.json>`续跑。补全架构须有原文依据；不为通过检查虚构组件、接口或调用。

默认处理全部用例、全部有效挂载。v2始终核验实际SSD/组成图的原文锚点，错误锚点阻断流程；完整性遗漏与未知契约作为质量诊断保留，不能把流程跑通视为源文完整。执行失败及未完成批次不视为未匹配。

## 续跑与局部运行

使用相同输入、配置和输出目录再次执行原命令，即可复用版本有效的成功批次。模型、Skill、规则或相关输入变化使对应结果过期，不能重标旧模型身份。

- `--checker-input <已核实运行>/existing_scenarios.json`：在来源和抽取规则一致时复用独立检查器基线。
- `--use-case-id <ID>`：显式选择用例，可重复指定；默认不限制。
- `--reuse-run <run-dir>`：只复用输入包与实际执行证明一致的成功抽取；旧匹配和评分不作为新版结果。
- `--recommendation-seed <整数>`：无同类历史时的固定随机抽样种子，默认42。
- `--source-quality-gate`：旧v1协议的额外正常模型来源审查门禁，默认`strict`；`structural`限显式代表范围。v2保留此兼容配置记录，图锚点检查及质量诊断不由该选项切换。

逆向检查发现生成条目本身的原子原因或操作位置错误时，可执行 `repair-gap-generation --output-dir <run-dir> --config <config.json>`，用 `--unit-id <ID>`指定被实际拒绝的单元。修复只读取该生成条目、原关注点挂载及正常SSD证据，保留拒绝执行和替换执行；不使用已有异常或测试GT，不重生成其他成功条目。修复完成后再次执行原流程命令。

已有异常或测试的逆向定位/拆分被检查器拒绝时，使用 `repair-gap-reverse --output-dir <run-dir> --collection E --unit-id <ID> --config <config.json>`；测试通道改为 `--collection T`。只修复同通道的实际拒绝单元，原始异常记录保持不变，随后重新检查。

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

输出包括生成/已有异常、全部配对决定、指标、推荐、测试采纳、章节诊断及图形；最终工作簿为 `scene_assessment.xlsx`，指标表在“类别”右侧提供中文“关注点说明”。四项指标使用规范化一一集合：漏报率=1−|(T−E)∩M|/|T−E|；生成有效率=|G∩T|/|G|；采纳率=|R∩T|/|R|；推荐误报率=|R−T|/|T|。空分母null，误报率不截断。测试明示和标记推导原因共同计入GT，分类数量不直接累加。

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
- 方法入口： [scene-concern-gap](.cac/skills/scene-concern-gap/SKILL.md)。
- 分层输入： [RR/SR输入规范](.cac/skills/scene-extract/references/rr_sr_input_schema.md)。
- 检查与修复接口： [tools说明](docs/rr_sr_tools_checks.md)。
- 逻辑查询返回数据： [来源协议](docs/rr_sr_logical_query_data_policy.md)。

新流程使用Agent语义处理及历史embedding，不使用rerank。旧流程通过 `--protocol rr-sr-ssd-identification-v1`或 `--protocol legacy`兼容，新旧语义结果使用不同运行目录。更多参数使用 `python .cac/tools/scene_completion.py <command> --help`查看。
