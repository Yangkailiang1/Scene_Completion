# 项目工作约定

当前仅支持scene-workflow-v5与最新关注点体系。先阅读README、docs/refactor/code-guide.md及本任务Skill。不得重新引入旧协议、旧关注点迁移或历史推荐算法。

Python源码全部位于src/scene_completion，按职责划分。HTTP与CLI只调用业务服务；资源路径统一由infrastructure/paths.py提供。Skill与Agent独立保留在.cac/skills和.cac/agents。

G/E/GT材料隔离。G只读正向材料；E和GT独立定位、识别关注点和细化场景。正常、可选及待确认不计分。关注点层按稳定四要素定位比较，场景层按独立失败条件比较；推荐只读取M与允许历史，不读取GT排序。

当前关注点四层为基础数据与业务属性约束、业务实体CRUD、业务专属、技术扩展，另有交互Service关系和独立全局业务依赖。可用性只针对适用的外部Service调用；枚举归数据范围，不恢复数据合法性、旧变更业务约束或资源消耗。具体定义以domain/concern_registry.json和项目最新确认版本为准。

行为输入的ssd.json定义RR，complete_behavior.json定义SR，main_success.json只提供时序引用。主成功、异常和备选按场景类型与步骤引用分流。原文、凭证、额度账本、项目数据及审核记录不删除。

缓存由任务语义版本、Schema、允许输入、来源及依赖身份控制。格式化、目录移动、拆分、模型或账号变化不改变任务语义版本；业务规则变化才更新workflow/task_semantics.json对应项。成功结果复用仍须完整校验。

修改运行make check，构建网页后方可发布。未经明确授权不调用付费模型。隔离补丁白名单使用src/scene_completion，修改不绕过校验或额度保护。不要把凭证、运行数据和账本提交到Git。
