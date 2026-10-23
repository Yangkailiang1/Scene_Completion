# Service关注点分层与迁移对照

注册表版本：`service-concerns-v2`。当前共有45个定义（包含抽象基础族），不固定定义数量。旧57项仅用于迁移审计。

所有被调用Service统一继承基础层；内部/外部保留位置和信任边界。五类功能由本次操作决定，可以组合；数据库和LLM只添加仍未覆盖的技术特性。

## 使用规则

- 基础层：服务可用性、条件性身份认证/授权、请求数据、返回契约/数据、业务结果。请求和返回共享七类数据定义。
- 功能层：展示交互、查询检索、资源变更、分析生成、发布生效；从SSD本次实际操作选择，不使用其他支持能力替代。
- 技术层：数据库唯一性/关联完整性/事务原子性/隔离保证；LLM事实依据/指令遵循/上下文充分性/提示词安全/允许范围内稳定性。
- 条件和关系：时限需明确数值/单位或可判定时序；设备、部署环境和调用边提供规则依据，不能补造设备或额外服务。普通取消正常，只检查违反明确状态或清理要求的情况。
- 适用、待确认、不适用分别输出；匹配到一个族不等于已有确定异常。未知类型、权限策略、期限或模型波动标准不填默认答案。
- 数据的接口、存储、上下文作用域和字段方向/位置分别处理；返回字段缺失与业务结果错误、上下文字段缺失与语义上下文不足分别判断。
- 父层与细分层命中同一交互/对象/具体原因/条件及作用域时，只保留一个失败单元和全部继承来源。不同具体原因即使同一关注点也不合并。

## 活跃定义

| 层次 | 标识 | 名称 | 父级 | 激活依据 |
| --- | --- | --- | --- | --- |
| 基础层 | `service.base.availability` | 服务可用性 | 基础/独立条件 | 本次实际调用或字段契约 |
| 基础层 | `service.base.authentication` | 调用方身份认证 | 基础/独立条件 | authentication |
| 基础层 | `service.base.authorization` | 访问授权 | 基础/独立条件 | authorization |
| 基础层 | `service.base.request_data` | 请求数据正确性 | 基础/独立条件 | 本次实际调用或字段契约 |
| 基础层 | `service.base.response_contract` | 返回契约与数据正确性 | 基础/独立条件 | 本次实际调用或字段契约 |
| 基础层 | `service.base.result_correctness` | 业务结果正确性 | 基础/独立条件 | result |
| 共享数据细分 | `api.data.completeness` | 数据完整性 | service.base.request_data、service.base.response_contract | 字段明示属性 |
| 共享数据细分 | `api.data.format` | 数据格式 | service.base.request_data、service.base.response_contract | 字段明示属性 |
| 共享数据细分 | `api.data.legality` | 数据合法性 | service.base.request_data、service.base.response_contract | 字段明示属性 |
| 共享数据细分 | `api.data.length` | 数据长度 | service.base.request_data、service.base.response_contract | 字段明示属性 |
| 共享数据细分 | `api.data.range` | 数据范围 | service.base.request_data、service.base.response_contract | 字段明示属性 |
| 共享数据细分 | `api.data.size` | 数据大小 | service.base.request_data、service.base.response_contract | 字段明示属性 |
| 共享数据细分 | `api.data.type` | 数据类型 | service.base.request_data、service.base.response_contract | 字段明示属性 |
| 基础层 | `service.contract.compatibility` | 接口契约兼容性 | service.base.response_contract | compatibility |
| 功能层 | `service.display_interaction.display_correctness` | 显示正确性 | service.base.result_correctness | result |
| 功能层 | `service.display_interaction.device_adaptation` | 设备适配性 | service.base.result_correctness | device |
| 功能层 | `service.query_retrieval.resource_existence` | 资源存在性 | service.base.result_correctness | resource_lookup |
| 功能层 | `service.query_retrieval.result_correctness` | 查询结果正确性 | service.base.result_correctness | result |
| 功能层 | `service.query_retrieval.data_visibility` | 数据可见性 | service.base.authorization | authorization |
| 功能层 | `service.resource_mutation.business_constraint` | 变更业务约束 | service.base.result_correctness | business |
| 功能层 | `service.resource_mutation.persistence_consistency` | 持久化一致性 | service.base.result_correctness | persistence |
| 功能层 | `service.resource_mutation.concurrency_consistency` | 并发一致性 | service.base.result_correctness | concurrency |
| 功能层 | `service.resource_mutation.idempotency` | 幂等性 | service.base.result_correctness | idempotency |
| 功能层 | `service.analysis_generation.result_correctness` | 处理正确性 | service.base.result_correctness | result |
| 功能层 | `service.analysis_generation.resource_consumption` | 资源消耗 | service.base.result_correctness | resource_limit |
| 功能层 | `service.release_activation.prerequisite` | 发布前置条件 | service.base.result_correctness | release |
| 功能层 | `service.release_activation.result_consistency` | 发布结果一致性 | service.base.result_correctness | result |
| 功能层 | `service.release_activation.failure_recovery` | 失败恢复 | service.base.result_correctness | recovery |
| 技术扩展 | `database.uniqueness` | 唯一性约束 | service.resource_mutation.business_constraint | unique |
| 技术扩展 | `database.referential_integrity` | 关联完整性 | service.base.result_correctness、service.query_retrieval.result_correctness、service.resource_mutation.business_constraint | reference |
| 技术扩展 | `database.transaction_atomicity` | 事务原子性 | service.resource_mutation.persistence_consistency | transaction |
| 技术扩展 | `database.isolation` | 事务隔离保证 | service.base.result_correctness、service.query_retrieval.result_correctness、service.resource_mutation.concurrency_consistency | isolation |
| 技术扩展 | `llm.grounding` | 事实与依据一致性 | service.base.result_correctness、service.analysis_generation.result_correctness、service.query_retrieval.result_correctness | grounding |
| 技术扩展 | `llm.instruction_following` | 指令遵循 | service.base.result_correctness、service.analysis_generation.result_correctness、service.query_retrieval.result_correctness | instruction |
| 技术扩展 | `llm.context_sufficiency` | 上下文充分性 | service.base.request_data | context |
| 技术扩展 | `llm.prompt_security` | 提示词安全 | service.base.result_correctness、service.analysis_generation.result_correctness、service.query_retrieval.result_correctness | prompt_security |
| 技术扩展 | `llm.output_stability` | 输出稳定性 | service.base.result_correctness、service.analysis_generation.result_correctness、service.query_retrieval.result_correctness | stability |
| 条件层 | `common.timeout` | 超时关注点 | 基础/独立条件 | timing |
| 关系约束 | `service_relation.call_order` | 调用顺序 | 基础/独立条件 | relation |
| 关系约束 | `service_relation.dependency_consistency` | 依赖一致性 | 基础/独立条件 | relation |
| 关系约束 | `service_relation.cascade_operation` | 级联操作 | 基础/独立条件 | relation |
| 关系约束 | `service_relation.cross_service_consistency` | 跨服务数据一致性 | 基础/独立条件 | relation |
| 关系约束 | `service_relation.idempotency` | 幂等性 | 基础/独立条件 | relation |
| 关系约束 | `service_relation.concurrency_consistency` | 并发一致性 | 基础/独立条件 | relation |
| 条件层 | `service.workflow.interruption` | 取消与中止后的状态及副作用 | 基础/独立条件 | recovery |

