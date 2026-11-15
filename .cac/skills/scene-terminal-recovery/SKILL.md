---
name: scene-terminal-recovery
description: 由用户启动的终端 Code Agent 接管 SSD 或项目范围流水线；不依赖 HTTP，按具体失败批次校验并恢复。
---

# 终端工作台接管

本 Skill 供用户在 Claude Code 等终端 Code Agent 中调用。系统只准备诊断，不自动启动或付费调用另一个 Agent。根目录 `scene.py` 为正式 CLI；全局参数必须放在子命令前。使用绝对项目目录，终端可处于任意工作目录。

1. `python /ABS/scene.py capabilities` 查看能力；`python /ABS/scene.py --local --data-dir /ABS/DATA --env-file /ABS/.env status --project ID` 查看任务、执行完成与业务审核完成两种状态。
2. 同样全局参数下 `run --project ID --wait` 启动并等待。退出码0表示执行完成，仍可能有业务待确认；2表示失败/阻塞/需接管；3表示等待超时，先查看 status，不能盲目另启 worker。所有输出为 JSON/JSONL。
3. 失败后 `diagnose --project ID --node NODE` 查看 handoff、故障种类、批次清单、检查点、运行参数、错误及堆栈。`run/code_agent_handoff/` 保留历史。额度不足、用量不确定、待回答业务问题须交用户处理，不得用修复包绕过。
4. 模型任务：`repair-export --project ID --node NODE --batch BATCH --out /ABS/repair.json`。单批次节点可以省略 `--batch`。多个批次必须精确选择，不按“最后一个任务包”猜测。只使用该包冻结输入、原 Schema、提示、候选及短编号映射。
5. 每次业务修复使用该节点的独立允许上下文。G只看正向需求、SSD、接口、实体和规则，不读取E/GT。E和GT分别只看自己的异常来源。只有比较节点能看指定两侧。只修改payload及note；不能增加不存在的字段/锚点、删除固定模板或伪造出处。未知事实按契约保留pending。
6. `repair-submit --project ID --node NODE --batch BATCH --file /ABS/repair.json --validate-only`，通过后去掉 `--validate-only` 提交。拒绝过期、错节点、错批次、跨通道、冻结Schema不符的结果。提交是Code Agent修复，不得描述为配置模型重新推理。
7. `run --project ID --wait` 继续。若已暂停，用 `execution-control --project ID --action resume` 后查看status；成功批次校验后复用，只处理失败和受影响下游。不要额外添加指导导致刚提交的修复失效。若要改变业务指导，应重新导出相应新版本修复包。
8. 脚本/调度故障：交接标记 `code_failure`，可能没有模型任务包。根据堆栈修复源码、运行必要检查，再用`rerun --project ID --node NODE`恢复，并用run--wait核验；不能手写正式产物跳过脚本。源码修复与业务payload补交分开记录。
9. `results --project ID --analysis-scope all` 核对三层结果及指标；`results --project ID --case UC-001` 查看交互修订。核对任务身份、修复来源、业务待确认范围和额度账本，不能重置账本、强杀无关进程或覆盖人工修改。

本地模式与HTTP共用应用服务、项目锁和存活worker检查。运行中的项目不能并发提交修复或再启动。暂停等待在途请求结束；停止可能产生用量不确定，必须先核对，不能自动重发。

本 Skill 与模型运行时 `.cac/skills/scene-node-recovery/SKILL.md` 分工不同：后者只修业务JSON且禁止改源码；本终端 Skill 对代码故障允许修源码并验证，不能降低业务校验规则。
