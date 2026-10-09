# 三角色协议与操作

## CLI 与子 Agent

scene-pipeline 接受 --model、重复 --spec-document、--output-dir。
默认 --match-backend agent、--recommend-backend agent、--agent-mode packets。
可选 --analysis-layers SR,AR；默认沿用现有方法的 SR 关注点视角，融合 SSD 保留 RR/SR/AR 证据。

packet 模式依次停在 checker、matching、recommendation 等待阶段。
阅读 run_manifest.json 的 stages 与对应 batches 目录，最多开启三个子 Agent 分工。
子 Agent 可以直接读 packets 并将提案 JSON 保存为 results/<batch_id>.json；
接受的匹配需执行 worker 完成逐对复核。分别执行 run-agent-batches --stage-dir <目录> --sources-index <索引>
--worker-index 0|1|2 --worker-count 3 --env-file .env。
分片 worker 内串行请求，合计最多三个并发；单个独立 worker 最多三个并发。
结果须包含原 packet 的 batch_id、input_hash 和 output_contract 规定的字段。

每阶段结果完成后重跑同一 scene-pipeline 命令，工具校验并推进到下一阶段。
--agent-mode external 可在一个进程自动调度最多三个 ECNU 语义 worker。
已有合法结果按 packet 内容哈希复用；未知 ID、缺结果、重复、无依据或伪造引用均拒绝。
等待阶段退出码为 0，表示批次成功准备，不代表完整交付；必须检查 complete=true。
外部请求失败或结果无效须修复后续跑，不切换后端冒充成功。

## 原始场景与章节

scenarios 中统一使用 scenario_id、use_case_id、scenario_type、name、preconditions、
trigger、scenario_steps、expected_result、recovery、concern_keys、source_refs、target_sections。
source_refs 包含 document、chapter_id、heading_path、line_start、line_end。
target_sections 按文档分别列出所属用例章节，空数组表示缺少关联。
Markdown 保留原始空行，忽略代码围栏中的假标题。
示例章节定位基于 Markdown/TXT 标题；Word/PDF 的文本抽取能力仍保留在旧入口，
新用例分包要求可定位的标题及用例标识，缺少时应补充规范抽取输入而非伪造行号。

生成候选追加 candidate_id、exchange_id、ssd_message_id、generation_status。
显式异常的生成端分类保留有效输入标签并使用本地词汇，检查端分类独立由语义抽取完成；
两端标签有差异时报告 classification_discrepancies，不能自动改写标签抬高指标。
classification_coverage 明示显式异常的标签覆盖与未分类 ID；分类指标的有效解释依赖标签覆盖。
Checker 的稳定 ID 包含用例、类型、前置条件、触发、步骤及结果，保留同触发/结果但不同约束的场景。

## 匹配与指标

Agent 场景匹配需要 checker_scenario_id、generated_scenario_id、status、evidence、
missing_behavior。partial 必須填写缺少的行为；unmatched 由完整批次的无匹配集合推导，
不使用虚假占位场景 ID。
full 的 missing_behavior 必须为空。每个有接受链接的批次须携带 semantic_verification：
version=grounded-pair-v2、pairs_hash、proposed_matches、decisions、model。
决策按 pair_index 绑定提案，保存两端完整 trigger 原文、full/partial/unmatched、理由与缺失行为。
分别返回布尔语义判断 same_specific_trigger、shared_core_behavior、same_expected_outcome、
compatible_constraints；触发、行为或约束兼容任一为假则 unmatched，四项皆真才可 full，否则 partial。
最终状态按分项派生，原始标签矛盾时保存 llm_status，不要求模型改写语义判断来通过格式。
不同失败机制、实体或操作不能只凭同类错误归为 partial。
worker 将每组最多八对提交给独立的第二轮 LLM 判断；脚本校验引文、完整性与结果一致性。
仅共享大类、用例或成功流程前缀不算匹配；未知异常响应不能报 full。
未完成复核的提案不得进入正式指标；该步骤仅审查匹配关系，不审查或删除生成候选。

可用当前原生子 Agent 对全部已接受关系再独立复核：

~~~bash
python .cac/tools/scene_completion.py prepare-matching-review \
  --stage-dir <output>/batches/matching --review-file <review_packet.json>
python .cac/tools/scene_completion.py apply-matching-review \
  --stage-dir <output>/batches/matching --review-file <review_results.json>
~~~

