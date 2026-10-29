# 业务离线审核与反馈回收（business-review-v1）

当前网页和CLI共用一套API、Schema、版本和审计记录。业务疑问不等于异常；未知事实不能靠回答表单的默认值自动补成异常。

## 交接流程

1. 研发完成有依据的分析。在“待确认项”区分补规则、异常判定、归属确认和一般澄清；技术错误单列，仍须研发修复。
2. 在“审核交接”导出Windows业务审核包。项目必须停止执行。包包含Python、网页、正式产物、原始文档、冻结推荐和审核快照，默认不带密钥、账号配置、额度账本、模型缓存、原始思考及Agent轨迹。含业务材料的审核包只通过业务允许的渠道交付，不上传GitHub。
3. 业务完整解压，运行`start.cmd`，不必配置模型。服务端审核模式禁止模型运行、重跑、配置变更、文档替换和关注点编辑；允许浏览、回答和审核推荐。目录改变不会重算source_id。`check.cmd`在审核模式只做只读启动检查。
4. 业务在“待确认项”补充实际规则、决定或对应关系。点击“点击以查看文档”，项目栏收窄，回答区和原文区左右各半，原文按原source_id/章节/行号定位和高亮。问题列表可折叠。保存、修改、撤回均保留审核人、渠道、时间和版本，不执行模型。
5. 业务在“推荐审核”决定采纳／不适用／无需纳入／已有覆盖／暂缓。采纳只更新业务版GT和工具计算的指标，不修改本轮G/E/M/Q和排序。
6. 在“审核交接”导出小型JSON反馈文件，交回研发，无需返还整个data目录。
7. 研发选择反馈文件，先看新增、修改和冲突，再显式保存。相同反馈不重复应用。问题、产物或研发回答已经变化时不覆盖；可显式只导入无冲突项，冲突及原反馈历史仍保留。
8. 研发预览来源节点和真实DAG下游，再点击“按此范围重跑”。保存回答、导入反馈、采纳推荐均不自动启动模型。重跑前归档原manifest、报告、任务状态及受影响输出；无关成功产物按原缓存规则复用。

## Markdown原文阅读与大纲

待确认问题的依据卡片仍使用原始source_id、文件快照和引用行号。在并排原文框中：

- 默认“阅读”模式，渲染标题、加粗、列表、引用、GFM表格及代码块；黄色标记对应引用段落或表格行。
- “大纲”展开章节目录，也可以用“跳转到章节”直接选择；支持中文及重复标题。跳转仅滚动原文框，不跳离回答页面。“返回引用”回到原引用。
- “源码”保留精确行号及按行前后查看，适合核对Markdown语法或原始JSON；切换不清除尚未保存的回答。
- 阅读模式按需加载完整文档，以避免截取片段破坏表格及代码围栏。超过2MB时明确提示改用分页源码，不静默截断。Markdown解析器只在打开阅读内容时加载。
- 代码块按源码展示（包括Mermaid），本版不将Mermaid转换为图。原文中的脚本/任意HTML不会执行，外部图片不自动加载；可主动点击图片链接查看。无需联网加载Markdown组件。

本次只改阅读呈现和来源读取接口，不改原文、问题、审核记录及模型结果。离线审核包继续使用同一快照校验和跨目录source_id映射。

## 回答的适用范围

- `rule_completion`：补充规则／明确不要求校验／仍待补充。例：categoryId有效性需要哪些条件、由谁执行，不问“是否异常”。
- `scenario_classification`：是异常／不是异常／待确认。确认异常时选择当前启用的具体关注点，并填写触发条件及依据。
- `binding_confirmation`：确认／修正用例、交互或对象关系／待确认。结构错误交回研发核查，不能改判成异常。
- `general_clarification`：明确待决定事项，自由文本补充；无法可靠归类的历史问题使用此表单。

业务确认材料独立版本化，不改写原文。只有研发显式应用后，才按来源节点和通道进入允许上下文：正向规则可供该节点及其正常依赖使用；E侧和GT侧回答不能进入G。撤回已应用回答也要预览影响并重算，旧报告和旧回答仍可读。

模型工具调用和JSON文本提交都支持同时提交已知结果和非阻断问题。业务问题不会重置调用/修复预算；限流、截断、无效Schema、文件写入错误仍是技术失败，不能伪装成成功。“执行完成但有待确认项”和“审核完成”分开显示。

## 三套GT及推荐指标

