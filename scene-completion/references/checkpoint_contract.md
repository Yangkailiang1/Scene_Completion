# V2 关注点协议

V2 不再使用固定检查点。关注点由系统组成节点、交互方向、API 边界和 Service 类型动态路由。

- 全量候选项必须保留在 concern matrix。
- `applicable` 项可以生成异常场景。
- `not_applicable` 和 `needs_requirement` 项不生成异常，但必须保留判断依据。
- 需求未给出时限时，超时关注点使用 `needs_requirement`。
- 结果中的稳定主键是 `interaction_id`、`concern_key` 和 tools 生成的异常 ID。
