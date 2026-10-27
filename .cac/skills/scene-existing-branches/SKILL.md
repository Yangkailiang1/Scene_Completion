---
name: scene-existing-branches
description: 原文异常分支抽取，用于检查器对应独立处理任务。
---

# 原文异常分支抽取

从existing-documents并行抽取RR/SR原文异常分支。只输出branches，含id、case_hint、description、operation_hint、party_hint、source_refs。保留原文宽泛措辞和原始行号；不看G、GT，不按关注点补造原文没有的分支。

未知字段、约束与后续行为不补造。来源仅来自允许输入。业务问题通过ask_user非阻断记录；有据结果仍通过submit_result校验提交，不能仅提问而省略结果。

逐分支区分scenario_type：exception为违反约定的失败；normal为正常路径；optional为允许的成功替代/普通取消/正常空结果；pending为无法确定。不能因“扩展路径”标题或出现失败二字就认定是异常。只有exception进入后续匹配，其他保留排除来源。服务真正失败及其恢复是同一失败；不得把恢复成功当第二个异常。
