# SSD 交互结果、共用外部服务与业务报告

当前分析范围版本为 `interaction-shared-services-v1`。`scene-workflow-v5` 运行协议、`ssd-case-v1` 用例结构和原命令保持不变。业务链路由测试侧负责：当前流程不再抽取依赖、生成链路异常、执行链路匹配或将链路测试计入漏报分母。旧链路、架构快照及报告保留只读，读取不触发模型或历史迁移。

## 执行与定位

结构化输入按用例执行 `ssd-prepare → ssd-resolve → ssd-generate → ssd-compare`。原始 RR/SR 文档先转换成相同 SSD。每个成功用例随后触发 `shared-services-merge` 脚本；一个用例失败不会阻塞其他用例发布或服务汇总。

发送方、操作、数据、接收方沿用稳定 step_id。操作属性保存实际 CRUD：人工优先，其次明确声明、语义与 HTTP 方法；GET 为 R、DELETE 为 D、PUT/PATCH 为 U，POST 按实际业务判断。没有 RR API 仍可运行，api_id 保持空；字段约束可来自准确的正向原文，不把 RR Authorization 冒充未声明该属性的 SR 接口。请求、响应与存储字段分别定位，不复制全部实体属性。

第二层名称为“第二层：功能类型关注点”，CRUD 子类与操作规则不变。确定性范围、类型等数据场景继续走脚本。身份认证等固定场景逐项保留，由 LLM 根据当前用例、步骤和对象写分析，可补充适用场景。G 只读取正向材料；E、GT 独立识别，IR/SR 同一失败优先 SR 并保留所有出处。

## 外部服务先生成，再归并

服务可用性在实际外部请求的接收方生成，不在本地 action、返回或人类 Actor 上重复挂载。项目按同一实际服务身份合并关注点，再按故障类型合并场景。无法确认身份时保留待定位，不靠同名强合并。

三方分别合并后比较。每个合并记录保存成员用例、步骤、原记录及修订、失败条件、业务分析、处理预期、原文引用与成员判定。不同故障不合并；成员中 full/partial 均算已覆盖。工作台“交互级”下分“用例交互”和“共用外部服务”，可展开回到对应交互。原架构结果只作带来源标识的兼容投影。

普通交互按用例计分；可用性副本只在调用处展示，项目按合并单位计一次。项目指标分别累计关注点、场景的分子分母。`coverage-any-confirmed-v2` 允许多对多，full、partial 均覆盖；历史指标冻结。纯展示改名不升级无关模型语义。

## 编辑与原文

保留现有三方表、步骤导航与功能栏，支持逐格编辑、补录、清格、删行、框架关注点补漏和匹配草稿。保存检查 base_revision，失败或冲突保留草稿；重跑保留人工增删改。共用服务修订还检查全部调用成员版本；身份及原始调用由脚本维护。历史视图不可编辑。

每条记录在页内弹窗阅读最初始 RR/SR Markdown，支持格式渲染、章节、行高亮及源码切换。GT 区分测试出处和关联需求，不把需求引用冒充测试来源。

人工新增或修订的记录可在编辑弹窗“来源（原文出处）”中选择本用例快照内的文档、填写起始行与结束行并预览高亮，保存后“查看原始出处”直接跳到对应行。出处按文件自身行号（从 1 开始）计，单条最多 1001 行；引文留空时取所选行原文。手工出处标记 `origin=manual` 并在表格与来源列表中注明“人工补录”。保存校验只接受快照内文档和合法行号，因此不会留下点不开的出处。

结果页出处使用快照文档 ID，导入来源使用各自来源 ID。原文接口对快照 ID 按内容完全一致且唯一的来源文件解析；内容不同或同时存在不同副本时拒绝定位，不按文件名猜测。

一条记录常有多个出处，原文弹窗按“RR/SR 在前、其余保持记录顺序”稳定排列，并提供“跳到人工补录出处”直接定位手工引用，便于在众多机器出处中核对人工补充的依据。

