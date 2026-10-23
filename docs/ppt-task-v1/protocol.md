# ppt-task-v1：27页PPT独立任务协议

适用底稿是27页版本，包括记忆库交互细化页及11页Skill。不是32页方案，不新增架构图/依赖图任务。本次不修改PPT、不迁移执行框架，也没有付费模型效果或稳定性对照实验。

## 任务与精确输入

命令`scene-task --task TASK --input-json INPUT.json --output-dir RUN`中的INPUT是下表的命名对象。未知键、未知字段、字段类型错误均拒绝。JSON Schema原件在[schemas](schemas)中，源码`ppt_contracts.py`是执行依据；CI检查两者同步。

| task / Skill | 输入键 | 输出核心字段 |
| --- | --- | --- |
| components / scene-components | RR、SR：normal通道Markdown投影数组 | components：name、composition_type；relations：from_id、to_id、relation |
| rr-ssd / scene-rr-ssd | RR：normal投影数组 | interactions：sender、operation、data、receiver；sequence、direction |
| sr-ssd / scene-sr-ssd | SR：normal投影数组 | 同上，保留接口标识、请求/返回与父交互 |
| object-operations / scene-object-operations | components、rr-ssd、test-operations | objects：name、supported_operations（name与来源） |
| api-map / scene-api-map | SR：normal投影数组 | services：name、interfaces（id、name、method、address） |
| api-parameters / scene-api-parameters | SR：normal投影数组 | apis：id、name、address、parameters |
| concern-match / scene-concern-match | components、rr-ssd、sr-ssd、api-map、api-parameters、registry | matches：interaction_id、target、object、concern_key、basis、concrete_rule；pending |
| exception-generate / scene-exception-generate | 上述正向五项、concern-match、registry | scenarios（G）与pending |
| existing-extract / scene-existing-extract | existing-documents（RR/SR原文）、registry | scenarios（E），仅明示异常 |
| gap-compare / scene-gap-compare | left、right：异常数组；purpose（G_E/GT_G/GT_E） | 全部候选对decisions：left_id、right_id、status、reason |
| gap-recommend / scene-gap-recommend | 空对象 | enabled=false、status=未启用 |

`registry`使用`ppt_contracts.registry()`，内容为固定57项当前定义，指纹`953166eb205f01f63d16b413a1f27c6373ba44a44aa72b8e279a605f9e6b67c9`。定义变化必须显式升级协议，不能悄悄重提取或替换。

参数字段：`name, location(header/path/query/body/response/business), data_type, required, default, constraints, source_refs`。约束含`id, kind, value, status(explicit/pending), source_refs`，每条独立约束单独记录；类型未知/必填性未知使用null，不能填猜测值。默认值不是异常边界。`data_type`是类型规则的唯一展示属性，避免在constraints中重复计数。

交互字段：`id, case_id, sequence, parent_id, layer, sender, operation, data, receiver, direction, api_id, source_refs`。双方含`name, position, source_refs`；操作含`name, kinds, sequence, optional, source_refs`；数据含`sequence`参数列表。`parent_id`指同层父调用；返回是单独的有序交互。RR与SR分别抽取，不虚构跨层展开关系。

异常字段：`id, case_id, interaction_id, layer, object, operation, cause, conditions, concern_key, field, rule_id, source_status, derivation, source_refs`。field=null表示双方/业务异常；字段异常由确定性代码按明示属性逐项细化。具体原因与必要条件决定粒度，不按关注点名称合并。

## 文档、来源与隔离

输入Markdown由`ppt_sources.read_documents()`读取，文档对象格式：

```json
{"source_id":"稳定来源标识","name":"RR.md","channel":"normal","lines":[{"number":1,"text":"原文一行"}]}
```

允许normal、existing、test三个通道。normal投影排除异常/扩展/错误处理章节及错误码内容，保留原始行号；不把已有异常作为正常约束反向取反。当前投影支持Markdown标题和“6. 扩展路径”一类编号节，采用保守排除。复杂混写文档可能丢弃正向内容，须先检查`packets/`中的正向投影；不得通过放入整篇原文来绕过隔离。来源真实不等于语义必然正确，离线校验不替代真实效果审查。

来源引用格式：`{source_id,line_start,line_end,quote}`。明示事实必须给精确引文，行区间不得越过本任务允许的正向行；不允许借邻近异常行作依据。原始来源与源文档内的指令均只作为数据。

两个内部辅助任务不是新增PPT任务：

- test-operation-project：只输出对象名称与支持操作。每项来源quote必须等于操作名称，禁止把含错误码/预期响应的整句引文传入能力任务。原文测试只留在这一独立投影任务和GT任务。
- test-ground-truth：输入test-documents、normal-constraints（仅API参数正向约束）、registry。允许框架推导直接进入GT，但必须给推导依据，source_status区分explicit/framework_inferred。不得读取G、E比较或缺失结果。

