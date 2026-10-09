# 三 Agent 场景评估

- 漏报率：18/97 = 18.56%
- 当前已有完整率：347/472 = 73.52%
- 匹配后端：embedding；推荐后端：embedding；rerank：True
- 完整与部分匹配均计重合；分类分别去重，数量不可直接相加。
- 推荐评分未经概率校准；候选不代表已证实的产品缺陷。
- checker 显式异常标签覆盖：72/76；未分类 4 项。未分类异常只计入总计及未分类桶，分类指标依赖标签覆盖。
- generator 显式异常标签覆盖：3/37；未分类 34 项。未分类异常只计入总计及未分类桶，分类指标依赖标签覆盖。

## 各关注点指标

|关注点|漏报率|当前已有完整率|
|---|---|---|
|api.data.completeness（数据完整性）|5/5 = 100.00%|0/28 = 0.00%|
|api.data.format（数据格式）|2/5 = 40.00%|5/29 = 17.24%|
|api.data.legality（数据合法性）|10/12 = 83.33%|4/28 = 14.29%|
|api.data.length（数据长度）|不可计算（分母为0）|0/28 = 0.00%|
|api.data.range（数据范围）|4/6 = 66.67%|1/29 = 3.45%|
|api.data.size（数据大小）|1/1 = 100.00%|0/28 = 0.00%|
|api.data.type（数据类型）|不可计算（分母为0）|0/28 = 0.00%|
|common.timeout（超时关注点）|1/5 = 20.00%|5/15 = 33.33%|
|external_database.availability（数据库服务可用性）|不可计算（分母为0）|不可计算（分母为0）|
|external_database.query_performance（查询性能）|2/2 = 100.00%|不可计算（分母为0）|
|external_llm.access_permission（访问权限）|不可计算（分母为0）|不可计算（分母为0）|
|external_llm.availability（外部模型可用性）|不可计算（分母为0）|不可计算（分母为0）|
|external_llm.contract（外部接口契约）|不可计算（分母为0）|不可计算（分母为0）|
|external_llm.quality.context_completeness（上下文完整性）|不可计算（分母为0）|不可计算（分母为0）|
|external_llm.quality.instruction_following（指令遵循）|不可计算（分母为0）|不可计算（分母为0）|
|external_llm.quality.output_stability（输出稳定性）|不可计算（分母为0）|不可计算（分母为0）|
|external_llm.quality.prompt_security（提示词安全）|不可计算（分母为0）|不可计算（分母为0）|
|external_llm.quality.semantic_correctness（语义正确性）|不可计算（分母为0）|不可计算（分母为0）|
|external_service.availability（外部服务可用性）|15/15 = 100.00%|不可计算（分母为0）|
|external_service.contract（外部接口契约）|不可计算（分母为0）|不可计算（分母为0）|
|external_service.identity（调用方身份）|1/1 = 100.00%|不可计算（分母为0）|
|external_service.permission（调用权限）|4/4 = 100.00%|不可计算（分母为0）|
|human.authentication（身份认证）|不可计算（分母为0）|0/13 = 0.00%|
|human.authorization（权限控制）|5/5 = 100.00%|0/13 = 0.00%|
|internal_database.availability（数据库可用性）|1/1 = 100.00%|0/14 = 0.00%|
|internal_database.concurrency_consistency（并发一致性）|2/5 = 40.00%|3/14 = 21.43%|
|internal_database.field_validity（字段合法性）|2/2 = 100.00%|0/14 = 0.00%|
|internal_database.idempotency（幂等性）|1/5 = 20.00%|4/14 = 28.57%|
|internal_database.persistence（持久化能力）|不可计算（分母为0）|0/14 = 0.00%|
|internal_database.query_performance（查询性能）|0/1 = 0.00%|1/14 = 7.14%|
|internal_database.referential_consistency（关联一致性）|2/2 = 100.00%|0/14 = 0.00%|
|internal_database.required_field_completeness（必填字段完整性）|0/3 = 0.00%|3/14 = 21.43%|
|internal_database.resource_existence（资源存在性）|3/6 = 50.00%|3/14 = 21.43%|
|internal_database.uniqueness（唯一性约束）|0/1 = 0.00%|1/14 = 7.14%|
|service.analysis_generation.execution_deadline（执行时限）|不可计算（分母为0）|不可计算（分母为0）|
|service.analysis_generation.resource_consumption（资源消耗）|不可计算（分母为0）|不可计算（分母为0）|
|service.analysis_generation.result_correctness（处理正确性）|不可计算（分母为0）|不可计算（分母为0）|
|service.display_interaction.display_correctness（显示正确性）|1/1 = 100.00%|0/2 = 0.00%|
|service.display_interaction.render_performance（渲染性能）|不可计算（分母为0）|0/2 = 0.00%|
|service.query_retrieval.data_visibility（数据可见性）|1/1 = 100.00%|0/2 = 0.00%|
|service.query_retrieval.resource_existence（资源存在性）|8/9 = 88.89%|1/2 = 50.00%|
|service.query_retrieval.result_correctness（结果正确性）|不可计算（分母为0）|0/2 = 0.00%|
|service.release_activation.failure_recovery（失败恢复）|不可计算（分母为0）|0/1 = 0.00%|
|service.release_activation.prerequisite（发布前置条件）|0/1 = 0.00%|1/1 = 100.00%|
|service.release_activation.result_consistency（发布结果一致性）|1/1 = 100.00%|0/1 = 0.00%|
|service.resource_mutation.business_constraint（业务约束）|18/21 = 85.71%|2/9 = 22.22%|
|service.resource_mutation.concurrency_idempotency（并发与幂等性）|7/8 = 87.50%|1/9 = 11.11%|
|service.resource_mutation.persistence_consistency（持久化一致性）|不可计算（分母为0）|0/9 = 0.00%|
|service_relation.call_order（调用顺序）|不可计算（分母为0）|不可计算（分母为0）|
|service_relation.cascade_operation（级联操作）|不可计算（分母为0）|不可计算（分母为0）|
|service_relation.concurrency_consistency（并发一致性）|3/3 = 100.00%|不可计算（分母为0）|
|service_relation.cross_service_consistency（跨服务数据一致性）|6/6 = 100.00%|不可计算（分母为0）|
|service_relation.dependency_consistency（依赖一致性）|6/6 = 100.00%|不可计算（分母为0）|
|service_relation.idempotency（幂等性）|4/4 = 100.00%|不可计算（分母为0）|

## 各大类指标

|类别|漏报率|当前已有完整率|
|---|---|---|
|api_data|12/18 = 66.67%|14/198 = 7.07%|
|common|1/5 = 20.00%|5/15 = 33.33%|
|external_database|2/2 = 100.00%|不可计算（分母为0）|
|external_llm|不可计算（分母为0）|不可计算（分母为0）|
|external_llm_quality|不可计算（分母为0）|不可计算（分母为0）|
|external_service|19/19 = 100.00%|不可计算（分母为0）|
|human|5/5 = 100.00%|0/26 = 0.00%|
|internal_database|9/26 = 34.62%|38/140 = 27.14%|
|service_analysis_generation|不可计算（分母为0）|不可计算（分母为0）|
|service_display_interaction|1/1 = 100.00%|0/4 = 0.00%|
|service_query_retrieval|9/10 = 90.00%|3/6 = 50.00%|
|service_relation|18/18 = 100.00%|不可计算（分母为0）|
|service_release_activation|1/2 = 50.00%|1/3 = 33.33%|
|service_resource_mutation|25/29 = 86.21%|3/27 = 11.11%|

## 主成功、可选与未分类指标

|类别|漏报率|当前已有完整率|
|---|---|---|
|main_success|0/14 = 0.00%|14/14 = 100.00%|
|alternative|2/7 = 28.57%|5/5 = 100.00%|
|unclassified_exception|0/4 = 0.00%|4/34 = 11.76%|

## 完整匹配

- CHK-dc033d67ed6d7fea7386 ↔ GEN-A80786BF86：full。Embedding cosine=0.954041; uncalibrated thresholds 缺少行为：无
- CHK-e5d6373797f199d4819f ↔ GEN-40BF014705：full。Embedding cosine=0.952303; uncalibrated thresholds 缺少行为：无
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-2970C4053A：full。Embedding cosine=0.950290; uncalibrated thresholds 缺少行为：无
- CHK-230844760854191af35e ↔ GEN-4EF83574B5：full。Embedding cosine=0.950043; uncalibrated thresholds 缺少行为：无
- CHK-eec92d2501ba3f586f26 ↔ GEN-473A451238：full。Embedding cosine=0.960312; uncalibrated thresholds 缺少行为：无
- CHK-12bdaf49c4649869fb74 ↔ GEN-CB7E648FCA：full。Embedding cosine=0.950619; uncalibrated thresholds 缺少行为：无

## 部分匹配与缺少行为

