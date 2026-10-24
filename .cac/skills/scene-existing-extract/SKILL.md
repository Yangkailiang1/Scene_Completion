---
name: scene-existing-extract
description: 异常关注点逆向细化，用于检查器对应独立处理任务。
---

# 异常关注点逆向细化

读取原文分支及已确认bindings、融合SSD、明示接口约束和最新版registry。输出scenarios并保留original_branch_id、canonical_interaction_id、interaction_type、source_status、derivation。只细化绑定交互；参数非法分支设coverage_kind=input_parameters，可覆盖该交互必填缺失及全部明示类型/枚举/范围等请求错误；绝不覆盖输出。其他异常设exact，具体原因与必要条件须对应。允许framework_inferred直接计覆盖但保留推导依据；不读取G或GT。返回数据错误绑定返回交互。

未知字段、约束与后续行为不补造。来源仅来自允许输入。阻断问题通过ask_user提问，结果通过submit_result校验提交。
