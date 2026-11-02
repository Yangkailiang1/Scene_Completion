---
name: scene-existing-bind
description: 已有异常交互绑定，用于检查器对应独立处理任务。
---

# 已有异常交互绑定

读取branches、case-group、fused-ssd与registry，将每个原文异常绑定融合SSD具体交互。输出bindings：branch_id、interaction_id、status、basis、source_refs。不属于本用例标not_this_case；无法确定标pending并调用ask_user。不按RR/SR拆为不同评测空间；同一次调用的重复视图使用canonical交互ID。

未知字段、约束与后续行为不补造。来源仅来自允许输入。业务问题通过ask_user非阻断记录；有据结果仍通过submit_result校验提交，不能仅提问而省略结果。

## 接口层级与校验职责定位

先依据本异常自己的接口路径、调用双方、实际操作及本地校验职责确定实际请求，再挂载关注点或细化场景。不同接口定义来源及不同实际调用的接口互不替代；不得通过路径前缀推断RR/SR或内外部身份。同名字段不能作为跨接口转移的依据。读取interface_ownership中的交互—接口对应及normal-rules.owner_service。平台本地字段校验绑定进入平台的请求，AdminService名称唯一性检查绑定其实际接收请求；传播的错误返回不作为另一条失败。只有已确认的同一次调用RR/SR重复视图共用SR身份。未知接口约束保持待确认，不读取G、其他来源的异常或匹配结果补答案。