- CHK-ca73433b0e4c5508040d ↔ GEN-2C16B99ABA：partial。Embedding cosine=0.919328; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-C52071CA71：partial。Embedding cosine=0.857919; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-13471D5938：partial。Embedding cosine=0.857919; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-3F756E8C43：partial。Embedding cosine=0.855758; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-1220FCB729：partial。Embedding cosine=0.855758; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-9FA15340C5：partial。Embedding cosine=0.851175; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-8D4F17F2CF：partial。Embedding cosine=0.851175; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-0C3FC4D752：partial。Embedding cosine=0.864741; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-8904B87C4B：partial。Embedding cosine=0.864741; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-1BE6AA7D6A：partial。Embedding cosine=0.867080; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-E637EE2685：partial。Embedding cosine=0.864806; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-F6B6716AB1：partial。Embedding cosine=0.853820; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-1B1F5BBC08：partial。Embedding cosine=0.850803; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-7C6D5AB474：partial。Embedding cosine=0.867461; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-A07569096B：partial。Embedding cosine=0.850720; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca73433b0e4c5508040d ↔ GEN-195E413858：partial。Embedding cosine=0.855049; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a140a6abf63a298d41d ↔ GEN-2C16B99ABA：partial。Embedding cosine=0.877054; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a140a6abf63a298d41d ↔ GEN-A7BEC826FF：partial。Embedding cosine=0.857796; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-2C16B99ABA：partial。Embedding cosine=0.904658; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-4E8410AA60：partial。Embedding cosine=0.871485; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-C52071CA71：partial。Embedding cosine=0.869466; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-13471D5938：partial。Embedding cosine=0.869466; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-3F756E8C43：partial。Embedding cosine=0.851528; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-1220FCB729：partial。Embedding cosine=0.851528; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-1BE6AA7D6A：partial。Embedding cosine=0.861105; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-E637EE2685：partial。Embedding cosine=0.862512; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-CD6D491158：partial。Embedding cosine=0.880640; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-F6B6716AB1：partial。Embedding cosine=0.879014; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-1B1F5BBC08：partial。Embedding cosine=0.877474; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-0F5CDC9B52：partial。Embedding cosine=0.867791; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-300C1C77E1：partial。Embedding cosine=0.868121; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-7C6D5AB474：partial。Embedding cosine=0.891766; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-764C8A64DC：partial。Embedding cosine=0.868485; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-A07569096B：partial。Embedding cosine=0.897498; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-195E413858：partial。Embedding cosine=0.896587; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462f39e4d7b711d9762d ↔ GEN-BE0AD4D45C：partial。Embedding cosine=0.864828; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ef03a7912ff59e5f9845 ↔ GEN-9CD781DEB4：partial。Embedding cosine=0.903300; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-2C16B99ABA：partial。Embedding cosine=0.858432; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-A00696170B：partial。Embedding cosine=0.874134; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-9F571B285A：partial。Embedding cosine=0.854059; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-1004A63E78：partial。Embedding cosine=0.854059; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-9FA15340C5：partial。Embedding cosine=0.858187; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-8D4F17F2CF：partial。Embedding cosine=0.858187; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-0C3FC4D752：partial。Embedding cosine=0.852183; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-8904B87C4B：partial。Embedding cosine=0.852183; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-35F76CD15C：partial。Embedding cosine=0.879386; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-CD6D491158：partial。Embedding cosine=0.862053; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-F6B6716AB1：partial。Embedding cosine=0.854257; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-1B1F5BBC08：partial。Embedding cosine=0.859304; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-0F5CDC9B52：partial。Embedding cosine=0.857664; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-300C1C77E1：partial。Embedding cosine=0.859871; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-7C6D5AB474：partial。Embedding cosine=0.893371; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-A07569096B：partial。Embedding cosine=0.850519; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-195E413858：partial。Embedding cosine=0.853524; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b127aa3162f66058e2fc ↔ GEN-BE0AD4D45C：partial。Embedding cosine=0.850269; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-3814b7488cac8d6dbfae ↔ GEN-4E8410AA60：partial。Embedding cosine=0.862239; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-3814b7488cac8d6dbfae ↔ GEN-A07569096B：partial。Embedding cosine=0.886163; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-723f2f5b18ccca1aa280 ↔ GEN-651DCB33AE：partial。Embedding cosine=0.872071; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0602c57e38b4c86d277 ↔ GEN-AE1C0334D2：partial。Embedding cosine=0.873678; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0602c57e38b4c86d277 ↔ GEN-B461A3A569：partial。Embedding cosine=0.873678; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-dbdb241c78cfd3dd4523 ↔ GEN-651DCB33AE：partial。Embedding cosine=0.877305; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-dbdb241c78cfd3dd4523 ↔ GEN-6ABDFABD2C：partial。Embedding cosine=0.947336; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-dbdb241c78cfd3dd4523 ↔ GEN-E80F0305D0：partial。Embedding cosine=0.857760; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-dbdb241c78cfd3dd4523 ↔ GEN-7B805E063F：partial。Embedding cosine=0.872704; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-dbdb241c78cfd3dd4523 ↔ GEN-BA08DD9531：partial。Embedding cosine=0.850228; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2e6002a6916c1cf742e8 ↔ GEN-651DCB33AE：partial。Embedding cosine=0.857988; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2e6002a6916c1cf742e8 ↔ GEN-6ABDFABD2C：partial。Embedding cosine=0.857353; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2e6002a6916c1cf742e8 ↔ GEN-E80F0305D0：partial。Embedding cosine=0.946925; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8441c6a972093a3b55d2 ↔ GEN-651DCB33AE：partial。Embedding cosine=0.886896; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8441c6a972093a3b55d2 ↔ GEN-6ABDFABD2C：partial。Embedding cosine=0.883526; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8441c6a972093a3b55d2 ↔ GEN-E80F0305D0：partial。Embedding cosine=0.851077; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8441c6a972093a3b55d2 ↔ GEN-7B805E063F：partial。Embedding cosine=0.932018; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8441c6a972093a3b55d2 ↔ GEN-50CF959F96：partial。Embedding cosine=0.852651; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8441c6a972093a3b55d2 ↔ GEN-533C8BD9C0：partial。Embedding cosine=0.891565; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8441c6a972093a3b55d2 ↔ GEN-A1D8671D23：partial。Embedding cosine=0.860336; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-a869c37581099b729c9a ↔ GEN-651DCB33AE：partial。Embedding cosine=0.875731; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-a869c37581099b729c9a ↔ GEN-7B805E063F：partial。Embedding cosine=0.850578; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-a869c37581099b729c9a ↔ GEN-5A2E65117E：partial。Embedding cosine=0.850319; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-a869c37581099b729c9a ↔ GEN-6799F1828B：partial。Embedding cosine=0.850319; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-a869c37581099b729c9a ↔ GEN-A94A4EE310：partial。Embedding cosine=0.865410; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-a869c37581099b729c9a ↔ GEN-D11418A07C：partial。Embedding cosine=0.870294; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-F7D7301370：partial。Embedding cosine=0.904954; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-61CC4C1495：partial。Embedding cosine=0.875233; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-67053C4136：partial。Embedding cosine=0.852570; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-A384331BF8：partial。Embedding cosine=0.852570; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-9E5F0AAB79：partial。Embedding cosine=0.858272; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-67FC2CF80A：partial。Embedding cosine=0.858272; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-DCA7585256：partial。Embedding cosine=0.858361; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-814CDDDEB8：partial。Embedding cosine=0.858361; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-142515D67A：partial。Embedding cosine=0.853393; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-51FE655D68：partial。Embedding cosine=0.853393; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-0C08B9C8B0：partial。Embedding cosine=0.857029; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-4D71771701：partial。Embedding cosine=0.854169; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-9416B7F8ED：partial。Embedding cosine=0.852803; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-3200C77527：partial。Embedding cosine=0.850540; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-FA900161EC：partial。Embedding cosine=0.852487; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-33f1bcdad44751fd6f70 ↔ GEN-24E83907B6：partial。Embedding cosine=0.851943; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a352df1236c99304736 ↔ GEN-F7D7301370：partial。Embedding cosine=0.875849; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a352df1236c99304736 ↔ GEN-49C77EEBE5：partial。Embedding cosine=0.943244; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a352df1236c99304736 ↔ GEN-61CC4C1495：partial。Embedding cosine=0.891203; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a352df1236c99304736 ↔ GEN-9416B7F8ED：partial。Embedding cosine=0.856423; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a352df1236c99304736 ↔ GEN-3200C77527：partial。Embedding cosine=0.855359; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a352df1236c99304736 ↔ GEN-FA900161EC：partial。Embedding cosine=0.868959; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4a352df1236c99304736 ↔ GEN-24E83907B6：partial。Embedding cosine=0.875464; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-37bb2a5379e510c7dd2d ↔ GEN-F7D7301370：partial。Embedding cosine=0.858266; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-37bb2a5379e510c7dd2d ↔ GEN-4581F93AAA：partial。Embedding cosine=0.928930; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e951f76a761ef8f161ed ↔ GEN-F7D7301370：partial。Embedding cosine=0.880353; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e951f76a761ef8f161ed ↔ GEN-49C77EEBE5：partial。Embedding cosine=0.860913; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e951f76a761ef8f161ed ↔ GEN-61CC4C1495：partial。Embedding cosine=0.932412; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e951f76a761ef8f161ed ↔ GEN-0807CDC1A9：partial。Embedding cosine=0.850709; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-22182443284cac31365b ↔ GEN-61CC4C1495：partial。Embedding cosine=0.890979; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b6e4acfd9edfa6b8494b ↔ GEN-49C77EEBE5：partial。Embedding cosine=0.860529; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b6e4acfd9edfa6b8494b ↔ GEN-FA900161EC：partial。Embedding cosine=0.853175; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-61efa0586abc16381114 ↔ GEN-C8A9312AFA：partial。Embedding cosine=0.885601; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-8D90BBB6CA：partial。Embedding cosine=0.941579; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-A01F9F0DBB：partial。Embedding cosine=0.859877; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-FF96158501：partial。Embedding cosine=0.853154; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-C20ED2EB65：partial。Embedding cosine=0.868111; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-8C71A5B82F：partial。Embedding cosine=0.859806; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-A88E7FFCD9：partial。Embedding cosine=0.855793; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-8A0E57C3C5：partial。Embedding cosine=0.850953; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-758A23C15F：partial。Embedding cosine=0.860653; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-81f1f8a4b88787b52967 ↔ GEN-216F7CA856：partial。Embedding cosine=0.857036; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-19666234a3786e63908f ↔ GEN-C8A9312AFA：partial。Embedding cosine=0.863902; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-19666234a3786e63908f ↔ GEN-7C9D158555：partial。Embedding cosine=0.943500; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-545c47406a75022d945a ↔ GEN-A01F9F0DBB：partial。Embedding cosine=0.884420; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-545c47406a75022d945a ↔ GEN-4A0AD69249：partial。Embedding cosine=0.850547; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd7720d75dcdd50ee230 ↔ GEN-FF96158501：partial。Embedding cosine=0.859437; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd7720d75dcdd50ee230 ↔ GEN-8C71A5B82F：partial。Embedding cosine=0.853527; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-db6deedddaa171e1ac54 ↔ GEN-7C9D158555：partial。Embedding cosine=0.851418; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-bb6c915e3b07e026a36a ↔ GEN-69F1AC0A02：partial。Embedding cosine=0.904762; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-bb6c915e3b07e026a36a ↔ GEN-34CFF8E551：partial。Embedding cosine=0.854834; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-bb6c915e3b07e026a36a ↔ GEN-2D2E542386：partial。Embedding cosine=0.854834; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-bb6c915e3b07e026a36a ↔ GEN-B8B9049E64：partial。Embedding cosine=0.851473; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-bb6c915e3b07e026a36a ↔ GEN-527E3DBA70：partial。Embedding cosine=0.851473; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-bb6c915e3b07e026a36a ↔ GEN-6281AAC9B1：partial。Embedding cosine=0.879166; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-bb6c915e3b07e026a36a ↔ GEN-5C083761AD：partial。Embedding cosine=0.857293; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-69F1AC0A02：partial。Embedding cosine=0.874813; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-88352D1CC0：partial。Embedding cosine=0.920035; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-A80786BF86：partial。Embedding cosine=0.855379; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-40BF014705：partial。Embedding cosine=0.851108; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-34CFF8E551：partial。Embedding cosine=0.861000; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-2D2E542386：partial。Embedding cosine=0.861000; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-3164C18FFD：partial。Embedding cosine=0.850323; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-CE3954E6FA：partial。Embedding cosine=0.850323; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-FDDCAAFE7E：partial。Embedding cosine=0.873715; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-F0064F1F05：partial。Embedding cosine=0.873715; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-5406886B89：partial。Embedding cosine=0.875339; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-1C8A4E5F0F：partial。Embedding cosine=0.875339; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-F56ADD8C97：partial。Embedding cosine=0.868209; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-073716B04B：partial。Embedding cosine=0.868209; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-B8B9049E64：partial。Embedding cosine=0.863727; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-527E3DBA70：partial。Embedding cosine=0.863727; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-58B011C3BF：partial。Embedding cosine=0.881748; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-6281AAC9B1：partial。Embedding cosine=0.870128; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-741ABFDB7C：partial。Embedding cosine=0.865867; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-5C083761AD：partial。Embedding cosine=0.878155; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-49d0fd8a7b02c8eb15da ↔ GEN-2C2A29EE38：partial。Embedding cosine=0.877175; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-dc033d67ed6d7fea7386 ↔ GEN-69F1AC0A02：partial。Embedding cosine=0.867224; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-dc033d67ed6d7fea7386 ↔ GEN-88352D1CC0：partial。Embedding cosine=0.852699; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e5d6373797f199d4819f ↔ GEN-69F1AC0A02：partial。Embedding cosine=0.861366; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e5d6373797f199d4819f ↔ GEN-C4F606A5C7：partial。Embedding cosine=0.868565; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e5d6373797f199d4819f ↔ GEN-7B845CE134：partial。Embedding cosine=0.890894; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e5d6373797f199d4819f ↔ GEN-80245B2409：partial。Embedding cosine=0.851576; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e5d6373797f199d4819f ↔ GEN-2C2A29EE38：partial。Embedding cosine=0.854767; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e5d6373797f199d4819f ↔ GEN-A3E4E8A897：partial。Embedding cosine=0.854404; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e5d6373797f199d4819f ↔ GEN-61B6E05B7A：partial。Embedding cosine=0.867174; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-69F1AC0A02：partial。Embedding cosine=0.877805; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-B8B9049E64：partial。Embedding cosine=0.854146; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-527E3DBA70：partial。Embedding cosine=0.854146; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-6281AAC9B1：partial。Embedding cosine=0.859886; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-5C083761AD：partial。Embedding cosine=0.851846; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-8E48196DDC：partial。Embedding cosine=0.859311; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-C4F606A5C7：partial。Embedding cosine=0.859285; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-54259CC79E：partial。Embedding cosine=0.863182; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-2C2A29EE38：partial。Embedding cosine=0.861471; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-765d10533c4bd2bc4f9e ↔ GEN-BDFE7023D6：partial。Embedding cosine=0.850923; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-901FF2D9C6：partial。Embedding cosine=0.910907; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-FFF4ABBA38：partial。Embedding cosine=0.855016; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-8374E4EDBB：partial。Embedding cosine=0.877550; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-BCC3E27560：partial。Embedding cosine=0.877550; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-5F6DB81748：partial。Embedding cosine=0.880156; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-86C6EC9A26：partial。Embedding cosine=0.880156; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-D4B995F12C：partial。Embedding cosine=0.861014; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-1AB235AB66：partial。Embedding cosine=0.861014; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-A5B180D24F：partial。Embedding cosine=0.876933; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-CE7541AED7：partial。Embedding cosine=0.876933; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-233718120A：partial。Embedding cosine=0.869433; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-BF1265D365：partial。Embedding cosine=0.869433; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-1FE69D9E91：partial。Embedding cosine=0.861751; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-F4C6A9A661：partial。Embedding cosine=0.861751; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-5FF97FFAE7：partial。Embedding cosine=0.877974; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-B419A69125：partial。Embedding cosine=0.850425; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-CC2857D09A：partial。Embedding cosine=0.866836; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-D6EF57EBF5：partial。Embedding cosine=0.865641; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-F5BAC8C3F4：partial。Embedding cosine=0.879890; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-AFDBE39B08：partial。Embedding cosine=0.855453; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-1D0A74161A：partial。Embedding cosine=0.857983; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-F0B79B061E：partial。Embedding cosine=0.862043; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-C4D9F57F38：partial。Embedding cosine=0.863923; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-33994B884D：partial。Embedding cosine=0.852190; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0e1fe1af96c01903bd ↔ GEN-B2A9FBC71E：partial。Embedding cosine=0.858548; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-944fb29222ba7668e96b ↔ GEN-901FF2D9C6：partial。Embedding cosine=0.861267; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-944fb29222ba7668e96b ↔ GEN-801F8EF3B7：partial。Embedding cosine=0.932376; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-944fb29222ba7668e96b ↔ GEN-2970C4053A：partial。Embedding cosine=0.856621; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-944fb29222ba7668e96b ↔ GEN-AFDBE39B08：partial。Embedding cosine=0.851934; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-944fb29222ba7668e96b ↔ GEN-F0B79B061E：partial。Embedding cosine=0.857542; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-944fb29222ba7668e96b ↔ GEN-C4D9F57F38：partial。Embedding cosine=0.850281; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-944fb29222ba7668e96b ↔ GEN-B2A9FBC71E：partial。Embedding cosine=0.854151; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-901FF2D9C6：partial。Embedding cosine=0.886376; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-801F8EF3B7：partial。Embedding cosine=0.868729; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-FFF4ABBA38：partial。Embedding cosine=0.898296; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-8374E4EDBB：partial。Embedding cosine=0.872455; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-BCC3E27560：partial。Embedding cosine=0.872455; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-5F6DB81748：partial。Embedding cosine=0.875369; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-86C6EC9A26：partial。Embedding cosine=0.875369; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-D4B995F12C：partial。Embedding cosine=0.853962; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-1AB235AB66：partial。Embedding cosine=0.853962; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-A5B180D24F：partial。Embedding cosine=0.857664; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-CE7541AED7：partial。Embedding cosine=0.857664; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-233718120A：partial。Embedding cosine=0.853052; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-BF1265D365：partial。Embedding cosine=0.853052; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-1FE69D9E91：partial。Embedding cosine=0.865308; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-F4C6A9A661：partial。Embedding cosine=0.865308; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-5FF97FFAE7：partial。Embedding cosine=0.883313; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-CC2857D09A：partial。Embedding cosine=0.850768; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-D6EF57EBF5：partial。Embedding cosine=0.884803; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-F5BAC8C3F4：partial。Embedding cosine=0.873852; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-B2A9FBC71E：partial。Embedding cosine=0.855247; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-7f7d740673100d1eecb1 ↔ GEN-2970C4053A：partial。Embedding cosine=0.854511; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-7f7d740673100d1eecb1 ↔ GEN-FFF4ABBA38：partial。Embedding cosine=0.914562; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-71490921e52f1f10aa97 ↔ GEN-5F6DB81748：partial。Embedding cosine=0.870783; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-71490921e52f1f10aa97 ↔ GEN-86C6EC9A26：partial。Embedding cosine=0.870783; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-71490921e52f1f10aa97 ↔ GEN-D4B995F12C：partial。Embedding cosine=0.855454; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-71490921e52f1f10aa97 ↔ GEN-1AB235AB66：partial。Embedding cosine=0.855454; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-71490921e52f1f10aa97 ↔ GEN-F5BAC8C3F4：partial。Embedding cosine=0.855327; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-71490921e52f1f10aa97 ↔ GEN-F0B79B061E：partial。Embedding cosine=0.857269; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-901FF2D9C6：partial。Embedding cosine=0.874178; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-8374E4EDBB：partial。Embedding cosine=0.855423; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-BCC3E27560：partial。Embedding cosine=0.855423; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-5F6DB81748：partial。Embedding cosine=0.858625; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-86C6EC9A26：partial。Embedding cosine=0.858625; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-128A74F22C：partial。Embedding cosine=0.859645; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-67D9769AD5：partial。Embedding cosine=0.859645; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-A5B180D24F：partial。Embedding cosine=0.871529; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-CE7541AED7：partial。Embedding cosine=0.871529; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-233718120A：partial。Embedding cosine=0.860382; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-BF1265D365：partial。Embedding cosine=0.860382; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-0A2E0D655B：partial。Embedding cosine=0.883153; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-5FF97FFAE7：partial。Embedding cosine=0.854416; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-CC2857D09A：partial。Embedding cosine=0.860461; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-D6EF57EBF5：partial。Embedding cosine=0.850252; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-F5BAC8C3F4：partial。Embedding cosine=0.863702; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-F0B79B061E：partial。Embedding cosine=0.856570; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e56f84568d20c22ad13a ↔ GEN-C4D9F57F38：partial。Embedding cosine=0.884848; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-8D66DC286D：partial。Embedding cosine=0.926886; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-AB2FC6BAC5：partial。Embedding cosine=0.856787; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-252DEF68FD：partial。Embedding cosine=0.853015; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-964A3CB67B：partial。Embedding cosine=0.853015; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-2FF8201A3B：partial。Embedding cosine=0.861354; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-C31A3EE6A4：partial。Embedding cosine=0.861354; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-DE83CDF2DA：partial。Embedding cosine=0.851360; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-855CA96E87：partial。Embedding cosine=0.851360; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-9FC5EFBC18：partial。Embedding cosine=0.857534; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-8550F18DDF：partial。Embedding cosine=0.857534; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-4AC6310AC6：partial。Embedding cosine=0.851950; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-7DBFAC465E：partial。Embedding cosine=0.851950; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-2940C9864A：partial。Embedding cosine=0.876156; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-294B4AEFC2：partial。Embedding cosine=0.853620; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-5472ADDF19：partial。Embedding cosine=0.853901; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-72F0043513：partial。Embedding cosine=0.857371; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-43DE8E309C：partial。Embedding cosine=0.864681; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-E715FF2075：partial。Embedding cosine=0.860720; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-22CFCD08BE：partial。Embedding cosine=0.864688; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c0237b15933e095fd3e3 ↔ GEN-C679E18DAD：partial。Embedding cosine=0.850782; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-dbf0e948531ce6ad332d ↔ GEN-D966960BCA：partial。Embedding cosine=0.946311; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1743557bce9b7fc30c6b ↔ GEN-AB2FC6BAC5：partial。Embedding cosine=0.900783; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-58270c542d0f127448ae ↔ GEN-AB2FC6BAC5：partial。Embedding cosine=0.860913; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-58270c542d0f127448ae ↔ GEN-D0DF305D5F：partial。Embedding cosine=0.924337; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1db9dc94c376ebb44ead ↔ GEN-D966960BCA：partial。Embedding cosine=0.874396; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-d1745e6f53c0fb74c9d1 ↔ GEN-D966960BCA：partial。Embedding cosine=0.860487; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-4574710C63：partial。Embedding cosine=0.896416; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-DAA8D90358：partial。Embedding cosine=0.859953; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-21A9B22C8E：partial。Embedding cosine=0.851112; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-6A8823FAD3：partial。Embedding cosine=0.871201; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-0B3F37F4F7：partial。Embedding cosine=0.871201; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-E78C46C637：partial。Embedding cosine=0.881761; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-DA7E800AAD：partial。Embedding cosine=0.881761; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-F872707739：partial。Embedding cosine=0.857875; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-5563DF48D0：partial。Embedding cosine=0.857875; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-9736014C36：partial。Embedding cosine=0.855081; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-2B48907944：partial。Embedding cosine=0.855081; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-8A97BD7401：partial。Embedding cosine=0.874470; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-20C05FFEED：partial。Embedding cosine=0.874470; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-E8BEE00CCC：partial。Embedding cosine=0.866774; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-98E2F204CD：partial。Embedding cosine=0.866774; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-7B0CC087C9：partial。Embedding cosine=0.880902; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-18C3B8EFEE：partial。Embedding cosine=0.880902; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-17344844ED：partial。Embedding cosine=0.856474; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-B6BC7C72B1：partial。Embedding cosine=0.882020; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-15180B7015：partial。Embedding cosine=0.853085; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-242695AE04：partial。Embedding cosine=0.893937; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-C2170B9421：partial。Embedding cosine=0.887130; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-388FDB168B：partial。Embedding cosine=0.883497; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-B8AF03CF55：partial。Embedding cosine=0.870529; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-F3E9616DBE：partial。Embedding cosine=0.881151; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-C787E26252：partial。Embedding cosine=0.895349; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-5215C5FEB6：partial。Embedding cosine=0.887070; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-06613888BB：partial。Embedding cosine=0.880797; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-163A286332：partial。Embedding cosine=0.889931; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c54cbf06c953c63c7c9d ↔ GEN-19ACAEF207：partial。Embedding cosine=0.879240; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8a80a7b9fe059e83d163 ↔ GEN-8FC1C0C244：partial。Embedding cosine=0.894660; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-9d505743da1052cee407 ↔ GEN-21A9B22C8E：partial。Embedding cosine=0.859736; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b28ebd69df6bb24e11fc ↔ GEN-4574710C63：partial。Embedding cosine=0.851858; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b28ebd69df6bb24e11fc ↔ GEN-DAA8D90358：partial。Embedding cosine=0.897999; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b28ebd69df6bb24e11fc ↔ GEN-21A9B22C8E：partial。Embedding cosine=0.938206; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b28ebd69df6bb24e11fc ↔ GEN-C2170B9421：partial。Embedding cosine=0.852507; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b28ebd69df6bb24e11fc ↔ GEN-C787E26252：partial。Embedding cosine=0.856958; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b28ebd69df6bb24e11fc ↔ GEN-5215C5FEB6：partial。Embedding cosine=0.850326; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b28ebd69df6bb24e11fc ↔ GEN-163A286332：partial。Embedding cosine=0.866147; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-777cb47e30ea9fa81fa8 ↔ GEN-DAA8D90358：partial。Embedding cosine=0.895257; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-777cb47e30ea9fa81fa8 ↔ GEN-B8AF03CF55：partial。Embedding cosine=0.901915; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-A62997BDE7：partial。Embedding cosine=0.918173; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-D29B34D82A：partial。Embedding cosine=0.860584; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-4EF83574B5：partial。Embedding cosine=0.878180; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-32EB226631：partial。Embedding cosine=0.877310; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-70E1A2766D：partial。Embedding cosine=0.877310; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-C768757F0D：partial。Embedding cosine=0.868054; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-1C629C3CB6：partial。Embedding cosine=0.868054; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-28776040F7：partial。Embedding cosine=0.864031; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-B13CF70E86：partial。Embedding cosine=0.864031; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-CE9511DDF7：partial。Embedding cosine=0.875549; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-0CD498E876：partial。Embedding cosine=0.875549; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-DB928F534A：partial。Embedding cosine=0.870294; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-CB57E74916：partial。Embedding cosine=0.870294; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-1EDCB9AB04：partial。Embedding cosine=0.864095; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-C0F5765232：partial。Embedding cosine=0.864095; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-983554CCFF：partial。Embedding cosine=0.857074; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-8543765468：partial。Embedding cosine=0.879031; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-DB80CDDFA5：partial。Embedding cosine=0.851708; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-F5B53E7B83：partial。Embedding cosine=0.871047; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-AD63DADCFA：partial。Embedding cosine=0.863056; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-B3BCB44D21：partial。Embedding cosine=0.884921; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-0FD03C3336：partial。Embedding cosine=0.859193; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-9ABCCE26E8：partial。Embedding cosine=0.857067; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-A1DA416D3D：partial。Embedding cosine=0.857464; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-095279A263：partial。Embedding cosine=0.861604; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-D0CCAFB1EE：partial。Embedding cosine=0.850543; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-67A9C8BE47：partial。Embedding cosine=0.851236; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-318dfa302f240d5d9923 ↔ GEN-A88F0A1919：partial。Embedding cosine=0.941183; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-8ef7fa52c5238e92ef51 ↔ GEN-D29B34D82A：partial。Embedding cosine=0.904807; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-230844760854191af35e ↔ GEN-A62997BDE7：partial。Embedding cosine=0.885010; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-230844760854191af35e ↔ GEN-A88F0A1919：partial。Embedding cosine=0.858121; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-230844760854191af35e ↔ GEN-0FD03C3336：partial。Embedding cosine=0.854009; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-230844760854191af35e ↔ GEN-9ABCCE26E8：partial。Embedding cosine=0.864187; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-230844760854191af35e ↔ GEN-A1DA416D3D：partial。Embedding cosine=0.855463; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-230844760854191af35e ↔ GEN-095279A263：partial。Embedding cosine=0.860225; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-230844760854191af35e ↔ GEN-67A9C8BE47：partial。Embedding cosine=0.858288; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b831d91adde18bcf91eb ↔ GEN-A62997BDE7：partial。Embedding cosine=0.884263; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b831d91adde18bcf91eb ↔ GEN-A88F0A1919：partial。Embedding cosine=0.894797; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b831d91adde18bcf91eb ↔ GEN-D29B34D82A：partial。Embedding cosine=0.888992; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b831d91adde18bcf91eb ↔ GEN-4EF83574B5：partial。Embedding cosine=0.857943; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b831d91adde18bcf91eb ↔ GEN-67A9C8BE47：partial。Embedding cosine=0.855242; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b831d91adde18bcf91eb ↔ GEN-74E776479F：partial。Embedding cosine=0.859228; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ad6aad03fa47c475fd5e ↔ GEN-3631596A4F：partial。Embedding cosine=0.873726; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ad6aad03fa47c475fd5e ↔ GEN-1559FF16D9：partial。Embedding cosine=0.852551; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-3631596A4F：partial。Embedding cosine=0.902599; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-2F24462982：partial。Embedding cosine=0.871536; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-FF204E7272：partial。Embedding cosine=0.871536; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-889514E9A1：partial。Embedding cosine=0.872039; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-183BAFCCC3：partial。Embedding cosine=0.872039; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-D6D180C693：partial。Embedding cosine=0.863267; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-51A024EF4D：partial。Embedding cosine=0.863267; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-31BDD2014D：partial。Embedding cosine=0.850178; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-1D827B9553：partial。Embedding cosine=0.850178; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-E4EBEAB4E2：partial。Embedding cosine=0.872650; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-104F862031：partial。Embedding cosine=0.872650; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-49DCEB94D7：partial。Embedding cosine=0.865103; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-344F0C6370：partial。Embedding cosine=0.865103; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-D91177F57F：partial。Embedding cosine=0.865933; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-C0C19268A8：partial。Embedding cosine=0.865933; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-6F8D33F3F4：partial。Embedding cosine=0.860023; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-1559FF16D9：partial。Embedding cosine=0.880021; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-9E219D4020：partial。Embedding cosine=0.850694; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-B41AD72017：partial。Embedding cosine=0.889225; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-eec92d2501ba3f586f26 ↔ GEN-CC191D6F91：partial。Embedding cosine=0.857887; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-3631596A4F：partial。Embedding cosine=0.855710; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-3C19AB2A05：partial。Embedding cosine=0.939434; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-0310D69FD9：partial。Embedding cosine=0.890238; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-473A451238：partial。Embedding cosine=0.860713; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-889514E9A1：partial。Embedding cosine=0.851033; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-183BAFCCC3：partial。Embedding cosine=0.851033; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-31BDD2014D：partial。Embedding cosine=0.858135; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-1D827B9553：partial。Embedding cosine=0.858135; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-E4EBEAB4E2：partial。Embedding cosine=0.865310; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-104F862031：partial。Embedding cosine=0.865310; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-49DCEB94D7：partial。Embedding cosine=0.855016; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-344F0C6370：partial。Embedding cosine=0.855016; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-6F8D33F3F4：partial。Embedding cosine=0.854047; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-1559FF16D9：partial。Embedding cosine=0.857836; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-B41AD72017：partial。Embedding cosine=0.861913; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-8F8B8BC748：partial。Embedding cosine=0.855408; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-943C97A7EC：partial。Embedding cosine=0.854160; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-8AAF665D97：partial。Embedding cosine=0.863438; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-0347D25708：partial。Embedding cosine=0.857280; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-ECEBB52E63：partial。Embedding cosine=0.872043; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-8C1871BEFC：partial。Embedding cosine=0.854170; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-C3CF4C0FC2：partial。Embedding cosine=0.852990; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-217F34CBEA：partial。Embedding cosine=0.857618; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1a0bab617efb744e651a ↔ GEN-EEE3F596EA：partial。Embedding cosine=0.857124; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cf2143c59461871e04af ↔ GEN-3C19AB2A05：partial。Embedding cosine=0.884028; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cf2143c59461871e04af ↔ GEN-0310D69FD9：partial。Embedding cosine=0.947399; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cf2143c59461871e04af ↔ GEN-E4EBEAB4E2：partial。Embedding cosine=0.866647; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cf2143c59461871e04af ↔ GEN-104F862031：partial。Embedding cosine=0.866647; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cf2143c59461871e04af ↔ GEN-49DCEB94D7：partial。Embedding cosine=0.869331; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cf2143c59461871e04af ↔ GEN-344F0C6370：partial。Embedding cosine=0.869331; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cf2143c59461871e04af ↔ GEN-8AAF665D97：partial。Embedding cosine=0.853074; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cf2143c59461871e04af ↔ GEN-ECEBB52E63：partial。Embedding cosine=0.850027; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-3631596A4F：partial。Embedding cosine=0.881349; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-3C19AB2A05：partial。Embedding cosine=0.900419; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-0310D69FD9：partial。Embedding cosine=0.872784; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-473A451238：partial。Embedding cosine=0.866464; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-2F24462982：partial。Embedding cosine=0.857647; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-FF204E7272：partial。Embedding cosine=0.857647; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-889514E9A1：partial。Embedding cosine=0.876836; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-183BAFCCC3：partial。Embedding cosine=0.876836; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-E4EBEAB4E2：partial。Embedding cosine=0.861034; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-104F862031：partial。Embedding cosine=0.861034; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-49DCEB94D7：partial。Embedding cosine=0.855362; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-344F0C6370：partial。Embedding cosine=0.855362; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-D91177F57F：partial。Embedding cosine=0.872763; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-C0C19268A8：partial。Embedding cosine=0.872763; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-1559FF16D9：partial。Embedding cosine=0.856667; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-B41AD72017：partial。Embedding cosine=0.881201; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-8F8B8BC748：partial。Embedding cosine=0.880547; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-943C97A7EC：partial。Embedding cosine=0.870735; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-8AAF665D97：partial。Embedding cosine=0.873269; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-0347D25708：partial。Embedding cosine=0.859468; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-ECEBB52E63：partial。Embedding cosine=0.880925; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-8C1871BEFC：partial。Embedding cosine=0.863646; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-C3CF4C0FC2：partial。Embedding cosine=0.877439; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-217F34CBEA：partial。Embedding cosine=0.876114; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-400ec85f51ae814325c5 ↔ GEN-EEE3F596EA：partial。Embedding cosine=0.866698; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-AAB2A9E971：partial。Embedding cosine=0.915946; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-802AF95D0E：partial。Embedding cosine=0.867378; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-24F6E7D2F4：partial。Embedding cosine=0.867378; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-649EF2E24D：partial。Embedding cosine=0.864929; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-2C31540106：partial。Embedding cosine=0.864929; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-7462BA37EE：partial。Embedding cosine=0.858676; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-910ED085EA：partial。Embedding cosine=0.858676; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-DB2FFF029B：partial。Embedding cosine=0.859452; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-24C22B75A5：partial。Embedding cosine=0.859452; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-43BC03AE67：partial。Embedding cosine=0.859277; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-3AC0D7033E：partial。Embedding cosine=0.859277; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-6791B05920：partial。Embedding cosine=0.881356; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cd220172f1b8358bdef0 ↔ GEN-BFA4B43762：partial。Embedding cosine=0.859885; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-64701605d36308902bc3 ↔ GEN-AAB2A9E971：partial。Embedding cosine=0.876338; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-64701605d36308902bc3 ↔ GEN-CB7E648FCA：partial。Embedding cosine=0.868379; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-7bc136c6e74f4d811f6c ↔ GEN-CDEB6D42D0：partial。Embedding cosine=0.883381; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-7bc136c6e74f4d811f6c ↔ GEN-995F875E0B：partial。Embedding cosine=0.871501; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-7bc136c6e74f4d811f6c ↔ GEN-3B8A3A3EA4：partial。Embedding cosine=0.863678; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-AAB2A9E971：partial。Embedding cosine=0.855935; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-CB7E648FCA：partial。Embedding cosine=0.860711; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-649EF2E24D：partial。Embedding cosine=0.861761; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-2C31540106：partial。Embedding cosine=0.861761; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-3DECF2A84B：partial。Embedding cosine=0.868215; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-A127905E8C：partial。Embedding cosine=0.868215; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-43BC03AE67：partial。Embedding cosine=0.854122; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-3AC0D7033E：partial。Embedding cosine=0.854122; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-2FD927932E：partial。Embedding cosine=0.869013; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-B1BBA0BBD4：partial。Embedding cosine=0.851906; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-14189c81e2ad187ebe05 ↔ GEN-B3B8DFC01C：partial。Embedding cosine=0.854768; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-7602561DAB：partial。Embedding cosine=0.927855; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-322D316A51：partial。Embedding cosine=0.905790; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-C9AD1AE5AC：partial。Embedding cosine=0.885205; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-14AE26863A：partial。Embedding cosine=0.885205; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-D629BFE7E0：partial。Embedding cosine=0.904300; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-0614F4A82F：partial。Embedding cosine=0.904300; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-80BBDBE2D7：partial。Embedding cosine=0.876727; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-6898B2BE77：partial。Embedding cosine=0.876727; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-12234CEEE9：partial。Embedding cosine=0.875588; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-F42DC5134C：partial。Embedding cosine=0.875588; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-125159DDD8：partial。Embedding cosine=0.892677; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-F4717691CF：partial。Embedding cosine=0.892677; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-1FA6FE0CC3：partial。Embedding cosine=0.888866; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-98F6281E82：partial。Embedding cosine=0.888866; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-86F51A9577：partial。Embedding cosine=0.890434; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-0DC4B9EF25：partial。Embedding cosine=0.890434; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-D08A883689：partial。Embedding cosine=0.861067; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-5F40FFAA47：partial。Embedding cosine=0.888535; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-96BBA11BB2：partial。Embedding cosine=0.872856; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-06071A4EE9：partial。Embedding cosine=0.899130; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-9392088419：partial。Embedding cosine=0.862618; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-A4AC0C5125：partial。Embedding cosine=0.878293; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-6B5F2B8438：partial。Embedding cosine=0.868382; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-F7B2AD9B71：partial。Embedding cosine=0.856894; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-56601C9482：partial。Embedding cosine=0.869888; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-A063226993：partial。Embedding cosine=0.859358; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-31CB207F4B：partial。Embedding cosine=0.851833; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2a0ada7b478be136a80d ↔ GEN-9B94AA0425：partial。Embedding cosine=0.859193; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-72eb2cd30962cedcccee ↔ GEN-7602561DAB：partial。Embedding cosine=0.891412; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-72eb2cd30962cedcccee ↔ GEN-322D316A51：partial。Embedding cosine=0.913394; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-72eb2cd30962cedcccee ↔ GEN-31CB207F4B：partial。Embedding cosine=0.855600; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-72eb2cd30962cedcccee ↔ GEN-9B94AA0425：partial。Embedding cosine=0.852660; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-E5CA74E988：partial。Embedding cosine=0.855499; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-C9AD1AE5AC：partial。Embedding cosine=0.856914; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-14AE26863A：partial。Embedding cosine=0.856914; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-D629BFE7E0：partial。Embedding cosine=0.853860; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-0614F4A82F：partial。Embedding cosine=0.853860; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-86F51A9577：partial。Embedding cosine=0.854336; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-0DC4B9EF25：partial。Embedding cosine=0.854336; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-5F40FFAA47：partial。Embedding cosine=0.863798; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-06071A4EE9：partial。Embedding cosine=0.856366; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-98f19675fc52a1b65b4b ↔ GEN-9B94AA0425：partial。Embedding cosine=0.857246; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-3d6e42c38f9c955123a1 ↔ GEN-E5CA74E988：partial。Embedding cosine=0.899775; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-903dbb576e28d2358f49 ↔ GEN-9FCFD67BBA：partial。Embedding cosine=0.902931; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-BB13252D3D：partial。Embedding cosine=0.911137; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-0BB9E4A934：partial。Embedding cosine=0.864975; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-1673D36091：partial。Embedding cosine=0.861565; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-D39A1BF21C：partial。Embedding cosine=0.869710; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-854696338A：partial。Embedding cosine=0.863210; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-FD8C23DF6E：partial。Embedding cosine=0.863210; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-C582C81F8D：partial。Embedding cosine=0.875292; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-D6967BBE26：partial。Embedding cosine=0.875292; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-793EC23E15：partial。Embedding cosine=0.864952; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-C5D6D1ECB7：partial。Embedding cosine=0.864952; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-320E803230：partial。Embedding cosine=0.852449; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-0D0F69097F：partial。Embedding cosine=0.852449; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-4D900C8F7C：partial。Embedding cosine=0.870065; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-14ED2234B4：partial。Embedding cosine=0.870065; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-EE977E6747：partial。Embedding cosine=0.869199; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-1E556985DB：partial。Embedding cosine=0.869199; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-7CC14B6B29：partial。Embedding cosine=0.861432; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-20599B6077：partial。Embedding cosine=0.861432; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-D21F3CFFEA：partial。Embedding cosine=0.875607; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-F628F02B48：partial。Embedding cosine=0.858776; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-ECFFB1D2C3：partial。Embedding cosine=0.873466; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-4CD12AA7C3：partial。Embedding cosine=0.873745; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-D39E225B32：partial。Embedding cosine=0.867282; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-2621CFFA34：partial。Embedding cosine=0.879256; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-02F1D20F6A：partial。Embedding cosine=0.850642; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-6E23D85EF3：partial。Embedding cosine=0.873466; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-62024FBD12：partial。Embedding cosine=0.862333; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-B68A400EE4：partial。Embedding cosine=0.865769; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-6F443B1F6B：partial。Embedding cosine=0.871646; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-265E452FD4：partial。Embedding cosine=0.873225; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-2153b1d6618c25ec8da4 ↔ GEN-7B00E90BB9：partial。Embedding cosine=0.859046; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1984e090dc09d0197e36 ↔ GEN-BB13252D3D：partial。Embedding cosine=0.861500; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1984e090dc09d0197e36 ↔ GEN-0BB9E4A934：partial。Embedding cosine=0.936499; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1984e090dc09d0197e36 ↔ GEN-1673D36091：partial。Embedding cosine=0.861114; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1984e090dc09d0197e36 ↔ GEN-4CD12AA7C3：partial。Embedding cosine=0.855466; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1984e090dc09d0197e36 ↔ GEN-2621CFFA34：partial。Embedding cosine=0.851126; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1984e090dc09d0197e36 ↔ GEN-6E23D85EF3：partial。Embedding cosine=0.852490; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1984e090dc09d0197e36 ↔ GEN-6F443B1F6B：partial。Embedding cosine=0.854986; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-1984e090dc09d0197e36 ↔ GEN-265E452FD4：partial。Embedding cosine=0.851336; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-BB13252D3D：partial。Embedding cosine=0.857420; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-0BB9E4A934：partial。Embedding cosine=0.869417; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-1673D36091：partial。Embedding cosine=0.932580; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-D39A1BF21C：partial。Embedding cosine=0.862022; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-4CD12AA7C3：partial。Embedding cosine=0.851513; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-2621CFFA34：partial。Embedding cosine=0.872824; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-02F1D20F6A：partial。Embedding cosine=0.853689; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-62024FBD12：partial。Embedding cosine=0.851366; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-6F443B1F6B：partial。Embedding cosine=0.858819; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-cb391f063c913ad11fb2 ↔ GEN-265E452FD4：partial。Embedding cosine=0.857290; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-BB13252D3D：partial。Embedding cosine=0.860975; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-0BB9E4A934：partial。Embedding cosine=0.862175; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-1673D36091：partial。Embedding cosine=0.889129; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-D39A1BF21C：partial。Embedding cosine=0.923811; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-4CD12AA7C3：partial。Embedding cosine=0.864258; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-D39E225B32：partial。Embedding cosine=0.873609; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-2621CFFA34：partial。Embedding cosine=0.866607; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-02F1D20F6A：partial。Embedding cosine=0.864081; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-6E23D85EF3：partial。Embedding cosine=0.866901; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-62024FBD12：partial。Embedding cosine=0.871464; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-B68A400EE4：partial。Embedding cosine=0.873292; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-6F443B1F6B：partial。Embedding cosine=0.868496; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-265E452FD4：partial。Embedding cosine=0.860965; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-462143f05fc7600e5345 ↔ GEN-7B00E90BB9：partial。Embedding cosine=0.870942; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c3c3b00b09d2323548a9 ↔ GEN-02F1D20F6A：partial。Embedding cosine=0.867700; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-c3c3b00b09d2323548a9 ↔ GEN-7B00E90BB9：partial。Embedding cosine=0.856383; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-181d0bed34d736c416a8 ↔ GEN-BB13252D3D：partial。Embedding cosine=0.859121; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-181d0bed34d736c416a8 ↔ GEN-0BB9E4A934：partial。Embedding cosine=0.860724; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-181d0bed34d736c416a8 ↔ GEN-1673D36091：partial。Embedding cosine=0.872215; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-181d0bed34d736c416a8 ↔ GEN-D39A1BF21C：partial。Embedding cosine=0.862065; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-181d0bed34d736c416a8 ↔ GEN-6F443B1F6B：partial。Embedding cosine=0.851065; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-181d0bed34d736c416a8 ↔ GEN-265E452FD4：partial。Embedding cosine=0.861521; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-97A70117ED：partial。Embedding cosine=0.920493; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-C7D76AAAF5：partial。Embedding cosine=0.856404; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-062B16EA89：partial。Embedding cosine=0.855542; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-B2A9ED0EF8：partial。Embedding cosine=0.850769; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-555AEF11B9：partial。Embedding cosine=0.859726; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-FE41FAD06A：partial。Embedding cosine=0.856482; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-938797536D：partial。Embedding cosine=0.861517; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-80F0F4DF70：partial。Embedding cosine=0.853539; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f8a9252e43df41aec6cd ↔ GEN-ECC73CF0E9：partial。Embedding cosine=0.857494; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca9712500b46cea1e16a ↔ GEN-0A397765C8：partial。Embedding cosine=0.901216; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-ca9712500b46cea1e16a ↔ GEN-BEF9B3427E：partial。Embedding cosine=0.864933; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-0A397765C8：partial。Embedding cosine=0.870510; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-0580C339C6：partial。Embedding cosine=0.919012; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-B2A9ED0EF8：partial。Embedding cosine=0.858119; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-555AEF11B9：partial。Embedding cosine=0.864045; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-FE41FAD06A：partial。Embedding cosine=0.873650; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-938797536D：partial。Embedding cosine=0.865133; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-80F0F4DF70：partial。Embedding cosine=0.853729; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-BEF9B3427E：partial。Embedding cosine=0.863184; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-ECC73CF0E9：partial。Embedding cosine=0.856343; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-b245099b769bfcb02fa1 ↔ GEN-DED59764CC：partial。Embedding cosine=0.857391; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-97A70117ED：partial。Embedding cosine=0.855692; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-0A397765C8：partial。Embedding cosine=0.866802; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-0580C339C6：partial。Embedding cosine=0.853562; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-FC09184269：partial。Embedding cosine=0.855181; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-2CF44AD1EB：partial。Embedding cosine=0.855181; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-D61C6F7248：partial。Embedding cosine=0.850003; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-8ABE773E72：partial。Embedding cosine=0.850003; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-062B16EA89：partial。Embedding cosine=0.851754; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-B2A9ED0EF8：partial。Embedding cosine=0.854286; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-FE41FAD06A：partial。Embedding cosine=0.852215; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-938797536D：partial。Embedding cosine=0.851472; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-f79a83f1653a04673461 ↔ GEN-ECC73CF0E9：partial。Embedding cosine=0.852530; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-e70fa35f741a7cd05bf2 ↔ GEN-555AEF11B9：partial。Embedding cosine=0.852497; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-d1f102d7a2a5adc1f771 ↔ GEN-64CDB603C5：partial。Embedding cosine=0.918532; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认
- CHK-a39da7598fe2018c4a9d ↔ GEN-64CDB603C5：partial。Embedding cosine=0.905949; uncalibrated thresholds 缺少行为：相似度处于部分匹配区间，具体行为差异待人工确认

