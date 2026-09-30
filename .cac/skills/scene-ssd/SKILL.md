---
name: scene-ssd
description: 根据规范化用例和架构映射抽取、构造、校验 RR/SR/AR 交互时序及融合 SSD。
title: Scene SSD
version: 1.0.0
---

# Scene SSD

职责限于 SSD 交互语义和时序图，不负责需求抽取、关注点审核或最终组装。

输入：通过模型校验的 `scene_model.json`、接口/实现映射及来源证据。Agent 识别逐步调用关系、参与者、请求/响应字段和逐层返回；工具生成并校验 RR、SR、AR、fused SSD JSON/SVG/PNG。顾客/商家到系统只表达业务动作；SR API 才包含接口与参数；Implementation API 与 AR 微服务按已确认模型映射。不得为了画图虚构调用或返回。

按需读取 `references/diagrams_v2/interaction_concern.md` 中与交互结构相关的约定。主要入口为 `python .cac/tools/scene_completion.py generate-ssd|validate-ssd`。本 Skill 不调用其他 Skill。
