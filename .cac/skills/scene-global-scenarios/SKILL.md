---
name: scene-global-scenarios
description: 从已识别的全局业务依赖关注点展开独立异常场景。
---

# 全局业务异常场景生成

仅使用正向业务实体、明确的依赖条件及本任务输入中已识别成功的 `global.*` 关注点。一个关注点可以展开多个独立失败条件。调用顺序必须有明确前置关系；依赖一致性检查明确的存在、状态、版本或生效条件；级联组按每一项独立清理义务拆成场景。不得仅凭 CRUD 或关系线推断业务规则，不得读取已有异常、测试或比较结果。

每条场景输出 `id、dependency_id、concern_key、object、cause、conditions、source_status、resolution、executable、source_refs`。缺乏必要条件的写 `pending`，不补造阈值或后续响应。来源引用必须指向本任务允许的正向材料。

当输入business-operations时，本任务按一个用例＋业务实体＋实际C/U/D操作分析全局幂等性，使用其真实business_operation_id，dependency_id填null；不伪造依赖或交互ID，object使用entity_id。多个Service及本地action共同完成同一业务操作不重复计数。G_c的强制规则由已确认框架策略提供，E_c/GT_c只能从各自异常原文独立识别，不因C/U/D默认存在就补E或GT。查询R不强制。
场景仍以独立失败条件区分：重复提交造成额外业务影响、同键同内容未重放、同键不同内容未拒绝互不等同；后两者必须有幂等键机制的明示依据。不得补造幂等键、状态码或响应；业务已发布状态不等于幂等键冲突。普通成功重放不计异常。
