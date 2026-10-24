# 当前关注点分类

版本：`interaction-concerns-v3`；40个定义，包含两个抽象数据族。以用户2026-10-24分类图为准。设备特性分析暂不纳入；展示类型中的设备适配定义保留，只有明确适用依据时启用。

交互分人类Actor→系统/Service、Service→Service；内外部位置与这两类独立。返回沿原请求解释调用关系。

| 分组 | 关注点 | 稳定键 |
|---|---|---|
| base / service_base | 服务可用性 | `service.base.availability` |
| base / service_base | 输入数据关注点 | `service.base.request_data` |
| base / service_base | 输出数据关注点 | `service.base.response_contract` |
| shared / api_data | 数据完整性 | `api.data.completeness` |
| shared / api_data | 数据格式 | `api.data.format` |
| shared / api_data | 数据合法性 | `api.data.legality` |
| shared / api_data | 数据长度 | `api.data.length` |
| shared / api_data | 数据范围 | `api.data.range` |
| shared / api_data | 数据大小 | `api.data.size` |
| shared / api_data | 数据类型 | `api.data.type` |
| functional / display_interaction | 显示正确性 | `service.display_interaction.display_correctness` |
| functional / display_interaction | 设备适配性 | `service.display_interaction.device_adaptation` |
| functional / query_retrieval | 资源存在性 | `service.query_retrieval.resource_existence` |
| functional / query_retrieval | 数据可见性 | `service.query_retrieval.data_visibility` |
| functional / resource_mutation | 变更业务约束 | `service.resource_mutation.business_constraint` |
| functional / resource_mutation | 持久化一致性 | `service.resource_mutation.persistence_consistency` |
| functional / resource_mutation | 并发一致性 | `service.resource_mutation.concurrency_consistency` |
| functional / resource_mutation | 幂等性 | `service.resource_mutation.idempotency` |
| functional / analysis_generation | 资源消耗 | `service.analysis_generation.resource_consumption` |
| functional / release_activation | 发布前置条件 | `service.release_activation.prerequisite` |
| functional / release_activation | 发布结果一致性 | `service.release_activation.result_consistency` |
| functional / release_activation | 失败恢复 | `service.release_activation.failure_recovery` |
| technology / database | 唯一性约束 | `database.uniqueness` |
| technology / database | 关联一致性 | `database.referential_integrity` |
| technology / llm | 事实与依据一致性 | `llm.grounding` |
| technology / llm | 指令遵循 | `llm.instruction_following` |
| technology / llm | 上下文充分性 | `llm.context_sufficiency` |
| technology / llm | 提示词安全 | `llm.prompt_security` |
| technology / llm | 输出稳定性 | `llm.output_stability` |
| relation / service_relation | 调用顺序 | `service_relation.call_order` |
| relation / service_relation | 依赖一致性 | `service_relation.dependency_consistency` |
| relation / service_relation | 级联操作 | `service_relation.cascade_operation` |
| relation / service_relation | 跨服务数据一致性 | `service_relation.cross_service_consistency` |
| relation / service_relation | 并发一致性 | `service_relation.concurrency_consistency` |
| human / human | 身份认证 | `human.authentication` |
| relation / service_relation | 调用方身份认证 | `service_relation.authentication` |
| human / human | 权限控制 | `human.authorization` |
| relation / service_relation | 调用授权 | `service_relation.authorization` |
| functional / analysis_generation | 执行时限 | `service.analysis_generation.execution_deadline` |
| technology / database | 查询性能 | `database.query_performance` |

基础层只含服务可用性、输入数据族和输出数据族；两族复用完整性、类型、格式、长度、大小、范围、合法性。字段方向与位置分别检查；可选缺省正常，未知规则待确认。

人类身份/权限使用human键，Service调用认证/授权使用service_relation键。适用条件必须有本次接口规则支持。五类按实际操作组合，数据库和LLM只补充本次相关技术特性。

分析执行时限及数据库查询性能须有明示阈值或可判定时序；没有依据不编造。父族不生成独立异常，同一具体失败不重复计分。

旧57项迁移映射仅作历史审计。已移除项的targets为空并标retired_by_user_taxonomy，不能作为活跃输出。
