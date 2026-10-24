---
name: scene-existing-branches
description: 原文异常分支抽取，用于检查器对应独立处理任务。
---

# 原文异常分支抽取

从existing-documents并行抽取RR/SR原文异常分支。只输出branches，含id、case_hint、description、operation_hint、party_hint、source_refs。保留原文宽泛措辞和原始行号；不看G、GT，不按关注点补造原文没有的分支。

未知字段、约束与后续行为不补造。来源仅来自允许输入。阻断问题通过ask_user提问，结果通过submit_result校验提交。