## 分类差异（581 条）

两端标签不一致可能来自一端未分类或分类口径不同；逐条记录保存在 metrics.json。

## 生成器漏报

### CHK-02aff36aecb68c044b67：备选流程A5：idempotencyKey重复（幂等返回已有条目）

idempotencyKey重复

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 基本流程（591-591行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 备选流程（602-602行）

### CHK-3374884c60d737e3819f：备选流程A1：quantity不合法（quantity<1）

请求参数 quantity 不合法（例如 quantity<1）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 前置条件（580-580行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 基本流程（586-586行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 备选流程（598-598行）

### CHK-3396a4c7f663c0245fd6：产品目录服务不可用

ProductCatalogService不可用

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品 → 备选流程（512-512行）

### CHK-34b174cde6b7291fa1ef：categoryId 无效或已失效

categoryId 不存在或已失效

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品 → 基本流程（500-500行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品 → 备选流程（509-509行）

### CHK-408aa00b83f2b1f16899：ProductCatalogService不可用

ProductCatalogService不可用（调用价格与库存校验能力失败）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 备选流程（653-653行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 基本流程（637-637行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 前置条件（625-625行）

### CHK-5073a9a7be40e20a067f：MerchantProductService不可用

系统调用 MerchantProductService 创建商品能力时服务不可用。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品 → 前置条件（950-950行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品 → 备选流程（971-971行）