子 Agent 阅读 packet 全部 pairs，按其中 instructions 填写完整 decisions，保留 input_hash、
model、reasoning_effort。每条 review_id 必须且只能出现一次，并引用两端完整 trigger；
判定量表沿用四项语义判断和缺失行为。应用前校验全部结果和批次内容指纹，
拒绝遗漏、未知关系、过期输入和伪造引文；不得只手工调整选中的关系。
保存 native_review.json 和此前复核记录，标明实际复核模型。
后续 recovery 可以寻找其他具体关系，但不能恢复已被原生复核否决的同一关系；
新增接受关系也应独立复核。保留每轮输入与决定，防止续跑重新采纳已发现的反例。
应用后重跑 scene-pipeline，重新汇总指标、候选与推荐；历史结果不能直接当作新结果。

漏报率：没有 full/partial 链接的 C 场景数 / C 总数。
当前已有完整率：有 full/partial 链接的 G 场景数 / G 总数。
具体关注点、大类、特殊类型各在自己的集合内去重，分类重合要求两端同属该分类。
主成功、可选、未分类异常单列。零分母为 null，多标签各类数量不能相加。
旧 score-scenario-matches 的参考测试覆盖率/自动采纳代理率仍保持兼容的 full-only 定义。

## Embedding 与 Rerank

--match-backend embedding --recommend-backend embedding 使用 ECNU_EMBEDDING_TEXT。
完整阈值默认 0.85，部分阈值默认 0.70；可用 --full-threshold、--partial-threshold 修改。
阈值与相似度只能作为未校准判定，不能解释成概率。

--rerank 默认关闭；使用 ECNU_RERANK，POST /rerank，提交 query、documents、top_n。
top_n 为证据候选总数，避免接口默认只返回 5 条；校验每条返回的 index 和 relevance_score。
生成场景到关联用例章节的证据片段先用 embedding 召回最多 20 条，再 rerank。
Agent 阅读排序证据后判断支持度；embedding 推荐以 rerank 最高分替换相关度代理。
缺失度、匹配、总指标/分类指标和待推荐集合保持原口径。
分数 0.7 × support_score + 0.3 × missing_score，低于 0.5 标记待确认，0.75 起为高优先级。
Agent 的 support_score≥0.75 须保存 support_verification（support-scale-v1）：
复核候选、引用证据、原始评分/理由及其哈希；按证据量表标注 none/topic/context/explicit_constraint/direct，
上限分别为 0/0.25/0.5/0.75/1，0.75 及以上保存证据中的支持约束原句。
复核按量表降低过高支持度，保留 initial_support_score、initial_basis、复核理由及模型；缺失度不变。
保存相关度分数和来源；相关度不等于逻辑蕴含，不同评分后端不能当作同一校准概率比较。

## 交付文件

sources_index.json、scene_model.json、generated_scenarios.json、existing_scenarios.json、
scenario_matches.json、metrics.json、recommendations.json、run_manifest.json、
report.md、scene_assessment.xlsx。
JSON 为可复现实验与分类指标的完整来源，Excel 不执行文档/模型内容中的公式。
metrics.json 仅在匹配和推荐全部完成后发布；失败或等待批次时不保留旧正式指标与报告。
本地 .scene_cache 忽略 Git；密钥仅来自环境，不进入结果与日志。
缓存也保存经校验的 rerank 索引/分数；候选评分复用要求候选内容、证据与增强开关的哈希完全一致。
相同 packet 续跑保留原始结果的模型与完整证明；重分包复用保留每项原执行批次、输入哈希和模型。模型身份缺失或与当前后端不同的推荐评分必须重新执行，不能用当前配置替旧结果补写模型身份。
worker-status-* 保存每个分片的完成/失败状态；run_manifest 记录模型、输入版本及最终阶段状态。
run-agent-batches 可重复传 --batch-id，只重试该 worker 分配范围内的指定批次；完整性仍按全部 manifest 计算。

## 需求专用异常验收

本轮显式使用 --requirement-document 与 --design-document。生成器可读两类文档，检查器分包只读 checker_sources_index.json 的 requirement 文档；设计新增异常和参考测试集不进入 C。旧 --spec-document 兼容原来的全输入抽取口径，不能用于本轮验收。