本轮不执行额外“读测试补SSD”、不把能力表送入G。只读交互拒绝写入类关注点。资源数据库保留在组成中；使用已有normalize_resource_services生成logical_only的SR资源服务和物理映射，SR逻辑视图只改对象身份，不补造方法、路径、部署或调用。

## 执行和恢复

默认`scene-pipeline`使用ppt-task-v1。固定DAG由五个正向抽取、独立测试操作投影、能力并集、关注点匹配、G、独立E、独立GT、三路比较和报告构成。可就绪任务并行，不要求一次Skill只调用一次模型；对象操作并集、已知字段规则、匹配后的集合运算由工具完成。任务按照依赖继续推进；本版任务粒度是本次选定用例集合，不会自动按每个用例建立独立子DAG。需要按用例独立恢复可用不同目录及`--use-case-id`显式分批；不把改变目录当成重置失败预算的办法。

`--use-case-id`是显式抽取范围，留空处理全输入。不同范围使用不同输入身份。`--agent-mode packets`只写任务包，任务待执行返回码2；恢复时传`--responses-dir RESULTS`，文件名为包的batch_id.json，格式：

```json
{"protocol":"ppt-task-v1","task":"rr-ssd","batch_id":"从当前任务包复制","payload":{"interactions":[]}}
```

上例只说明包格式，真实用例不能用空交互冒充抽取成功。batch_id绑定协议、任务、输入、Schema、规则、Skill及修复轮次，旧包不能覆盖当前结果。不要手工拷贝旧运行产物作为响应。

显式external模式复用现有SemanticClient或LunaSubprocessClient。支持模型原生Schema时在配置写`"structured_output":"json_schema"`，不会按模型名字猜能力；其他模型继续JSON模式及严格本地Schema/来源验证，失败保留拒绝输出并最多定向修复两轮。若供应商拒绝Schema，应修正配置为JSON模式后使用新身份，不自动重复隐藏调用。

共享CallGate负责实际API请求并发、全局冷却、限额和暂停；TokenBudget原有预留/结算保留。Scheduler持久化成功结果、输入版本、失败原因与修复轮次。输入哈希包括依赖、模型/配置身份、任务Skill、Schema及实现版本；源码或语义输入变化使相关任务失效，测试修改不会使正向图表或G重做。超长输入由已有上下文预算拒绝，不截断证据。本轮不新增动态规划或自动Deep Agents子代理。

`run_manifest.json`绑定协议、执行身份和固定关注点指纹。不同协议目录、无清单的旧调度缓存、mock目录升级成真实运行均拒绝。推荐停用任务永不调用模型/embedding或历史库，报告完整性不依赖推荐。

## 制品

- `packets/*.json`：实际作用域、格式与输出Schema。
- `attempts/<batch>/<round>.json`：已返回的结果与执行证据，包括拒绝结果。
- `case_tasks.json`、`task_outputs/`：持久化DAG与成功结果；JSON含协议、任务、payload及metadata。
- `artifacts/*.json`、`*.metadata.json`：实际独立任务制品、来源、物理数据库与SR逻辑映射。
- 适用表格的`*.md`使用PPT中文字段；组成和SSD输出可编辑`*.dot`，检测到Graphviz时额外渲染`*.svg`。
- `missing_report.json`：G、E、GT、M、完整对应、部分对应诊断、明示/推导GT统计和停用推荐状态。

## 匹配与指标

比较器穷举候选，按同场景、同层级、对象、实际操作、原因和必要条件作语义判断。full才能进入最大一一对应；partial只用于诊断。限制到缺失GT和M后重新分配，防止现有分支抢占缺失命中。“无匹配项返回空列表”不覆盖“实例不存在”。完全重复单元去重；同真值只能得分一次。

抽取只使用Acc=H/N×100%，各英文字母含义写入输出。最小单元：组成名称—类型；SSD整条有序四元组（内含所需属性）；对象—单项操作；服务—单项接口；接口—参数—属性—属性值。GT未知属性不计；程序默认作全部已知属性一致的匹配，可传经过语义核验的一一对应决策；不使用文本相似度阈值。没有人工GT就不报告抽取数值。

异常漏报率`(1-|M∩(GT-E)|/|GT-E|)×100%`；生成有效率`|G∩GT|/|G|×100%`。G、E、GT、M含义在报告中注明，空分母不适用。推荐的两项指标value=null、状态未启用；不生成Q，也不输出伪造的0。

## 验证与迁移

新增验收基线在`tests/fixtures/ppt_v1/acceptance.json`，先于实现冻结。记忆库例子检查8条字段规则及已有空列表分支不覆盖实例缺失；通用变体换名称、编号及字段，防止生产逻辑硬编码。完整测试命令见README。

旧代码未重写历史实验身份或协议。原Skill追加兼容声明；原主控全文在scene-controller/references/legacy-controller.md，原README在README.legacy-v2.md。显式选择旧协议时旧方法保持可复现，其指标不用于本轮新报告。没有迁移旧缓存，没有启动付费评测，也没有向远端推送。