### CHK-565edced39d2e5bca003：LogisticsServiceAdapter服务不可用

系统调用LogisticsServiceAdapter查询物流信息时服务不可用

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息 → 备选流程（880-880行）

### CHK-5f4a963f70cbdfd6c580：idempotencyKey重复

系统调用PaymentAdapter创建支付能力时，idempotencyKey重复。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单 → 备选流程（699-699行）

### CHK-758d31d1647732af6ed5：查询期间商品状态变更或库存归零

查询期间商品状态被商家修改为 OFF_SALE 或库存变为 0

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品 → 备选流程（513-513行）

### CHK-7659c518930d34514ef3：请求参数校验失败（merchantId 非法或 idempotencyKey 为空）

商家发送创建请求，merchantId 格式不合法或 idempotencyKey 为空。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品 → 基本流程（958-958行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1179-1179行）

### CHK-798be5d677963fe5cc1f：ProductCatalogService不可用

ProductCatalogService 不可用

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（543-554行）

### CHK-961a6aceb1e32a8565f0：idempotencyKey 重复时返回已有退款单

RefundService 按 idempotencyKey 执行幂等校验时发现该键已存在

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 基本流程（914-914行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 备选流程（928-928行）

### CHK-b80d4031de1c9557f147：物流单号在 shipment 表中不存在（TRACKING_NUMBER_NOT_FOUND）

