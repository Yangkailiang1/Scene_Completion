# V5 RR/SR/AR 融合 SSD 与关注点

不再把一张汇总交互图作为主要用例图。每个 RR 用例的主成功流程分别生成 RR SSD、SR SSD、AR SSD 和融合 SSD；关注点分析以融合 SSD 的标准化请求—响应交换为输入。

- RR SSD 只表达 Actor、系统和抽象服务之间的业务交互。
- SR SSD 展示系统到 SR 抽象服务/API，以及 SR 外部 Service、外部数据库、外部 LLM 的交互。
- AR SSD 通过 `SR 抽象服务 -> ImplementationAPI -> 内部微服务 -> 内部数据库` 展开；映射缺失时保留上层交互并生成待确认项，不虚构微服务。
- 每条融合消息使用稳定的 `ssd_id`、`interaction_id`、`source_step_index` 和 `source_location`，便于从异常回溯到需求。
- 每条请求—响应交换保留 `exchange_id`、`parent_exchange_id`、`reply_to_message_id`；ImplementationAPI 与 AR 微服务合并为一条生命线。
- 顾客/商家到系统只保留 RR 业务动作，具体 HTTP 方法、路径和参数从系统到 SR Service 的消息开始出现。
- 融合 SSD 的消息使用有方向箭头；其来源节点和目标节点仍通过结构化 `node_id/kind` 识别。
- 每个 RR 用例对应一个 RR `abstract_service` 节点和 `rr_main`、`sr_main`、`ar_main`、`fused_main` 四套 JSON/SVG 产物。
- 备选流程和异常流程本阶段保留为异常判断证据，不单独生成 SSD。
- `applicable` 才表示需要生成异常；`needs_requirement` 只表示待确认，不生成异常。
- 超时关注点要区分需求满足、后续行为执行、系统与环境协调三个影响维度。
- API 数据关注点与数据来源无关，所有 API 数据入口都按数据特征检查。
