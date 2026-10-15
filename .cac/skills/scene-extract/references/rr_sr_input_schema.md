# RR/SR 正常交互输入协议

新输入/输出声明 `query_data_policy=logical-query-results-v1`。原文明示正常 read/query 且协议结构未给出时，允许 `response_fields` 中的逻辑查询结果，须逐项保存 `derived_response_data=[{field, derivation_reason, evidence_quote, source_refs, protocol_structure_unknown:true}]`；仅绑定该同层 read 交换的原文正向查询。明确返回字段不标推导；不能推导 JSON 成员、类型、布尔校验结果或新调用。独立来源检查使用 `source_kind=explicit|query_semantics`，工具验证每项推导的字段、查询引句、引用和实际返回映射，不自动接受旧模型。

原文角色明确区分 RR、SR；IR 等同 RR。先独立抽取正常与普通可选流程，不附加异常集合。测试和检查器输出不在生成输入中。

`use_case_hierarchy` 是拆分单元列表，每项包含：

- `unit_id`：包内唯一标识，不依赖项目编号规则。
- `source_id`、`name`：原文用例或接口编号/名称；没有编号时使用精确 `文档名:L行号` 锚点，不能编造业务编号。
- `layer`：RR、SR、AR、IMPLEMENTATION。
- `parent_ids`：上一个层级的单元 ID；RR 为 []。允许一对多以及有证据的单元复用，禁止跳层、未知父级和循环。
- `source_refs`：原文文件名、整数行号和完整章节路径。RR/SR 用例必须有本层原文引用。

例如，一个 RR 可包含 SR-query、SR-filter；SR-query 可包含多个 AR；各 AR 可包含多个实现接口。当前项目即使数量相同，也不强制其他项目一一对应。没有 AR 或软件接口证据时保留已有层级，记待补充，不生成假的下层单元。

`exchanges` 仅记录 RR/SR 正常或普通可选的请求交换，每项包含 `local_id`、`requirement_layer`、`hierarchy_unit_id`、交互双方、操作、字段、绑定契约和引用。SR 必须指定 `parent_rr_local_id`；嵌套 SR 调用还必须指定 `parent_sr_local_id`，且父消息目标等于子消息调用方。工具独立校验用例分解与消息嵌套的一致性并构造逐层返回。

人类actor本身不设置`boundary_role`；RR交互终点的UI使用`boundary_role=ui`。SR从同一个UI或接收边界进入有原文依据的入口接口，再展开内部服务调用，不能为修复嵌套错误删掉入口交互。每条SR交换必须引用SR原文，RR到SR的映射不能替代本层来源。校验失败应精确给出交换ID、双方、声明层级和实际来源；定向修复保留已正确的消息及父子关系。

每个交换必填 `operation_kinds`，按本交换原文语义取 read/create/update/delete/display/process/publish/external_call（可多选）。只读调用不能继承其他流程的修改能力。`data_relations` 默认为 []；有原文依据时每项保存 `object`、`relation`（reference/foreign_key/cascade/unique_key）及 `source_refs`。正常流程中的关联对象和正向契约用于确定性关注点路由，不新增调用边，也不从异常或关注点名称猜测隐式写、联查、外键或级联。全部关注点注册始终保留，未知操作特征需修正模型，不能手工猜分类。

`normal_scenarios` 同样指定同层 `hierarchy_unit_id`，保留原文步骤。它们不参与异常评估。AR/实现单元仅进入追溯图，不进入异常挂载、生成或指标。
data_relations 每项另保存 evidence_quote，逐字引用表达该关系类型的正向契约，不能仅引用对象/标识符并推断唯一键、外键或级联。未知关系不填；未知调用 URI 保持待确认，不阻断有原文参与者及正常调用依据的 SR 交换。

同名服务的 SR 接口和 AR 内部实现分别记录角色、层级及来源。数据库以保留物理来源的 SR 资源服务生命线参与交互；已有包装服务优先复用，不虚构 HTTP 路径。
组件使用唯一 `component_id`，消息通过 `from_component_id/to_component_id` 关联。同名 SR/AR 角色可以有不同 ID，不能仅凭显示名关联消息。资源服务的 `physical_resource_id` 指向包内真实物理资源 ID，由工具转换为全局稳定 ID 后复用。

`model_gaps` 只记录妨碍真实分析锚点的对象、交互、层级和来源矛盾。未知响应、恢复、默认展示值、AR 实现细节写入 `pending_details`，不因其缺失删候选或影响异常识别判定。

历史 `input_schema.md`、单对象 `architecture.sr` 和 `layer_use_case_ids` 只作为兼容输入提示，不限制新模型数量，也不能代替有证据的拆分图。

输入种子只含业务身份和架构提示。对于 SR 编号与 RR 不共享前缀的项目，可用 `source_use_case_ids: {"RR": ["R-1"], "SR": ["S-4", "S-9"]}` 指定需要独立抽取的原文章节，或使用 `architecture.sr` 列表中的多个 `design_use_case_id` 提供定位提示。提示不创建拆分单元；模型仍必须读取对应原文、给出层级和父级证据。架构提示不能包含检查器或测试异常。

当前RR交互可保存business_service_roles，每项仅service_type、同层正向evidence_quote/source_refs、真实mapped_sr_local_ids。tools校验SR交互属于本RR展开，并保存rr_business_service_roles与关注点挂载追溯。角色是逻辑职责，不新增部署组件或请求；RR/SR异常独立生成。participants由真实交互双方补全，并由scene-participants核实原Actor漏写。cancellable只表示正常可选能力，不自动挂异常。
