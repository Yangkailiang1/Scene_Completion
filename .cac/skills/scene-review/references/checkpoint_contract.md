# V6 关注点协议

V5 不再使用固定检查点。关注点由融合 SSD 的请求—响应交换、系统组成节点、交互方向、API 边界和 Service 类型动态路由。RR/SR/AR 层级用于追溯和补充架构信息，不替代关注点状态判断。

- 全量候选项必须保留在 concern matrix。
- `applicable` 项可以生成异常场景。
- `pending_review` 只表示候选尚未被 Agent 审查，不能进入最终 assemble。
- `not_applicable` 和 `needs_requirement` 项不生成异常，但必须保留具体判断依据和证据类型。
- 需求未给出时限时，超时关注点使用 `needs_requirement`。
- API 数据关注点绑定到 API 入口本身，不因来源是人类 Actor 或外部 Service 而改变。
- 来源人类、目标外部 Service 和 API 存在性必须由结构化 `kind` 与 API 字段判断，不从节点名称或普通消息文本猜测。
- 每个 finding 应能回溯到融合 SSD 消息、用例步骤和原始文档定位。
- 结果中的稳定主键是 `use_case_id`、`exchange_id`、`concern_key`、`prediction_id` 和 `scenario_id`。
- 每个 `main_success`、`alternative`、`requirement_exception` 和 `concern_derived_exception` 都必须出现在场景清单中。
- 外部 Service、外部数据库、外部 LLM 的关注点属于 SR；内部微服务、Implementation API 和内部数据库的关注点属于 AR。
- 顾客/商家到 System 的 RR 业务消息不得被当成具体 API 数据入口；只有结构化 API 交换才生成 `api.data.*`。
- 超时关注点只有在三个影响维度至少一个为 `yes` 时才能为 `applicable`。
- 适用性可以由需求、架构、接口契约、SSD 结构或领域规则共同证明；性能、容量和时限阈值仍需明确证据。
- 每条候选必须有 `concern_subject`、`subject_node_id`、`evidence_types` 和 `source_location`。
- 每个 RR Use Case 必须有且仅有一个 RR 抽象服务；所有下游工具使用归一化模型。
- SSD 语义重复消息必须在渲染前合并；同一交换和同一语义身份出现冲突文本时必须报错。
