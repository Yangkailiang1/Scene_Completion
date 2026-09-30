---
name: scene-assemble
description: 将通过审核的需求模型、SSD 与异常 finding 汇总为可追溯场景、预测、图表和工作簿。
title: Scene Assemble
version: 1.0.0
---

# Scene Assemble

职责限于审计通过后的合并、去重、导出和产物验收。保留主成功、可选、需求异常；只有有效 finding 产生关注点异常。预测和场景均使用稳定 ID，Spec 来源与关注点分类分开记录。生成 JSON、Excel、依赖/组成图及可用 PNG，并验证 manifest 与文件存在。不要在本 Skill 中重新判断需求语义或调用其他 Skill。

使用 `python .cac/tools/scene_completion.py assemble --require-png`。图、输出 schema 及 CRUD 语义按需读取 `references/system_composition.md`、`references/output_schema.md`。本 Skill 不调用其他 Skill。
