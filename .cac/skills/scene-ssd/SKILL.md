---
name: scene-ssd
description: 根据规范化用例和架构映射抽取、构造、校验 RR/SR/AR 交互时序及融合 SSD。
metadata:
  title: Scene SSD
  version: "2.0.0"
---

# Scene SSD

职责限于 SSD 交互语义和时序图，不负责需求抽取、关注点审核或最终组装。

输入：通过模型校验的 `scene_model.json`、接口/实现映射及来源证据。Agent 识别逐步调用关系、参与者、请求/响应字段和逐层返回；工具生成并校验 RR、SR、AR、fused SSD JSON/SVG/PNG。顾客/商家到系统只表达业务动作；SR API 才包含接口与参数；Implementation API 与 AR 微服务按已确认模型映射。不得为了画图虚构调用或返回。

按需读取 `references/diagrams_v2/interaction_concern.md` 中与交互结构相关的约定。主要入口为 `python .cac/tools/scene_completion.py generate-ssd|validate-ssd`。本 Skill 不调用其他 Skill。

有文档证据时，一个 AR 实现可以包含多个 dependencies；分别记录数据库、内部服务、外部服务，不能由数据库默认依赖覆盖支付或物流调用。每项保存 target_node_id、direction、operation、source_step_index 和 source_refs。二级服务调用使用 caller_node_id 引用已有实际服务；incoming 表示外部回调。依赖请求/返回必须绑定同一交换与调用，原始业务步骤和执行顺序分别保存。明确空依赖列表表示无依赖，不补默认数据库。不依据操作名称猜测依赖。
