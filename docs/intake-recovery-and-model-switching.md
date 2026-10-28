# 同事产物接入、后台恢复与模型吞吐监视

本版在现有业务流水线上增加接入、恢复与运行配置能力，不改变关注点/场景的两层计分口径。机器测试补全对新配置默认关闭；历史扩展测试与报告保留。

## 将命令交给 Code Agent

先启动服务，再查询能力和项目。Windows使用 `scene.cmd`，开发环境可将其替换为 `python scene.py`。

```bat
start.cmd --no-browser
status.cmd
scene.cmd capabilities
scene.cmd projects
scene.cmd accounts
scene.cmd configure --project PROJECT_ID --thinking off --thinking-api chat_template_kwargs --concurrency 3 --no-supplement-tests
scene.cmd input-scan --project PROJECT_ID --directory C:\scene-input --watch
scene.cmd imports --project PROJECT_ID
scene.cmd run --project PROJECT_ID --priority-case G-001 --mode auto --wait
```

`--case G-001`只跑一个已确认用例；`--priority-case G-001`先完成它，再继续其余用例。共享抽取仍是项目范围。业务审核模式禁止模型执行、产物转换及恢复。启动窗口和浏览器关闭不会停止后台服务；`stop.cmd`显式停止并保存检查点。服务日志在`data/server.log`，项目执行日志在项目`run/worker.log`。

## 输入与导入

网页“输入与导入”支持文件/文件夹上传和服务端目录监控。注册目录每5秒扫描，文件连续两次检查内容稳定后接收；内容哈希去重。只接收支持文件，跳过隐藏、程序、凭证和越界符号链接。

支持系统组成、API映射/参数、RR/SR/融合SSD和对象操作。标准JSON与Markdown表格先用工具解析，Mermaid先提取字面结构；不确定格式由转换Agent按章节处理。原始RR/SR、正向产物、已有异常和测试通道分开，混合/未知文件不自动成为G的输入。

完整、唯一归属且校验通过的产物可跳过相应模型调用。无完整性声明的原始JSON默认部分覆盖，不能凭一张小表宣称完成全项目。部分覆盖需确认，原流程只补缺项；替换成功产物、归属歧义或多文件冲突需明确决定。原件、引用、转换、版本及启用记录均保留。正在执行的节点使用冻结导入快照，新文件在下一安全执行边界生效。

```json
{"task":"api-map","coverage":"partial","payload":{"services":[]}}
```

上面只说明封套格式；实际payload须符合本任务Schema，空表不能代替本应存在的接口。查询 `imports` 获得文件ID、产物ID、revision；用JSON文件提交 `imports --item FILE_ID --file decision.json --dry-run` 预览，再去掉`--dry-run`保存。

## 失败恢复与重试上下文

正常修复重复出现相同错误会提前熔断，转有界恢复。默认每节点最多额外2次模型请求、每执行轮20次，持久账本在重启后保留。恢复只接收该节点允许的输入、Skill、Schema、诊断和被拒绝候选，不读取其他通道答案、不改代码/校验器/原文。修复上下文由当前任务包和有限修复反馈构造，不无限拼接所有历史对话。

`recovery --project PROJECT_ID`查看设置与预算；JSON写入需`expected_revision`，支持`--dry-run`。提高输出只能在项目显式允许的恢复上限内，不能自动换账号或重置额度。未知POST超时、断流或认证/额度错误不会盲目重发；程序故障保留本地诊断，独立用例继续执行。

## 模型列表在哪里

数据目录的`model-accounts.local.json`中，每个连接的`models`是本机允许列表，项目`model.local.json`通过`model_account_id`选择连接。在`.env`新增Qwen变量不会自动扩大一个已保存的DeepSeek连接。网页“模型配置”或CLI `save-account`编辑相应连接的模型列表；列表不代表网关必然有权限，不会自动付费探测。

## 思考与吞吐

客户支持的关闭思考请求为：

```json
{"chat_template_kwargs":{"enable_thinking":false}}
```

显式设置会清理冲突的旧思考开关，保留无关模板参数；实际是否遵守仍看网关返回。正文、工具参数及网关提供的公开推理流分开记录。吞吐使用已接收正文、工具参数、公开推理内容的UTF-8字节数/4作估算，心跳不算输出，**不是账单Token**。网关不返回推理内容时不能据心跳推断其推理吞吐。

自动切换默认关闭，须显式配置候选；同账号示例：

```bat
scene.cmd configure --project PROJECT_ID --auto-switch --fallback-model QWEN_MODEL_ID --min-throughput 2 --throughput-window 30 --throughput-grace 60 --stall-timeout 120
```

完整配置可用`configure --config-file runtime.json --dry-run`预览，再保存：

```json
{"resilience":{"enabled":true,"candidates":[{"model":"QWEN_MODEL_ID"},{"account_id":"OTHER_ACCOUNT_ID","model":"OTHER_MODEL_ID"}],"min_tokens_per_second":2,"window_seconds":30,"grace_seconds":60,"low_windows":2,"no_output_seconds":120,"max_switches":2,"cooldown_seconds":300,"switch_on_rejection":true}}
```

候选须属于对应账号模型允许列表；启用额度保护时必须已有独立账本和额度配置，不继承旧模型余额。所有项目/账号/导入/恢复在同一网关origin合计最多3路HTTP请求。不同网关各自限流。

流式读取连续低速窗口或无输出超时后，客户端中止当前读取并保存诊断，再只重做当前未完成节点。服务端可能仍在推理，原请求保留未知用量/预留，不能当成未消费。低速、429、明确模型不可用、输出截断及配置允许的内容拒绝可切换；未知网络POST超时、断流、认证错误及额度耗尽不盲目重放。默认每任务最多2次切换，模型冷却记录持久保存。普通非流请求仍使用连接/总超时。

运行中可以修改阈值、候选和运行模型配置；阈值约每秒重读，下一次任务尝试读取最新路由。已经发出的请求不会即时换模型。

## 成功产物复用与旧版本

模型、账号、输出预算、并发及吞吐配置不再属于业务产物身份；它们仍留在调用和产物来源记录中。通过产物必须满足实际输入哈希、任务逻辑/Skill/Schema版本、引用/结构校验。输入、业务逻辑、关注点、人工指导或相关导入变化时，仅相应任务及受影响下游失效。

对`2aee6cc`存在明确迁移证明的任务，可在精确重建旧身份、核对输出内容和当前输入校验后复用；不接受任意历史结果。业务实现已变化、证明不足或校验失败的节点仍需重跑。旧模型语义响应缓存不跨模型冒充新响应。失败节点在显式配置改变后可以开启新的有界尝试窗口，旧失败、用量及修复记录保留。

## 验证范围

离线测试涵盖完整/部分导入、来源隔离、恢复预算、优先用例、嵌套思考参数、跨Key网关并发、缓存迁移、动态候选及独立账号额度。后台服务在本机隔离数据目录检查；Windows原生运行和客户网关降速切换仍需客户验证。不将模拟响应说成14用例真实验收，也不据离线测试宣称语义质量提升。
