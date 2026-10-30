# 指标诊断与关注点优化建议

入口：**最终结果 → 指标诊断**。诊断独立于节点的网络／格式技术诊断，不修改正式G/E/GT、匹配或分数。

## 使用流程

1. 选择原始、扩展或业务审核后的测试来源，可诊断全项目或当前用例。没有完整评测也可手动诊断，报告会标出未完成范围。
2. 工具冻结执行、来源、定义、模式、匹配与活跃节点产物版本，完整列出正式指标的损失。缺少保存的单位对应时显示核对缺口，不推测未命中ID。
3. 管理Agent的独立模型按相关交互、字段、规则及引用片段分析；每项只有一个主因，可有次因，区分已核实、疑似、待确认。GT未验证不等于生成错误。
4. 点击指标筛选损失；E/G/GT横向查看，引用支持Markdown阅读和行号定位。清单按当前用例取片，每页100项；完整JSON、Markdown可下载。
5. 有正向材料、框架或独立已审核历史依据时提出关注点／模式／推荐配置建议；代码、原始需求和测试问题只作为处理建议。
6. 人工选择建议、填写确认人，先查看修改前后与DAG影响，再确认应用并重跑。管理Agent没有批准诊断建议的工具。
7. 修改保留版本及原报告。新评测完成后保存前后对照；测试来源、分类、粒度及分母变化标为口径变化，不能称为模型质量提升。

## 指标与原因

沿用正式评测，不重定义公式：

| 层级／指标 | 损失对象 |
|---|---|
| 关注点漏报率 | GT_c−E_c中未被M_c命中的绑定 |
| 关注点生成有效率 | G_c中未被GT_c验证的绑定 |
| 场景采纳率／误报率 | M或Q中未被场景GT验证的候选；分别采用原公式分母 |
| 推荐筛选遗漏 | M已命中的GT对应项未进入Q |
| 关键缺失召回 | 关键GT−E中未被Q命中的场景 |
| 实际人工采纳率 | 人工明确“无需纳入”的推荐；暂缓与未审核不作负反馈 |
| 抽取Acc | 人工GT中的未命中单元；新结果保存对应ID，历史仅H/N时明确待展开 |

正常、可选、不适用及待确认项不进入确定集合。报告保留排除原因、计数核对及版本不一致信息。跨指标重复出现的同一对象不代表额外的异常计数。

主因分类：识别／适用、定位、分类与定义、模式与粒度、GT与覆盖、场景匹配、推荐排序、任务／材料未就绪、GT未验证、待查明。规则清单完整与模型已核查范围分别统计。

## 自动执行与费用

- 仅在新执行轮的评测完成后自动排队一次，同快照复用。服务启动不扫描旧项目批量调用模型。
- 每次诊断追加独立的100,000 Token上限，同时沿用管理Agent账号账本、模型配置与网关最多3并发。重试也计入，未知用量保守保留，不清账。
- 模型上下文仅含本批记录、对应交互、必要定义和原文片段；完整资料留在冻结快照。没有额外的无上限压缩调用。
- 格式校验最多两轮修复，不反复追加完整失败历史。预算、配置或网关问题交付部分报告，不阻塞业务流水线。
- 断点只恢复安全检查点。已收到的完整响应先本地重新校验；状态未知的POST不会自动重发。可通过“继续未完成诊断”显式恢复，预算不重置。
- 业务审核包只携带已保存report.json，可浏览但禁止调用模型、应用建议；模型上下文、响应、预算账本及诊断快照不进入交接包。

## CLI

```bat
scene.cmd quality diagnose --project PROJECT_ID --test-set original --wait
scene.cmd quality diagnose --project PROJECT_ID --case G-001 --test-set original --wait
scene.cmd quality diagnose --project PROJECT_ID --tool-only
scene.cmd quality diagnose --project PROJECT_ID --resume DIAGNOSIS_ID --wait
scene.cmd quality report --project PROJECT_ID --diagnosis DIAGNOSIS_ID
scene.cmd quality impact --project PROJECT_ID --diagnosis DIAGNOSIS_ID --file approvals.json
scene.cmd quality apply --project PROJECT_ID --diagnosis DIAGNOSIS_ID --file approvals.json --dry-run
scene.cmd quality apply --project PROJECT_ID --diagnosis DIAGNOSIS_ID --file approvals.json --rerun
```

确认文件：

```json
{
  "snapshot_hash": "报告的snapshot_hash",
  "reviewer": "实际确认人",
  "approvals": ["报告中可应用的建议ID"]
}
```

`--dry-run`不会应用定义，也不会启动模型。CLI与网页共享版本校验和审计。模型只能建议，显式quality apply才是执行授权。无依据或研发建议不能应用；快照过期、项目运行中或配置冲突会拒绝覆盖。

管理工具：`quality_diagnose`、`quality_report`、`quality_evidence`。证据每次限同一用例1—6项；诊断资料不得注入G或推荐排序上下文。

## 数据与复用

项目目录`quality-diagnostics/<ID>/`保存冻结快照、报告、响应、独立预算及人工应用审计。报告可恢复和下载，敏感诊断材料不提交Git或程序包。

关注点语义调整保守覆盖G_c/E_c/GT_c及相关下游；模式调整覆盖相应场景链；只改K及排序权重使用独立的排序身份，不重做抽取、识别或GT整理。影响不能证明局部时明确扩大范围，不能虚报只影响一个节点。

Windows包只包含程序及说明，不含项目数据、凭证或账本。原生Windows与客户网关仍需现场验证。
