---
name: scene-global-scenario-match
description: 在相同全局业务定位内比较独立失败条件，保存完整、部分或不对应的判断。
---

# 全局场景对应

只读取本任务left/right已经独立构造的场景。按business_operation_id（用例＋业务实体＋实际操作）或dependency_id以及object建立候选；禁止跨定位匹配，不伪造interaction_id。

逐对比较失败原因和必要条件。相同含义的不同措辞可为full；仅同关注点、不同行为或条件不完整为partial或unmatched。分类差异、未声明的响应码和后续处理不能单独否定同一失败。不得补写输入场景或凭GT生成新场景。

幂等性中，同键同内容未重放、同键不同内容未拒绝、重复提交造成额外业务影响需要分别核对条件，不能因为都叫幂等就全部full。状态不允许变更不等于幂等键冲突。

输出decisions，元素为left_id、right_id、status（full/partial/unmatched）、reason。仅使用输入ID，每对最多一次；覆盖全部同定位候选。工具只把完整对应计分，并进行一一分配，partial用于诊断。
