---
name: scene-controller
description: 持续编排场景分析流水线，处理批次阻塞并完成工具验收及产物交付；用于Claude Code或其他宿主主控，不作为批量语义包。
---

# 主控编排与交付

主控负责让当前授权范围到达可验证的交付状态。后台进程启动、正常退出、单阶段通过或流水线`complete=true`都不代表任务交付。不得约定固定轮询次数后把收尾留给只读监控。模型、推理、并发、预算及范围沿用当前配置；不为完成验证扩大实验或重跑成功阶段。

先用`python .cac/tools/scene_workflow_status.py --run-dir <run>`读取紧凑任务状态。可传`--process-file <执行器状态>`及重复的`--budget-ledger <账本>`，WSL中使用WSL进程状态文件。`--wait-seconds 60`仅在状态变化或超时返回，避免把完整版本、原文、原包及日志不断送给主控。未交付时退出码2是状态，不能据此重新启动实验。

执行器仍活跃时不启动第二份流水线，不编辑它已经加载的语义工具。需要维护时先用状态工具的`--pause-admission`停止新调用，让在途请求完成、用量结算和缓存落盘；执行器停止后再修改。按任务定位失败的JSON字段、条目和证据。批量最多两轮、首次自动主控接手各自持久计数；它们不是主控放弃任务的条件。新组件、调用、关注点或原文修订先确认；确认期间继续独立任务。未知用量或额度停止不得清账本或提高额度。检查器误判先修通用规则并离线复验原返回，不能用重生成掩盖误判。

主控不得把失败都归因于模型。区分原文不足、抽取错误、结构/引用协议错误、验证器错误、限流/断连、预算和编排遗漏。工具错误只调查对应函数和相关测试。首次接手仍失败时，继续定位剩余缺陷、修改通用工具或提示词、运行相关回归并离线复检旧输出；不能重复同一请求等模型碰运气。确需新语义修复时，用`scene_supervisor_continue.py`登记新的纠正计划，再恢复原流水线；计数累计，不重置批量预算，不改通过标签。修复后继续当前目录，保留原包、拒绝、执行模型和用量证明。未知用量默认停止；显式配置保守续跑时，保留原请求全部占额，核算同账户所有模型后才允许接手，不能重发超时请求或换账本避开限额。仅真实缺证据、必要授权、无法安全预留或全部配置额度耗尽时报告具体阻塞。协议及计划字段详见`../scene-concern-gap/references/case_execution.md`。

流水线计算结束后，主控仍需完成：

1. `check-interaction-run --output-dir <run>`检查完整来源、集合、依赖与执行证明。
2. `validate-interaction-run --output-dir <run>`生成真实回归和零新增模型调用续跑证明。
3. `prepare-interaction-review --output-dir <run>`准备独立效果审查。审查必须真实执行并匹配运行配置中的review_policy；不能把主控自述、另一模型或手写通过字段充当独立审查。缺少可执行审查入口时明确报工具缺口，不伪造审查记录。
4. `evaluate-modeling --output-dir <run>`核实`accepted=true`及实际验收理由。
5. `export-interaction-snapshot --output-dir <run> --snapshot-file <run>/final_snapshot.json`，然后`rebuild-interaction-snapshot --snapshot-file <run>/final_snapshot.json --output-dir <run>/rebuilt`，保留重建结果；离线重建不宣称新模型执行验收。
6. `python .cac/tools/scene_workflow_status.py --run-dir <run> --verify`核查执行验收绑定、快照和产物。自定义快照或重建目录时传`--snapshot-file`及`--rebuilt-dir`。默认状态读取不改运行；`--verify`在执行器停止后运行，离线重放可能刷新批次status文件，不调用模型。

只有`ready_to_deliver=true`才交付正式最终产物链接：Excel、Markdown、结构化结果、图、性能记录和快照，并明确实际用例范围。未完成时交付已有有效产物及准确阻塞，不能说全任务完成。Git只维护通用方法及工具；实验数据、指标、缓存和凭证保留本地。

可用`scene_finalize.py --run-dir <run> --review-config <独立配置>`实际执行回归、缓存续跑、独立API效果审查、验收及快照重建。审查配置须与运行的review_policy一致，保留原始模型执行证明。发现真实审查问题时继续诊断，不能改审查通过字段。

用`scene_controller_watch.py --run-dir <run> --state-file <本地watch.json>`检测停滞。连续600秒没有任务、纠正代码、诊断或真实回归证据变化时返回3，主控立即定位具体阻塞；反复状态查询、日志增长、长篇思考不算推进。已确定需外部处理时报告并结束付费空转，不把活进程冒充正常推进。

模型可用性预检、候选独立/主控辅助口径、筛选预算与最终交付试验见 [模型试验](references/model_trials.md)。只有需要开展候选对比时读取，模型列表和额度来自运行配置及用户授权，不写入语义提示词。

诊断超限、生成源缺陷、比较引用及部分匹配修复见 [定向恢复细则](references/recovery_details.md)。按当前失败阶段读取，不把全部历史规则重复发送给每个语义包。
