# Pi 受限文件工具与普通 LLM 接口实验

这是独立的显式实验，不改变正式 Deep Agents 默认执行方式。原72次 Deep Agents/Pi 对照保持原样。本实验按用户确认只比较两组：D为普通顺序LLM/工具接口循环，F为Pi SDK 1.5.2加受限JSON文件工具。Pi可自主选用文件，不强制读写；实际使用次数独立记录。两组同时改变运行循环和文件能力，不能单独归因文件权限。

## 固定条件

沿用原18个冻结实际批次、原业务提示/Skill/输入/Schema。五用例各绑定、生成、语义匹配一批，另E识别一批及GT识别两批；各独立两次，共72次。已退役的项目范围E/GT任务仅作为历史基准材料，不重新接入当前正式工作流。先完成原先五类代表样本的20次执行，再完成其余52次。首轮先跑方按批次交错，第二轮反转。每次新会话，无旧答案或成功缓存；最多5次真实请求，包含文件操作和修复。

普通LLM不运行Agent SDK循环；共同准备代码只捕获现行完整提示，不发送探测请求。两组采用相同实验JSON文本传输，经现有Python计费post与额度保护；只有可用文件工具Schema及使用说明不同。最终调用原submit_result闭包，通过同一格式、身份、引用、挂载及固定模板校验。根业务JSON也只会被适配到该提交接口。普通接口与无文件Pi控制的首请求逐字段一致已由模拟接入测试验证。

## 目录隔离

每次F执行拥有全新的workspaces/执行ID目录。input/task.json和input/schema.json为本任务冻结材料，只读且校验哈希；work/*.json允许创建、覆盖、读取和精确编辑。只允许两段相对路径，拒绝绝对路径、上级目录、隐藏路径、非JSON文件、符号链接、硬链接、特殊文件及目录越界。目录描述符与O_NOFOLLOW限制实际打开位置。单工作文件2MiB、总量16MiB、最多32个文件；分页读取最大120000字符。

Pi没有Shell、任意代码执行、内置工具、子Agent、全局Skill、插件或跨会话历史。Node启用权限模式，只读SDK运行代码/依赖及本执行SDK临时目录，仅可写本执行pi-home；子进程和其他主机文件访问被拒绝。SDK网络提供商关闭，请求全部由Python broker计费。文件工具只经Python小型白名单接口读写；Node不需要读取真实业务目录、凭证、账本或其他执行目录。

发现SDK即使noSkills仍探测用户全局Skill位置，实验改用未发现资源的内存容器及冻结提示，不扩大文件白名单。全局环境和HOME不修改。文件/候选版本和动作在独立运行目录与wire响应中保留，审计后可整体清理该实验目录，不涉及正式项目。

## 账本与恢复

共享本地授权上限100M Token（含全部历史），不重置、不退款、不更换模型/账户。只承认既有两笔已获明确继续授权的未知用量，绑定原请求ID、模型和扣账额：69098及94342。新未知用量立即停止后续派发，保守扣账且不重发。既有在途请求也阻止派发。experiment-cap.json只是额外子上限，不能替代共享账本。

```sh
python deployment/experiments/pi_node/file_experiment.py freeze --source OLD_FROZEN_EXPERIMENT --output NEW_EMPTY_EXPERIMENT
python deployment/experiments/pi_node/file_experiment.py run --output NEW_EMPTY_EXPERIMENT --phase pilot
python deployment/experiments/pi_node/file_experiment.py resume --output NEW_EMPTY_EXPERIMENT --phase all
python deployment/experiments/pi_node/file_experiment.py status --output NEW_EMPTY_EXPERIMENT
```

恢复跳过已有summary的完整执行。开始过但无summary的执行停止，先审计，不能盲目重发。代码、材料和独立原文检查表均绑定哈希；中途变更必须另行审计，不混改历史结果。

## 评测

分别报告首次提交、首次请求即交付、五次请求内最终交付、修复/拒绝、请求、Token、耗时和每份原文核对合格产物成本。记录请求配置名及网关实际返回模型；不同模型配对不进入同模型推断。工具使用率、读写/编辑次数单列，未使用工具不能冒充文件工作流成功。

冻结原文检查表先于本实验结果；匿名核对结果，按字段约束、来源、用例/步骤/方向、固定项、补充事实及失败条件匹配记录具体问题。程序校验、有限原文核对和业务专家签字是不同状态；不以JSON可解析或另一个模型赞同充当业务真值。重复执行按18个原始批次聚类，结论仅限当前小样本。
