---
name: dependency-graph
description: 按用例—实体 CRUD 矩阵确定性生成数据依赖边、DOT 图和依赖四元组。
title: Dependency Graph
version: 1.0.0
---

# Dependency Graph

RR/SR 异常识别还需要独立的 SR 服务调用依赖图：由原始正常/可选交互中的明确 SR 调用构建，标记调用顺序、依赖一致性、级联、跨服务数据一致性、幂等和并发一致性挂载。
内外数据库实际以 SR 资源服务呈现并保留物理映射；AR内部实现调用不提升为SR关系。新组件/边先确认依据与图上位置。
scene-pipeline 新协议输出 diagrams/service_dependencies.mmd 和 concern_mounts.json。此图与下列 CRUD 数据生命周期图各自保留。

本 Skill 独立实现附件定义的 CRUD 生命周期依赖，不与系统中已有的证据型服务依赖图混用。对同一实体，R/U/D 用例指向创建该实体的 C 用例；方向表示源用例依赖目标用例；过滤自环和跨实体配对。每对用例合并边标签并记录所有实体来源；四元组按每个实体及源操作分别列出。

输入为已抽取且可追溯的实体和 CRUD 操作。执行算法前必须阅读 `references/crud-dependency-algorithm.md`，不可用本页摘要替代完整规则。输出包括机器可读 JSON、Graphviz DOT `digraph G`、人类可读依赖边清单和逐缘由四元组 Markdown；工具检查实体、操作符、用例和来源引用，Agent 不得改写方向或规则。入口：`python .cac/tools/scene_completion.py build-crud-dependency-graph --model scene_model.json --output-dir <dir>`。本 Skill 不调用其他 Skill。