LogisticsServiceAdapter 校验 trackingNumber 时发现 shipment 表中不存在对应记录

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（821-832行）
系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（268-271行）

### CHK-bc2e4d3da049e9d74ced：事件编码非法（INVALID_EVENT_CODE）

signature 校验通过但 eventCode 非法（不在允许的事件编码范围内）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息 → 备选流程（835-836行）
系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（268-273行）

### CHK-dea130c386fca4bb806d：商品状态不是 DRAFT（已发布）

MerchantProductService 查询 product 表校验状态时，发现商品状态不是 DRAFT（已发布）。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 基本流程（1003-1003行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 备选流程（1016-1016行）

### CHK-e2f9c3d0949cf37f9472：支付金额与订单应付金额不一致

系统校验订单时发现支付金额与订单应付金额不一致。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单 → 备选流程（696-696行）

### CHK-ee6f4a5782147c29ae53：备选流程A6：ProductCatalogService不可用

ProductCatalogService不可用（连接失败或调用失败）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 基本流程（587-587行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 备选流程（603-603行）

### CHK-f4cabf884c9f40ae55b4：版本不一致（商品已被其他操作修改）

MerchantProductService 校验 version 时发现不一致（商品已被其他操作修改）。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 基本流程（1003-1003行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 备选流程（1015-1015行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1185-1185行）