- 原始测试GT：保留原异常测试来源及自动整理标识。
- 冻结扩展测试GT：原始测试＋独立补全的异常测试，是本轮冻结基线。
- 业务审核后GT：冻结扩展GT＋人工采纳增补，包含对应的关注点绑定和具体场景，单独版本保存。

采纳Q中已完整对应现有GT的场景，只增加确认记录，不重复计数。同定位、同模式的疑似重复项需明确关联已有GT或确认新增独立失败。撤回仅移除该次人工增补，不删除基线，也不删除其他有效确认。未知/未完成状态不显示为0。

关注点漏报率 `(1−|Mc∩(GTc−Ec)|/|GTc−Ec|)×100%`、生成有效率 `|Gc∩GTc|/|Gc|×100%`。场景推荐前以全部M为基线，推荐后以Q为候选：采纳率 `|Q∩GTs|/|Q|×100%`、误报率 `|Q−(Q∩GTs)|/|GTs|×100%`（保留GT分母，可能超过100%）。人工实际采纳率另报，不能与测试GT命中率混称。采纳改变GT导致的指标变化不表示生成模型质量提升。

## Code Agent CLI

先启动网页服务。Windows使用`scene.cmd`，源码使用`.venv/bin/python scene.py`。`--server`放在子命令之前；只连接本机工作台。

```console
scene.cmd capabilities
scene.cmd projects
scene.cmd pending --project PROJECT_ID
scene.cmd sources --project PROJECT_ID
scene.cmd sources --project PROJECT_ID --source SOURCE_ID --start 10 --end 20
scene.cmd pending --project PROJECT_ID --item QUESTION_ID --file answer.json --dry-run
scene.cmd pending --project PROJECT_ID --item QUESTION_ID --file answer.json
scene.cmd handoff --project PROJECT_ID --out business-review.zip
scene.cmd feedback --project PROJECT_ID --out business-feedback.json
scene.cmd feedback --project PROJECT_ID --file business-feedback.json --dry-run
scene.cmd feedback --project PROJECT_ID --file business-feedback.json
scene.cmd impact --project PROJECT_ID
scene.cmd rerun --project PROJECT_ID --affected --plan-id PLAN_ID --dry-run
scene.cmd rerun --project PROJECT_ID --affected --plan-id PLAN_ID
```

审核包只允许查询、`pending`回答和`recommendations`反馈，禁止其他写入命令。`handoff --format project`导出不含Python的项目审核快照，适合已具备当前程序的受控交接；完整Windows业务包用默认格式。

`answer.json`使用当前问题返回的revision、answer_spec.choices和origin_bindings：

```json
{"revision":0,"reviewer":"业务审核人","choice":"provide_rule","answer":"分类必须存在且启用，由商城入口校验。"}
```

可附`expected_origin_bindings`校验展示时的来源产物身份。修改、撤回用最新revision；撤回choice为`withdraw`。不得将全部问题统一回答“是异常”。

其他公开操作：`config/configure`模型与路由、`accounts/save-account`每Key模型白名单、`registry`关注点、`patterns`模式风险与K、`reviews`产物审核、`recommendations`推荐反馈、`test-sources`测试源、`repair-export/repair-submit`外部Code Agent修复。写入JSON结构及参数由`capabilities`和各命令`--help`发现，修改支持`--dry-run`和现有版本校验。禁止直接改正式产物、配额账本或绕过校验器。

CLI等待返回0表示可执行节点已完成（可能仍有非阻断业务待确认）；2表示等待产物审核/配置或技术执行未完成；3表示CLI停止等待，服务端仍继续。

## 文件与API

`business_questions.json`、`pending_decisions.json`保存问题与完整历史；`review_applied.json`记录显式应用的版本；`business_truth_versions/`保存业务版GT；`handoffs/`和`feedback_imports.json`保存快照身份和原始反馈审计。审核SQLite通过一致性备份导出，只保留必要问答，不带模型事件和检查点。

公开接口包含`/sources`、`/pending/{id}/history`、`/impact`、`/rerun-affected`、`/handoff/export`、`/feedback/export`、`/feedback/import`、`/business-truth/{case}`，与CLI共用校验。Windows公共程序包不包含上述业务数据；具体项目审核包在本地另行导出。

本次不调用付费模型、不重算旧验收分数。离线和跨目录模拟能验证身份、隔离与流程，不能替代Windows原生和客户网关联调。客户侧需实际验证完整解压、中文/空格路径、浏览原文、保存和导出反馈。
