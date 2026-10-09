# SR 主关注点注册表与路由

Tools 中的结构化 CONCERN_DEFINITIONS 是候选 key、标签、主体、证据类型和活跃状态的唯一来源；本目录中的单项 Markdown 只补充适用/排除规则和例子。新矩阵记录 registry_version 与 analysis_layers，旧注册表矩阵必须重新规划。
当前注册表 sr-evidence-2，共 56 个活跃关注点；新增内部依赖可用性、业务流程取消与中止两项。三角色生成器保留未审查候选；本目录的适用/排除规则不构成新流程的候选删除门。

默认 analysis_layers=["SR"]。融合 SSD 用于把 SR 交互和实现证据关联起来，AR 实现消息不自动变成 SR 交互候选。内部数据库由模型中的 inferred SR 资源服务作为逻辑关注主体；物理数据库保持 AR，不伪造实际部署服务或 HTTP 路径。候选分别记录 concern_layer、exchange_layer、candidate_id、端点、消息、请求/响应载荷方向和来源。

## 活跃关注点族

- common.timeout：实际 SR/可选 AR 请求—响应交换。
- human.authentication、human.authorization：绑定关联的 Use Case 人类 Actor；不路由笼统输入行为。
- api.data.*：API 输入七项（完整性、类型、格式、长度、大小、范围、合法性）；请求与响应载荷分别形成候选。只有契约/需求提供约束时才能生成字段异常。
- external_service.*、external_database.*、external_llm.*：依调用方向路由。LLM 另有语义正确性、指令遵循、提示词安全、上下文完整性和输出稳定性。
- service.<type>.*：五类 SR 业务职责；类别取自本 Use Case 的 SR Service/API 映射，而非名称或 AR 技术职责。
- internal_database.*：十项内部资源关注点。默认作为 SR 资源服务关注点，AR 物理访问仅是证据；显式开启 AR 时才按 AR 层级分析物理 DB。
- service_relation.*：直接 SR 调用或有需求/设计证据的服务依赖。非调用关系使用 relation_id，不补造 SSD 消息。
- [service.dependency.availability](service__dependency__availability.md)：有文档证据的内部服务调用边；实现调用只提供实际位置，不造跨用例 SR 关系。
- [service.workflow.interruption](service__workflow__interruption.md)：有文档证据的取消/中止事件及状态，记录副作用与互斥成功步骤边界。

服务业务类别及对应 key：

| SR Service 分类 | 活跃关注点 |
| --- | --- |
| display_interaction | service.display_interaction.display_correctness、service.display_interaction.render_performance；设备适配暂不启用 |
| query_retrieval | service.query_retrieval.resource_existence、service.query_retrieval.result_correctness、service.query_retrieval.data_visibility |
| resource_mutation | service.resource_mutation.business_constraint、service.resource_mutation.persistence_consistency、service.resource_mutation.concurrency_idempotency |
| analysis_generation | service.analysis_generation.result_correctness、service.analysis_generation.execution_deadline、service.analysis_generation.resource_consumption |
| release_activation | service.release_activation.prerequisite、service.release_activation.result_consistency、service.release_activation.failure_recovery |

旧 human.input_data、internal_service.parameter_validity、internal_service.* 通用旧项及 ar_service.* 技术草案不属于活跃注册表；不能进入新候选或异常预测。未知 SR 分类只保留通用节点/数据/超时关注点并生成分类待确认，不路由类型专属项。

## 语义边界

- 查询遗漏、结果错误、分页重复 → service.query_retrieval.result_correctness。
- 用户/租户/权限范围越界或错误暴露 → service.query_retrieval.data_visibility。
- 目标资源不存在 → service.query_retrieval.resource_existence。
- API 字段缺失或格式/范围错误 → 相应 api.data.*；不创建泛化“参数有效性”。
- 内部业务服务不可用 → service.dependency.availability；第三方支付/物流不可用 → external_service.availability；数据库不可用 → 对应数据库关注点，不能用单一数据库依赖替代其他调用。
- 取消支付或流程中止 → service.workflow.interruption；不与服务故障合并，不执行取消后的互斥成功步骤。
- 资源变更的一次候选可以有多个原子 finding，例如重复请求与并发冲突；标签采用“并发与幂等性”关注点体系。
- 超时三个影响维度仅用于 common.timeout；缺证据时留空/待需求确认，不写 unknown 冒充已判断。
- pending_review 是唯一的新候选初始状态。applicable 必须有 finding；not_applicable 必须有排除依据；needs_requirement 必须说明缺少的证据。

每个关注点的独立知识文件按 load-concern --key <key> 加载。SR 服务文件仍沿用历史目录名时由 loader 做兼容映射。
