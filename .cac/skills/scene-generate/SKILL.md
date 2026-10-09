---
name: scene-generate
description: 使用现有 SSD 与关注点路由确定性生成全部未审查场景候选。
---

# 场景生成

输入规范模型、原始需求/设计文档及可选 SSD manifest，使用共享 CLI 的 scene-pipeline。
生成主成功、可选、需求明确异常和全部候选，不等待 scene-review 或 LLM 审查。
候选应带稳定 ID、关注点、SSD 引用、主流程锚点、来源与补充章节。
无明确依据的响应、恢复、参数上限使用待需求确认，不为增加覆盖率读入检查器结果。

新协议、批次和输出见 ../scene-check/references/three_roles.md。本 Skill 不调用其他 Skill。
