# 最小交互步骤与异常粒度分流

适用于 `scene-workflow-v5`；匹配规则版本为 `two-level-concern-scenario-v8-atomic-scoped-failures`。旧报告保持历史版本，不能用旧场景反推新版关注点。

## 建模与定位

`fused-ssd-source` 保存输入或模型给出的原融合SSD。`interaction-normalize` 输出规范化步骤计划，`fused-ssd` 工具恢复正式消息数据和API身份。明确给出双方、原子步骤、Order和返回关系的结构化输入先逐条核验；歧义、混合处理或返回配对不唯一时才调用模型。工具不会代替模型识别关注点。

每个本地自检、跨对象请求、返回分别占一步。明确的数据库本地执行不能藏入返回消息的括号或说明中。平台响应校验和向Actor返回分别保存；已有真实返回只保留一次。一个数据库原子事务内的业务校验与原子写入不机械拆散。

- `execution_order` 是跨RR/SR的实际总顺序；`sequence` 是层内序号，两者不能混排。
- `source_step_ids` 与 `normalization.origins` 保留原步骤到多个子步骤的映射。
- 请求／响应数据由工具从原消息恢复，不让模型重新抄写字段或跨接口复制约束。
- 本地字段校验通过 `validates` 引用实际消息，不增加同一字段的计分绑定。
- 明确由数据库执行的存在性、唯一性、版本、状态等业务检查归实际自检；上游只保留关联。
- 外部Service及外部数据库的已确认调用必须识别可用性，逻辑资源服务仍保留物理来源和外部身份。具体超时需要独立依据。

## 独立分流与全局分析

每个用例的 `existing-scope` 和 `test-scope` 分别读取各自原始异常单元，输出 `interaction`、`global`、`pending`。同一原分支混合多个触发时拆成多个单位，保留原分支ID；正常、可选和待确认不进入确定集合。

交互级进入请求／响应／自检定位。全局级进入调用顺序、依赖一致性、级联清理义务或C/U/D幂等业务操作定位，不伪造交互ID。跨服务数据一致性仍属于交互级。G、E和GT分别识别、细化，不共享异常答案。

G/E完成后先输出 `global-concern-compare`、`global-scenario-compare` 和 `global-recommend`。GT单独完成后生成 `global-concern-evaluation`、`global-scenario-evaluation`、`global-evaluation`。GT独立发现的关系可以揭示G遗漏，不能因G未抽到依赖而删除GT。

## 查看、纠正与重跑

最终结果的“交互对照”只查看交互异常；“全局异常对照”独立查看全局关注点、场景、推荐和指标。同一个全局失败关联多个用例时项目只计一次。

全局页的“审核异常的交互／全局归属”可更正分流。CLI：

```bat
scene.cmd scope-review --project PROJECT_ID
scene.cmd scope-review --project PROJECT_ID --file scope-answer.json --dry-run
scene.cmd scope-review --project PROJECT_ID --file scope-answer.json
```

输入包含 `task_key`、`expected_version`、完整 `units`，可附 `reviewer`、`reason`。单位字段：`source_id`、`trigger`、`scope`、`global_kind`、`entity_ids`、`related_cases`、`reason`。全局关联用例和实体的顺序表示依赖方向；不能随意排序。

保存保留审核人、时间、历史及输入身份，返回实际下游影响范围，不调用模型。研发再显式定向重跑；输入或审核版本改变时拒绝覆盖。审核包携带粒度回答，反馈导入先预览冲突，重复反馈不重复应用。

## 验证与限制

离线回归覆盖原步骤一对多、执行顺序、反向返回、本地字段不复制、跨通道分流、GT独立关系、GT失败不阻塞G/E、人工修正和版本冲突。真实验收的成功节点、指标、Token和未解决事项另存验收记录；离线通过不代表真实模型输出已稳定。
