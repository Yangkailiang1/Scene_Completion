# service.resource_mutation.concurrency_idempotency

关注对象：RR 用例对应的 SR 资源变更 Service/API。

用于审核有证据的并发冲突和重复请求副作用。这是一个关注点族；Agent 可拆成多个原子 finding，例如“并发更新覆盖”与“重试导致重复创建”，但每个 finding 必须指向该 SR API 的具体步骤/交换。

证据可来自 API 幂等键契约、状态/版本约束、并发控制说明、重试语义或需求中的并行操作。没有重复请求、重试或并发行为证据时，不得仅凭存在写接口推断异常。
