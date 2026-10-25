---
name: scene-normal-rules
description: 从单个用例的正向RR/SR正文建立服务本地正常规则索引，供独立生成和逆向通道定位失败位置。
---

读取normal-documents和fused-ssd，仅整理本用例正常业务校验，不读异常分支、测试或评测结果。输出rules、pending，遵守提交Schema。

每条rule引用直接支持条件的原文，condition逐字摘录所引原文的一段完整正常条件，不改写、不用相邻句支撑；violation写该条件的具体反面。绑定负责执行该条件的Service接收请求交互。校验属于服务本地处理，不编造自调用消息。保存owner_service、interaction_id、condition、violation、concern_key、fields、functional_kinds、resolution、pending_details、source_refs；id使用稳定、互不冲突的标识。

从原文明示操作选择功能类别，可组合：发布含写入和版本校验可标publish、update，读取不能因支持写入而标update。引用行须支持字段、条件及阈值，不把相邻句当作依据。

一条独立规则取反对应一个具体失败。独立字段和OR连接的独立失败拆开；真正的跨字段比较保持整体。不重复API必填、类型等机械规则；保留服务本地业务前置条件、资源存在性、并发、发布、查询可见性等条件。

服务规则使用活跃关注点键：service.query_retrieval.resource_existence、service.query_retrieval.data_visibility、service.resource_mutation.business_constraint、service.resource_mutation.persistence_consistency、service.resource_mutation.concurrency_consistency、service.resource_mutation.idempotency、service.release_activation.prerequisite、service.release_activation.result_consistency、service.release_activation.failure_recovery；必要的关系/数据库/LLM规则只选择注册表对应定义。

有明示格式、数量或范围校验但具体标准未知，可输出conditional条件级规则，pending_details说明缺失信息，不编造数值；其他可判定规则为explicit。没有正常规则依据只列pending。

必须拆分：不存在、已停用、归属不符、状态不符、版本不符是不同失败；violation不能用“或”合并原因。同一字段不同约束亦独立。数据规则fields恰好一个，字段须出现在本交互数据或接口定义；不要将多个字段校验合成一条length/format规则。原文“甲调用乙校验”时执行者为乙，绑定乙的实际接收请求；不能仍绑定甲。

子任务仅整理当前fused-ssd中唯一的接收方实际执行的规则；全用例正文用于查依据，其他服务的规则不要代领。API数据规则fields使用本交互data.sequence给出的字段名；字段仅在数据库状态中出现而不是本次传递数据时使用业务/技术关注点，不伪装为接口输入字段。
