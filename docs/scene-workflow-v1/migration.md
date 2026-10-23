# 本轮迁移

从abda573基线继续修改codex/ppt-skill-refactor；实施前已完整备份含Git历史与缓存。原始RR/SR/test Markdown和本地凭证配置保留。未修改PPT或Downloads副本。

原五个ppt前缀模块已移除：契约进入contracts.py；运行进入workflow.py；来源进入source_documents.py；导出与计分分为artifact_exports.py / evaluation.py；方法按interaction_enrichment.py、concern_matching.py、exception_generation.py、exception_comparison.py、validation.py拆分。

57项定义迁入独立concern_registry.json；definitions哈希保持原值，registry_version仅记录定义来源，不是可执行旧协议。数据库封装、语义一一匹配、JSON IO独立于旧容器。请求传输、模型配置和凭证范围断路、原生CLI证据、流式读取、token账本迁为公共模块。调度模块只保留新流程实际使用的固定依赖、成功缓存、共享限流和两轮修复，不保留三角色或历史监督修复分支。

删除旧通用Skill、旧协议入口、失效文档/示例、历史产物、历史推荐与对应测试；保留有价值的传输/计费/流式/原生执行回归测试并新增方法边界验收。目录不保留兼容副本；历史内容可由备份和Git历史恢复。

旧命令不提供兼容别名。使用README中的pipeline、task、score-extraction、check-run。必须为新协议创建运行目录，不能直接拿旧结果当当前输出。没有提供GT时不是零分，而是未评测。

测试操作投影/测试GT/交互对应/评测对应在prompts目录有各自内部规则，不新增公开任务Skill。缺失比较直接返回M；测试GT或评测失败时仍可交付成功用例的有效缺失报告。恢复仍使用同一输出目录和当前输入。