## 按章节查看未匹配场景与补充建议

### GEN-1C6EAA0529：超时关注点：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.7300；支持度：0.9724；缺失度：0.1645；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：延时是否影响需求满足、后续行为执行或系统与环境协调

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-9021C050C2：持久化一致性：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.7255；支持度：0.9717；缺失度：0.1512；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：操作结果未可靠持久化或局部成功

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-0BA303A669：并发与幂等性：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.7246；支持度：0.9639；缺失度：0.1662；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：并发变更产生冲突，或重复请求导致重复变更

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-066A77A957：并发与幂等性：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.7241；支持度：0.9690；缺失度：0.1527；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：并发变更产生冲突，或重复请求导致重复变更

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-6A6E0E793F：权限控制：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.7172；支持度：0.9484；缺失度：0.1775；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：水平越权或垂直越权

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-291A7E5B95：数据完整性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.7160；支持度：0.9536；缺失度：0.1615；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：必填数据缺失或请求体为空

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-5C5A3FF406：数据完整性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.7160；支持度：0.9536；缺失度：0.1615；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：必填数据缺失或请求体为空

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-649DB4A161：持久化一致性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.7158；支持度：0.9357；缺失度：0.2028；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：操作结果未可靠持久化或局部成功

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4718D4278A：幂等性：Read or update Payment records

