---
name: scene-existing-extract
description: 异常关注点逆向细化，用于检查器对应独立处理任务。
---

# 异常关注点逆向细化

读取原文分支及已确认bindings、融合SSD、明示接口约束和最新版registry。输出scenarios并保留original_branch_id、canonical_interaction_id、interaction_type、source_status、derivation。只细化绑定交互；参数非法分支设coverage_kind=input_parameters，可覆盖该交互必填缺失及全部明示类型/枚举/范围等请求错误；绝不覆盖输出。其他异常设exact，具体原因与必要条件须对应。允许framework_inferred直接计覆盖但保留推导依据；不读取G或GT。返回数据错误绑定返回交互。

未知字段、约束与后续行为不补造。来源仅来自允许输入。阻断问题通过ask_user提问，结果通过submit_result校验提交。

优先参照独立normal-rules定位本分支失败发生处；填写对应rule_id，保留入口和后续传播，不在整条链任意匹配。位置与字段路径分开，独立原因拆开。允许缺省的正常容错不算异常。响应码/后续行为与失败原因分开，不强求G补造响应。

原分支的异常触发与后续处理分离：成功回退、待同步状态和重试动作放入documented_follow_up，不作为新的失败项。只有原分支自身描述了恢复失败时才细化恢复失败原因。一个触发的标题和解释只保留一个失败单元，拆分独立原因后不保留复合父项。

只输出违反明确正常约定的异常。普通取消、成功、可选成功路径及仅描述预期恢复不得计为独立失败；不确定进入pending或保留排除说明。需要保留非异常时设置scenario_type为normal/optional/pending，工具会排除计分并保存来源。

先读取本来源已独立识别的identified-concerns，只对其中确定关注点细化具体场景；未知项保留待确认，不通过场景新增关注点。

## 按需上下文与模型传输

上述字段描述保存产物；模型只填写当前传输Schema要求的新判断。交互、四要素对象、关注点及来源身份由工具按本来源独立识别的binding_ref恢复，不重复生成。按已识别的交互和对象取片，独立失败条件分组，真正跨字段关系保持整体。其余正常规则仅提供索引，确需补查时使用给定evidence_id，不得读取其他渠道结果。
