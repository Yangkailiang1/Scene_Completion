---
name: dependency-graph
description: 按用例—实体 CRUD 矩阵确定性生成数据依赖边、DOT 图和依赖四元组。
title: Dependency Graph
version: 1.0.0
---

# Dependency Graph

本 Skill 独立实现附件定义的 CRUD 生命周期依赖，不与系统中已有的证据型服务依赖图混用。对同一实体，R/U/D 用例指向创建该实体的 C 用例；方向表示源用例依赖目标用例；过滤自环和跨实体配对。每对用例合并边标签并记录所有实体来源；四元组按每个实体及源操作分别列出。

输入为已抽取且可追溯的实体和 CRUD 操作。输出边 JSON、Graphviz DOT `digraph G` 和 Markdown 四元组；工具检查实体、操作符、用例和来源引用，Agent 不得改写方向或规则。入口：`python .cac/tools/scene_completion.py build-crud-dependency-graph --model scene_model.json --output-dir <dir>`。细则见 `references/SKILL.md`。本 Skill 不调用其他 Skill。