推荐评分：0.7136；支持度：0.9486；缺失度：0.1654；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：重复请求导致重复操作异常

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-D2C1E8AA68：幂等性：Read or update Refund records

推荐评分：0.7112；支持度：0.9463；缺失度：0.1626；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：重复请求导致重复操作异常

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-E370ED9096：超时关注点：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.7104；支持度：0.9274；缺失度：0.2040；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：延时是否影响需求满足、后续行为执行或系统与环境协调

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-A509CACD5E：数据合法性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.7086；支持度：0.9442；缺失度：0.1587；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-F1F4E0081C：数据合法性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.7086；支持度：0.9442；缺失度：0.1587；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-1CDB8E4FC1：数据长度：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.7084；支持度：0.9387；缺失度：0.1710；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-578E0E5F05：数据长度：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.7084；支持度：0.9387；缺失度：0.1710；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-028787EB7C：超时关注点：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.7068；支持度：0.9344；缺失度：0.1757；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：延时是否影响需求满足、后续行为执行或系统与环境协调

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-DA6C881968：关联一致性：Read or update Payment records

推荐评分：0.7061；支持度：0.9404；缺失度：0.1595；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：级联删除失效或子对象残留

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-F4DDB5757B：持久化能力：Read or update Refund records

推荐评分：0.7058；支持度：0.9431；缺失度：0.1520；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：写入失败或事务回滚

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-00614820AF：数据类型：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.7048；支持度：0.9413；缺失度：0.1529；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-33151E5505：数据类型：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.7048；支持度：0.9413；缺失度：0.1529；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-54EF0D36E9：数据完整性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.7039；支持度：0.9412；缺失度：0.1503；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：必填数据缺失或请求体为空

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-6B2E228FF9：数据完整性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.7039；支持度：0.9412；缺失度：0.1503；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：必填数据缺失或请求体为空

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-39D15BC889：并发与幂等性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.7036；支持度：0.9343；缺失度：0.1653；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：并发变更产生冲突，或重复请求导致重复变更

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-42223EA7E3：持久化能力：Read or update Payment records

推荐评分：0.7036；支持度：0.9406；缺失度：0.1506；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：写入失败或事务回滚

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-255C6B4A40：发布结果一致性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.7027；支持度：0.9383；缺失度：0.1531；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：发布状态与实际生效状态不一致

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-15AF457EE1：唯一性约束：Read or update Refund records

推荐评分：0.7014；支持度：0.9332；缺失度：0.1606；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：名称重复或唯一键冲突

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-647031FB7B：权限控制：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.7008；支持度：0.9131；缺失度：0.2055；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：水平越权或垂直越权

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-C661DBEB6B：唯一性约束：Read or update Payment records

推荐评分：0.7007；支持度：0.9325；缺失度：0.1599；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：名称重复或唯一键冲突

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-E04C2C6EB0：并发与幂等性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.7002；支持度：0.9224；缺失度：0.1819；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：并发变更产生冲突，或重复请求导致重复变更

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-0858C2EEC3：持久化一致性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.6996；支持度：0.9327；缺失度：0.1557；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：操作结果未可靠持久化或局部成功

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-91773F88F3：超时关注点：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6983；支持度：0.9198；缺失度：0.1816；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：延时是否影响需求满足、后续行为执行或系统与环境协调

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-2E4C702771：数据合法性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6963；支持度：0.9239；缺失度：0.1653；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-CAF11D090A：数据合法性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6963；支持度：0.9239；缺失度：0.1653；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-9DAF9DCBEA：数据合法性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6948；支持度：0.9121；缺失度：0.1878；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-B15CF36573：数据合法性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6948；支持度：0.9121；缺失度：0.1878；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-9F61BDCA50：数据大小：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6880；支持度：0.9152；缺失度：0.1578；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：文件或请求体超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-EB5F2E6E15：数据大小：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6880；支持度：0.9152；缺失度：0.1578；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：文件或请求体超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-87D772DB5C：权限控制：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6870；支持度：0.9070；缺失度：0.1737；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：水平越权或垂直越权

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-12E1480B79：持久化一致性：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6815；支持度：0.8933；缺失度：0.1871；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：操作结果未可靠持久化或局部成功

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4BE5721D79：数据长度：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6812；支持度：0.9029；缺失度：0.1638；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-78FD0E9E7F：数据长度：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6812；支持度：0.9029；缺失度：0.1638；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-79954A57E0：业务约束：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6809；支持度：0.8997；缺失度：0.1705；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：当前业务条件不满足变更要求

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-BDCCA13EFF：数据类型：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6796；支持度：0.9063；缺失度：0.1506；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-F6A6B19570：数据类型：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6796；支持度：0.9063；缺失度：0.1506；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-B8096B8140：数据完整性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6776；支持度：0.8954；缺失度：0.1693；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：必填数据缺失或请求体为空

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-C76431EE89：数据完整性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6776；支持度：0.8954；缺失度：0.1693；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：必填数据缺失或请求体为空

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-5106A0576E：关联一致性：Read or update SKU records

推荐评分：0.6765；支持度：0.8953；缺失度：0.1659；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：级联删除失效或子对象残留

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-D1432E6F2C：超时关注点：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.6754；支持度：0.8881；缺失度：0.1791；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：延时是否影响需求满足、后续行为执行或系统与环境协调

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-D218F18258：数据类型：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6741；支持度：0.8884；缺失度：0.1739；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-F62525FA8C：数据类型：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6741；支持度：0.8884；缺失度：0.1739；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-112683E654：并发与幂等性：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6739；支持度：0.8803；缺失度：0.1922；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：并发变更产生冲突，或重复请求导致重复变更

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-524CEF92E6：失败恢复：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6713；支持度：0.8943；缺失度：0.1511；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：发布失败后未恢复或留下半成品状态

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-ED793ACC41：并发与幂等性：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.6681；支持度：0.8865；缺失度：0.1584；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：并发变更产生冲突，或重复请求导致重复变更

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-D2A6BC0297：幂等性：Read or update SKU records

