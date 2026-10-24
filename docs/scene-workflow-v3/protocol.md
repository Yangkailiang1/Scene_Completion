# scene-workflow-v3

本版以融合SSD中的具体交互为分析和比较单位。两类交互为人类Actor↔Service、Service↔Service；RR/SR保留来源、步骤展开和显示视图，不能用来源层级不同直接拒绝同一交互的匹配。只有在已确认展开关系中、端点和方向相同的重复视图才归为同一次调用；真实下游调用不能合并。关注点继续使用interaction-concerns-v3注册表，不新增设备规则。

## 独立输入和产物

- 共享组成、RR/SR目录、API映射、接口索引、原文异常分支可并行。用例对应就绪后动态展开用例任务，无关API任务不会阻塞完整SSD。
- API索引给出接口ID、名称、原文范围；每接口子任务只输出索引指定接口，单独校验、缓存和保存，再合并API参数表。未知属性不猜测。
- 建模器从正向描述、能力表、API表和预定义关注点形成G，不读取E、测试GT或比较结果。
- existing-branches保留原分支；existing-bind绑定具体交互并标明confirmed/pending/not_this_case；existing-extract细化为E，保留original_branch_id、canonical_interaction_id、interaction_type、coverage_kind、source_status、derivation。
- 测试GT由测试spec、融合SSD和明确正常约束独立整理。宽泛测试参数异常按已知约束展开，只有可判定细项进入GT，未知规则进入pending，不向G取答案。

当前JSON Schema见schemas目录；稳定机器字段与来源引用同样保留。新任务Skill：原文异常分支抽取、异常交互绑定。逆向细化沿用独立Skill入口，普通核对仍在各任务内部。

## 覆盖和指标

E的exact项仍按对象、操作、原因及必要条件完整对应；同一交互的input_parameters原分支可覆盖多个请求参数细项，包括必填缺失和违反类型、格式、枚举、范围等已知约束。不覆盖返回数据、其他交互或存储Schema约束。原分支和细化子项同时保留用于追溯，生成细项的覆盖只计一次。

M={g∈G | 没有适用E覆盖g}。无匹配记录不覆盖指定实例不存在。GT按字段和具体失败原因去重，GT↔G仍语义一一对应；GT↔E支持上述宽泛覆盖。

- 缺失异常漏报率：(1−|M∩(GT−E)|/|GT−E|)×100%。
- 生成有效率：|G∩GT|/|G|×100%。
- GT明示／框架推导分别列出；没有测试GT显示未评测，空分母不适用。推荐未启用，不生成Q。

## 会话、执行状态与接口

节点会话持久化在事件数据库的messages表，恢复点保存在checkpoints表；不作为其他节点或角色的共享记忆。普通指导在下一次模型调用注入，标记已接收／已生效。当前HTTP不会被假装即时修改，新指导尚未应用时提交不会晋升为正式产物。

ask_user记录问题、原文依据和待决定事项，当前节点awaiting_answer，独立节点继续。回答后恢复会话、累计调用计数和修复轮次。到探索预算时只允许提交或提问；每个已回答问题增加一次恢复调用额度，默认最多3次澄清，累计计数不清零，避免回答后无法继续或无限提问。完成后指导可重新执行该节点；成功结果与受影响下游按输入和指导版本失效，无关任务复用。

新增接口：

- GET/POST `/api/projects/{id}/conversation`：读取节点会话或发送指导（task_key、text）。
- POST `/api/projects/{id}/answer`：task_key、question_id、text，回答后恢复。
- POST `/api/projects/{id}/rerun-node`：按最新指导重做；产物仍需验证。
- graph补充planned、input_summary、artifacts、question、guidance_revision、retry_at、retry_count；流程预告不计进度。
- SSE增加conversation_message、guidance_applied、question_asked、rate_limit_wait。模型正文与工具参数仍增量持久化，正式产物只接受完整已验证结果。

429共享降并发并冷却，遵守Retry-After，缺省2/4/8秒，单请求最多3次自动重试；额度、认证、超时、截断分别记录。超时不自动重POST。完成节点立即导出；旧失效产物移入previous_artifacts，不通过当前产物区发布。

## 升级

旧协议运行记录保持不变。旧项目点击继续运行会创建新版项目并复制源文及本地配置，不复用旧异常/计分缓存。原项目、失败和审核历史继续可查。正文/原有文档不修改。本轮只交付网页，不创建Windows发布Tag或离线包。

## 模型传输等待

连接／首响应使用timeout_seconds；stream_idle_timeout_seconds默认300、stream_total_timeout_seconds默认900。流式每次读取上限取无数据等待与剩余总时限的较小值。项目显式配置优先，界面可调整。超时记录phase、timeout_kind、elapsed_seconds、first_event_seconds、last_event_age_seconds、partial_content_bytes与incomplete_tools，不包含请求头/密钥或模型隐私推理文本。输入文档以完整原行号文本呈现，Schema只通过提交工具提供；可查虚拟原文件保留。
