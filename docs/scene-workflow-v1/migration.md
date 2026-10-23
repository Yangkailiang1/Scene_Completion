# 本轮迁移

从abda573基线继续修改codex/ppt-skill-refactor；实施前已完整备份含Git历史与缓存。原始RR/SR/test Markdown和本地凭证配置保留。未修改PPT或Downloads副本。

原五个ppt前缀模块已移除：契约进入contracts.py；运行进入workflow.py；来源进入source_documents.py；导出与计分分为artifact_exports.py / evaluation.py；方法按interaction_enrichment.py、concern_matching.py、exception_generation.py、exception_comparison.py、validation.py拆分。

原57项现已重组为service-concerns-v2（45个分层定义，包含基础族），旧项通过legacy_mapping逐项对应。移除固定数量及旧摘要断言，使用自校验摘要和无环父级校验，旧键不是活跃输出接口。数据库封装、语义一一匹配、JSON IO独立于旧容器。请求传输、模型配置和凭证范围断路、原生CLI证据、流式读取、token账本迁为公共模块。调度模块只保留新流程实际使用的固定依赖、成功缓存、共享限流和两轮修复，不保留三角色或历史监督修复分支。

删除旧通用Skill、旧协议入口、失效文档/示例、历史产物、历史推荐与对应测试；保留有价值的传输/计费/流式/原生执行回归测试并新增方法边界验收。目录不保留兼容副本；历史内容可由备份和Git历史恢复。

旧命令不提供兼容别名。使用README中的pipeline、task、score-extraction、check-run。必须为新协议创建运行目录，不能直接拿旧结果当当前输出。没有提供GT时不是零分，而是未评测。

测试操作投影/测试GT/交互对应/评测对应在prompts目录有各自内部规则，不新增公开任务Skill。缺失比较直接返回M；测试GT或评测失败时仍可交付成功用例的有效缺失报告。恢复仍使用同一输出目录和当前输入。

## 本次关注点升级（基线ac9b9ea）

实施前再次完整备份。新增独立注册表和继承匹配模块，保持scene-workflow-v1的11任务及主控入口。普通/数据库服务的查询资源存在性统一；认证错误不再混入可用性，接口/存储字段复用七类但保持作用域。

关注点匹配可读取可选的当前用例正向normal-documents来确认安全、时限、技术身份及业务规则；不读原文已有异常和测试答案。匹配最终输出三态及激活依据，G只接受适用的具体规则。异常增加继承来源，缺失比较与计分按去重后的失败单元处理。

旧的单一“并发与幂等性”映射到两个明确检查；旧LLM可用性中混入的认证失败必须按原因分开映射。迁移表不是自动复制开关，也不恢复旧协议兼容入口。注册表变化会失效匹配、生成、E/GT整理与比较，正常图表任务不因为注册表内容变化重调模型；代码/Schema变化仍会触发任务版本更新。
