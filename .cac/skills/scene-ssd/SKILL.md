---
name: scene-ssd
description: 根据规范化用例和架构映射抽取、构造、校验 RR/SR/AR 交互时序及融合 SSD。
metadata:
  title: Scene SSD
  version: "2.0.0"
---

# Scene SSD

职责限于 SSD 交互语义和时序图，不负责需求抽取、关注点审核或最终组装。

当前入口使用 rr-sr-concern-gap-v2，兼容 rr-sr-ssd-identification-v1：IR=RR。RR 人与 UI/外部调用方与逻辑接收边界；SR 边界到明确服务接口及有依据的 SR 服务间交互。
RR 与 SR 一对多展开，保留分支、调用顺序及逐层返回。AR 微服务仅为融合图参考，不参与异常分析。
选择对象、填写字段后一次确认可属于同一次请求的输入准备；保留各步骤及数据锚点，不仅凭编号步骤另造调用或重放整个 SR 副作用流程。只有本层原文明示独立请求或中间系统交互，才拆成多个发起交换。含义不明确时先确认，不用补造接口消除来源审查意见。
分别保存 RR→多个 SR→多个 AR→多个软件实现接口的有证据分解图，以及 RR 消息→多个 SR 消息的请求/返回嵌套；两者不是同一关系。复用单元可有多个有依据父级，不要求用例编号一致。无证据的 AR/实现拆分不补造，标记待补充。
内部及外部数据库必须转换为 SR 资源服务实际生命线和消息端点，保留物理来源映射，不虚构接口路径。
每个分析挂载必须引用真实同层交换/消息。缺少交互或不明确层级时输出缺口，禁止生成后补锚点。
每个正常交换提取 operation_kinds（read/create/update/delete/display/process/publish/external_call，可多选），仅记录本交换实际执行的操作，不能继承服务在其他交互中的写能力。data_relations 只记录原文明确的 reference/foreign_key/cascade/unique_key，保存具体关联对象和引用；不能从关注点名称猜测缓存、隐式写入、联查或外键。tools 用这些正向特征确定性挂载已有关注点，全部关注点定义始终保留。
逻辑 UI/接收边界及数据库服务化已获授权；其他组件/调用边增删先交用户确认原文依据和图上位置。
data_relations 同时保存 evidence_quote，逐字引用明确表达关联类型的正向契约；仅有字段名或 ID 不证明唯一键、外键或级联。身份挂载按当前交互调用边界区分：UI 为人类身份/权限，接收边界为外部调用方身份/权限，内部调用不自动归人类。外部 LLM 访问本系统的权限仅挂入站方向，下游模型保留可用性、契约和五项质量关注点。
SR 正常流程明确调用已命名参与者时，不因缺少 URI 删掉交互或产生虚假模型阻断；接口路径、实现细节待确认，仍在新增调用生成前提交原文及位置确认。

输入：通过模型校验的 `scene_model.json`、接口/实现映射及来源证据。Agent 识别逐步调用关系、参与者、请求/响应字段和逐层返回；工具生成并校验 RR、SR、AR、fused SSD JSON/SVG/PNG。顾客/商家到系统只表达业务动作；SR API 才包含接口与参数；Implementation API 与 AR 微服务按已确认模型映射。不得为了画图虚构调用或返回。
本地所有权／状态校验不是自动返回的布尔字段，保存或更新的值不自动成为返回数据；明确资源写入值进入请求数据，返回只保留真实传输内容。未指明资源目标的服务本地操作保留在当前职责和正向契约中，不能猜测成某张数据库的调用。

正常原文明示查询/读取而协议结构缺省时，允许有源查询语义推导的逻辑返回对象。保留 derived_response_data 的原文引句、引用、推导理由和 protocol_structure_unknown=true；仅标记已有 read 交换的返回消息，不能增加调用、JSON 字段、类型或布尔结果。SSD JSON 保存 derived_data，图中明确显示“查询语义推导（协议结构待确认）”，不把逻辑标签冒充原文协议定义。

新协议由 scene-pipeline 的 interaction-model/build_ssd 生成并校验分析图及用例分解图，输入规范见 ../scene-extract/references/rr_sr_input_schema.md。`references/diagrams_v2/interaction_concern.md` 与 generate-ssd/validate-ssd 为历史兼容约定，不用于本轮候选筛选或数量限制。本 Skill 不调用其他 Skill。

有文档证据时，一个 AR 实现可以包含多个 dependencies；分别记录数据库、内部服务、外部服务，不能由数据库默认依赖覆盖支付或物流调用。每项保存 target_node_id、direction、operation、source_step_index 和 source_refs。二级服务调用使用 caller_node_id 引用已有实际服务；incoming 表示外部回调。依赖请求/返回必须绑定同一交换与调用，原始业务步骤和执行顺序分别保存。明确空依赖列表表示无依赖，不补默认数据库。不依据操作名称猜测依赖。

当前RR交互可保存business_service_roles，每项仅service_type、同层正向evidence_quote/source_refs、真实mapped_sr_local_ids。tools校验SR交互属于本RR展开，并保存rr_business_service_roles与关注点挂载追溯。角色是逻辑职责，不新增部署组件或请求；RR/SR异常独立生成。participants由真实交互双方补全，并由scene-participants核实原Actor漏写。cancellable只表示正常可选能力，不自动挂异常。
