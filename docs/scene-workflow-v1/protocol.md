# scene-workflow-v1 输入与输出

所有正式任务结果以 `{protocol,task,payload,metadata}` 保存。外部结果必须绑定完整任务包batch_id。JSON Schema使用Draft2020-12、必需字段和additionalProperties=false；只有通过Schema、证据与方法约束的结果才提升为成功缓存。

## 任务边界

| Skill任务 | 输入 | 输出及处理 |
| --- | --- | --- |
| components | 正向RR、SR的DOCUMENT数组 | components名称/类型/所属边界/来源状态；relations有据关系 |
| rr-ssd | 本用例正向RR | 有序interactions，RR基本四元组，含请求和返回 |
| sr-ssd | 本用例正向SR | 有序interactions，SR基本四元组、接口身份和字段约束 |
| object-operations | components、基础rr-ssd、测试操作投影 | objects名称/单项supported_operations并集，确定性程序执行 |
| api-map | 正向SR | services名称/interfaces接口ID、名称、方法、地址 |
| api-parameters | 正向SR | apis身份/地址/parameters各位置字段属性 |
| concern-match | 组成、基础SSD、能力表、API两表、富化交互、57定义 | matches交互/双方或数据对象/concern_key/依据/具体规则；pending |
| exception-generate | 正向组成/SSD/API、只含本次操作能力的富化交互、匹配结果、57定义 | scenarios G、pending；不读取E/测试GT/比较 |
| existing-extract | 当前版本RR/SR已有分支、57定义 | 明示scenarios E |
| gap-compare | left G、right E、purpose G_E | decisions所有候选对、missing完整缺失场景M；不读取测试GT |
| gap-recommend | 空对象 | enabled=false，status=未启用；不生成Q |

具体必需字段与字段类型以[Schema目录](schemas/)及`contracts.py`为准。人工GT文件是payload，不需要来源引用，但结构应与相应产物一致。

### 文档和字段

DOCUMENT含source_id、name、channel、lines[{number,text}]，保留真实行号。先去除明示“变更前”段；正向投影排除异常/扩展块和错误响应，已有异常通道保留当前版本这些分支。原始Markdown文件不变。表格中的混合异常叙述会保守排除，非标准文档请检查任务包，不假设正则分段可以理解所有自然语言。

每条基础交互包含id、case_id、sequence、layer、parent_id、sender、operation、data、receiver、direction、api_id、source_refs。parent_id只指同层请求/交互；跨层对应另存rr_sr_links，不用相邻顺序猜测。

双方含name、position、source_refs；操作含name、kinds、sequence、optional；数据sequence内每个PARAMETER含name、location（header/path/query/body/response/business）、data_type、required、default、constraints、source_refs。约束逐项含id、kind、value、status、source_refs。返回数据只分析response字段；API-M-IF2之类抽象身份不是数据库，不补造HTTP方法或URI。

富化交互附component_id、resource_service物理映射、接收方supported_operations、associated_api、双方及数据concerns；RR/SR links必须有依据，否则pending。组成原始物理数据库不被删除；逻辑SR资源服务不表示真实新增部署。

异常scenario含稳定id、case/interaction/layer、object、operation、cause、conditions、concern_key、field、rule_id、source_status、derivation、source_refs、steps。steps含normal_context、trigger、documented_follow_up[{action,source_refs}]。后续未知为空，不能发明错误码或恢复动作。

字段规则及有据集合查询候选由确定性工具生成，tool_rule_coverage提供给生成任务；模型只补充其他有具体规则的双方/操作异常，避免依赖模型猜测精确字段表达。

请求与返回分别检查必填缺省、类型、枚举、格式、长度、大小、范围等每个独立已知约束。可选缺省正常；必填字段已提供但规则未知写pending，不生成虚构异常。明确集合查询独立产生no_matching_records；指定实例不存在是不同原因。普通查询服务与数据库逻辑服务分别使用注册表已有的两种资源存在性；物理外部数据库封装也使用数据库定义。

## 内部阶段

内部提示规则在`prompts/`，不是额外公开Skill：test-operation-project只整理对象/操作且引文严格等于操作名；test-ground-truth只依据测试描述、正常API约束与既定框架，必须引用测试依据，可保存framework_inferred并计分；interaction-align整理有据别名/跨层对应；semantic-compare仅用于GT_G、GT_E语义核验。不能回退到已有异常Skill。

G不能看到测试异常行、错误码或预期结果；能力表与关注点任务可见的测试证据已经投影。GT/E不回流G。缺失报告依赖G/E/对应关系，不等待GT。分析完成和评测完成单独记录。一个用例的阶段失败只阻塞其依赖链。

## 计分与语义核验

抽取只有Acc（抽取准确率）=H（命中的真值单元数）/N（真值单元总数）×100%。GT为人工真值集合。

| 产物 | 最小匹配单元 |
| --- | --- |
| 系统组成 | 名称—组成类型 |
| RR/SR SSD | 整条有序发送方、操作、数据、接收方；GT明确属性包含在四元组中，不独立拆分 |
| 对象操作 | 名称—单项操作 |
| API映射 | 服务—单项接口，已知方法/地址；抽象接口以ID标识 |
| API参数 | 接口—参数—属性—属性值；类型、必填性、每条独立约束分别计数 |

同场景、同层级，SSD还须同序；同一单元GT明确属性全部满足才命中。待确认不能命中已知GT；GT未知属性不纳入计分；重复不加分。无GT为未评测，明确空分母为不适用。

不提供语义决策时只比较精确规范值与GT明确属性，不伪装为语义核验。需要人工/外部语义核验时，先运行计分得到truth_units/extracted_units，再提供已确认的full/partial/unmatched决策；只full进入最大一一匹配。可复用格式：

```json
{"protocol":"scene-workflow-v1","task":"components","extracted_hash":"上次计分input_identity中的值","truth_hash":"同上","decisions":[{"left_id":"truth_unit_id","right_id":"extracted_unit_id","status":"full","reason":"已人工确认同一名称与组成类型"}]}
```

人工即时确认的原始决策数组也可传入；跨输入复用必须用绑定格式。校验未知ID、重复候选、状态及SSD场景/层级/顺序，不以字符串相似度自动确认。

异常计分：缺失漏报率=(1-|M∩(GT−E)|/|GT−E|)×100%，生成有效率=|G∩GT|/|G|×100%。完整语义一一对应才是交集，partial仅诊断；空分母不适用。GT明示项和框架推导项分开报告。Q未启用，采纳率与误报率都为未启用而非0。

## 缓存和执行

运行目录协议、mock/真实执行来源、任务契约、Skill/内部提示、注册表、语义代码、输入及配置模型共同决定身份。旧协议结果不能进入新流程。各任务依赖只使用已验证payload进行下游失效判断；元数据变化不强迫下游模型重跑。修改测试异常文字会重做内部投影/GT，但投影payload不变时正常SSD、匹配和G复用。

全局并发许可、限流退避、token账本、配置错误断路及独占运行锁保留。初次拒绝后最多两轮修复，外部超时/未知用量不当作有效语义结果，不自动无限重试。恢复在同一目录进行，不清空修复预算。