matching 每包一个 C、最多八个同用例 G，decisions 必须覆盖全部笛卡尔场景对（包括 unmatched）；遗漏任一对拒绝整个批次。先独立复核接受关系，再对仍未覆盖的需求异常复核相关比较。完整匹配要求具体触发、行为、结果及约束一致；部分匹配必须共享具体异常条件与核心行为，并指出缺少内容。不同失败机制、对象、操作或明确矛盾不得匹配。
decisions 是逐对判断的权威记录，tools 据此生成汇总 matches。模型两处汇总文字不同时保留 raw_match_summary，但 ID、状态、覆盖集合必须一致；冲突拒绝，不能通过整理解释文字改变语义状态。
冗余 matches 汇总省略或为 null 时仍从全部 decisions 构建，并保留原值；缺少任一逐对判断仍拒绝。工具不会从空汇总推断场景已覆盖。

exception_overall 按全部 Gₑ 与需求异常 C 去重计算；generation_contributions 单列明确异常保留、关注点推导和共同贡献。by_concern_exception、by_group_exception 保留异常分类小指标，overall 继续给全部场景指标。严格 miss_rate < 0.05、分母 > 0、全部批次完成，才通过验收。evaluate-generator 重新核对这些输入与保存指标。
本轮验收要求两端独立分类审计、实际 ecnu-max 批次身份，以及 primary/recovery 全量 gpt-6-luna / max 复核。归档的原生决定必须逐项等于计分证明，恢复前的 ECNU 证明与原始输入也要完整绑定；仅有相同输入哈希不能证明决定一致。

coverage_diagnostics.json 逐条列出需求章节、异常触发、关注点、组件/调用边、生成候选、匹配依据、缺口原因与建议。scene_assessment.xlsx 导出所有类型场景，指标表“关注点说明”紧随“类别”，中文说明与原编码并存。禁止通过删减 C、宽泛匹配或把检查结果直接写入 G 改善指标。
需求专用检查的推荐目标仅限已评估需求章节；设计章节单列为相关证据，不据此断言设计缺少异常。既有实现组件缺少精确 SSD 交换时，在挂载清单中标记待确认检查位置，不虚构调用关系。

架构与挂载另输出 architecture_changes.json、architecture_calls.svg、concern_placements.md；RR 参与总览和实际依赖调用分别展示。run_manifest 保存工具文件哈希、源版本；生成输入记录实际 Skill 哈希。已知明确矛盾不得转为部分匹配；未知或遗漏细节作为缺失行为列出。
架构关系的原文证据单独以 architecture_evidence_review.json 全量复核：40 条明示关联与 7 条待确认关联的演示中，图以实线/虚线区分，保留输入绑定和理由。字段/错误码存在不能证明直接调用，原文“系统”执行也不能自动宣称某具名实现服务为调用方；不删除生成候选或改变匹配指标。

需要复核检查器分类时运行 `prepare-checker-taxonomy --output-dir <output>`，再以 checker_sources_index.json 执行该目录下 batches/checker-taxonomy 的 worker。复核仅输入固定 C 的行为、原始需求章节和关注点定义，不读取 G、设计或原标签；不允许改变场景内容、ID 或分母。重跑编排自动应用完整复核，保存分类变化、原因和章节依据。未完成或过期复核会阻止发布正式结果。分类未标注不直接等同于关注点体系无法表达。
分类提案必须经 requirement-taxonomy-proof-v1 独立复核：每条异常逐字绑定触发条件，每个提案 key 给出 supported 布尔判断及依据；只有 supported=true 的标签进入分类。原提案、全部判断、引用、模型及输入哈希随结果保留。复核允许补充有直接原文依据的遗漏标签，不能推断数据库实现或把内部服务误当第三方；矛盾说明或缺少任一提案标签判断都会阻止完成。
原始需求参与者/系统边界上下文随分类包提供，可引用该明确提供的行范围；其余未分配章节仍禁止引用。matching_verification_tile_size 默认为 8，可在配置中设为 1—8，用于缩小独立复核包；不改变完整比较集合或匹配量表，证明记录实际分片大小。
生成器的独立标签复核入口为 prepare-generator-taxonomy，使用 sources_index.json 与 batches/generator-taxonomy。只核实明确分支与来源约束的分类，原始需求/设计可用，C、匹配及原标签不输入。场景不增删、行为与 ID 不变；泛化候选保留其注册表定义。此步骤不判断适用性；标签变化、分项依据及引用保留，缺失或过期证明阻止正式生成阶段完成。
