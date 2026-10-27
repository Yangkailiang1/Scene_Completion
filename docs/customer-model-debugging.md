# Windows客户模型调试与Code Agent节点接管

所有CLI连接同一本地工作台，网页显示同一任务/产物。先完整解压包、关闭旧服务，再启动`start.cmd`。不要在ZIP预览中运行；建议较短目录如`C:\SceneCompletion`。升级前备份旧目录和data；密钥、账本、审核和项目数据不随发布包分发。

## 本次客户已定位的三种失败

1. `agent_trace_history/...tmp`写入失败：旧临时名在长目标名后追加进程/线程号，容易触及Windows路径限制。现在同目录使用短随机临时名、Windows文件IO使用扩展路径、轨迹历史文件名缩短。审计轨迹写入失败独立记录，不再覆盖原模型/Schema错误。不能据此保证客户杀毒、权限及磁盘异常均已解决。
2. `finish_reason=length`，12000输出Token全部消耗于reasoning：这是输出截断，不发布残缺JSON。输出上限不是正文保证额度；思考/正文分配和上限以实际网关为准。
3. Mermaid里的`METHOD /path<br/>说明`：提取器和校验器统一只把纯path计为接口。工具仅清理由本接口引文支持的展示标签，保留原始引用；缺失`}`等有歧义的地址不猜补，使用原文其他完整声明或保留null并待修。

## CLI读写完整运行参数

先查看真实项目ID和连接ID：

```bat
scene.cmd projects
scene.cmd accounts
scene.cmd config --project PROJECT_ID
scene.cmd config --project PROJECT_ID --task components
scene.cmd diagnose --project PROJECT_ID --node components
```

`config`展示当前生效的账号/模型、全局与任务输出预算、提交模式、思考控制、超时和上下文上限，不回显密钥；`diagnose`读取失败、finish_reason、usage、校验拒绝原因及本地IO错误，不调用模型。

可先尝试下列兼容预设，再依据内网网关支持情况调整。这里的32K/64K是调试起点，不是对客户模型最大输出的断言；保存后仍会检查真实输入+工具Schema+输出预留是否超过200K上下文。

```bat
scene.cmd configure --project PROJECT_ID --preset deepseek-thinking --max-output-tokens 32768 --stage-output components=65536 --concurrency 1
scene.cmd config --project PROJECT_ID --task components
scene.cmd run --project PROJECT_ID --wait --mode auto
```

- `--max-output-tokens`、`--max-tokens`、`--maxtokens`是同一参数。
- `--stage-output TASK=TOKENS`可重复；TASK是业务阶段名，如`components`、`fused-ssd`。`--node`则必须使用执行图真实节点ID，如`G-001:fused-ssd`。
- `--thinking on/off/auto`；`auto`不额外发送开关，跟随网关默认。`--thinking-api legacy/enable_thinking/omit`选择网关字段；`legacy`为`thinking.type`，`enable_thinking`为布尔字段。
- `--reasoning-effort low/high/max/omit`只有网关支持时使用；`omit`不发送。`--thinking-budget`只用于声明支持该字段的网关，需`--no-send-reasoning-effort`，不能认为所有DeepSeek都支持。
- `--no-supports-tool-choice`、`--no-supports-parallel-tool-calls`不发送对应字段。
- `--reasoning-replay`将网关工具轮次要求的reasoning_content仅保存在调用内存并回传，不进入网页正文、事件、轨迹或恢复文件。服务重启后以原任务和已保存指导恢复，调用预算不清空。
- `--submission-mode json_text`可在工具调用不兼容时使用。仍通过同一业务校验器提交，不是跳过校验。网关不支持JSON模式字段时可配`--no-json-response-format`，提示词仍要求JSON。
- `--max-tokens-parameter max_tokens/max_completion_tokens`选择网关实际接受的字段，不能同时发送两者。
- `--connect-timeout`、`--idle-timeout`、`--total-timeout`单位秒；持续思考增量不会显示为“正文卡死”，页面单列思考字节数，且不显示思考原文。
- `--config-file FILE.json`可设置stage_max_tokens、stage_extra_body、role_models、task_models、model_profiles等。示例见`examples/config/deepseek-thinking.json`。扩展参数不能覆盖消息、凭证、模型、工具或输出上限，不能用此入口重置配额账本。
- `--dry-run`只核对参数，不保存不调用；真实账号及请求预算保存/发送时再校验。部分更新保留未改动字段；运行中不允许改配置。

模型选择属于每个API Key的允许列表，不自动换密钥。客户Gateway即使兼容OpenAI也可能不接受全部扩展参数。预设是显式选项，不依据模型名称自动改模式。DeepSeek官方说明思考工具模式需回传reasoning_content；其官方集成说明也提示tool_choice兼容限制。内网实现仍以实际返回为准：

- https://api-docs.deepseek.com/guides/thinking_mode/
- https://api-docs.deepseek.com/quick_start/agent_integrations/oh_my_pi/

## 某节点有界重试后，由客户Code Agent接管

```bat
scene.cmd diagnose --project PROJECT_ID --node api-map
scene.cmd repair-export --project PROJECT_ID --node api-map --out api-map-repair.json
```

交给Code Agent的指令：

> 读取导出的修复包，只按task_packet中本节点允许的原文和Skill修复payload，填写note解释依据。不要修改binding、state_identity、原文、Schema或校验器；不要读取其他通道答案。接口path须从明示原文提取，不能猜补未知地址。先执行repair-submit --validate-only；只有通过后才提交，再run继续。无法确定的业务事实保留未知或请我确认，不用空产物跳过任务。

```bat
scene.cmd repair-submit --project PROJECT_ID --node api-map --file api-map-repair.json --validate-only
scene.cmd repair-submit --project PROJECT_ID --node api-map --file api-map-repair.json
scene.cmd run --project PROJECT_ID --wait
```

修复绑定任务、输入、Schema、Skill、指导及关注点版本，并核对导出时状态。过期/跨节点/未通过证据校验的修复会被拒绝。提交保存独立版本与之前失败记录，不直接改正式产物；继续运行时再次验证，并执行现有后处理/审核流程，下游按真实依赖更新。原有独立节点继续运行，不能绕过失败依赖。

`rerun --project ... --node ... --text ...`是重新调用模型，**不是提交外部修复**；该命令沿用现有节点指导机制。修复包含本节点业务原文，只保留客户本地，不提交Git或发布附件。

## 验证边界

离线测试覆盖思考流计数、工具轮次回传与不落盘、JSON/截断错误区别、任务预算及凭证/账本隔离、Mermaid路径清理、长路径短临时名、修复包过期与校验、局部失败不阻塞独立节点。包在macOS交叉制作；不能代替Windows实机和客户内网DeepSeek模型全链路验证，不宣称调大预算后一定成功。
