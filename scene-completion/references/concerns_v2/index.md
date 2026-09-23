# V2 关注点知识索引

先读取本索引，再按具体 `concern_key` 加载一个关注点文件。判断证据可以来自需求/设计文档、SSD 结构、接口契约、Service 行为或状态/关系约束；定量阈值证据不足时使用 `needs_requirement`。

系统组成和图生成知识位于 `references/diagrams_v2/`，不与关注点定义混载。

服务专属关注点按映射层级隔离：`sr_service.*` 仅适用于当前 RR 用例的 SR Service/API 分类；`ar_service.*` 仅适用于当前 AR 实现映射分类。共享 Service 名称不共享分类，`unknown` 不路由类型专属项。SR 五类与 AR 五类的详细适用/排除规则分别见对应的 `sr_service__*.md`、`ar_service__*.md` 文件。
