---
name: scene-existing-bind
description: 已有异常交互绑定，用于检查器对应独立处理任务。
---

# 已有异常交互绑定

读取branches、case-group、fused-ssd与registry，将每个原文异常绑定融合SSD具体交互。输出bindings：branch_id、interaction_id、status、basis、source_refs。不属于本用例标not_this_case；无法确定标pending并调用ask_user。不按RR/SR拆为不同评测空间；同一次调用的重复视图使用canonical交互ID。

未知字段、约束与后续行为不补造。来源仅来自允许输入。业务问题通过ask_user非阻断记录；有据结果仍通过submit_result校验提交，不能仅提问而省略结果。
