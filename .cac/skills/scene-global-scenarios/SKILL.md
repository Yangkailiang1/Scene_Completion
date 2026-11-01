---
name: scene-global-scenarios
description: 从已识别的全局业务依赖关注点展开独立异常场景。
---

# 全局业务异常场景生成

仅使用正向业务实体、明确的依赖条件及本任务输入中已识别成功的 `global.*` 关注点。一个关注点可以展开多个独立失败条件。调用顺序必须有明确前置关系；依赖一致性检查明确的存在、状态、版本或生效条件；级联组按每一项独立清理义务拆成场景。不得仅凭 CRUD 或关系线推断业务规则，不得读取已有异常、测试或比较结果。

每条场景输出 `id、dependency_id、concern_key、object、cause、conditions、source_status、resolution、executable、source_refs`。缺乏必要条件的写 `pending`，不补造阈值或后续响应。来源引用必须指向本任务允许的正向材料。
