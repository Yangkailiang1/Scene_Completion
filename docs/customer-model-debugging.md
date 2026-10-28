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
- `--thinking on/off/auto`；显式on/off覆盖旧的任务扩展参数和模型配置。`auto`解除全局强制，恢复模型配置／网关默认，并不表示关闭。`--thinking-api legacy/enable_thinking/omit`选择网关字段；`legacy`为`thinking.type`，`enable_thinking`为布尔字段。off不能与omit组合，否则根本没有发出关闭请求。
- `--reasoning-effort low/high/max/omit`只有网关支持时使用；`omit`不发送。`--thinking-budget`只用于声明支持该字段的网关，需`--no-send-reasoning-effort`，不能认为所有DeepSeek都支持。
- `--no-supports-tool-choice`、`--no-supports-parallel-tool-calls`不发送对应字段。
- `--reasoning-replay`将网关工具轮次要求的reasoning_content保存在调用内存并回传，不保存到Agent轨迹或检查点。它与思考流显示独立，单独启用replay不会记录思考原文。服务重启后以原任务和已保存指导恢复，调用预算不清空。
- `--submission-mode json_text`可在工具调用不兼容时使用。仍通过同一业务校验器提交，不是跳过校验。网关不支持JSON模式字段时可配`--no-json-response-format`，提示词仍要求JSON。
- `--max-tokens-parameter max_tokens/max_completion_tokens`选择网关实际接受的字段，不能同时发送两者。
- `--connect-timeout`、`--idle-timeout`、`--total-timeout`单位秒；持续思考增量会显示为“模型正在思考，尚无正文／工具参数”，思考与正文的字节数分开统计。
- `--config-file FILE.json`可设置stage_max_tokens、stage_extra_body、role_models、task_models、model_profiles等。示例见`examples/config/deepseek-thinking.json`。扩展参数不能覆盖消息、凭证、模型、工具或输出上限，不能用此入口重置配额账本。
- `--dry-run`只核对参数，不保存不调用；真实账号及请求预算保存/发送时再校验。部分更新保留未改动字段；运行中不允许改配置。

## 显示思考流，以及直接关闭思考

`output_bytes=0`只表示尚无正文／工具参数，不能据此判定没有收到模型增量。旧版只记录reasoning进度；本版可显示网关实际返回的`reasoning_content`，不推测或补造思考内容。

开启显示（后续请求生效）：

```bat
scene.cmd configure --project PROJECT_ID --stream --show-reasoning
scene.cmd config --project PROJECT_ID --task components
scene.cmd run --project PROJECT_ID --wait --mode auto
scene.cmd events --project PROJECT_ID --node components --after 0
```

`--show-reasoning`等价于`--stream-reasoning`；`--no-show-reasoning`关闭记录。网页的“模型配置→高级运行参数→模型思考流”也可设置。节点中按思考／正文／工具参数分别显示，思考块可收起隐藏；CLI事件中为`stream_delta`且`data.channel=reasoning`。刷新可恢复已保存事件，旧运行未保存的思考文本无法补回。运行中需等本轮结束再改配置。

**思考显示默认关闭。显式开启会把供应商思考文本保存在本地节点事件，可能随项目导出；不要分享包含敏感业务内容的事件。**思考流不进入正式产物JSON、业务Schema校验、Agent轨迹或检查点，也不改变修复／配额预算。网页中的“显示模型思考流”复选框仅隐藏显示，不停止模型思考或事件保存。

关闭模型思考（与隐藏思考流不同）：

```bat
scene.cmd configure --project PROJECT_ID --thinking off --thinking-api legacy
scene.cmd config --project PROJECT_ID --task components
```

实际请求应显示`"thinking":{"type":"disabled"}`。若网关使用布尔开关，改为`--thinking-api enable_thinking`，实际请求应显示`"enable_thinking":false`。显式关闭会移除旧扩展参数中的thinking、reasoning_effort和thinking_budget，且不被旧模型／任务thinking配置重新开启；每个任务最终采用的开关格式仍可通过`config --task`核对。

网关可能拒绝关闭、忽略参数，或模型本身不支持非思考模式。若关闭后仍收到reasoning_content，页面与`diagnose`会提示`disabled_requested_but_reasoning_returned`；未观察到思考也不等于证明服务端完全关闭。不能仅凭发送了off就宣称成功。显示思考只能解释等待过程，**不会解决输出预算耗尽**；仍需按网关能力关闭思考、调整输出上限或拆分任务。

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

离线测试覆盖思考流计数、默认不记录原文、显式开启后事件保存／续接、思考与正式JSON隔离、工具轮次回传、关闭思考的参数优先级及网关返回核验、JSON/截断错误区别、任务预算及凭证/账本隔离、Mermaid路径清理、长路径短临时名、修复包过期与校验、局部失败不阻塞独立节点。包在macOS交叉制作；不能代替Windows实机和客户内网DeepSeek模型全链路验证，不宣称调大预算后一定成功。

## 客户端：接口映射提交失败与思考流为空

`VERSION.json` 的 `source_commit` 是40位十六进制Git版本号，不是乱码。保持 `start.cmd` 运行，在包根目录执行：

```bat
scene.cmd projects
scene.cmd diagnose --project PROJECT_ID --node api-map > api-map-diagnose.json
scene.cmd config --project PROJECT_ID --task api-map > api-map-config.json
```

提供版本号和这两个JSON即可诊断，无需 `.env`、API Key或思考原文。`diagnose` 中的 `stream_observation` 记录该次请求的思考显示开关、网关字段名、思考字节数及SSE/完整JSON响应方式；旧记录无法补造这些字段。

已修复一条可复现的提交失败路径：模型把 `review_questions` 写成字符串列表时，旧代码直接展开字符串，会报 `'str' object is not a mapping`。现在先检查问题列表与所有嵌套产物容器，给出如 `review_questions[0]`、`payload.services[0].interfaces[0]` 的精确位置；保留被拒绝的业务结果及问题，在原有两轮修复预算内修正，不把字符串猜成业务事实。客户同文案报错仍需诊断文件核对，不能仅凭报错确定来源。

思考流显示仍需显式开启，与开启/关闭模型思考是两个独立选项：

```bat
scene.cmd configure --project PROJECT_ID --stream --show-reasoning
scene.cmd config --project PROJECT_ID --task api-map
```

对后续请求生效；正在执行的HTTP请求和旧日志不会追补。网页“更多操作→模型设置→运行参数→模型思考流”也可开启。网关公开的 `reasoning_content`、`reasoning` 文本和 `reasoning_details` 可读文本/摘要均可单列显示，重复别名只计一次；加密内容不作为可读文本。正式产物仍只使用正文或工具参数。若供应商只发心跳、不公开思考，或以完整JSON缓冲到结束，客户端无法实时还原；后者会明确标注“完整JSON而非SSE”。仅有reasoning token用量也不代表网关返回了思考文本。

关闭思考需选择网关实际支持的参数格式，例如：

```bat
scene.cmd configure --project PROJECT_ID --thinking off --thinking-api legacy
```

网关若使用布尔开关则选 `--thinking-api enable_thinking`。此命令发送关闭请求，不保证网关执行；若仍收到思考字段，诊断会如实记录。不要盲目增大重试次数来处理空正文。