推荐评分：0.6679；支持度：0.8806；缺失度：0.1717；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：重复请求导致重复操作异常

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-1A962C9C31：数据长度：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6645；支持度：0.8654；缺失度：0.1958；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-49681DEB1C：数据长度：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6645；支持度：0.8654；缺失度：0.1958；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-CAAE9F9578：并发一致性：Read or update SKU records

推荐评分：0.6644；支持度：0.8813；缺失度：0.1581；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：并发更新冲突或后写覆盖前写

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-5F9827876B：持久化能力：Read or update SKU records

推荐评分：0.6637；支持度：0.8812；缺失度：0.1562；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：写入失败或事务回滚

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-8784F26EA7：并发与幂等性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6620；支持度：0.8684；缺失度：0.1806；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：并发变更产生冲突，或重复请求导致重复变更

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-44FFAC49C0：超时关注点：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6615；支持度：0.8679；缺失度：0.1800；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：延时是否影响需求满足、后续行为执行或系统与环境协调

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-D974AA2834：身份认证：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6593；支持度：0.8671；缺失度：0.1745；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：无凭证、Token 无效或过期

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4525B6D283：字段合法性：Read or update SKU records

推荐评分：0.6529；支持度：0.8680；缺失度：0.1508；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：类型错误、非法字符或超长

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-11EBD529FC：数据大小：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6494；支持度：0.8499；缺失度：0.1818；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：文件或请求体超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-280CF8A581：数据大小：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6494；支持度：0.8499；缺失度：0.1818；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：文件或请求体超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-B0214B43DC：唯一性约束：Read or update SKU records

推荐评分：0.6437；支持度：0.8458；缺失度：0.1719；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：名称重复或唯一键冲突

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4414FB106B：数据范围：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6415；支持度：0.8393；缺失度：0.1800；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数值超出允许范围

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-F9C097B077：数据范围：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6415；支持度：0.8393；缺失度：0.1800；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数值超出允许范围

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-5FA4F82032：数据格式：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6400；支持度：0.8407；缺失度：0.1718；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数据不满足格式规范

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-97BD90F9BA：数据格式：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6400；支持度：0.8407；缺失度：0.1718；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数据不满足格式规范

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-DD2C95D9C5：幂等性：Read or update Shipment records

推荐评分：0.6392；支持度：0.8370；缺失度：0.1777；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：重复请求导致重复操作异常

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-6A05A922D8：持久化一致性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6353；支持度：0.8301；缺失度：0.1809；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：操作结果未可靠持久化或局部成功

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-8686269E46：数据合法性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6320；支持度：0.8357；缺失度：0.1568；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-F25B4A4775：数据合法性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6320；支持度：0.8357；缺失度：0.1568；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4A0A79A8E4：渲染性能：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.6313；支持度：0.8200；缺失度：0.1912；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：渲染耗时影响用户后续操作

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-5F310AFEA0：数据库可用性：Read or update Category records

推荐评分：0.6216；支持度：0.8192；缺失度：0.1606；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：连接失败或数据库宕机

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-8D10EB9190：查询性能：Read or update Category records

推荐评分：0.6213；支持度：0.8168；缺失度：0.1652；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：大表联查超时

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-D7CA59C975：查询性能：Read or update Cart records

推荐评分：0.6197；支持度：0.8198；缺失度：0.1527；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：大表联查超时

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4AF6F65876：数据类型：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6164；支持度：0.8137；缺失度：0.1560；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-5C220A24AF：数据类型：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6164；支持度：0.8137；缺失度：0.1560；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-46C69DAB74：幂等性：Read or update Category records

推荐评分：0.6160；支持度：0.8086；缺失度：0.1664；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：重复请求导致重复操作异常

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-42433AC82F：幂等性：Read or update Cart records

推荐评分：0.6153；支持度：0.8091；缺失度：0.1631；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：重复请求导致重复操作异常

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-EDB6A97EF5：持久化能力：Read or update Category records

推荐评分：0.6086；支持度：0.8036；缺失度：0.1535；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：写入失败或事务回滚

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-F66EEEE418：关联一致性：Read or update Shipment records

推荐评分：0.6065；支持度：0.8004；缺失度：0.1543；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：级联删除失效或子对象残留

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-735BA3590A：唯一性约束：Read or update Shipment records

推荐评分：0.6060；支持度：0.7909；缺失度：0.1747；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：名称重复或唯一键冲突

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-84AE56AE64：权限控制：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5996；支持度：0.7747；缺失度：0.1912；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：水平越权或垂直越权

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-9365063340：持久化能力：Read or update Cart records

推荐评分：0.5977；支持度：0.7865；缺失度：0.1571；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：写入失败或事务回滚

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4574A3F4FC：持久化能力：Read or update Order records

推荐评分：0.5953；支持度：0.7818；缺失度：0.1602；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：写入失败或事务回滚

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-B334B476D1：持久化能力：Read or update Shipment records

推荐评分：0.5935；支持度：0.7784；缺失度：0.1621；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：写入失败或事务回滚

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-667D2D9853：资源存在性：Read or update OrderItem records

推荐评分：0.5879；支持度：0.7724；缺失度：0.1575；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：查询、修改或删除不存在资源

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-0D6A8FCABC：持久化能力：Read or update Category records

推荐评分：0.5877；支持度：0.7704；缺失度：0.1615；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：写入失败或事务回滚

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-11AD7119BB：数据类型：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5836；支持度：0.7663；缺失度：0.1575；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4C19B60846：数据类型：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5836；支持度：0.7663；缺失度：0.1575；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-735FF66A37：渲染性能：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5815；支持度：0.7543；缺失度：0.1781；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：渲染耗时影响用户后续操作

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-9F1AB24665：显示正确性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5810；支持度：0.7641；缺失度：0.1537；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：展示内容与业务结果不一致

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-682E1135B1：必填字段完整性：Read or update Order records

推荐评分：0.5785；支持度：0.7616；缺失度：0.1510；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：必要字段缺失

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-16B0E40326：权限控制：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5783；支持度：0.7545；缺失度：0.1671；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：水平越权或垂直越权

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-56C59B41F1：唯一性约束：Read or update Category records

推荐评分：0.5770；支持度：0.7471；缺失度：0.1801；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：名称重复或唯一键冲突

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-54D7CBE58D：幂等性：Read or update Category records

推荐评分：0.5694；支持度：0.7446；缺失度：0.1607；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：重复请求导致重复操作异常

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-03B4583D2B：数据完整性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5676；支持度：0.7456；缺失度：0.1522；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：必填数据缺失或请求体为空

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-EB77A47FDE：数据完整性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5676；支持度：0.7456；缺失度：0.1522；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：必填数据缺失或请求体为空

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-9F3192BC84：数据长度：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5673；支持度：0.7440；缺失度：0.1550；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-D560AD285F：数据长度：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5673；支持度：0.7440；缺失度：0.1550；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-9F8F199760：唯一性约束：Read or update Cart records

推荐评分：0.5499；支持度：0.7178；缺失度：0.1582；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：名称重复或唯一键冲突

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-1DA816CEB6：关联一致性：Read or update Category records

推荐评分：0.5488；支持度：0.7130；缺失度：0.1655；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：级联删除失效或子对象残留

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-E3D63F9584：关联一致性：Read or update Cart records

推荐评分：0.5442；支持度：0.7127；缺失度：0.1508；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：级联删除失效或子对象残留

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-758EFD5D32：并发一致性：Read or update Category records

推荐评分：0.5413；支持度：0.7053；缺失度：0.1587；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：并发更新冲突或后写覆盖前写

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-765120790D：数据合法性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5409；支持度：0.7020；缺失度：0.1652；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-DDF5AD355C：数据合法性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5409；支持度：0.7020；缺失度：0.1652；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-0895BB4597：持久化一致性：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.5382；支持度：0.6943；缺失度：0.1740；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：操作结果未可靠持久化或局部成功

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-DBEBED3C54：数据类型：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5351；支持度：0.6990；缺失度：0.1526；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-E4BF289003：数据类型：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5351；支持度：0.6990；缺失度：0.1526；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：数据类型与接口定义不符

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-77AB459B56：数据长度：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5315；支持度：0.6936；缺失度：0.1534；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-7C9FD22D69：数据长度：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5315；支持度：0.6936；缺失度：0.1534；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-4DDBC09059：权限控制：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.5272；支持度：0.6876；缺失度：0.1528；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：水平越权或垂直越权

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-142B3FD0A4：数据合法性：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5050；支持度：0.6542；缺失度：0.1568；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-6948F60E61：数据合法性：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5050；支持度：0.6542；缺失度：0.1568；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：非法字符、不允许字段或非法取值

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-0E90856B11：数据大小：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5044；支持度：0.6533；缺失度：0.1570；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：文件或请求体超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-13A4A7D15D：数据大小：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5044；支持度：0.6533；缺失度：0.1570；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：文件或请求体超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-BA750716F6：权限控制：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5043；支持度：0.6517；缺失度：0.1605；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：水平越权或垂直越权

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-6EBA9383BA：查询性能：Read or update Category records

推荐评分：0.4750；支持度：0.6131；缺失度：0.1529；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：大表联查超时

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-04EED632EB：数据长度：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4597；支持度：0.5888；缺失度：0.1584；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-33DC8BF192：数据长度：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4597；支持度：0.5888；缺失度：0.1584；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：字符串长度超过限制

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-A668DB9101：幂等性：Read or update Category records

推荐评分：0.4556；支持度：0.5812；缺失度：0.1624；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：重复请求导致重复操作异常

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-A1AD07D988：数据库可用性：Read or update Category records

推荐评分：0.3817；支持度：0.4806；缺失度：0.1511；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：连接失败或数据库宕机

证据相关度代理（非逻辑证明）与已有场景距离的加权评分

### GEN-5928D0E6F9：唯一性约束：Read or update Category records

推荐评分：0.3550；支持度：0.4393；缺失度：0.1583；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：名称重复或唯一键冲突

证据相关度代理（非逻辑证明）与已有场景距离的加权评分
