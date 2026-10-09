---
name: scene-review
description: 基于 SSD 交换及证据规划、审核和严格校验异常关注点候选。
title: Scene Review
version: 1.0.0
---

# Scene Review

本 Skill 用于兼容旧审核流程。新三角色流程由 scene-generate 直接生成候选，不调用本 Skill 过滤场景。

职责仅为关注点候选路由、语义审核、finding 证据和完整性审计，不负责生成 SSD 或组装工作簿。

输入是规范模型、全量 SSD manifest、需求/API 证据。工具按注册表规划候选，初始 `pending_review`；Agent 按 `candidate_id` 和交换分批审核，按需读取 `references/concerns_v2/index.md` 与命中的知识文件，并给出适用/排除/待需求依据。只有 `applicable` 且有原子 finding 才形成关注点异常。超时、数据、主体、关系候选分别依其证据判断，不以候选数或比例制造异常。

使用 `python .cac/tools/scene_completion.py plan-concerns`、`review-concerns`、`validate-concerns --require-complete`、`audit-run`。支持 external/agent/auto 模式；密钥不落盘。输入输出字段与续审协议见 `references/review_modes.md` 和 `references/checkpoint_contract.md`。本 Skill 不调用其他 Skill。
