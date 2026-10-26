---
name: scene-test-supplement
description: 依据正向需求和接口契约独立补充异常测试，用于扩展测试GT，禁止读取生成异常或覆盖答案。
---

# 独立异常测试补全

输入为当前实际交互、明示正常规则（没有violation反面候选）、正常接口约束、已存在异常测试的目录及项目关注点。不得读取G、E、匹配、缺失报告或历史异常生成输出。

工具独立补齐必填、类型、枚举、上下界、格式等接口约束测试及基础服务不可用测试。本Skill只补充尚需语义理解的业务约束、身份权限、持久化、并发和发布等异常测试；不要再次输出字段或基础不可用测试。

每条业务测试必须选择当前normal-rules中的normal_rule_id，且interaction_id和concern_key必须与该规则相同。只能取反该规则明确规定的条件，不能借引用相邻句发明关联完整性、未知类型、性能阈值或额外调用顺序。field必须为null，scope为service，data_location为null；业务字段写入触发条件。source_refs仅复制该规则的依据。没有适用规则时输出空tests。

每条tests记录填写normal_rule_id、interaction_id、concern_key、field、scope、data_location、preconditions、trigger、test_data、steps、expected_result、source_refs、executable、pending_details。preconditions是正常前提，trigger只含一个真正失败条件，steps要能够指导测试执行。来源仅引用当前正向材料。正常结果、普通取消、已约定的成功降级不作为异常。响应与恢复是expected_result，不另造失败；未明示错误码或处理行为不得补造。

一个字段或独立原因一条，两个独立上下界分开；真正跨字段关系整体保留。不强制每个关注点有测试。没有明确具体标准则标executable=false并列待确认事项；没有正常依据则不补造。原始测试目录用于避免重复，不得改写它的类型。输出只含tests。

紧凑模型Schema可只要求normal_rule_id和新测试内容；已知交互、关注点、位置和来源由工具按规则ID回填，不能自行选择另一条邻近规则。重复请求本身不是异常，应描述重复请求违反约定、造成重复副作用等具体失败。trigger不附加多个错误取值的举例，枚举约束整体取反即可。

当前每次只输入一条正向业务规则，至多输出一条测试。只违反该规则，不扩充到同句其他字段或其他规则；不得将合法的重复请求当失败。未知信息不足以形成失败时输出空tests，保留规则的待确认状态。

## 成本控制与质量门槛

继续按正向正常规则独立补全和缓存。字段及基础可用性由工具负责，模型只处理业务语义。试验性省略测试前提和步骤曾遗漏明确业务失败，未启用该精简方案；不能以Token下降替代必要测试条件。缺少依据不强造测试，失败与待确认保留来源。