## 旧57项逐项对应

多目标表示按具体原因细分，不表示全部同时激活。尤其旧LLM“可用性”中的认证失败，应迁至认证；版本/结构/字段错误按契约及七类数据关注点细分。

| 旧标识 | 旧名称 | 新目标 |
| --- | --- | --- |
| `api.data.completeness` | 数据完整性 | `api.data.completeness` |
| `api.data.format` | 数据格式 | `api.data.format` |
| `api.data.legality` | 数据合法性 | `api.data.legality` |
| `api.data.length` | 数据长度 | `api.data.length` |
| `api.data.range` | 数据范围 | `api.data.range` |
| `api.data.size` | 数据大小 | `api.data.size` |
| `api.data.type` | 数据类型 | `api.data.type` |
| `common.timeout` | 超时关注点 | `common.timeout` |
| `external_database.availability` | 数据库服务可用性 | `service.base.availability` |
| `external_database.query_performance` | 查询性能 | `common.timeout` |
| `external_llm.access_permission` | 访问权限 | `service.base.authorization` |
| `external_llm.availability` | 外部模型可用性 | `service.base.availability`、`service.base.authentication` |
| `external_llm.contract` | 外部接口契约 | `service.base.response_contract`、`service.contract.compatibility` |
| `external_llm.quality.context_completeness` | 上下文完整性 | `llm.context_sufficiency` |
| `external_llm.quality.instruction_following` | 指令遵循 | `llm.instruction_following` |
| `external_llm.quality.output_stability` | 输出稳定性 | `llm.output_stability` |
| `external_llm.quality.prompt_security` | 提示词安全 | `llm.prompt_security` |
| `external_llm.quality.semantic_correctness` | 语义正确性 | `llm.grounding` |
| `external_service.availability` | 外部服务可用性 | `service.base.availability` |
| `external_service.contract` | 外部接口契约 | `service.base.response_contract`、`service.contract.compatibility` |
| `external_service.identity` | 调用方身份 | `service.base.authentication` |
| `external_service.permission` | 调用权限 | `service.base.authorization` |
| `human.authentication` | 身份认证 | `service.base.authentication` |
| `human.authorization` | 权限控制 | `service.base.authorization` |
| `internal_database.availability` | 数据库可用性 | `service.base.availability` |
| `internal_database.concurrency_consistency` | 并发一致性 | `service.resource_mutation.concurrency_consistency` |
| `internal_database.field_validity` | 字段合法性 | `api.data.type`、`api.data.format`、`api.data.length`、`api.data.legality` |
| `internal_database.idempotency` | 幂等性 | `service.resource_mutation.idempotency` |
| `internal_database.persistence` | 持久化能力 | `service.resource_mutation.persistence_consistency` |
| `internal_database.query_performance` | 查询性能 | `common.timeout` |
| `internal_database.referential_consistency` | 关联一致性 | `database.referential_integrity` |
| `internal_database.required_field_completeness` | 必填字段完整性 | `api.data.completeness` |
| `internal_database.resource_existence` | 资源存在性 | `service.query_retrieval.resource_existence` |
| `internal_database.uniqueness` | 唯一性约束 | `database.uniqueness` |
| `service.analysis_generation.execution_deadline` | 执行时限 | `common.timeout` |
| `service.analysis_generation.resource_consumption` | 资源消耗 | `service.analysis_generation.resource_consumption` |
| `service.analysis_generation.result_correctness` | 处理正确性 | `service.analysis_generation.result_correctness` |
| `service.dependency.availability` | 内部依赖可用性 | `service.base.availability` |
| `service.display_interaction.display_correctness` | 显示正确性 | `service.display_interaction.display_correctness` |
| `service.display_interaction.render_performance` | 渲染性能 | `common.timeout` |
| `service.query_retrieval.data_visibility` | 数据可见性 | `service.query_retrieval.data_visibility` |
| `service.query_retrieval.resource_existence` | 资源存在性 | `service.query_retrieval.resource_existence` |
| `service.query_retrieval.result_correctness` | 结果正确性 | `service.query_retrieval.result_correctness` |
| `service.release_activation.failure_recovery` | 失败恢复 | `service.release_activation.failure_recovery` |
| `service.release_activation.prerequisite` | 发布前置条件 | `service.release_activation.prerequisite` |
| `service.release_activation.result_consistency` | 发布结果一致性 | `service.release_activation.result_consistency` |
| `service.resource_mutation.business_constraint` | 业务约束 | `service.resource_mutation.business_constraint` |
| `service.resource_mutation.concurrency_idempotency` | 并发与幂等性 | `service.resource_mutation.concurrency_consistency`、`service.resource_mutation.idempotency` |
| `service.resource_mutation.persistence_consistency` | 持久化一致性 | `service.resource_mutation.persistence_consistency` |
| `service.workflow.interruption` | 业务流程取消与中止 | `service.workflow.interruption` |
| `service_relation.call_order` | 调用顺序 | `service_relation.call_order` |
| `service_relation.cascade_operation` | 级联操作 | `service_relation.cascade_operation` |
| `service_relation.concurrency_consistency` | 并发一致性 | `service_relation.concurrency_consistency` |
| `service_relation.cross_service_consistency` | 跨服务数据一致性 | `service_relation.cross_service_consistency` |
| `service_relation.dependency_consistency` | 依赖一致性 | `service_relation.dependency_consistency` |
| `service_relation.idempotency` | 幂等性 | `service_relation.idempotency` |
| `service.display_interaction.device_adaptation` | 设备适配性 | `service.display_interaction.device_adaptation` |

## 记忆库示例

API-M-IF2的8条请求数据异常保持：两个必填字段缺失、memoryType枚举不符、page类型/下界、pageSize类型/下界/上界。可选缺省正常，page默认1、pageSize默认20。返回字段另按其明示规则处理。

基础可用性针对实际被调用服务；认证及权限未明示时待确认，不推断所有接口都需登录。指定路径资源不存在与集合无匹配记录分别生成、分别比较。数据库读取不增加写入/回滚异常。时限未声明不启用；只声明实时要求而未给判据则待确认。

`python examples/memory_demo.py --output-dir /tmp/memory-concern-demo`运行标记为mock的完整演示。抽取和比较是固定夹具，只验证程序机制，不是模型实测结果。