## 一个离线业务报告

标题固定“需求异常场景识别结果”，使用实际用例数并标明未完成用例。`business-adoption-v3` 三项按场景统计，E 仅作参考，不额外扣除：

1. G ∩ 测试逆向：每条被任一 GT 的 full/partial 确认覆盖的 G 只计一次。
2. G 有、测试逆向没有：只收已完成识别、生成、匹配且明确未覆盖的 G。
3. G 没有、测试逆向有：只收相关生成、匹配完成且未被任何 G 确认覆盖的 GT。

每项先列各用例的数量和明细/依据入口，展开按步骤和对象关注点展示 E/G/GT。末尾单列共用服务，明确“用例合计＋共用服务＝本项总数”，关联所有调用用例；不增加虚假用例。待确认、未挂载及未完成项单列原因。

第一、三项只读；第二项可独立采纳/撤销、写意见、预览业务补充 GT。保存 HTML 后重开可继续，原文弹窗可断网阅读；一个文件回导预览并选择应用。服务端仅从冻结 G 构造 GT，标记“业务审核补充”，不冒充测试原文；成员版本冲突不覆盖，重复导入不重复新增。

仍读取旧 business-adoption-v2：交互反馈可预览应用，业务链路反馈标记不适用于当前范围；旧架构只读，需重新导出共用服务报告再审核。原内容不会被静默改写。

## 入口与存储

继续使用 `ssd-review/summary、export、preview、apply`。导出默认全部用例及共用服务，可用 scopes、case_ids、anchor_ids、record_ids、item_ids 精确选择。草稿须先保存，不静默导出旧版本。

- `ssd-results`：用例索引；`results/{case}/editor、revisions`：交互编辑和历史。
- `project-results`：当前交互/共用服务及项目汇总；`project-results/shared_services/editor、revisions`：共用服务修订。历史 business_chain/architecture 的 GET 仍可读，POST 修订被拒绝。
- 共用服务保存于 `shared_service_results/`，不迁移或删除原 `project_results/`、`ssd_results/`。
- 终端 `scene.py --local --data-dir DATA results --project ID --analysis-scope all|interaction|shared_services` 与 HTTP 使用同一服务。接管操作见[终端 Code Agent](terminal-code-agent.md)。

## 验收

执行 make check、前端生产构建、便携资源检查。用真实五用例项目副本验证增量生成、合并与报告回导，17 用例夹具验证动态数量。旧历史与原项目草稿不用于试写；模拟测试不代替真实模型运行，原生 Windows 验收状态单独报告。

## 同事交接的核心 JSON

项目可混用原始 `SysOperation.json`、按目录拆分的 `main-success.json` 以及合并的 `authoring-case.json`。分件文件同目录读取 `existing-exceptions.json`、`extension-mapping.json`、`test-exceptions.json`，项目根目录提供参与者索引 `architecture.json`。导入按用例 ID 决定输入，冲突用例可独立排查。

单用例命令支持 `export-core --input INPUT --output NEW_DIRECTORY [--case ID]`。输出可直接重新导入，并包含 `source-map.json`。清单中的 `file` 与 `json_pointer` 指向导出时读取的原输入。四元组仍为发送方、操作、实体和接收方，v2 主成功文件的 `declared_fields` 保存额外的接口字段声明。实体异常用 `entity_id`、`attribute` 标识，接口异常用 `parameter.name`、`parameter.location`、`parameter.direction` 标识。扩展映射一条对应一个测试扩展，`bindings` 记录已确认的独立挂载。

E 和 GT 独立导入，保留实际失败步骤。同用例同实体同属性的约束在不同行可以相互对应。接口字段继续按所属步骤和字段方向区分。当前规则自动生成 CRUD 功能类型关注点，展示、分析生成、发布功能类型暂不生成，技术扩展仅自动挂载数据库特殊字符。未提供 GT 时生成结果可查看，相关覆盖指标标为未评估。
