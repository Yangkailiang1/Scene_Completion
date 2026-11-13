# 项目工作约定

当前项目协议为scene-workflow-v5，默认SSD主流程使用ssd-case-v1。先阅读README、docs/architecture/code-guide.md、docs/reference/versions.md及本任务Skill。compat/detailed、compat/standalone、compat/saved分别保留详细流程、独立旧格式和保存报告，不代表恢复v2/v3/v4协议。不得以整理目录为由改变现有算法或重算历史成绩。

Python源码全部位于src/scene_completion。application协调用例，domain承载规则，workflow编排，inputs转换，analysis计算，infrastructure持久化；HTTP与CLI调用应用服务。资源路径统一由infrastructure/paths.py提供。前端results入口只路由到ssd或saved，shared仅放共用设施。Skill与Agent保留在.cac/skills和.cac/agents。目录整理不得修改模型实际加载的.cac/**/*.md和domain/prompts/**/*.md。

G/E/GT材料隔离。G只读正向材料；E和GT独立定位、识别关注点和细化场景。正常、可选及待确认不计分。关注点层按稳定四要素定位比较，场景层按独立失败条件比较；推荐只读取M与允许历史，不读取GT排序。

当前关注点四层为基础数据与业务属性约束、业务实体CRUD、业务专属、技术扩展，另有交互Service关系和独立全局业务依赖。可用性只针对适用的外部Service调用；枚举归数据范围，不恢复数据合法性、旧变更业务约束或资源消耗。具体定义以domain/concern_registry.json和项目最新确认版本为准。

行为输入的ssd.json定义RR，complete_behavior.json定义SR，main_success.json只提供时序引用。主成功、异常和备选按场景类型与步骤引用分流。原文、凭证、额度账本、项目数据及审核记录不删除。

缓存由任务语义版本、Schema、允许输入、来源及依赖身份控制。格式化、目录移动、拆分、模型或账号变化不改变任务语义版本；业务规则变化才更新workflow/task_semantics.json对应项。成功结果复用仍须完整校验。

文档分为docs/current、architecture、reference、history；唯一迁移清单为docs/architecture/module-map.json。保留docs/ssd-result-contract.md与docs/scene-workflow-v5/schemas发布路径。Windows模板位于deployment/windows，experiments不作为正式入口；tests按职责分类，共享测试工具位于tests/support。

修改运行make check，构建网页后方可发布。未经明确授权不调用付费模型。隔离补丁白名单使用src/scene_completion，修改不绕过校验或额度保护。不要把凭证、运行数据和账本提交到Git。
