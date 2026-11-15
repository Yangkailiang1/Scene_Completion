# 本地 CLI 与 Code Agent 接管

用户启动终端 Agent，系统准备诊断与交接包。执行步骤见 [终端接管 Skill](../../.cac/skills/scene-terminal-recovery/SKILL.md)。现有根启动入口、HTTP路径和存储位置保留。

```sh
python /ABS/scene.py --local --data-dir /ABS/DATA --env-file /ABS/.env run --project ID --wait
python /ABS/scene.py --local --data-dir /ABS/DATA diagnose --project ID --node UC-001:ssd-generate
python /ABS/scene.py --local --data-dir /ABS/DATA repair-export --project ID --node UC-001:ssd-generate --batch BATCH --out /ABS/repair.json
python /ABS/scene.py --local --data-dir /ABS/DATA repair-submit --project ID --node UC-001:ssd-generate --batch BATCH --file /ABS/repair.json --validate-only
python /ABS/scene.py --local --data-dir /ABS/DATA repair-submit --project ID --node UC-001:ssd-generate --batch BATCH --file /ABS/repair.json
python /ABS/scene.py --local --data-dir /ABS/DATA run --project ID --wait
```

`--local`直接调用应用服务，不启HTTP，也不自动回退HTTP。支持projects/create、status、diagnose、prompts、repair-export/submit、rerun单节点、run--wait、execution-control、configure和results。其他审核、账号管理等既有命令仍使用HTTP；capabilities明确列出本地支持范围。

`execution_complete`指调度产物是否全部完成，`result_pending_count`保留最近执行中待修正范围数量，`complete`及`review_complete`仍独立反映业务问题/审核；不能把执行完成当作所有业务已确认。命令退出码：0成功，2失败/阻塞/待接管，3等待超时。诊断中的handoff状态为complete、needs_agent或needs_user。运行时观察JSONL的kind，不解析自然语言日志来判断完成。

多批次修复采用任务类型及冻结语义输入的稳定批次ID；节点修复版本同时进入SSD及项目范围调度身份。绑定原输入、Schema、提示、注册表、指导、任务语义版本及节点版本。修复通过原业务校验后才供流水线采用。成功批次保存带校验身份和内容校验和的检查点；节点其他批次失败不会让其重新调用模型。

子任务的真实模型调用、检查点复用及Code Agent提交分别保存在事件与执行元数据中。诊断历史保留原因、采用/拒绝、错误堆栈和原任务包。代码故障须修源码并检查，使用`rerun --project ID --node NODE`开启新的有界执行窗口，再用run--wait核验；额度阻塞和未决用量不能借业务修复跳过。独立worker在CLI返回后继续执行，共用跨进程锁。
