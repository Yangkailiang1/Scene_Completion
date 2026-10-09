# 三 Agent 场景评估

- 漏报率：54/97 = 55.67%
- 当前已有完整率：47/472 = 9.96%
- 匹配后端：agent；推荐后端：agent；rerank：False
- 完整与部分匹配均计重合；分类分别去重，数量不可直接相加。
- 推荐评分未经概率校准；候选不代表已证实的产品缺陷。
- checker 显式异常标签覆盖：72/76；未分类 4 项。未分类异常只计入总计及未分类桶，分类指标依赖标签覆盖。
- generator 显式异常标签覆盖：3/37；未分类 34 项。未分类异常只计入总计及未分类桶，分类指标依赖标签覆盖。

## 各关注点指标

|关注点|漏报率|当前已有完整率|
|---|---|---|
|api.data.completeness（数据完整性）|5/5 = 100.00%|0/28 = 0.00%|
|api.data.format（数据格式）|3/5 = 60.00%|2/29 = 6.90%|
|api.data.legality（数据合法性）|9/12 = 75.00%|4/28 = 14.29%|
|api.data.length（数据长度）|不可计算（分母为0）|0/28 = 0.00%|
|api.data.range（数据范围）|5/6 = 83.33%|1/29 = 3.45%|
|api.data.size（数据大小）|1/1 = 100.00%|0/28 = 0.00%|
|api.data.type（数据类型）|不可计算（分母为0）|0/28 = 0.00%|
|common.timeout（超时关注点）|5/5 = 100.00%|0/15 = 0.00%|
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
|internal_database.concurrency_consistency（并发一致性）|5/5 = 100.00%|0/14 = 0.00%|
|internal_database.field_validity（字段合法性）|2/2 = 100.00%|0/14 = 0.00%|
|internal_database.idempotency（幂等性）|5/5 = 100.00%|0/14 = 0.00%|
|internal_database.persistence（持久化能力）|不可计算（分母为0）|0/14 = 0.00%|
|internal_database.query_performance（查询性能）|1/1 = 100.00%|0/14 = 0.00%|
|internal_database.referential_consistency（关联一致性）|2/2 = 100.00%|0/14 = 0.00%|
|internal_database.required_field_completeness（必填字段完整性）|3/3 = 100.00%|0/14 = 0.00%|
|internal_database.resource_existence（资源存在性）|6/6 = 100.00%|0/14 = 0.00%|
|internal_database.uniqueness（唯一性约束）|1/1 = 100.00%|0/14 = 0.00%|
|service.analysis_generation.execution_deadline（执行时限）|不可计算（分母为0）|不可计算（分母为0）|
|service.analysis_generation.resource_consumption（资源消耗）|不可计算（分母为0）|不可计算（分母为0）|
|service.analysis_generation.result_correctness（处理正确性）|不可计算（分母为0）|不可计算（分母为0）|
|service.display_interaction.display_correctness（显示正确性）|1/1 = 100.00%|0/2 = 0.00%|
|service.display_interaction.render_performance（渲染性能）|不可计算（分母为0）|0/2 = 0.00%|
|service.query_retrieval.data_visibility（数据可见性）|1/1 = 100.00%|0/2 = 0.00%|
|service.query_retrieval.resource_existence（资源存在性）|9/9 = 100.00%|0/2 = 0.00%|
|service.query_retrieval.result_correctness（结果正确性）|不可计算（分母为0）|0/2 = 0.00%|
|service.release_activation.failure_recovery（失败恢复）|不可计算（分母为0）|0/1 = 0.00%|
|service.release_activation.prerequisite（发布前置条件）|1/1 = 100.00%|0/1 = 0.00%|
|service.release_activation.result_consistency（发布结果一致性）|1/1 = 100.00%|0/1 = 0.00%|
|service.resource_mutation.business_constraint（业务约束）|21/21 = 100.00%|0/9 = 0.00%|
|service.resource_mutation.concurrency_idempotency（并发与幂等性）|8/8 = 100.00%|0/9 = 0.00%|
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
|api_data|13/18 = 72.22%|10/198 = 5.05%|
|common|5/5 = 100.00%|0/15 = 0.00%|
|external_database|2/2 = 100.00%|不可计算（分母为0）|
|external_llm|不可计算（分母为0）|不可计算（分母为0）|
|external_llm_quality|不可计算（分母为0）|不可计算（分母为0）|
|external_service|19/19 = 100.00%|不可计算（分母为0）|
|human|5/5 = 100.00%|0/26 = 0.00%|
|internal_database|26/26 = 100.00%|0/140 = 0.00%|
|service_analysis_generation|不可计算（分母为0）|不可计算（分母为0）|
|service_display_interaction|1/1 = 100.00%|0/4 = 0.00%|
|service_query_retrieval|10/10 = 100.00%|0/6 = 0.00%|
|service_relation|18/18 = 100.00%|不可计算（分母为0）|
|service_release_activation|2/2 = 100.00%|0/3 = 0.00%|
|service_resource_mutation|29/29 = 100.00%|0/27 = 0.00%|

## 主成功、可选与未分类指标

|类别|漏报率|当前已有完整率|
|---|---|---|
|main_success|1/14 = 7.14%|13/14 = 92.86%|
|alternative|3/7 = 42.86%|4/5 = 80.00%|
|unclassified_exception|1/4 = 25.00%|2/34 = 5.88%|

## 完整匹配

- CHK-4a140a6abf63a298d41d ↔ GEN-A7BEC826FF：full。两端触发条件均为顾客未设置搜索/筛选条件；都要求按默认规则展示商品列表。生成场景的用例上下文也保留正常浏览前提，没有与此分支冲突的分支约束。 缺少行为：无
- CHK-545c47406a75022d945a ↔ GEN-A01F9F0DBB：full。两端都是相同幂等标识的订单重复提交，均返回已创建订单且不重复创建；触发、实体、操作和结果一致。 缺少行为：无
- CHK-72eb2cd30962cedcccee ↔ GEN-322D316A51：full。两端均在商品信息未完成时允许保存草稿但禁止发布；结果都保持 DRAFT，触发和允许/禁止行为一致。 缺少行为：无

## 部分匹配与缺少行为

- CHK-462f39e4d7b711d9762d ↔ GEN-4E8410AA60：partial。两端都在商品浏览查询无匹配时返回空列表并提示暂无符合条件商品；检查器明确限定只查询 ON_SALE 商品，生成器触发条件没有保留该状态限定。 缺少行为：生成器应明确本场景的查询集合限定为状态 ON_SALE。
- CHK-ef03a7912ff59e5f9845 ↔ GEN-142B3FD0A4：partial。同为 GET /products 的非法查询参数校验；生成器明确覆盖非法取值这一子类，可对应检查器列出的 min/max、page、sortBy 等非法值，但没有具体列出约束且响应待确认。 缺少行为：逐项保留 minPrice>maxPrice、page<1、sortBy 白名单、pageSize范围、minPrice非负等触发条件。；检查器要求提示修正查询条件；生成器的异常响应仍待确认。
- CHK-723f2f5b18ccca1aa280 ↔ GEN-651DCB33AE：partial。两端均由顾客从商品列表选择目标商品并展示完整详情；生成器没有复述检查器要求的 HTTP 200 和响应字段清单。 缺少行为：明确 HTTP 200 以及 productId、name、description、images、价格、库存状态和销量等响应字段。
- CHK-c0602c57e38b4c86d277 ↔ GEN-AE1C0334D2：partial。API-S-IF2 的路径变量是 productId；检查器的 productId 格式错误与生成器在同一路径调用中的数据格式不符合，指向同一参数格式校验，但生成器没有定义失败响应。 缺少行为：明确返回 HTTP 400 Bad Request 和错误码 INVALID_PRODUCT_ID。
- CHK-c0602c57e38b4c86d277 ↔ GEN-765120790D：partial。同为 GET /products/{productId} 的参数校验；生成器列出的非法取值可覆盖格式错误的 productId，但它也包含不允许字段等更广泛情形，且未明确失败响应。 缺少行为：将触发条件收窄并绑定到 productId 格式错误。；明确 HTTP 400 和 INVALID_PRODUCT_ID。
- CHK-dbdb241c78cfd3dd4523 ↔ GEN-6ABDFABD2C：partial。两端都是顾客选择商品后查询不到目标商品，均提示商品不存在并返回商品列表；生成器未包含检查器的 404 响应细节。 缺少行为：补充 HTTP 404 Not Found 和错误码 PRODUCT_NOT_FOUND。
- CHK-2e6002a6916c1cf742e8 ↔ GEN-E80F0305D0：partial。两端均指目标商品已下架并提示已下架、禁止购买；生成器未包含检查器规定的 HTTP 410 和错误码。 缺少行为：补充 HTTP 410 Gone 和 PRODUCT_OFF_SHELF。
- CHK-33f1bcdad44751fd6f70 ↔ GEN-F7D7301370：partial。两端都是详情页选择 SKU/数量后加入购物车，且都保存购物项；生成器未覆盖检查器要求的 HTTP 200 响应字段。 缺少行为：补充 cartItemId、quantity、cartItemCount、amountSummary 及 HTTP 200。
- CHK-4a352df1236c99304736 ↔ GEN-49C77EEBE5：partial。均在加入购物车时因库存不足而拒绝/提示当前可购买数量；生成器缺少检查器明确的数量比较、409 和错误码。 缺少行为：明确 stock_quantity < quantity 的判定。；补充 HTTP 409、OUT_OF_STOCK 及当前可购买数量响应体。
- CHK-37bb2a5379e510c7dd2d ↔ GEN-4581F93AAA：partial。均为加入购物车时商品已下架，拒绝加入；生成器未覆盖 HTTP 状态码和错误码。 缺少行为：补充 HTTP 410 Gone 和 PRODUCT_OFF_SHELF。
- CHK-e951f76a761ef8f161ed ↔ GEN-61CC4C1495：partial。两端均处理购物车已存在同一 SKU 的数量累加，并受库存和限购上限约束；生成器未覆盖接口返回字段。 缺少行为：补充 HTTP 200、cartItemId、累加后的 quantity、cartItemCount 和 amountSummary。
- CHK-b6e4acfd9edfa6b8494b ↔ GEN-49C77EEBE5：partial。检查器聚合列举商品不存在、库存不足、重复购物项三种 SR 错误；生成器仅覆盖其中明确存在的“库存不足”分支，并提示可购买数量，不能代表另外两种分支。 缺少行为：此配对只覆盖库存不足子分支；商品不存在和购物车条目重复需分别核对。；对齐 STOCK_NOT_ENOUGH 与生成器提示当前可购买数量的响应定义。
- CHK-61efa0586abc16381114 ↔ GEN-C8A9312AFA：partial。两端均为结算确认提交订单并生成 WAIT_PAY 订单、锁定库存；生成器省略接口响应字段与 HTTP 状态。 缺少行为：补充 HTTP 200、orderId、orderStatus、payableAmount 和 expireAt。
- CHK-81f1f8a4b88787b52967 ↔ GEN-8D90BBB6CA：partial。均因商品价格变化/confirmedAmount 与当前价不一致，展示新价格并要求重新确认；生成器没有响应状态、错误码或最新价格字段。 缺少行为：明确 confirmedAmount 与当前价格不一致的校验。；补充 HTTP 409、PRICE_CHANGED 及最新价格响应体。
- CHK-19666234a3786e63908f ↔ GEN-7C9D158555：partial。均为订单创建时库存不足，标记缺货商品并阻止创建；生成器缺少 ProductCatalogService 数量判定及 API 响应细节。 缺少行为：明确 stock_quantity 不满足请求 quantity 的条件。；补充 HTTP 409、OUT_OF_STOCK、缺货商品及当前库存信息。
- CHK-bb6c915e3b07e026a36a ↔ GEN-69F1AC0A02：partial。两端均由顾客确认支付并使订单变为 PAID、记录支付流水；生成器遗漏检查器规定的支付成功页面，且未描述同一支付请求的接口响应。 缺少行为：补充向顾客展示支付成功页面及支付接口收到的请求上下文。
- CHK-2a0e1fe1af96c01903bd ↔ GEN-901FF2D9C6：partial。两端都是顾客从订单列表选择本人订单并查看商品、金额、支付和履约信息；生成器未列出 HTTP 200 和响应结构字段。 缺少行为：补充 HTTP 200 及 orderId、status、items、amountSummary、paymentSummary、shipmentSummary。
- CHK-944fb29222ba7668e96b ↔ GEN-801F8EF3B7：partial。两端都是目标订单不属于当前顾客，均拒绝访问并记录安全事件；生成器遗漏 403 和 ORDER_ACCESS_DENIED。 缺少行为：补充 HTTP 403 Forbidden 和 ORDER_ACCESS_DENIED。
- CHK-84ee2b6e1b4fc96e9faa ↔ GEN-2970C4053A：partial。均为订单详情查询未找到目标订单，并提示订单不存在；生成器遗漏 404 响应细节。 缺少行为：补充 HTTP 404 Not Found 和 ORDER_NOT_FOUND。
- CHK-c0237b15933e095fd3e3 ↔ GEN-8D66DC286D：partial。均为商家为已支付且备货完成的订单填写承运商/物流单号并确认发货，订单变为 SHIPPED 且保存物流单号；生成器未覆盖物流登记和接口回执。 缺少行为：补充 shipment 记录创建并向 LogisticsService 登记。；补充 HTTP 200、shipmentId、orderStatus 和 trackingNumber。
- CHK-dbf0e948531ce6ad332d ↔ GEN-D966960BCA：partial。两端触发均为发货时订单状态不是 PAID，生成器也拒绝发货；检查器明确订单不更新、409 和 ORDER_STATUS_INVALID。生成器分支自身前置条件待确认；用例中的 PAID 是成功路径上下文，不视作该异常分支的条件。 缺少行为：补充订单状态不更新、HTTP 409 和 ORDER_STATUS_INVALID。
- CHK-1743557bce9b7fc30c6b ↔ GEN-AB2FC6BAC5：partial。两端均为物流单号格式错误并提示商家修正；生成器未明确无发货记录副作用和 HTTP 错误信息。 缺少行为：明确不创建发货记录。；补充 HTTP 400 和 INVALID_TRACKING_NUMBER。
- CHK-58270c542d0f127448ae ↔ GEN-D0DF305D5F：partial。均为发货时 LogisticsService 暂不可用/登记调用失败，并保留待同步记录进入重试；生成器未明确订单仍为 SHIPPED、异步登记及错误码。 缺少行为：明确订单状态仍更新为 SHIPPED，物流登记异步重试。；补充 LOGISTICS_SERVICE_UNAVAILABLE。
- CHK-c54cbf06c953c63c7c9d ↔ GEN-4574710C63：partial。两端都是 LogisticsService 推送新轨迹后保存最新物流节点并更新物流状态；生成器未包含检查器的 duplicate 标记、accepted 回执及订单物流摘要。 缺少行为：补充更新订单物流摘要。；补充 accepted=true、duplicate=false 等协议回执。
- CHK-8a80a7b9fe059e83d163 ↔ GEN-8FC1C0C244：partial。两端均因签名校验失败拒绝物流消息并记录安全告警；生成器遗漏 HTTP 401 和 INVALID_SIGNATURE。 缺少行为：补充 HTTP 401 Unauthorized 和 INVALID_SIGNATURE。
- CHK-4ed26b74fbdc98ac82c0 ↔ GEN-A62997BDE7：partial。两端均由顾客在本人已发货订单详情查看最新物流状态和轨迹；生成器遗漏 HTTP 200 与结构字段。 缺少行为：补充 trackingNumber、status、events、lastUpdatedAt、dataSource 和 HTTP 200。
- CHK-318dfa302f240d5d9923 ↔ GEN-A88F0A1919：partial。两端均因订单尚未发货而提示商家尚未发货；生成器遗漏冲突响应状态码和错误码。 缺少行为：补充 HTTP 409 Conflict 和 ORDER_NOT_SHIPPED。
- CHK-8ef7fa52c5238e92ef51 ↔ GEN-D29B34D82A：partial。两端均在外部物流查询失败时向顾客展示最近一次成功同步的数据；检查器还明确包含超时，并要求标记 CACHE、更新时间字段。 缺少行为：明确外部查询超时也触发此分支。；补充 dataSource=CACHE 和 lastUpdatedAt。
- CHK-230844760854191af35e ↔ GEN-4EF83574B5：partial。两端都在物流已签收时展示签收时间与签收状态；生成器没有保留 DELIVERED 状态、签收事件数组与响应字段。 缺少行为：补充 status=DELIVERED、events[] 中的签收节点及签收时间字段。
- CHK-ad6aad03fa47c475fd5e ↔ GEN-3631596A4F：partial。两端都是顾客提交退款申请并生成退款单；检查器要求选择退款商品与数量，生成器只明确选择原因后提交，未保证退款对象与数量被选择。 缺少行为：明确选择退款商品和数量。；补充 refundId、refundStatus 和 acceptedAmount。
- CHK-cd220172f1b8358bdef0 ↔ GEN-AAB2A9E971：partial。两端都是有资质且有权限的商家发起创建商品，创建 DRAFT 并返回商品编号；生成器遗漏 HTTP 响应字段。 缺少行为：补充 HTTP 200、productId、status 和 version。
- CHK-12bdaf49c4649869fb74 ↔ GEN-CB7E648FCA：partial。两端都是商品创建时商家经营资质失效，均拒绝创建并要求重新认证；生成器异常分支前置条件待确认，用例的有效资质条件是成功路径上下文，不视作异常分支前提。 缺少行为：补充 HTTP 403 Forbidden 和 MERCHANT_NOT_QUALIFIED。
- CHK-14189c81e2ad187ebe05 ↔ GEN-3DECF2A84B：partial。检查器明确包含创建请求中的商品数据非法子分支；生成器同一商品创建 API 的非法字符、不允许字段或非法取值与该子分支相交，但不能覆盖“类目不存在”，且响应待确认。 缺少行为：明确生成器覆盖的具体商品字段/非法值。；单独保留 CATEGORY_NOT_FOUND 分支并定义错误响应。
- CHK-14189c81e2ad187ebe05 ↔ GEN-649EF2E24D：partial。生成器在同一商品创建 API 明确提出商品数据不符合格式规范，与检查器列出的商品数据非法子分支相符；它未涵盖类目不存在，且响应待确认。 缺少行为：明确违反格式规范的商品字段和检查结果。；单独覆盖类目不存在及 CATEGORY_NOT_FOUND。
- CHK-14189c81e2ad187ebe05 ↔ GEN-A127905E8C：partial。同一商品创建请求的非法字段/字符/取值触发，与检查器明确列出的商品数据非法子分支相符；不能代表类目不存在分支，生成器没有响应定义。 缺少行为：明确具体字段与非法值如何拒绝。；单独定义 CATEGORY_NOT_FOUND 分支。
- CHK-14189c81e2ad187ebe05 ↔ GEN-43BC03AE67：partial。生成器指出商品创建请求字段类型与接口定义不符，是检查器商品数据非法子分支的具体形式；但不能覆盖类目不存在，且响应待确认。 缺少行为：明确涉及的商品字段及 INVALID_PRODUCT 响应。；单独覆盖 CATEGORY_NOT_FOUND。
- CHK-14189c81e2ad187ebe05 ↔ GEN-3AC0D7033E：partial。生成器指出同一商品创建请求的字段类型错误，属于检查器“商品数据非法”子分支；没有覆盖类目不存在，也没有定义错误响应。 缺少行为：明确涉及字段及 INVALID_PRODUCT 响应。；单独覆盖 CATEGORY_NOT_FOUND。
- CHK-2a0ada7b478be136a80d ↔ GEN-7602561DAB：partial。两端均为商家编辑属于自己的 DRAFT 商品基本资料并保存名称/描述/分类/图片；生成器没有保留版本递增、持久化和响应字段。 缺少行为：明确 product.version 递增及持久化结果。；补充 HTTP 200、productId、status、version、updatedAt。
- CHK-2153b1d6618c25ec8da4 ↔ GEN-BB13252D3D：partial。两端都是商家提交 SKU 库存与价格并保存；生成器未覆盖检查器要求的最新版本号及具体请求字段。 缺少行为：补充返回最新 version，并明确 skus[]、skuId、stock、salePrice/originalPrice 等字段。
- CHK-1984e090dc09d0197e36 ↔ GEN-0BB9E4A934：partial。两端均因提交负库存而拒绝保存并标记错误 SKU；生成器遗漏 HTTP 400 和 NEGATIVE_STOCK。 缺少行为：补充 HTTP 400 Bad Request 和 NEGATIVE_STOCK。
- CHK-cb391f063c913ad11fb2 ↔ GEN-1673D36091：partial。两端均因销售价格不在允许范围而提示修正；生成器遗漏 HTTP 400 和 INVALID_PRICE。 缺少行为：明确负数/格式错误及 originalPrice 等范围覆盖。；补充 HTTP 400 和 INVALID_PRICE。
- CHK-462143f05fc7600e5345 ↔ GEN-D39A1BF21C：partial。两端均因商品被他处更新造成版本冲突，要求重新加载；生成器遗漏 409、VERSION_CONFLICT 和最新版本。 缺少行为：补充 HTTP 409、VERSION_CONFLICT 及最新 version。
- CHK-f8a9252e43df41aec6cd ↔ GEN-97A70117ED：partial。两端均由商家发布资料完整且资质有效的 DRAFT 商品，使商品进入 ON_SALE 并可查询；生成器遗漏成功提示、发布时间、目录同步状态和 HTTP 响应。 缺少行为：补充发布成功提示及 HTTP 200。；补充 publishedAt、catalogSyncStatus 和响应字段。
- CHK-ca9712500b46cea1e16a ↔ GEN-0A397765C8：partial。两端都是资料不完整时阻止发布并列出缺失信息；生成器未明确商品保持 DRAFT、409 和 PRODUCT_INCOMPLETE。 缺少行为：明确发布被阻止后商品仍保持 DRAFT。；补充 HTTP 409、PRODUCT_INCOMPLETE 及缺失字段列表。
- CHK-b245099b769bfcb02fa1 ↔ GEN-0580C339C6：partial。两端都是商品不满足类目规则时送入人工审核；生成器未包含检查器规定的 HTTP 409 和 CATEGORY_RULE_VIOLATION。 缺少行为：补充 HTTP 409 Conflict 和 CATEGORY_RULE_VIOLATION。

## 分类差异（28 条）

两端标签不一致可能来自一端未分类或分类口径不同；逐条记录保存在 metrics.json。

## 生成器漏报

### CHK-02aff36aecb68c044b67：备选流程A5：idempotencyKey重复（幂等返回已有条目）

idempotencyKey重复

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 基本流程（591-591行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 备选流程（602-602行）

### CHK-181d0bed34d736c416a8：异常：商品不存在

请求中的productId对应的商品不存在。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格 → 基本流程（1048-1048行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格 → 备选流程（1061-1061行）

### CHK-1a0bab617efb744e651a：超过退款期限或退款有效期时拒绝申请

系统或 RefundService 校验退款时限时发现已超过退款期限

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（324-325行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 基本流程（915-915行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 备选流程（924-924行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1173-1173行）

### CHK-1db9dc94c376ebb44ead：异常：shippedItems[] 中商品不属于该订单

系统校验 shippedItems[] 时发现商品与该订单不匹配。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货 → 备选流程（790-790行）

### CHK-22182443284cac31365b：备选流程A4：相同SKU累加后超出限购上限

累加数量后超出限购上限（quantity > limit_per_order）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 基本流程（589-589行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 基本流程（591-591行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 备选流程（601-601行）

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

### CHK-3814b7488cac8d6dbfae：商品必要字段缺失

商品必要字段缺失，例如 product_name、sale_price 或 cover_image_url 为空

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品 → 备选流程（514-514行）

### CHK-3d6e42c38f9c955123a1：商品分类不存在或已停用

CategoryService 校验 categoryId 时，分类不存在或已停用（扩展路径 2.a；categoryId 不存在或已停用）。

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（370-371行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 基本流程（1004-1004行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 备选流程（1013-1013行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1185-1185行）

### CHK-400ec85f51ae814325c5：订单状态不满足退款条件时拒绝

系统校验订单状态时发现订单状态不满足退款条件

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 基本流程（912-912行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 备选流程（926-926行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1173-1173行）

### CHK-408aa00b83f2b1f16899：ProductCatalogService不可用

ProductCatalogService不可用（调用价格与库存校验能力失败）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 备选流程（653-653行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 基本流程（637-637行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 前置条件（625-625行）

### CHK-49d0fd8a7b02c8eb15da：PaymentService不可用或超时

PaymentService不可用或超时。

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（202-203行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单 → 备选流程（697-697行）

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

### CHK-64701605d36308902bc3：商家无商品管理权限

商家发起商品创建，系统校验商家权限时发现无商品管理权限。

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（335-335行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品 → 基本流程（960-960行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品 → 备选流程（969-969行）

### CHK-71490921e52f1f10aa97：orderId 格式错误

在线商城系统校验 orderId 格式时发现格式不合法

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情 → 备选流程（741-741行）

### CHK-758d31d1647732af6ed5：查询期间商品状态变更或库存归零

查询期间商品状态被商家修改为 OFF_SALE 或库存变为 0

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品 → 备选流程（513-513行）

### CHK-7659c518930d34514ef3：请求参数校验失败（merchantId 非法或 idempotencyKey 为空）

商家发送创建请求，merchantId 格式不合法或 idempotencyKey 为空。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品 → 基本流程（958-958行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1179-1179行）

### CHK-765d10533c4bd2bc4f9e：订单状态不是 WAIT_PAY

系统校验订单状态时发现订单状态不是 WAIT_PAY。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单 → 备选流程（695-695行）

### CHK-777cb47e30ea9fa81fa8：重复物流节点（幂等处理）

LogisticsServiceAdapter 幂等校验时发现收到重复物流节点（eventId 已存在）

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（277-278行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（823-834行）

### CHK-798be5d677963fe5cc1f：ProductCatalogService不可用

ProductCatalogService 不可用

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（543-554行）

### CHK-7bc136c6e74f4d811f6c：重复提交（幂等）返回已有草稿

商家重复发起商品创建请求，idempotencyKey 重复。

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（350-351行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品 → 基本流程（961-961行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品 → 备选流程（970-970行）

### CHK-7f7d740673100d1eecb1：订单尚未发货不展示物流轨迹

系统组合订单履约信息时发现订单尚未发货

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（230-231行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情 → 备选流程（744-744行）

### CHK-8441c6a972093a3b55d2：部分非关键展示信息缺失

description、image_urls 等非关键展示字段缺失

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（131-132行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（546-555行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1125-1125行）

### CHK-903dbb576e28d2358f49：图片格式或大小不符合要求

系统校验图片时，图片格式或大小不符合要求；imageUrls[] 中每项 URL 格式不合法或数量超限。

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（372-373行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 基本流程（1005-1005行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 备选流程（1014-1014行）

### CHK-961a6aceb1e32a8565f0：idempotencyKey 重复时返回已有退款单

RefundService 按 idempotencyKey 执行幂等校验时发现该键已存在

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 基本流程（914-914行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 备选流程（928-928行）

### CHK-98f19675fc52a1b65b4b：商品不存在

商家对不存在的 productId 发起 PUT /api/v1/merchant/products/{productId} 请求，MerchantProductService 查询 product 表未获取到对应商品。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 备选流程（1012-1012行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1185-1185行）

### CHK-9d505743da1052cee407：物流节点时间不合理（INVALID_EVENT_TIME）

LogisticsServiceAdapter 校验 eventTime 合理性时发现 eventTime 早于发货时间或晚于当前时间

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（822-833行）
系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（271-271行）

### CHK-a39da7598fe2018c4a9d：目录同步失败错误码目录同步失败

ProductCatalogService同步失败

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1197-1197行）

### CHK-a869c37581099b729c9a：ProductCatalogService查询超时

ProductCatalogService 查询超时

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（543-553行）

### CHK-b127aa3162f66058e2fc：产品目录服务查询超时

ProductCatalogService查询超时

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（108-109行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品 → 备选流程（511-511行）

### CHK-b28ebd69df6bb24e11fc：物流节点时间早于已保存节点（保留原状态并送审核队列）

系统校验物流节点的时间顺序时，发现收到的物流节点时间早于已保存节点

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（279-280行）
系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（271-271行）

### CHK-b80d4031de1c9557f147：物流单号在 shipment 表中不存在（TRACKING_NUMBER_NOT_FOUND）

LogisticsServiceAdapter 校验 trackingNumber 时发现 shipment 表中不存在对应记录

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（821-832行）
系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（268-271行）

### CHK-b831d91adde18bcf91eb：本地物流数据不存在

查询本地轨迹时未找到物流数据

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息 → 备选流程（877-877行）

### CHK-bc2e4d3da049e9d74ced：事件编码非法（INVALID_EVENT_CODE）

signature 校验通过但 eventCode 非法（不在允许的事件编码范围内）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息 → 备选流程（835-836行）
系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（268-273行）

### CHK-c3c3b00b09d2323548a9：异常：skus[]中存在重复的skuId

请求的skus[]中存在重复的skuId。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格 → 基本流程（1049-1049行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格 → 备选流程（1059-1059行）

### CHK-ca73433b0e4c5508040d：浏览商品主成功路径

顾客进入商品浏览页面，或发起商品搜索、筛选请求（GET /api/v1/products，可携带 keyword、categoryId、minPrice、maxPrice、sortBy、page、pageSize）

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-100行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（361-365行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品 → 基本流程（499-504行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1118-1120行）

### CHK-cd7720d75dcdd50ee230：收货地址无效或不属于当前顾客

收货地址无效或不属于当前顾客

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 备选流程（650-650行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 基本流程（640-640行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 前置条件（627-627行）

### CHK-cf2143c59461871e04af：申请金额超过可退款金额时提示调整

系统或 RefundService 校验退款金额时发现 requestedAmount 超过可退款金额

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（326-327行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 基本流程（915-915行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 备选流程（925-925行）

### CHK-d1745e6f53c0fb74c9d1：异常：商家无订单处理权限

系统校验 Authorization Token 与权限时发现商家无订单处理权限。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货 → 前置条件（768-768行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货 → 基本流程（774-774行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货 → 备选流程（791-791行）

### CHK-d1f102d7a2a5adc1f771：商品目录索引刷新失败记录待同步任务并重试

MerchantProductService调用ProductCatalogService刷新可售索引失败

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（424-425行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品 → 基本流程（1097-1099行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品 → 备选流程（1108-1108行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1197-1197行）

### CHK-db6deedddaa171e1ac54：购物车商品为空

cartItemIds非空校验失败或购物车条目为空（CART_EMPTY）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 备选流程（652-652行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单 → 基本流程（635-636行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1137-1137行）

### CHK-dc033d67ed6d7fea7386：顾客取消支付

顾客取消支付。

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（204-205行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单 → 备选流程（698-698行）

### CHK-dea130c386fca4bb806d：商品状态不是 DRAFT（已发布）

MerchantProductService 查询 product 表校验状态时，发现商品状态不是 DRAFT（已发布）。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 基本流程（1003-1003行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 备选流程（1016-1016行）

### CHK-e2f9c3d0949cf37f9472：支付金额与订单应付金额不一致

系统校验订单时发现支付金额与订单应付金额不一致。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单 → 备选流程（696-696行）

### CHK-e56f84568d20c22ad13a：OrderService 查询超时

OrderService 查询订单数据超时

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情 → 备选流程（745-745行）

### CHK-e5d6373797f199d4819f：支付结果重复通知

支付结果重复通知到达。

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（206-207行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单 → 备选流程（700-700行）

### CHK-e70fa35f741a7cd05bf2：版本不一致导致并发冲突

请求携带的 version 与数据库当前 version 不一致

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品 → 基本流程（1093-1093行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品 → 备选流程（1107-1107行）

### CHK-ee6f4a5782147c29ae53：备选流程A6：ProductCatalogService不可用

ProductCatalogService不可用（连接失败或调用失败）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 基本流程（587-587行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车 → 备选流程（603-603行）

### CHK-eec92d2501ba3f586f26：PaymentService 暂时不可用时保存待处理退款单并异步重试

RefundService 向 PaymentService 提交退款请求时 PaymentService 暂时不可用

系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（328-329行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 前置条件（902-902行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 基本流程（917-918行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款 → 备选流程（927-927行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1173-1173行）

### CHK-f4cabf884c9f40ae55b4：版本不一致（商品已被其他操作修改）

MerchantProductService 校验 version 时发现不一致（商品已被其他操作修改）。

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 基本流程（1003-1003行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息 → 备选流程（1015-1015行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1185-1185行）

### CHK-f79a83f1653a04673461：商品状态不是 DRAFT 无法发布

商品状态不是 DRAFT（如已发布或已删除）

功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品 → 基本流程（1093-1093行）
功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品 → 备选流程（1106-1106行）


## 按章节查看未匹配场景与补充建议

### GEN-1C8A4E5F0F：数据范围：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.7800；支持度：0.7500；缺失度：0.8500；等级：high

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：数值超出允许范围

Candidate asserts a numeric value-out-of-range failure (amount) on POST /payment/v1/payments. Evidence shows explicit amount validation (amount>=0) in step 3 and A2 AMOUNT_MISMATCH for amount inconsistency, directly supporting amount-range checking. However no upper bound / maximum amount is defined, and AMOUNT_MISMATCH addresses mismatch rather than out-of-range, so the specific range-constraint mechanism is only partly supported.；支持度复核：The candidate asserts a numeric out-of-range failure on amount for POST /payment/v1/payments. The cited basic flow (index 0) explicitly requires a numeric range constraint for amount ('amount>=0'), which directly supports a range-constraint mechanism for the amount field named in the trigger. It stops short of 'direct' because only the lower bound is specified (no upper bound or max amount), and A2 (index 1) covers AMOUNT_MISMATCH (consistency) rather than out-of-range.

### GEN-3164C18FFD：数据合法性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.7650；支持度：0.7500；缺失度：0.8000；等级：high

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：非法字符、不允许字段或非法取值

候选位于支付请求 PAYMENT-PAY-01 的请求参数校验步骤（source_step_index=3），触发条件为非法字符/不允许字段/非法取值。基本流程第3步明确校验 orderId 格式合法、amount>=0、paymentMethod 合法、notifyUrl 非空、idempotencyKey 非空，构成对「请求参数合法性」的显式约束，支持该失败机制。但被分配章节的备选流程仅覆盖 ORDER_STATUS_INVALID、AMOUNT_MISMATCH、服务不可用、取消、幂等，未给出格式非法/未知字段的具体响应码与恢复方式，故缺失度较高。；支持度复核：The candidate's step (source_step_index=3) is exactly the request-parameter validation step in the basic flow, and the cited first-step sequence explicitly constrains the fields in this same request payload (orderId format 合法, amount>=0, paymentMethod 合法, notifyUrl 非空, idempotencyKey 非空). This is a direct stated constraint on the request parameters of PAYMENT-PAY-01, thereby supporting the illegality-of-request-payload failure mechanism (非法字符/不允许字段/非法取值) for this entity. It is not direct=1 because the quote constrains specific named fields but does not itself name the failure mechanism or prescribe rejection behavior for illegal characters/unknown fields; the candidate's expected_result and recovery remain unconfirmed per the spec. It is above context=.5 because the constraint is on this exact operation's payload, not merely a related operation or an unrelated field.

### GEN-5F6DB81748：数据格式：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.7650；支持度：0.7500；缺失度：0.8000；等级：high

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：数据不满足格式规范

候选关注 API-O-IF2 请求参数“数据不满足格式规范”。证据显式给出 orderId 格式校验步骤并在 A1 规定格式错误返回 HTTP 400 INVALID_ORDER_ID，属于针对该接口的具体约束，可支撑 0.75。但除 orderId 格式外的“数据格式规范”判定范围（如路径参数之外的字段）未定义；需求侧扩展路径仅覆盖订单不属于该顾客、订单不存在、未发货情形，未就格式非法给出语义化响应，expected_result/recovery 亦标注待需求确认。；支持度复核：Candidate concern targets the API-O-IF2 request payload where 'data does not satisfy format specification' (api.data.format). Evidence index 2 explicitly defines the format-error branch for this exact interface: 'orderId 格式错误' returning HTTP 400 with code INVALID_ORDER_ID, and evidence index 1 adds an explicit validation step ('校验 orderId 格式合法'). This is a specific constraint tied to the request-payload format failure mechanism at API-O-IF2, not merely a generic validation context. However, the candidate's concern as scoped ('数据不满足格式规范') is broader than orderId alone; the spec only enumerates orderId format handling, and expected_result/recovery remain '待需求确认'. Hence it is an explicit constraint for the orderId format sub-case but does not fully cover the unenumerated broader data-format scope, so it does not reach direct-level completeness.

### GEN-9365063340：持久化能力：Read or update Cart records

推荐评分：0.7500；支持度：0.7500；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：写入失败或事务回滚

Candidate concerns internal_database.persistence (write failure/rollback) for 'Read or update Cart records' within API-C-IF1 加入购物车. Evidence is strong: step 9 of the basic flow explicitly writes to the cart_item table and computes cart totals, so the persistence boundary is explicitly described and a write-failure failure mechanism maps directly onto it. It stops short of 1.0 because no evidence describes behavior on write failure or transaction rollback (alternatives A1-A6 cover validation, stock, duplicates, idempotency, service unavailability only), so the required handling is genuinely missing/undeclared.；支持度复核：The candidate concern is persistence (write failure/transaction rollback) for 'Read or update Cart records' under API-C-IF1. Cited evidence 0, step 9 of the basic flow, explicitly names the CartService write operation and its target table (写入 cart_item 表), so the persistence boundary and the write action are directly and verbatim specified — this is an explicit constraint on the mechanism the candidate proposes to fail. It is not direct=1.0 because no cited unit states behavior on write failure or rollback; the alternatives A1–A6 (cited evidence 1) cover only validation, off-sale, out-of-stock, duplicate/l limit, idempotency, and catalog unavailability, leaving the failure response and recovery genuinely undeclared.

### GEN-12234CEEE9：数据长度：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.7350；支持度：0.7500；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：字符串长度超过限制

UCG-004-UC002 requires system to validate '文本长度' (step 3) on name/description, and the design basic flow explicitly validates 'name非空且长度合法、description长度合法'. The 备选流程 only lists 404 PRODUCT_NOT_FOUND, 400 INVALID_CATEGORY, 400 INVALID_IMAGE, 409 VERSION_CONFLICT, 409 INVALID_PRODUCT_STATUS — none addresses string-length-exceeds-limit. So mechanism (length validation exists) is supported, but the specific exception response/recovery is genuinely unspecified, matching the candidate's '待需求确认'.；支持度复核：The design basic flow explicitly constrains name and description length legality on PUT /api/v1/merchant/products/{productId}, directly matching api.data.length on this operation (SR step 3 also states '系统校验必填字段、文本长度和图片格式'). The 备选流程 A1–A5 cover only product-not-found, invalid category, invalid image, version conflict, and status, so the mechanism is explicitly constrained but the specific over-length exception response/recovery is unspecified.

### GEN-DD2C95D9C5：幂等性：Read or update Shipment records

推荐评分：0.7350；支持度：0.7500；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：重复请求导致重复操作异常

关注点为internal_database.idempotency（重复请求导致重复操作），目标是shipment记录的读/写。证据显示发货流程会写入shipment表并更新order状态为SHIPPED，且A3在LogisticsService不可用时保存待同步任务进入异步重试队列，涉及重复执行的天然风险面。但全部备选流程（A1订单状态非PAID 409、A2单号格式非法400、A3外部不可用异步重试、A4 shippedItems不属于订单400、A5无权限403）均未定义幂等键、重复提交判定或去重策略，故该约束与失败机制相关但无显式幂等规则支撑。；支持度复核：Contrary to the initial basis, the cited flow contains an explicit repetitive-execution mechanism: step 7 writes a shipment record, step 9 registers the tracking number with LogisticsService, and A3 persists a pending-sync task with asynchronous retry when that service is unavailable. That retry path is exactly the surface where a duplicate request or replays of the persisted task could re-write/re-register the same shipment, so the evidence directly constrains this failure mechanism. However it still specifies no idempotency key, duplicate-submission detection, or dedup rule for shipment records, so the constraint is explicit but partial (0.75) rather than a complete direct mechanism.

### GEN-2C16B99ABA：Main success

推荐评分：0.7300；支持度：1.0000；缺失度：0.1000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 用例级（步骤未定位）
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 用例级（步骤未定位）；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 用例级（步骤未定位）；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 用例级（步骤未定位）

建议补充：顾客进入商品浏览页面，或发起商品搜索、筛选请求。

Main success scenario for 浏览商品 is fully described: SR main path steps ①–⑤ match the candidate steps, and the design detail (API-S-IF1 GET /api/v1/products) plus V5 chain confirm traceability. Expected result (list of ON_SALE products with pagination) is explicitly stated. No meaningful gap.；支持度复核：Main success scenario for 浏览商品. Cited evidence index 0 (SR) reproduces steps ②–⑤ matching the candidate steps, including the ON_SALE query and pagination display; index 1 (design) gives the full basic flow GET /api/v1/products with ProductCatalogService querying the product table and returning page/pageSize/total/items[], plus A1 INVALID_QUERY_PARAM; index 2 (V5 chain) confirms API-S-IF1, request/response fields and errors. This is a fully specified main path with no exception gap: the scenario's own steps are exactly the documented ones. No unspecified mechanism remains, so the evidence is direct.

### GEN-D6EF57EBF5：资源存在性：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.7150；支持度：1.0000；缺失度：0.0500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：查询资源不存在或已失效

系统需求扩展路径「3.a 异常场景：订单不存在。→ 系统提示“订单不存在”」与候选触发「查询资源不存在或已失效」对应；功能设计备选流程 A3（ORDER_NOT_FOUND，404）及 A4（订单未发货时 shipmentSummary 物流字段为空）给出显式响应与降级行为，资源存在性关注点被直接覆盖。；支持度复核：该候选触发为“查询资源不存在或已失效”。功能设计备选流程 A3 直接给出订单不存在时的响应（HTTP 404 Not Found，错误码 ORDER_NOT_FOUND），与系统需求扩展路径 3.a“订单不存在→系统提示订单不存在”以及 A4（订单未发货时 shipmentSummary 物流字段为空）共同完整支撑该资源存在性失败机制，故为 direct。

### GEN-4A0AD69249：幂等性：Read or update Order records

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：重复请求导致重复操作异常

幂等性在本用例有显式证据：基本流程第10步「OrderService按 idempotencyKey 执行幂等校验」、备选 A4「idempotencyKey重复，OrderService返回已有订单，不重复创建」，SR 扩展路径 4.a 亦要求按幂等标识返回已创建订单。该约束直接支持“重复请求导致重复操作”的失败机制（0.75）。但证据将重复请求明确定义为正常返回已有订单，而非异常场景，候选将其建模为需确认的异常响应与恢复，与现有显式描述存在冲突，故 missing 中等偏高。；支持度复核：候选将其建模为“重复请求导致重复操作异常”并标注异常响应与恢复“待需求确认”。但引文 index 2 的备选流程 A4 明确将重复 idempotencyKey 定义为正常处置——返回已有订单、不重复创建（基本流程第 10 步亦要求按 idempotencyKey 执行幂等校验，SR 扩展 4.a 同义）。约束确实直接针对本场景的重复请求机制，属 explicit_constraint；同时因其规定为正常幂等返回而非异常分支，候选“异常+待确认恢复”的表述与显式语义相冲突，故不应给 direct。

### GEN-6281AAC9B1：身份认证：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：无凭证、Token 无效或过期

候选针对调用 PAYMENT-PAY-01（POST /payment/v1/payments）时无凭证、Token 无效或过期的身份认证异常，关注点为 human.authentication。证据明确记载前置条件「ACT-001已登录，请求携带合法 Authorization Token」，基本流程第2步「在线商城系统校验 Authorization Token，确认顾客身份」，构成对认证校验这一失败机制的显式约束支持。但备选流程（A1-A6）中未定义 Token 缺失/无效/过期时的具体响应，故该异常的响应与恢复仍缺失。；支持度复核：The candidate's concern is human.authentication failure (missing/invalid/expired credentials) at the POST /payment/v1/payments call. Evidence index 1 (basic flow step 2) explicitly establishes that the system performs Authorization Token validation to confirm customer identity — this is a direct mechanism constraint on the exact authentication/credential-validation failure point the candidate questions. The precondition quote (index 0) '请求携带合法 Authorization Token' is supporting context but the step-2 validation is the operative constraint. This is an explicit constraint, not 'direct', because the evidence does not itself define the failure response (401/403, error code, recovery) for the no-credential/invalid/expired case — no alternate flow covers it.

### GEN-649DB4A161：持久化一致性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：操作结果未可靠持久化或局部成功

候选针对调用 API-O-IF1（POST /api/v1/orders）时操作结果未可靠持久化或局部成功的持久化一致性异常。证据在第10步明确描述「创建订单并锁定库存，写入 order 表（...）和 order_item 表（...）」，涉及跨表写入与库存锁定，构成对持久化一致性失败机制的显式约束支持；同时备选流程 A4 仅覆盖 idempotencyKey 重复，未定义部分成功/未可靠持久化时的回滚、补偿或错误响应，故响应与恢复缺失。；支持度复核：The candidate concerns persistence consistency failure (operation not reliably persisted or partial success) at POST /api/v1/orders. Evidence index 1 (basic flow step 10) explicitly describes a multi-write operation — creating the order, locking inventory, and writing to both the order table and the order_item table — which is precisely the multi-step/partial-success write mechanism the candidate's failure mode targets. Inventory locking plus cross-table writes constitute a concrete mechanism constraint. Not 'direct' because the evidence specifies no rollback, compensation, or error response for partial failure (A4 only covers idempotencyKey duplication), so the failure behavior remains undefined.

### GEN-6791B05920：身份认证：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：无凭证、Token 无效或过期

候选针对调用 API-M-IF1（POST /api/v1/merchant/products）时无凭证、Token 无效或过期的身份认证异常。证据前置条件明确「ACT-002（商家）已登录...请求携带合法 Authorization Token」，基本流程第2步「校验 Authorization Token，确认商家身份」，构成对认证失败机制的显式约束支持。备选流程 A1/A2 分别覆盖资质失效（MERCHANT_NOT_QUALIFIED）与权限不足（PERMISSION_DENIED），但均非 Token 无效/过期场景，该认证异常的响应与恢复仍待明确。；支持度复核：The candidate concerns human.authentication failure (missing/invalid/expired credentials) at POST /api/v1/merchant/products. Evidence index 1 (basic flow step 2) explicitly states the system validates the Authorization Token to confirm merchant identity — a mechanism constraint exactly matching the credential-validation point questioned. The precondition (index 0) '请求携带合法 Authorization Token' reinforces this. Not 'direct' because the evidence defines no failure response for the absent/invalid/expired token case; alternate flows A1/A2 cover qualification validity (MERCHANT_NOT_QUALIFIED) and permission (PERMISSION_DENIED), neither of which is a token-invalid scenario, so the specific failure response/recovery is unspecified.

### GEN-8686269E46：数据合法性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：非法字符、不允许字段或非法取值

UCG-001-UC003 step 3 explicitly validates productId/skuId format legality and quantity>=1, and error path A1 gives INVALID_QUANTITY 400 for an illegal value. This is concrete evidence for a data-legality check on POST /api/v1/cart/items, though illegal-character cases are not itemized.；支持度复核：The concern is data legality (illegal characters, disallowed fields, or illegal values) on POST /api/v1/cart/items. Step 3 explicitly imposes a parameter validation constraint on this exact interface, and A1 defines the concrete illegal-value response (HTTP 400, INVALID_QUANTITY). This is an explicit constraint bound to this operation's payload, not merely context. It does not rise to direct because illegal-character / disallowed-field cases are not itemized and only illegal-value (quantity<1) has a defined response.

### GEN-AD63DADCFA：资源存在性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：查询资源不存在或已失效

查询物流用例明确规定了本地资源存在性相关的判别与响应：步骤6–7 查询 shipment 与 logistics_event 表，A2 明确“本地物流数据不存在”返回 HTTP 404 LOGISTICS_NOT_FOUND，前置条件要求订单状态为 SHIPPED 或更后。这为“查询资源不存在或已失效”提供了部分直接可验证证据（404 语义）；但“已失效”的具体判定条件（如过期阈值、shipment 与 order 不一致的处理）未在授权章节中定义，回退缓存路径 A3 与存在性失败的边界也未澄清。；支持度复核：The candidate concern is 'query retrieval resource existence' — whether the queried resource does not exist or is invalid. Cited evidence index 2 (备选流程 A2) explicitly defines the local logistics-data-not-found case, constraining the system response to HTTP 404 with error code LOGISTICS_NOT_FOUND, which is exactly the 'resource does not exist' half of this failure mechanism and is a verifiable constraint, not merely a field/format check. However the '已失效' (invalidated/expired) half is not bounded: evidence index 0 only states the precondition that the order is SHIPPED or later, and evidence index 1 (基本流程 step 8) describes a data-freshness/refresh path (dataSource CACHE fallback) rather than a defined failure judgment for invalidated resources; no expiry threshold or shipment/order inconsistency rule is specified. The 404 semantics are a directly usable explicit constraint, but they cover only part of the stated concern and the recovery behavior for the失效 branch remains 待需求确认 in the candidate, so explicit_constraint (.75) rather than direct is warranted.

### GEN-B419A69125：权限控制：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：水平越权或垂直越权

Sources explicitly cover order ownership validation and the 403 ORDER_ACCESS_DENIED alternative where an order does not belong to the caller, directly supporting the horizontal-authorization failure mechanism. Vertical escalation is not distinguished, and the response/recovery is stated rather than derived, so the concern is only partially explicit.；支持度复核：This alternative path explicitly establishes the authorization constraint that the order must belong to the current customer and specifies the system response (HTTP 403, ORDER_ACCESS_DENIED) when violated. This directly supports the horizontal-authorization failure mechanism, which is the core of this concern. However, the candidate's trigger also claims vertical escalation, and no source distinguishes vertical privilege levels or specifies a separate vertical-escalation check/response; the 403 path covers only horizontal ownership. Therefore the failure mechanism is explicitly constrained but only for one of the two claimed sub-cases, warranting explicit_constraint (0.75) rather than direct (1.0).

### GEN-DE83CDF2DA：数据合法性：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：非法字符、不允许字段或非法取值

关注点api.data.legality（非法字符、不允许字段、非法取值）针对POST /api/v1/orders/{orderId}/shipments的请求体。证据明确请求体字段orderId、carrierCode、trackingNumber、shippedItems[]，基本流程第3步校验orderId格式合法、carrierCode合法、trackingNumber非空、shippedItems[]非空，第6步校验trackingNumber长度、字符集、承运商编码规则，A2单号格式非法返回400 INVALID_TRACKING_NUMBER，A4 shippedItems不属于该订单返回400 INVALID_SHIPPED_ITEMS。这些是输入合法性校验的显式约束，但未穷尽非法字符、未定义字段（未知字段）、非法取值的统一处理与恢复策略。；支持度复核：The request payload for POST /api/v1/orders/{orderId}/shipments is defined with explicit legality constraints: step 3 validates orderId format, carrierCode validity, trackingNumber non-emptiness, and non-empty shippedItems[]; step 6 validates trackingNumber format (length, charset, carrier coding rules); A2 returns 400 INVALID_TRACKING_NUMBER and A4 returns 400 INVALID_SHIPPED_ITEMS. These constrain illegal characters/values for fields in this exact API, but do not cover unknown/extra fields or a uniform unlisted-field policy and recovery, so explicit_constraint rather than direct.

### GEN-F42DC5134C：数据长度：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：字符串长度超过限制

UCG-004-UC002 API-M-IF2 详细流程第3步明确校验 name 非空且长度合法、description 长度合法，说明文本长度超限是接口自身校验约束，支撑该失败机制的存在；但备选流程 A1-A5 未列出任何长度超限错误码或响应体，故具体响应/恢复未描述，属需求缺口。；支持度复核：Basic flow step 3 of the API-M-IF2 detailed design explicitly asserts a text-length validity constraint on name and description at the same layer and interface (SR, API-M-IF2 PUT /api/v1/merchant/products/{productId}) at which the candidate locates the failure, establishing that a length-overflow rejection mechanism exists for this entity. It is explicit_constraint rather than direct because no concrete bound, error code, or response body is specified: the alternative flows A1–A5 list PRODUCT_NOT_FOUND, INVALID_CATEGORY, INVALID_IMAGE, VERSION_CONFLICT, and INVALID_PRODUCT_STATUS but none for length overflow (evidence index 2), so the exact triggering threshold and the异常响应/恢复 remain a genuine requirement gap, consistent with the candidate's '待需求确认' expected_result and recovery.

### GEN-F5B53E7B83：数据可见性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.7050；支持度：0.7500；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：数据越过用户、租户或权限范围被访问或返回

UCG-003-UC003 前置条件明确「订单属于当前顾客且已发货」，物流查询流程第4步调用 OrderService 校验订单归属，仅在归属成立时才返回 trackingNumber/events；系统需求扩展路径 2.a 亦要求越权场景拒绝访问。这显式支撑了数据可见性边界的存在。但备选流程 A1-A5 未列出越权被访问或返回的错误码（如 403），未描述越权发生时的响应与恢复，故仍属需求缺口。；支持度复核：The candidate scenario is about data crossing user/tenant/permission boundaries on GET /api/v1/orders/{orderId}/logistics. The functional design explicitly constrains order ownership: step 4 of the basic flow requires OrderService to validate that the order belongs to the current customer before logistics data is fetched and returned, and the precondition states the order must belong to the current customer with a valid Authorization Token. This is a concrete access-control constraint on the exact interface/entity involved, so it reaches explicit_constraint. It does not reach direct because the source specifies no error code or response/recovery behavior for a violated ownership check (no 403 or equivalent), leaving the failure response unspecified.

### GEN-855CA96E87：数据合法性：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.7000；支持度：0.7000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：非法字符、不允许字段或非法取值

Same UCG-003-UC001 sections explicitly describe request-parameter legality checks (orderId格式合法、carrierCode合法、trackingNumber非空、shippedItems[]非空) and corresponding 400 errors INVALID_TRACKING_NUMBER and INVALID_SHIPPED_ITEMS, which directly support an illegal-field/illegal-value check at the shipment API. Illegal-character specifics are not enumerated, but the check point is concrete.

### GEN-86F51A9577：数据类型：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.7000；支持度：0.7000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：数据类型与接口定义不符

UCG-004-UC002 step 3 explicitly validates name/description length, categoryId format, imageUrls[] format and version non-empty, with A3 INVALID_IMAGE 400 for image URL format/count violations and A2 INVALID_CATEGORY 400. This directly supports a data-type/validity mismatch check on PUT /api/v1/merchant/products/{productId}, though a precise 'type mismatch vs definition' case is not separately enumerated.

### GEN-0DC4B9EF25：数据类型：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.6950；支持度：0.6500；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：数据类型与接口定义不符

The concern is api.data.type — data type mismatch on the product PUT (API-M-IF2). Evidence confirms interface params (name, description, categoryId, imageUrls[], version) and explicit validation steps including name length, description length, categoryId format, imageUrls format, but the interface spec never states field data types, so a type-mismatch failure is neither constrained nor mapped to an error response.

### GEN-9E219D4020：权限控制：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.6900；支持度：0.7500；缺失度：0.5500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：水平越权或垂直越权

Candidate asserts horizontal/vertical authorization failure on the refund API. The design detail does describe identity/ownership enforcement: step 2 validates the Authorization Token to confirm customer identity, and step 4 validates that the order belongs to the current customer. That is direct semantic support for the horizontal-authorization (ownership) aspect of the intent. Vertical/role authorization is not discussed (only a customer actor is modelled), and there is no dedicated error code or response for an authorization violation in the alternate flows, so the failure mechanism is supported in part but its full semantics and outcome are not specified.；支持度复核：The candidate's failure mechanism is horizontal/vertical authorization violation on the refund API. The evidence explicitly constrains ownership enforcement: after validating the Authorization Token, the system queries OrderService and checks that the order belongs to the current customer ('校验订单属于当前顾客'). This is a direct, verbatim ownership check governing access to the resource, which corresponds precisely to the horizontal-privilege aspect of the candidate's intent rather than to mere presence of an auth token. It is an explicit constraint rather than direct evidence because the evidence does not specify the outcome semantics for an authorization failure (no dedicated error code or response is given in the alternate flows), so the full failure-response mechanism is only implied. Vertical/role authorization is not separately constrained, but the ownership check itself is an explicit constraint supporting this failure entity.

### GEN-889514E9A1：数据格式：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.6850；支持度：0.7000；缺失度：0.6500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：数据不满足格式规范

UCG-003-UC004 step 3 validates request parameters (orderId格式合法、items[]非空、reasonCode合法、requestedAmount>=0、idempotencyKey非空), directly supporting a format-legality check on the refund request. Note: assigned SR sections give path POST /api/v1/refunds while the V5 chain lists POST /api/v1/orders/{orderId}/refunds, an internal conflict in the source; no specific format-error response is enumerated.

### GEN-8550F18DDF：数据范围：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6750；支持度：0.6000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：数值超出允许范围

UCG-003-UC001 defines shipment parameter validation (step 3: orderId format, carrierCode legal, trackingNumber non-empty, shippedItems[] non-empty) and error paths A2 (INVALID_TRACKING_NUMBER 400) and A4 (INVALID_SHIPPED_ITEMS 400), which is the range/legality validation surface. But no explicit numeric-range bound on any field is documented, so the specific '数值超出允许范围' trigger is not verifiable in the assigned sections. Expected response and recovery are unknown.

### GEN-B8AF03CF55：幂等性：Read or update LogisticsEvent records

推荐评分：0.6750；支持度：0.9000；缺失度：0.1500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：重复请求导致重复操作异常

Idempotency for LogisticsEvent records is explicitly documented. Requirements 3.a says '收到重复物流节点 → 系统进行幂等处理', and design step 5 states 'LogisticsServiceAdapter按 eventId 执行幂等校验', with A4 specifying that a duplicate eventId returns HTTP 200 with accepted=true, duplicate=true and '不重复写入'. This gives a direct mechanism and defined response, so support is high and missingness low. The residual gap is limited to why the candidate's expected_result/recovery remain '待需求确认' despite the explicit A4 branch.；支持度复核：The idempotency concern for LogisticsEvent records is directly supported: the basic flow step 5 explicitly performs an idempotency check on eventId against the logistics_event table, and alternative flow A4 defines the exact response ('eventId 已存在，LogisticsServiceAdapter返回 HTTP 200，响应体包含 accepted=true、duplicate=true，不重复写入'). Additionally the requirement extension path 3.a states '收到重复物流节点 → 系统进行幂等处理'. This gives both mechanism (eventId dedup check before write) and the concrete response, so the proposed high support is justified. The candidate's own expected_result/recovery being '待需求确认' is an internal inconsistency, but the evidence itself is direct.

### GEN-163A286332：资源存在性：Read or update LogisticsEvent records

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：查询、修改或删除不存在资源

logistics_event 写入的资源存在性失败机制在设计中有直接对应约束：步骤3校验 trackingNumber 是否在 shipment 表中存在，备选流程 A2 明确返回 HTTP 404 与 TRACKING_NUMBER_NOT_FOUND，属可验证的显式约束。但候选的触发语「查询、修改或删除不存在资源」比实际写入路径更宽泛，且未覆盖修改/删除语义，故资源存在性本身支持度高而表述存在缺口。；支持度复核：A2 explicitly defines a resource-existence failure response (HTTP 404, TRACKING_NUMBER_NOT_FOUND) for a missing shipment keyed by trackingNumber, and basic-flow step 3 validates existence in the shipment table, directly supporting the resource-existence concern on the write path. The candidate trigger is broader (queries/updates/deletes) and does not cover update/delete semantics, hence explicit constraint rather than full direct alignment.

### GEN-35F76CD15C：超时关注点：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：延时是否影响需求满足、后续行为执行或系统与环境协调

关注点为 common.timeout。系统需求扩展路径 4.c 明确存在“商品目录服务超时→系统提示商品加载失败”，功能设计备选流程 A4 给出明确处理：HTTP 504 Gateway Timeout、错误码 PRODUCT_SERVICE_TIMEOUT；A5 另给出服务不可用 503。该具体接口上下文的超时异常已被显式描述并有确定响应，因此缺失度较低（仅未定义客户端级重试/降级细节）。；支持度复核：Concern is common.timeout on API-S-IF1. Evidence index 3 (备选流程) explicitly names ProductCatalogService 查询超时 for this exact interface and fixes the response (HTTP 504 + PRODUCT_SERVICE_TIMEOUT), matching the failure mechanism (delay affecting downstream behavior). This is a definite constraint on this entity's timeout path, not merely context; it falls short of direct only because client-side retry/degradation details are not specified. Corroborated by requirement-level 扩展路径 4.c in evidence index 0 ('商品目录服务超时').

### GEN-6B5F2B8438：并发一致性：Read or update Category records

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：并发更新冲突或后写覆盖前写

Candidate concerns concurrent update conflict / lost update against the Category read path in API-M-IF2. Design detail explicitly frames description as a concurrency hazard: 'version 不一致（商品已被其他操作修改）' triggers HTTP 409 VERSION_CONFLICT with latest version returned and merchant reload (step 5 optimistic-lock check on product version). That is an explicit mitigation mechanism, though it is tied to the product record rather than explicitly to category read/update, and category access is read-only validation via CategoryService.；支持度复核：The candidate concern is concurrency consistency (lost update / concurrent conflict) on the read-or-update path of MerchantProductService. The cited design detail gives an explicit optimistic-lock mechanism: step 5 validates 'version 一致（乐观锁）' against the product table, and A4 defines the concrete response HTTP 409 VERSION_CONFLICT with the latest version and a reload instruction. This is a specific mechanism constraint supporting exactly this failure mode, though it is anchored on the product version rather than the category record, so it rises to explicit_constraint rather than direct.

### GEN-7B00E90BB9：唯一性约束：Read or update Category records

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：名称重复或唯一键冲突

Candidate frames a uniqueness conflict on Category records during API-M-IF3. Assigned sections give an explicitly specified, verifiable duplicate-key constraint on the same operation: step 6 validates that skuId has no duplicates and A3 returns HTTP 409 Conflict with DUPLICATE_SKU (lines 1054-1062), directly supporting the uniqueness failure mechanism. However, the candidate attributes it to 'Read or update Category records', whereas the documented target is the sku table/product-version operations (no category record read/update appears), so the specific entity/operation is a mis-attribution and partially unspecified; a Category-name duplicate unique key is not described. Support is explicit constraint evidence; missingness is moderate due to entity mismatch.；支持度复核：The concern is internal-database uniqueness conflict (duplicate name or unique-key conflict) during API-M-IF3. Evidence index 1 (design detail, lines 1054-1062) explicitly documents a duplicate-key constraint on this same operation: A3 returns HTTP 409 Conflict with DUPLICATE_SKU when skus[] contains duplicate skuId, and step 6 (in the basic-flow evidence) validates 'skuId 无重复'. That is a specified, verifiable uniqueness mechanism on the same interface, so it exceeds mere context. However, it is not direct: the candidate attributes the conflict to 'Read or update Category records' / duplicate category name, while the documented uniqueness target is the SKU/producer-product operation (skuId duplicates and version optimistic lock), and no Category-record read/update or category-name unique key appears in the cited sections. The mechanism (uniqueness conflict) is explicit but the entity/operation attribution is a mismatch, so the entity being constrained does not fully match the candidate.

### GEN-8784F26EA7：并发与幂等性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：并发变更产生冲突，或重复请求导致重复变更

UCG-001-UC003 step 8 explicitly performs idempotency verification on idempotencyKey and accumulates quantity on duplicate SKU; A5 states duplicate idempotencyKey returns the existing cart item without re-writing, and A4 handles cumulative purchase-limit conflict (409 PURCHASE_LIMIT_EXCEEDED). This is direct evidence for the concurrency/idempotency concern on POST /api/v1/cart/items, though concurrent-write-conflict handling per se is not separated.；支持度复核：The concern is concurrency/idempotency of resource mutation on POST /api/v1/cart/items. Step 8 explicitly mandates idempotency checking by idempotencyKey for this operation, and A5 specifies duplicate idempotencyKey returns the existing entry without re-writing; A4 additionally mandates cumulative purchase-limit checking (409). This is an explicit mechanism constraint tied to this interface. It is not direct because true concurrent-write/race conflict handling is not separately specified, and idempotency via idempotencyKey does not itself establish the concurrency-conflict mechanism.

### GEN-8D4F17F2CF：数据范围：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：数值超出允许范围

api.data.range on the GET /api/v1/products request/response is explicitly supported: step 2 defines concrete range constraints page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice, and A1 defines INVALID_QUERY_PARAM for violations such as page<1 or minPrice>maxPrice. These are verifiable numeric bounds with a defined error response, directly matching the stated '数值超出允许范围' failure mechanism for this interface.；支持度复核：Candidate concerns api.data.range on GET /api/v1/products, i.e. numeric values outside allowed bounds. The cited basic flow explicitly defines numeric range bounds for the same request parameters (page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice), and alternate flow A1 specifies HTTP 400 with error code INVALID_QUERY_PARAM for violations such as minPrice>maxPrice or page<1. This is a concrete, verifiable bound plus a defined violation response for the exact interface and failure mechanism, so it qualifies as explicit_constraint; it is not 'direct' only in the sense that it is a declared constraint rather than a fully worked out-of-range example interaction.

### GEN-9FA15340C5：数据范围：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：数值超出允许范围

Candidate targets numeric range violations on request parameters for GET /api/v1/products. Step 2 explicitly states page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice, with precondition that the listed query params must satisfy interface constraints, and A1 defines INVALID_QUERY_PARAM for out-of-range values. This is explicit constraint evidence squarely supporting an out-of-range data failure. The mechanism is thus concretely supported, though the candidate names 'numeric range' generically while sources specify only these particular numeric bounds.；支持度复核：Candidate concerns numeric out-of-range on request_payload of GET /api/v1/products (concern api.data.range). Step 2 of the basic flow explicitly states page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice, and preconditions state the query params must satisfy interface constraints; A1 specifically defines INVALID_QUERY_PARAM for out-of-range values such as page<1 or minPrice>maxPrice. This is a direct, specific constraint on the same entity/mechanism (numeric range for these request params), so it is explicit_constraint rather than context, though it stops short of a fully enumerated response code for every numeric field.

### GEN-B6BC7C72B1：业务约束：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：当前业务条件不满足变更要求

Alternative paths A3 and A5 explicitly reject events with unreasonable/nonconforming times or illegal event codes, matching the 'business condition not satisfied' constraint mechanism. Remaining source steps describe idempotency and signature checks, so the specific unsatisfied condition is only implicitly generalized.；支持度复核：Alternative path A3 explicitly states a business precondition (event time must not be before shipment time or after the current time), with the specific rejection response (HTTP 400, INVALID_EVENT_TIME) when that condition fails. This is a concrete business-constraint violation mechanism matching the claimed 'business condition not satisfied' trigger. It is explicit_constraint (0.75) because it constrains the mutation's business validity rather than directly defining a top-level domain invariant proving the candidate's abstract 'current business condition not satisfied' framing across all causes; related alternatives (A5 invalid event code, A1 signature) are additional constraints in the same family rather than a single direct match to the generic trigger.

### GEN-E04C2C6EB0：并发与幂等性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6750；支持度：0.7500；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：并发变更产生冲突，或重复请求导致重复变更

关注点为service.resource_mutation.concurrency_idempotency。证据高度相关：请求体含idempotencyKey，第10步OrderService按idempotencyKey执行幂等校验并创建订单、锁定库存、写order与order_item表，A4明确idempotencyKey重复时返回已有订单不重复创建；并发面包括库存锁定与价格校验（A1 PRICE_CHANGED 409、A2 OUT_OF_STOCK 409）。但仍缺少并发冲突（如库存抢占失败、乐观锁冲突）的具体响应与恢复规定，故仍有待确认缺口，但缺口语义较集中而非模糊。；支持度复核：This is a direct whole-mechanism definition for the concern: the request carries idempotencyKey, step 10 has OrderService perform idempotency validation by idempotencyKey before creating the order and locking stock, and A4 specifies that a repeated idempotencyKey returns the existing order without creating a duplicate. The concrete duplicated-request path is fully constrained (key-based dedup plus defined response). The concurrency half (price changed / out-of-stock conflicts) is also addressed via A1/A2 409 responses, so the evidence meets the direct level.

### GEN-9E5F0AAB79：数据格式：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6700；支持度：0.7000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：数据不满足格式规范

Candidate targets request-payload format violations on POST /api/v1/cart/items. The design detail explicitly validates productId/skuId format legality, quantity>=1 and idempotencyKey non-empty, and provides a concrete malformed-input alternative flow (INVALID_QUANTITY, HTTP 400). This is specific interface context with an explicit validation step supporting a format-failure mechanism. It does not, however, enumerate all format rules (field types, character sets, idempotencyKey shape), so only part of the intended format-failure surface is covered.

### GEN-4D71771701：业务约束：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6600；支持度：0.7500；缺失度：0.4500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：当前业务条件不满足变更要求

SR场景在 API-C-IF1（POST /api/v1/cart/items）上检查“业务约束：当前业务条件不满足变更要求”。证据支持失败机制的部分：主流程第6步明确校验库存与限购规则（stock_quantity>=quantity、quantity<=limit_per_order），备选流程给出明确业务约束失败响应 A3 OUT_OF_STOCK 409、A4 PURCHASE_LIMIT_EXCEEDED 409、A1 INVALID_QUANTITY 400。但候选触发器表述为泛化的“业务条件不满足变更要求”，与已记载的具体约束失败（库存/限购）存在术语不一致，且其 expected_result/recovery 仍为“待需求确认”，未与既有错误码对齐，故记为部分缺失。；支持度复核：该候选关注点为 service.resource_mutation.business_constraint，触发条件为调用 POST /api/v1/cart/items 时业务条件不满足。备选流程明确记载了针对同一接口的库存不足/限购/数量非法的具体业务约束失败及响应（A3 OUT_OF_STOCK 409、A4 PURCHASE_LIMIT_EXCEEDED 409、A1 INVALID_QUANTITY 400），基本流程第 6 步亦写明库存与限购校验逻辑，构成该失败机制的显式约束。但候选触发器为泛化表述，且 expected_result/recovery 仍标为待需求确认，未与既有错误码对齐，故为明确约束而非完全直接匹配。

### GEN-14ED2234B4：数据范围：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6450；支持度：0.7500；缺失度：0.4000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：数值超出允许范围

API-M-IF3 validates stock>=0, salePrice>=0, originalPrice>=0 and A1 NEGATIVE_STOCK, A2 INVALID_PRICE ('不合法，例如为负数或格式错误') directly address numeric out-of-range values. The specific upper/valid-range boundary is not fully enumerated (只给下限/非法示例), so the precise range-exceeded exception is partially specified but the overarching numeric-range failure is explicitly supported by A1/A2.；支持度复核：A1 explicitly defines the response (HTTP 400, NEGATIVE_STOCK) for negative stock, and A2 (INVALID_PRICE) treats negative/invalid prices as errors, directly supporting numeric out-of-range rejection for stock and price at this endpoint. Only the lower bound/examples are enumerated, not full upper bounds, which is why this is an explicit constraint rather than a complete direct specification.

### GEN-21A9B22C8E：物流节点时间早于已保存节点。

推荐评分：0.6450；支持度：0.7500；缺失度：0.4000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 3

建议补充：物流节点时间早于已保存节点。

该候选源自需求扩展路径3.b（物流节点时间早于已保存节点→保留原状态并送入审核队列），且功能设计明确了eventTime合理性校验（不早于发货时间、不晚于当前时间）及INVALID_EVENT_TIME错误码，构成对失败机制的具体支持。但送审队列行为在设计文档备选流程中未见独立条目，故保留一定缺省度。；支持度复核：The requirements extension path 3.b names exactly this failure mechanism (logistics node time earlier than saved node) and prescribes a specific handling mechanism (retain original state, route the anomalous message to the review queue). Additionally the functional design's INVALID_EVENT_TIME check (eventTime not earlier than shipping time / not later than now) corroborates time-ordering validation. This is an explicitly constrained handling, though the review-queue behavior itself has no independent design-document alternative-flow entry, so not full direct implementation proof.

### GEN-3B8A3A3EA4：幂等性：Read or update Category records

推荐评分：0.6450；支持度：0.7500；缺失度：0.4000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：重复请求导致重复操作异常

关注点为 internal_database.idempotency（重复请求导致重复操作）。证据对创建商品流程有明确幂等设计：MerchantProductService 按 idempotencyKey 执行幂等校验（第6步），备选流程 A3 明确“idempotencyKey 重复则返回已有商品草稿，不重复创建”，系统需求扩展路径 3.a 亦一致。该行为已显式描述，故支持度较高；缺失仅在于 Category/数据库层的重复写入防护细节未单独说明。；支持度复核：Concern is internal_database.idempotency (duplicate request causing duplicate operation) on the create-product flow. Evidence index 2 fixes the mechanism: MerchantProductService performs idempotency check by idempotencyKey (step 6) and A3 defines duplicate-key behavior (return existing draft, no duplicate creation). This directly constrains duplicate-create behavior for this operation, though it specifies service-level idempotency rather than the DB unique-key/constraint layer, so explicit_constraint rather than direct.

### GEN-7B845CE134：幂等性：Read or update OrderItem records

推荐评分：0.6450；支持度：0.7500；缺失度：0.4000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：重复请求导致重复操作异常

Candidate asserts idempotency failure on OrderItem records during payment. Assigned sections explicitly specify idempotency handling for the same flow — idempotencyKey accepted in the request, A5 'idempotencyKey重复，PaymentAdapter返回已有支付结果，不重复处理', and A6 idempotent callback handling by paymentId (lines 691-701) — so an explicit constraint supports the duplicate-operation mechanism. The candidate's specific object 'Read or update OrderItem records' does not appear in the assigned payment sections (documented writes are to payment and order tables), so the concrete target/behavior is partially unspecified.；支持度复核：Assigned payment sections explicitly constrain the idempotency/duplicate-operation mechanism in this same flow: the request carries idempotencyKey (step 1), and A5 states that on a repeated idempotencyKey the adapter returns the existing result without re-processing, with A6 specifying idempotent callback handling by paymentId. This directly supports the candidate's asserted failure mechanism (duplicate request causing duplicate operation) at the constraint level. It is not 'direct' for the full candidate because the specific object 'Read or update OrderItem records' is not documented anywhere in the assigned sections (writes described are to payment and order tables), so the concrete target is an unspecified implementation detail.

### GEN-86C6EC9A26：数据格式：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.6400；支持度：0.5500；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：数据不满足格式规范

UCG-002-UC003 step 3 validates orderId format and error path A1 returns INVALID_ORDER_ID 400, which is an endpoint-level format check. However this is a request-parameter format check on GET /api/v1/orders/{orderId}, whereas the scenario is scoped to the response payload format ('数据不满足格式规范' on response), which is not explicitly described in the assigned sections. Response body fields are enumerated but no format constraint or violation handling is given.

### GEN-1CDB8E4FC1：数据长度：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6350；支持度：0.5000；缺失度：0.9500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：字符串长度超过限制

候选场景为发布商品 API-M-IF4 请求体字符串长度超限异常。指定证据仅描述公共/类目/乐观锁/目录同步等校验与备选流程（A1-A5），未涉及请求参数（version、publishAt）的字符串长度上限，也无任何长度超限的错误码、响应或恢复策略。因此仅有具体接口上下文支持该机制在发布接口的适用位置，缺失部分高度明确。

### GEN-4DDBC09059：权限控制：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.6300；支持度：0.7500；缺失度：0.3500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：水平越权或垂直越权

SR场景在 API-M-IF1（POST /api/v1/merchant/products）上检查“水平越权或垂直越权”。证据直接支持权限失败机制：前置条件包含“经营资质有效，拥有商品管理权限”，基本流程第5步校验 merchant 表的 qualification_status 与 product_permission；备选流程明确 A1 MERCHANT_NOT_QUALIFIED 403、A2 PERMISSION_DENIED 403。但没有专门针对“水平越权”（跨商家 resource 归属）的证据，仅覆盖资质与功能权限（垂直），故 expected_result/recovery 仍需确认，支持为较强但不完全。；支持度复核：该候选关注点为 human.authorization，触发条件为水平或垂直越权。证据直接支持垂直越权/权限校验机制：前置条件包含经营资质有效且拥有商品管理权限，基本流程第 5 步校验 merchant 表 qualification_status 与 product_permission，备选流程给出 A1 MERCHANT_NOT_QUALIFIED 403、A2 PERMISSION_DENIED 403。但“水平越权”（跨商家资源归属）未有专门证据，仅覆盖资质与功能权限维度，故为明确约束而非完全直接支持。

### GEN-87D772DB5C：权限控制：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6300；支持度：0.7500；缺失度：0.3500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：水平越权或垂直越权

设计文档前置条件明确要求商家携带合法Authorization Token并具有订单处理权限，备选流程A5给出无权限时HTTP 403 PERMISSION_DENIED，直接支持垂直越权失败机制；但未显式区分水平越权（他人订单）与垂直越权，越权场景的区分描述缺失。；支持度复核：The design preconditions require the merchant to carry a valid Authorization Token and have order-processing permission, and alternative flow A5 explicitly specifies the failure response (HTTP 403 Forbidden, PERMISSION_DENIED) for lack of order-processing permission, directly constraining the vertical-privilege-escalation branch. However the candidate trigger also claims horizontal escalation (accessing another merchant's order), which has no explicit separated constraint in the cited evidence, so the evidence covers only part of the claimed mechanism.

### GEN-A07569096B：必填字段完整性：Read or update Product records

推荐评分：0.6300；支持度：0.7500；缺失度：0.3500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：必要字段缺失

Candidate concerns required-field completeness for Product records on the browse API (API-S-IF1, GET /api/v1/products). A7 in the detailed design is a direct, explicit constraint: '商品必要字段缺失，例如 product_name、sale_price 或 cover_image_url 为空，在线商城系统采用缺省值展示或过滤异常商品.' This explicitly names missing required fields for Product records and even provides the handling behavior (default value or filter), so support is strong. Missing_score is moderate-low because the behavior is already described (not absent); residual ambiguity is only whether the candidate's generic '必要字段缺失' maps exactly to the enumerated non-key fields versus critical keys, and the SR-level system requirement does not restate this handling.；支持度复核：候选异常为“执行 Read or update Product records 时必要字段缺失”，与 A7 直接对应：A7 明确处理商品记录（product 表涉及 product_name、sale_price、cover_image_url 等字段）的必要字段为空这一缺失场景，并给出处理机制（缺省值展示或过滤异常商品），属于针对该失败机制/实体的显式约束。但证据位于功能设计备选流程，SR 层系统需求（证据0）仅列 3.a/4.a–4.c 其他异常，未重述该缺失字段处理，因此定为 explicit_constraint 而非 direct。候选步骤“异常响应及恢复方式待需求确认”与 A7 已给出的处理行为存在部分不一致，但失败机制本身获得显式覆盖。

### GEN-19ACAEF207：唯一性约束：Read or update LogisticsEvent records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：名称重复或唯一键冲突

Candidate posits a uniqueness/uniquekey conflict when reading or updating LogisticsEvent records. Evidence shows explicit idempotency handling keyed on eventId within logistics_event (step 5 and A4), i.e. the system already has a duplicate-event mechanism. However the specific 'name duplication / unique key conflict' framing is a generic uniqueness concern that does not match the described idempotency-by-eventId semantics; the source describes duplicate handling as accepted=true/duplicate=true, not a uniqueness constraint violation. So the failure mechanism is only partly supported by existing duplicate-event logic, and the exact constraint/response is unspecified.；支持度复核：Candidate asserts a uniqueness/unique-key conflict on LogisticsEvent records ('name duplicate or unique key conflict'). Evidence shows idempotency keyed on eventId: step 5 queries logistics_event for existing eventId, and A4 returns HTTP 200 with accepted=true, duplicate=true without re-writing. This is a specific operation/entity (LogisticsEvent persistence) with a mechanism, but the mechanism is explicit idempotent duplicate handling, not a DB uniqueness-constraint violation. The sources never describe a unique-key conflict or 'name duplication'; per instructions, idempotent eventId handling does not prove a DB unique-key error. Therefore context, not explicit_constraint.

### GEN-1D0A74161A：并发一致性：Read or update Payment records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：并发更新冲突或后写覆盖前写

候选场景为查看订单详情 API-O-IF2 并发一致性异常。证据中 OrderService 只对 order、order_item、payment、shipment 表执行读取组合，无任何更新 payment 记录或并发冲突处理的步骤；备选流程 A1-A5 仅覆盖格式、权限、不存在、未发货与超时，未涉及并发更新冲突或后写覆盖，也无对应错误码或恢复方式。接口上下文具体，但机制缺失明确。

### GEN-1D827B9553：数据长度：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：字符串长度超过限制

候选场景为申请退款 API-R-IF1 响应/请求体字符串长度超限。证据中参数校验仅覆盖 orderId 格式、items[] 非空、reasonCode 合法、requestedAmount>=0、idempotencyKey 非空，未定义 reasonDescription 等字符串长度上限；备选流程 A1-A5 无长度相关错误码或响应。缺失明确，接口上下文具体。

### GEN-1DA816CEB6：关联一致性：Read or update Category records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：级联删除失效或子对象残留

候选场景为创建商品 API-M-IF1 关联一致性异常（Category records 级联删除失效或子对象残留）。证据中流程只读取 merchant 表做资质/权限校验并写入 product 表，无任何对 category 记录的写操作、级联删除或引用完整性校验；备选流程 A1-A4 也无相关错误码。机制在指定证据中完全缺位。

### GEN-1E556985DB：数据大小：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：文件或请求体超过限制

候选场景为设置库存与价格 API-M-IF3 请求体/文件大小超限。证据中参数校验只涉及 skus[] 非空、skuId 格式、stock/salePrice/originalPrice 数值与 version 非空，未定义请求体大小或文件大小上限；备选流程 A1-A5 无大小超限错误码或响应。缺失明确，接口上下文具体。

### GEN-1EDCB9AB04：数据类型：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：数据类型与接口定义不符

候选场景为查询物流 API-L-IF2 请求数据类型不符。证据中只校验 orderId 格式合法并校验订单归属与状态，未定义请求参数类型不匹配时的检查、错误码或响应；备选流程 A1-A5 均为状态/数据/服务可用性问题，无类型校验相关内容。缺失明确。

### GEN-1FA6FE0CC3：数据大小：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：文件或请求体超过限制

候选场景为填写商品信息 API-M-IF2 请求体/文件大小超限。证据中校验只规定 name/description 长度合法、categoryId 格式、imageUrls[] 格式与数量范围、version 非空，未定义请求体或图片文件大小限制；备选流程 A1-A5 含 INVALID_IMAGE 但仅指 URL 格式或数量超限，不含大小。缺失明确。

### GEN-1FE69D9E91：数据类型：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：数据类型与接口定义不符

候选场景为查看订单详情 API-O-IF2 请求数据类型不符。证据只说明 orderId 格式校验、订单归属与订单不存在等处理，未定义请求数据类型与接口定义不符时的检查逻辑或错误码；备选流程 A1-A5 中 INVALID_ORDER_ID 指格式错误而非类型不符。缺失明确。

### GEN-49681DEB1C：数据长度：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：字符串长度超过限制

创建订单 API-O-IF1 的请求/响应契约、字段与校验流程在证据中有完整描述（cartItemIds、addressId、idempotencyKey、confirmedAmount 校验；备选 A1-A6 错误码），但没有任何字符串长度上限的定义，且全部备选流程均非长度超限类。因此支持度仅停留在具体接口/SSD 上下文层面（0.5）。异常时的响应与恢复完全缺失，证据只表明请求字段会被校验格式，未说明长度约束或超限后的 HTTP/错误码处理，missing 高。

### GEN-49DCEB94D7：数据大小：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：文件或请求体超过限制

申请退款 API-R-IF1 的请求体字段（orderId、items[]、reasonCode、reasonDescription、requestedAmount、idempotencyKey）与参数校验、备选流程均有描述，reasonDescription 等字符串类字段确实存在，但没有任何大小上限或超限处理的定义。备选 A1-A5 均为时限、金额、状态、幂等服务错误，不含请求体过大类异常。接口上下文具体（0.5），但超限行为与恢复策略无证据。

### GEN-4A0A79A8E4：渲染性能：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：渲染耗时影响用户后续操作

查看商品详情 API-S-IF2 描述返回字段（images[]、description 等）并含超时/不可用/缺字段的备选（A4、A5、A6），存在渲染性能相关话题基础，但没有任何渲染耗时阈值、度量或影响后续操作的规则；SSD 主成功路径仅提到展示详情页。证据属具体接口上下文而非对渲染性能失败的明确约束，支持 0.5；渲染性能异常的判定与响应完全未描述。

### GEN-4AC6310AC6：数据大小：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：文件或请求体超过限制

商家发货 API-L-IF1 请求体字段与参数校验（carrierCode、trackingNumber、shippedItems[]）有描述，接口上下文具体，但未给出任何请求体/文件大小上限。备选 A1-A5 覆盖状态、格式、外部服务、权限，均非请求体超限；trackingNumber 仅描述“格式/长度”校验但无阈值。超限异常响应与恢复无证据。

### GEN-4AF6F65876：数据类型：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：数据类型与接口定义不符

加入购物车 API-C-IF1 有明确的参数校验（productId/skuId 格式、quantity>=1、idempotencyKey非空）与备选 A1-A6，接口上下文具体；但没有定义任何字段的数据类型契约细节或类型不符时的错误码（最接近的仅 quantity 不合法 INVALID_QUANTITY）。因此类型不符异常的响应与恢复完全无描述，missing 高。

### GEN-4BE5721D79：数据长度：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：字符串长度超过限制

与 GEN-4AC6310AC6 同源（同一 EXCH、同一 API-L-IF1 SSD 交换）。证据包含请求体字段与 trackingNumber 格式校验流程，但未规定任何字符串长度上限，也不存在长度超限类备选分支（A1-A5 无关）。支持仅限于具体接口上下文，异常响应与恢复缺失。

### GEN-4CD12AA7C3：数据库可用性：Read or update Category records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：连接失败或数据库宕机

设置库存与价格 API-M-IF3 涉及对 sku/product 表的读写（写入 sku 表、更新 product version），存在数据库交互的具体上下文，但证据未描述数据库不可用/连接失败的失败机制，备选 A1-A5 均为校验与乐观锁冲突类。候选所提 subject_node 为 Category records，而证据中实际操作对象是 sku/product 表，存在语义不符，进一步削弱支持。数据库宕机的响应与恢复无任何描述。

### GEN-78FD0E9E7F：数据长度：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：字符串长度超过限制

Candidate concerns api.data.length (string over length limit) at API-L-IF1 ship order. Evidence shows the interface POST /api/v1/orders/{orderId}/shipments with params orderId, carrierCode, trackingNumber, shippedItems[], and step 6 validates trackingNumber format (length, charset, carrier rules). This gives specific interface context (.5) and step 6 plausibly covers 'trackingNumber length' — but the candidate frames it at the API call level as a generic payload-length limit, whereas the evidenced constraint is specifically trackingNumber format validation hosted on OrderService, not the API layer, and no generic string-length limit is defined. Explicit error code INVALID_TRACKING_NUMBER exists for format failure. The generic '调用接口时字符串长度超过限制' response/recovery is not described, so missing is high.

### GEN-A509CACD5E：数据合法性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：非法字符、不允许字段或非法取值

查询物流用例明确对应 API-L-IF2（GET /api/v1/orders/{orderId}/logistics）并定义了响应字段 trackingNumber、status、events[]、lastUpdatedAt、dataSource，可为响应数据合法性提供接口上下文；但备选流程仅处理订单未发货、本地数据不存在、外部服务失败回退缓存、已签收、Adapter 不可用，完全未定义响应字段的合法性约束（字符集、允许字段集或字段取值域），故非法字符/不允许字段/非法取值的行为无显式描述。

### GEN-A88E7FFCD9：查询性能：Read or update Order records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：大表联查超时

创建订单用例步骤10显式写入 order 表和 order_item 表，说明存在对 Order 记录的读写与多表写入，符合“大表联查”的话题相关性；但 A1–A6 备选流程只覆盖价格变更、库存不足、地址无效、幂等重复、购物车空、ProductCatalogService 不可用，没有任何关于查询超时、联查性能阈值或慢查询降级的说明，性能类失效机制完全缺失。

### GEN-B41AD72017：业务约束：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：当前业务条件不满足变更要求

候选是关注点派生的未审查异常（business_constraint），触发描述为泛化的“当前业务条件不满足变更要求”，expected_result 与 recovery 均为“待需求确认”。源章节确实存在具体的退款业务约束（超期 REFUND_WINDOW_EXPIRED、金额超出 REFUND_AMOUNT_EXCEEDED、状态不满足 ORDER_STATUS_INVALID），但该泛化关注点未映射到任何一个具名约束，也未说明异常响应与恢复方式，故支持分限于接口上下文、缺失分很高。

### GEN-C3CF4C0FC2：必填字段完整性：Read or update Category records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：必要字段缺失

申请退款用例的主/备选流程列举了退款期限、金额超限、订单状态、PaymentService不可用、idempotencyKey重复等异常，且基本流程第3步明确校验请求参数（items[]非空、requestedAmount>=0、idempotencyKey非空），与'必要字段缺失'机制相关；但候选触发点被定位为数据库侧'Read or update Category records'的必填字段完整性，来源证据中没有任何Category记录或数据库NOT NULL约束的表述，触发对象与已描述内容不对应，故支持度中等偏低、缺失度高。

### GEN-CD6D491158：数据库可用性：Read or update Product records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：连接失败或数据库宕机

Evidence confirms UCG-001-UC001 browse-goods flow and API-S-IF1, which reads the product table via ProductCatalogService (lines 497-515 describe product table queries and service timeout/unavailable paths). However, the candidate's specific failure mechanism — internal database connection failure or DB outage while reading/updating Product records — is never described; A4/A5 only cover ProductCatalogService timeout/unavailable, not the DB layer. Expected result and recovery are explicitly marked 待需求确认.

### GEN-D21F3CFFEA：身份认证：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：无凭证、Token 无效或过期

API-M-IF3 的详细设计在基本流程第 2 步明确要求校验 Authorization Token 确认商家身份，前置条件也要求商家拥有编辑权限且请求携带合法 Token。这直接印证了'无凭证、Token 无效或过期'的关注点在该接口上确实存在约束。然而，所有备选流程 A1-A5 均为业务校验错误（NEGATIVE_STOCK、INVALID_PRICE、DUPLICATE_SKU、VERSION_CONFLICT、PRODUCT_NOT_FOUND），未定义认证失败时的 HTTP 状态码、错误码或恢复策略（如返回 401 或 403）。因此该异常的具体响应行为在给定章节中缺失。；支持度复核：The candidate concerns authentication failure (missing/invalid/expired token) on PUT /api/v1/merchant/products/{productId}/skus. Cited evidence 1 (line 1042-1053, basic flow step 2) shows '在线商城系统校验 Authorization Token，确认商家身份' and preconditions mention '请求携带合法 Authorization Token' — this establishes that the interface has an authentication operation and validates a credential (context, a specific operation on this interface). However, no cited evidence defines the failure mechanism response: all alternative flows A1–A5 (evidence index 2) cover only NEGATIVE_STOCK, INVALID_PRICE, DUPLICATE_SKU, VERSION_CONFLICT, PRODUCT_NOT_FOUND — no 401/403 status, error code, or recovery for auth failure. Because the token-validation constraint restricts only the success path identity check and does not specify the failure behavior, the evidence does not reach explicit_constraint; it supports only that authentication is a concern on this interface.

### GEN-D2A6BC0297：幂等性：Read or update SKU records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：重复请求导致重复操作异常

查看商品详情接口 API-S-IF2 为只读操作（GET /api/v1/products/{productId}），但候选触发条件描述为'Read or update SKU records'时重复请求导致重复操作异常。接口设计明确表明该操作为读取，且前置条件允许匿名访问，未定义任何写操作或幂等键机制。备选流程 A1-A6 仅覆盖参数格式错误、商品不存在、下架、超时、服务不可用及非关键字段缺失，未提及重复请求下的行为。因此该异常场景与接口语义存在矛盾，在源章节中无明确支撑。

### GEN-D2C1E8AA68：幂等性：Read or update Refund records

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：重复请求导致重复操作异常

查询物流接口 API-L-IF2 设计为只读操作（GET /api/v1/orders/{orderId}/logistics），但候选关注点描述为'Read or update Refund records'时重复请求导致重复操作异常，与接口涉及实体和操作类型均不一致。基本流程和备选流程 A1-A5 均未定义任何重复请求或退款记录更新的行为。该异常场景在给定章节中无对应描述。

### GEN-FDDCAAFE7E：数据长度：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.6200；支持度：0.5000；缺失度：0.9000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：字符串长度超过限制

Candidate concerns api.data.length (string over length limit) on POST /payment/v1/payments. Evidence documents the interface and enumerates checked parameters (orderId format, amount>=0, paymentMethod, notifyUrl non-empty, idempotencyKey non-empty) and alternates A1–A6, but none mention any string length constraint, maximum length, or a length-related error code. Only generic interface context is available, hence mid support; the absence of any length-limit specification (values, fields affected, response) is clear.

### GEN-0310D69FD9：申请金额超过可退款金额。

推荐评分：0.6150；支持度：0.7500；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：申请金额超过可退款金额。

Exception branch 2.b (申请金额超过可退款金额) is directly described in the spec extension path (→ 系统提示顾客调整退款内容), and the interface design explicitly defines alternative flow A2: REFUND_AMOUNT_EXCEEDED with response body containing refundable amount. The failure mechanism (requestedAmount exceeds refundable amount) is concretely supported. Minor gap: SR-level precondition/postcondition for this branch are marked 待需求确认, but the behavior itself is well specified in design.；支持度复核：SCN-541CD811DF branch 2.b claims exception '申请金额超过可退款金额'. Cited evidence index 1 (功能设计) explicitly defines alternative flow A2 with the exact failure mechanism (退款金额超过可退款金额), HTTP 409, error code REFUND_AMOUNT_EXCEEDED, and response body containing refundable amount. SR-level text (index 0) also states the branch with expected result 系统提示顾客调整退款内容. The mechanism/entity matches precisely, so the constraint is concrete and directly applicable rather than context. However, the SR-level precondition/postcondition are marked 待需求确认, leaving the branch's SR envelope partially unspecified; this limits it to explicit_constraint rather than a fully closed direct specification. No invention of the 409 code or REFUND_AMOUNT_EXCEEDED — both are verbatim from the design.

### GEN-3C19AB2A05：超过退款期限。

推荐评分：0.6150；支持度：0.7500；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：超过退款期限。

Exception branch 2.a (超过退款期限) is directly described in the SR extension path (→ 系统拒绝申请并说明原因) and design alternative flow A1 defines REFUND_WINDOW_EXPIRED (HTTP 409). The failure mechanism (request beyond refund window) is concretely supported; only the SR branch precondition/postcondition are 待需求确认.；支持度复核：SCN-3202ABD1A0 branch 2.a claims exception '超过退款期限'. Cited evidence index 1 explicitly defines A1 超过退款有效期 → HTTP 409 REFUND_WINDOW_EXPIRED; index 0 SR extension path states 2.a 系统拒绝申请并说明原因. The failure mechanism (request beyond refund window) matches the constraint entity directly, and the 409/error code are verbatim, not inferred. As with the sibling branch, the branch-specific pre/postconditions are 待需求确认, so it is an explicit constraint on the failure behavior rather than a fully closed direct scenario. No invented window length or expiry code.

### GEN-40BF014705：支付结果重复通知。

推荐评分：0.6150；支持度：0.7500；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 5

建议补充：支付结果重复通知。

Exception branch 5.a (支付结果重复通知) is directly described in the SR extension path (→ 系统进行幂等处理，不重复更新订单). Design alternative flows reinforce idempotency handling: A6 支付回调按 paymentId 幂等处理不重复更新订单状态, and A5 idempotencyKey重复返回已有支付结果. The mechanism (duplicate notification → idempotent no-op) is explicitly supported; only SR branch precondition/postcondition are 待需求确认.；支持度复核：SCN-48C0844474 branch 5.a claims exception '支付结果重复通知' with expected result '系统进行幂等处理，不重复更新订单'. Cited evidence index 2 explicitly specifies A6 idempotent handling by paymentId without re-updating order status, plus A5 idempotencyKey duplicate returning existing result — both matching the duplicate-notification failure mechanism. Index 1 SR confirms 5.a → 幂等处理，不重复更新订单. Note the anti-pattern warning: idempotency here is exactly the claimed mechanism (duplicate callback → idempotent no-op), not a DB unique-key error, so this is a genuine mechanism match rather than a cross-domain overreach. Emitted as explicit_constraint because the branch scenario's own precondition/postcondition remain 待需求确认 and the exact HTTP/error-code response for the callback path is not fully enumerated.

### GEN-473A451238：PaymentService暂时不可用。

推荐评分：0.6150；支持度：0.7500；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 4

建议补充：PaymentService暂时不可用。

Exception branch 4.a (PaymentService暂时不可用) is directly described in the SR path (→ 系统保存待处理退款单并异步重试). Design alternative flow A4 explicitly states RefundService keeps the refund单 PENDING and asynchronously retries, with refundStatus=PROCESSING; V5 chain lists PAYMENT_SERVICE_UNAVAILABLE error. Mechanism is concretely supported; only SR branch precondition/postcondition are 待需求确认.；支持度复核：SCN-90EF10C2AD branch 4.a claims exception 'PaymentService暂时不可用' with expected result '系统保存待处理退款单并异步重试'. Cited evidence index 1 explicitly defines A4: RefundService keeps the refund record PENDING, asynchronously retries submission, and returns refundStatus=PROCESSING. Index 0 SR extension path states the same. The failure mechanism (dependency unavailable → persist PENDING + async retry) matches the candidate's trigger and recovery exactly, and no PENDING/PROCESSING/retry semantics are invented. Remaining to explicit_constraint (not direct) because the branch's SR precondition/postcondition are 待需求确认 and only the design alternative flow closes the behavior.

### GEN-79954A57E0：业务约束：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6150；支持度：0.7500；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：当前业务条件不满足变更要求

Concern service.resource_mutation.business_constraint on API-O-IF1 POST /api/v1/orders ('当前业务条件不满足变更要求'). Evidence explicitly describes business-constraint validation: step 7 checks ON_SALE status, sufficient stock, confirmedAmount matches current price, coupon validity; backup flows include price changed (PRICE_CHANGED 409), out of stock (OUT_OF_STOCK 409), invalid address (INVALID_ADDRESS 400), cart empty (CART_EMPTY 400), and idempotency duplicate. These are concrete business conditions whose violation blocks the order mutation, supporting the failure mechanism. Missing is low-moderate because the candidate's abstract trigger is already substantially covered by named conditions, though the interface layer-level 'condition not satisfied' has multiple specific mapped responses rather than one generic one.；支持度复核：The concern is a business-constraint failure on POST /api/v1/orders where current business conditions are not met. Evidence index 1 (功能设计Delta_spec.md design detail, lines 629-640) explicitly specifies the business-condition validations performed on this exact operation (ON_SALE status, sufficient stock, confirmedAmount matching current price, coupon validity/scope), and evidence index 2 (lines 641-652) gives named backup flows for violations: PRICE_CHANGED 409, OUT_OF_STOCK 409, INVALID_ADDRESS 400, CART_EMPTY 400, plus idempotent duplicate handling. This is a concrete, documented set of conditions whose violation blocks the order mutation, so it supports THIS failure mechanism. It is explicit_constraint rather than context because the constraint itself (business precondition on the mutation) is specified, not merely the operation surface. It falls short of direct because the candidate's single abstract trigger maps to multiple distinct specific conditions and responses rather than one unambiguously documented generic exception; the mechanism is present but the candidate phrasing is not verbatim specified as a single failure.

### GEN-7C6D5AB474：查询性能：Read or update Product records

推荐评分：0.6150；支持度：0.7500；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：大表联查超时

Concern internal_database.query_performance on 'Read or update Product records' during 浏览商品 (API-S-IF1). Evidence explicitly describes ProductCatalogService querying the product table (step 4) and backup A4 '查询超时' → HTTP 504 Gateway Timeout PRODUCT_SERVICE_TIMEOUT, plus A5 (503) unavailability. This directly supports a large-table/timeout failure mechanism at the query boundary. Missing is low-moderate: the concrete failure (query timeout) and its response are documented, though '大表联查' (multi-table join) is not literally named — only single-table product query is shown, so the specific large-join cause is slightly more specific than the evidence.；支持度复核：The assigned design section explicitly documents the same query-boundary mechanism the candidate asserts: ProductCatalogService queries the product table (step 4), and alternative flow A4 specifies query timeout with a defined HTTP 504/PRODUCT_SERVICE_TIMEOUT response (A5 adds unavailable → 503). This is an explicit operational constraint on this exact failure mechanism, not merely field validation. It falls short of 'direct' only for the candidate's more specific '大表联查超时' cause: no multi-table join is documented (only a single product-table query), so that concrete cause remains unsupported specificity.

### GEN-E5CA74E988：分类不存在或已停用。

推荐评分：0.6150；支持度：0.7500；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 2

建议补充：分类不存在或已停用。

场景为需求层扩展分支『2.a 分类不存在或已停用 → 系统要求商家重新选择分类』。系统需求在该用例的扩展路径中逐字给出该分支及其期望结果，功能设计详情的备选流程 A2 亦给出对应实现：categoryId 不存在或已停用返回 HTTP 400 Bad Request / INVALID_CATEGORY，互为印证，支持度较高。但该分支的独立前置/后置条件在需求文档中确实未单独描述（候选自身标注『待需求确认』），且错误码在V5标准化调用链中被记录为 CATEGORY_NOT_FOUND 与详情中 INVALID_CATEGORY 命名不一致，存在轻微描述歧义。；支持度复核：The candidate's failure mechanism is exactly 'category does not exist or is deactivated → system requires merchant to reselect a category'. Requirement-layer extension 2.a states literally 分类不存在或已停用 → 系统要求商家重新选择分类, and design detail A2 supplies the specific HTTP 400 / INVALID_CATEGORY mapping for the same entity (categoryId validity) and same trigger. This is a direct mechanism/entity match, so it qualifies as an explicit constraint (0.75). It is not upgraded to direct because the candidate's own pre/postconditions remain 待需求确认 and the V5 chain records the error code inconsistently as CATEGORY_NOT_FOUND vs INVALID_CATEGORY; the behavioural constraint is explicitly stated and mutually corroborated, but the candidate's full response/recovery contract is not itself specified.

### GEN-ED793ACC41：并发与幂等性：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.6150；支持度：0.7500；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：并发变更产生冲突，或重复请求导致重复变更

设计文档明确引入idempotencyKey并由RefundService执行幂等校验，备选流程A5规定幂等键重复返回既有退款单不重复创建，直接支持并发与幂等性失败机制；但并发变更冲突（非重复请求）的具体处理未在设计文档中单列，存在轻微缺口。；支持度复核：The design explicitly introduces a client-generated idempotencyKey, requires RefundService to perform idempotency validation (step 6), and alternative flow A5 specifies exact duplicate-request handling (return existing refund, do not recreate). This directly constrains the idempotency half of the concern. Concurrent-modification conflict (non-duplicate concurrent change) is not separately specified as a distinct alternative flow, so it is only implicit.

### GEN-0D0F69097F：数据长度：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：字符串长度超过限制

The concern is api.data.length string-length-over-limit on the SKU PUT (API-M-IF3). Supplied evidence confirms request params and validation steps (skus[] non-empty, skuId format, stock>=0, salePrice>=0) and lists alternative flows (NEGATIVE_STOCK, INVALID_PRICE, DUPLICATE_SKU, VERSION_CONFLICT, PRODUCT_NOT_FOUND), but no length limit on any string field is stated and no overflow error code or response is defined, so the failure mechanism has an explicit validation frame but the specific constraint is absent.；支持度复核：The supplied sections define format/presence validation and numeric constraints on SKU fields plus alternative flows (NEGATIVE_STOCK, INVALID_PRICE, DUPLICATE_SKU, VERSION_CONFLICT, PRODUCT_NOT_FOUND), but no string length limit is specified for any field and no length-overflow error code or response exists. Per the rule that absent length limits mean field/format checks are merely context, this does not establish the api.data.length failure mechanism.

### GEN-0D6A8FCABC：持久化能力：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：写入失败或事务回滚

The concern is internal_database.persistence — write failure / transaction rollback when touching Category records during Create Product. The evidence shows MerchantProductService writes product table rows and a service-unavailable path (MERCHANT_SERVICE_UNAVAILABLE), which establishes that persistence writes exist in the flow, but no Category write is in the create-product flow and no rollback or write-failure behavior is defined.

### GEN-0F5CDC9B52：幂等性：Read or update Product records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：重复请求导致重复操作异常

The concern is internal_database.idempotency — duplicate request causing repeated operations during Browse Product (a read). The evidence shows a read-only retrieval flow (GET, query product table, return results) with no write operation, so a repeated-operation anomaly has no plausible mutation to guard; idempotency is only addressed for other use cases (create product, refund) via idempotencyKey. No idempotency semantics are specified for the browse interface.

### GEN-11EBD529FC：数据大小：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：文件或请求体超过限制

The concern is api.data.size — oversized request body on the order POST (API-O-IF1). Evidence confirms the request body fields and non-emptiness/format validation, giving an explicit validation frame, and the create-order flow lists several alternative errors, but no request/body size limit or size-exceeded error code is defined anywhere in the supplied sections.；支持度复核：Evidence confirms the POST /api/v1/orders request body fields (cartItemIds, addressId, couponId, idempotencyKey, confirmedAmount) and non-emptiness/format validation (step 3), plus alternative flows A1–A5 for price, stock, address, idempotency, and empty cart. No request/body size limit, bound, or size-exceeded error code appears anywhere; field-level format checks do not establish a size-overflow mechanism, so this is only context on the specific interface.

### GEN-16B0E40326：权限控制：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：水平越权或垂直越权

水平/垂直越权被挂在加入购物车接口上，但设计证据只说明步骤2校验 Authorization Token 确认顾客身份，所有备选流程均为数量非法、下架、库存、限购、幂等、依赖不可用，没有 403 或越权错误码，也没有资源属主校验约束。仅有具体接口与步骤上下文支撑，越权机制本身无显式描述。

### GEN-1A962C9C31：数据长度：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：字符串长度超过限制

Candidate asserts a string-length-over-limit failure on POST /api/v1/orders. Evidence shows explicit request parameter validation (step 3: cartItemIds non-empty, addressId format, confirmedAmount>=0, idempotencyKey non-empty) which supports that request field constraints exist, but no maximum length is stated and no length-exceeded error code is given. Failure mechanism plausibly supported by generic parameter validation, but the specific length constraint and response are absent.；支持度复核：Candidate asserts a string-length-over-limit failure on POST /api/v1/orders. Evidence shows request parameter validation (step 3: cartItemIds non-empty, addressId format legal, confirmedAmount>=0, idempotencyKey non-empty), establishing a specific interface with some field constraints. But no maximum length is stated and no length-exceeded error code is defined; the constraints present are non-emptiness/format/range, not length. Per instructions, data field/format checks without stated length limits do not prove a length-overflow mechanism. Hence context, not explicit_constraint.

### GEN-1AB235AB66：数据合法性：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：非法字符、不允许字段或非法取值

Candidate asserts illegal character / disallowed field / illegal value when calling GET /api/v1/orders/{orderId}. Evidence shows explicit orderId format validation (step 3) and A1 INVALID_ORDER_ID 400 response, which directly supports the legality-check mechanism for the identifier. However the concern generalizes beyond orderId to 'fields/values', where no explicit evidence exists. Failure mechanism is supported for the id but only partially for the broader legality scope.；支持度复核：Candidate asserts illegal character / disallowed field / illegal value when calling GET /api/v1/orders/{orderId}. Evidence shows a specific interface with orderId format validation (step 3) and A1 returning 400 INVALID_ORDER_ID for a malformed orderId, which is a legality check specifically for the path identifier. However the concern generalizes the failure to disallowed fields and illegal values beyond orderId, for which no mechanism/constraint is stated. The evidence covers only the orderId format-legality subset, so it is context rather than a full explicit constraint matching the asserted mechanism.

### GEN-1B1F5BBC08：字段合法性：Read or update Product records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：类型错误、非法字符或超长

Candidate asserts field validity (type error, illegal chars, over-length) on Product records read. Evidence shows parameter validation (page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice) and A1 INVALID_QUERY_PARAM / A7 missing-field handling, giving specific interface context for read validation. But the described concern targets Product records internal fields (target_node internal_database.field_validity), whereas evidence covers request query params and display fields, not the internal DB field-validity model described. Only topical/interface-level support.

### GEN-1C629C3CB6：数据格式：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：数据不满足格式规范

Candidate asserts a data-format violation when calling GET /api/v1/orders/{orderId}/logistics. Evidence defines structured response (trackingNumber, status, events[], lastUpdatedAt, dataSource) and A2/A3/A5 alternative flows, plus an error set (ORDER_NOT_FOUND, LOGISTICS_SERVICE_TIMEOUT), but no explicit format-validation failure branch exists for the response. The concern is topical to the interface but not backed by a described format-check mechanism or error code.

### GEN-31CB207F4B：必填字段完整性：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：必要字段缺失

候选把「必要字段缺失」定位到 Category 记录读取/更新（API-M-IF2 步骤4），但被分配章节将字段完整性校验放在 product 表写入与图片约束环节（name 非空、description 长度、version 非空），分类校验仅要求 categoryId 格式合法并确认分类有效未停用，并未描述 Category 记录自身必填字段缺失的失败机制。因此支持来自「存在必填字段校验」的间接语境，而非针对 Category 持久化的直接约束。备选流程 A1–A5 无必填字段缺失对应的响应。

### GEN-320E803230：数据长度：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：字符串长度超过限制

候选为 API-M-IF3 请求字符串长度超限。基本流程第3步校验 skus[] 非空、skuId 格式合法、stock>=0、salePrice>=0、originalPrice>=0、version 非空，未定义任何字符串长度上限；备选流程覆盖负数库存、非法价格、重复 skuId、版本冲突、商品不存在，均非长度异常。支持仅为「存在请求参数校验」这一泛化语境，长度超限行为无显式证据。

### GEN-33151E5505：数据类型：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：数据类型与接口定义不符

候选位于发布商品请求校验步骤，触发为请求数据类型与接口定义不符。基本流程第3步仅校验 version 非空、publishAt 格式合法，未定义 version 或 publishAt 的类型契约；备选流程 A1–A5 覆盖资料不完整、类目规则、状态、版本冲突、同步失败，均非类型错误。支持来自存在参数校验与格式校验的语境，但类型不匹配的具体失败与恢复无显式证据。

### GEN-3F756E8C43：数据格式：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：数据不满足格式规范

浏览商品接口 API-S-IF1 的参数约束在功能设计中有显式定义（page>=1、1<=pageSize<=100、minPrice>=0、maxPrice>=minPrice、categoryId 有效性校验），并且备选流程 A1/A2 已对非法参数给出 HTTP 400 INVALID_QUERY_PARAM / INVALID_CATEGORY。因此“数据不满足格式规范”这一失败机制在接口约束层面确实被部分支撑。但所提异常是“request_payload 数据格式不满足格式规范”，现有证据只覆盖数值范围与枚举（sortBy）校验，未覆盖通用“数据格式（format）”违规的判定与响应；且 expected_result/recovery 明确标注“待需求确认”，说明系统需求层面对该格式异常未给出可验证响应。；支持度复核：Concern is api.data.format on the request payload of GET /api/v1/products. The cited evidence defines parameter constraints and invalid-value handling (page>=1, 1<=pageSize<=100, minPrice/maxPrice ordering, categoryId validity, sortBy enum in A1: INVALID_QUERY_PARAM / INVALID_CATEGORY), i.e. value-range and enum validation. It does not constrain general data-format violations (malformed types/syntax) or specify a format-error response; expected_result/recovery are marked 待需求确认. Validation of other field properties is only context for this failure mechanism.

### GEN-4C19B60846：数据类型：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：数据类型与接口定义不符

该候选关注 API-S-IF2 响应 payload 的“数据类型与接口定义不符”。现有证据确实规定了 productId 的格式校验（A1 INVALID_PRODUCT_ID）以及响应字段集（productId、name、description、images[]、price、originalPrice、stockStatus、salesCount），提供了接口与响应结构的具体上下文，可支撑 0.5 分。但没有任何条款描述“响应字段数据类型不符”的判定、错误码或降级行为；需求侧扩展路径只覆盖商品不存在、已下架、非关键字段缺失，未覆盖响应数据类型异常。

### GEN-555AEF11B9：并发一致性：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：并发更新冲突或后写覆盖前写

候选针对发布流程中“读取或更新 Category 记录”的并发一致性（并发更新冲突或后写覆盖前写）。证据中产品本身存在乐观锁（第 5 步校验 version 一致，A4 返回 VERSION_CONFLICT 并返回最新 version），且第 7 步确实读取 category 表以获取类目必填属性与发布规则，因此涉及 Category 读取这一具体接口上下文被支撑（0.5）。但没有任何条款说明 category 记录的并发更新冲突处理、写覆盖保护或相应错误语义；乐观锁仅作用于 product 表的 status/version，不能直接覆盖 category 记录的并发一致性，缺口清晰。

### GEN-58B011C3BF：超时关注点：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：延时是否影响需求满足、后续行为执行或系统与环境协调

PAYMENT-PAY-01 章节仅出现「PaymentService 不可用或超时」的组合描述与 PAYMENT_SERVICE_UNAVAILABLE，并未单独定义超时时限、重试策略或超时与可用性的区分，来源索引/接口表也只列出 PAYMENT_TIMEOUT 而非超时时长或行为。候选人触发的「延时是否影响需求满足/后续行为/环境协调」属通用超时关注点，具有接口上下文但缺少可验证的超时约束，故支持度中等且缺失度高。

### GEN-682E1135B1：必填字段完整性：Read or update Order records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：必要字段缺失

The candidate concerns required-field completeness during 'Read or update Order records' (API-O-IF1 create-order flow, OrderService writing to the order/order_item tables). Step 10 of the basic flow enumerates the specific fields written to order and order_item tables, and step 3 validates request parameters (cartItemIds non-empty, addressId format, confirmedAmount>=0, idempotencyKey non-empty). However, there is no explicit database-level required-field completeness constraint, no NOT NULL specification, and no described failure mechanism for missing required fields in DB writes. The alternate flows cover price/stock/address/idempotency/cart-empty but not DB required-field violations. This makes the behavior largely inferred rather than described.

### GEN-6A6E0E793F：权限控制：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：水平越权或垂直越权

The candidate concerns authorization failure (horizontal/vertical privilege escalation) during API-M-IF4 (POST /api/v1/merchant/products/{productId}/publish). Basic flow step 2 validates Authorization Token to confirm merchant identity, and step 5 checks that the product belongs to the current merchant. However, the alternate flows A1-A5 cover incomplete data, category rule violations, product status, version conflict, and catalog sync failure—none address authorization/privilege escalation. There is no explicit error code or response for horizontal or vertical privilege escalation. The concern is only partially supported by generic token/product-ownership checks with no dedicated privilege-escalation failure handling described.

### GEN-735BA3590A：唯一性约束：Read or update Shipment records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：名称重复或唯一键冲突

场景声称在「Read or update Shipment records」执行时触发『名称重复或唯一键冲突』(internal_database.uniqueness)。源证据确证 shipment 记录的写入存在（设计用例详情基本流程第7步写 shipment 表，字段含 shipment_id、order_id、carrier_code、tracking_number 等），且备选流程覆盖了多种失败（A1 订单状态、A2 trackingNumber 格式、A4 shippedItems 归属、A5 权限），因此接口/SSD 上下文具体。但全篇未出现任何唯一性约束的语义，且备选流程中不存在『名称重复』或唯一键冲突的分支——shipment 记录本无『名称』字段，该失败机制与接口语义不匹配。仅凭订单与发货记录写入的一般上下文无法逻辑支撑名称重复触发。故支持度中低，缺失度高。

### GEN-7C9FD22D69：数据长度：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：字符串长度超过限制

Concern api.data.length on API-C-IF1 POST /api/v1/cart/items. Evidence gives interface context (step 3 checks productId/skuId format, quantity>=1, idempotencyKey non-empty; alternative A1 invalid quantity) but no rule about a generic string exceeding a length limit, and the listed error codes are INVALID_QUANTITY/OFF_SHELF/OUT_OF_STOCK/PURCHASE_LIMIT/CART service errors — none is a length-limit error. Support is interface-context level (.5); the specific length-limit failure and its response/recovery are not described, so missing is high.

### GEN-8A0E57C3C5：关联一致性：Read or update Order records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：级联删除失效或子对象残留

Concern internal_database.referential_consistency on Order records is contextually supported: the create-order detail flow defines explicit writes to the order table and the co-written order_item table (order_item rows reference order_id), establishing the parent-child write that could suffer cascade failure or orphan residuals. However, no source statement mentions cascade delete, FK integrity checks, or orphan handling, and the extension paths (A1-A6) cover only price/stock/address/idempotency/service-down cases. The precondition 'confirmedAmount与当前价格一致' is not a constraint on referential integrity.；支持度复核：Candidate concerns internal_database.referential_consistency — cascade delete failure or orphaned child rows. Cited evidence shows OrderService writes to the order table and the order_item table (child rows referencing order_id) within the same create-order step, which establishes a parent-child write operation as context, and the use case is a create (not delete) flow. No source statement mentions cascade delete, foreign-key integrity enforcement, orphan cleanup, or any referential-integrity failure mechanism; the alternate flows A1–A5 cover only price mismatch, stock shortage, invalid address, idempotency replay, and empty cart. The evidence is therefore a specific operation/interface without a mechanism constraint, i.e. context, not explicit_constraint.

### GEN-8AAF665D97：字段合法性：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：类型错误、非法字符或超长

internal_database.field_validity is supported only by the generic request-parameter validation step for the refund API (orderId format, items[] non-empty, reasonCode legality, requestedAmount>=0, idempotencyKey non-empty). No field-validity rules are specified for the Category records that are the nominated target node, and no type/length/charset constraints appear. The Category read path is only referenced in the design (category_id/category table) for product publish, not for refunds, making the target-subject binding weakly grounded.

### GEN-8C71A5B82F：字段合法性：Read or update Order records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：类型错误、非法字符或超长

internal_database.field_validity for Order records is partially supported by the create-order request-parameter validation step (cartItemIds non-empty, addressId format, confirmedAmount>=0, idempotencyKey non-empty) and the order/order_item write field list (order_id, customer_id, status, total_amount, etc.). These are format/non-empty checks rather than type/length/charset constraints on the persisted order fields, and no field-validity error path is defined. Target node 'Read or update Order records' rather than request payload narrows the match further.

### GEN-9021C050C2：持久化一致性：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：操作结果未可靠持久化或局部成功

Candidate concerns persistence consistency on API-M-IF3 PUT /api/v1/merchant/products/{productId}/skus. Evidence describes this exact interface and its write to sku table and product version update (steps 7-8) inside a version-carrying update, establishing the persistence surface where partial/reliable-persistence risk could arise, so specificity is met (.5). However, no evidence states any requirement for atomicity, transaction rollback, or partial-success handling — alternatives A1-A5 cover validation/conflict cases only. Behavior is therefore undefined ('异常响应及恢复方式待需求确认').

### GEN-91773F88F3：超时关注点：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：延时是否影响需求满足、后续行为执行或系统与环境协调

Candidate concerns common.timeout on API-M-IF4 POST .../publish. Evidence describes the exact publish interface including an optimistic-lock version check and a catalog sync step (steps 5, 9) that could plausibly be slow, which supports the timeout surface at interface level (.5). But no evidence specifies any latency budget, timeout threshold, or timeout response/recovery behavior; the closest alternative A5 covers catalog sync failure with retry, not request timeouts. Behavior remains undefined.

### GEN-938797536D：查询性能：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：大表联查超时

Candidate concerns internal_database.query_performance ('大表联查超时') on 'Read or update Category records' during API-M-IF4 发布商品. Evidence explicitly states that step 7 queries the category table to obtain required attributes and publishing rules, directly tying the publish flow to a category-table read, which supports the specific interface/processing context (.5). However, no evidence describes large-table joins, query timeouts, latency budgets, or any degradation/retry behavior for slow category queries; the failure mechanism and response are undefined.

### GEN-9416B7F8ED：数据库可用性：Read or update Cart records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：连接失败或数据库宕机

Candidate concerns internal_database.availability (connection failure/DB down) for 'Read or update Cart records' in 加入购物车. Evidence shows the cart write path against cart_item (step 9) and a 503 fallback only for ProductCatalogService unavailability (A6), which confirms a concrete DB-dependent write surface for this interface (.5). No evidence addresses database outage/connection loss for the cart persistence itself, and no recovery policy is stated, so the specific behavior is missing.

### GEN-A063226993：关联一致性：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：级联删除失效或子对象残留

Candidate targets '关联一致性：级联删除失效或子对象残留' on CategoryService records within UCG-004-UC002 (填写商品信息). The design describes only a VALIDATE/read of category (step 6: query category to confirm valid and not disabled), never a delete or referential cascade. A2 (INVALID_CATEGORY) covers nonexistent/disabled category but is not a cascade-delete failure. So the referential-consistency failure mechanism has no explicit counterpart in the interface constraints — context exists but the specific mechanism is absent.

### GEN-A3E4E8A897：关联一致性：Read or update OrderItem records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：级联删除失效或子对象残留

支付用例的授权章节明确描述 order/payment 表的读写与状态更新（步骤9更新 order 状态为 PAID 并记录支付流水），说明该场景步骤确实落在真实数据操作上，但所涉实体为 order/payment，而场景关注点是 OrderItem 记录的级联删除失效或子对象残留，该机制在支付用例的任何备选流程中均未出现（A1–A6 只覆盖状态非法、金额不一致、PaymentService 不可用、取消、idempotency 重复、回调幂等）。因此仅有接口/SSD 级别的相关上下文，无显式约束支撑该失效机制。

### GEN-A4AC0C5125：持久化一致性：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：操作结果未可靠持久化或局部成功

填写商品信息用例明确调用了 API-M-IF2（PUT /api/v1/merchant/products/{productId}），基本流程步骤8描述对 product 表的字段级更新，属于资源变更持久化的直接上下文；但备选流程 A1–A5 仅覆盖 PRODUCT_NOT_FOUND、INVALID_CATEGORY、INVALID_IMAGE、VERSION_CONFLICT、INVALID_PRODUCT_STATUS，没有任何“操作结果未可靠持久化或局部成功”的事务/部分写入说明，存在乐观锁与版本检查可部分缓解，但无明确持久化失败与回滚语义。

### GEN-A5B180D24F：数据范围：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：数值超出允许范围

查看订单详情用例明确调用 API-O-IF2（GET /api/v1/orders/{orderId}），请求参数为 orderId，并有 A1 备选流程处理 orderId 格式错误（HTTP 400 INVALID_ORDER_ID），说明请求参数存在格式/取值校验上下文；但“数值超出允许范围”作为独立范围约束未被定义——orderId 仅有格式校验描述，无长度、数值区间或边界值规格，且 A1 与所报触发的语义归属存在含糊（格式 vs 范围）。

### GEN-A668DB9101：幂等性：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：重复请求导致重复操作异常

填写商品信息流程步骤6显式调用 CategoryService 校验 categoryId、查询 category 表（category_id、status），确认分类有效且未停用，构成对 Category 记录读取的明确上下文；但 A2 仅处理 categoryId 不存在或已停用（HTTP 400 INVALID_CATEGORY），未提及重复请求导致的重复操作，且该节点为纯读校验，幂等性语义在分类读取路径上缺乏显式约束。

### GEN-BEF9B3427E：必填字段完整性：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：必要字段缺失

该未审查候选指派到“Read or update Category records”的必填字段完整性，但发布商品流程中的资料完整性校验（name/description/category_id/image_urls 非空、SKU 库存与价格）在设计中明确对应备选流程 A1 PRODUCT_INCOMPLETE，且该失败与 category 表读取无直接关联。关注点定位与源章节语义不符，且异常响应与恢复未确认，故支持分仅基于接口上下文。

### GEN-CE3954E6FA：数据合法性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：非法字符、不允许字段或非法取值

Evidence confirms payment flow via PAYMENT-PAY-01 POST /payment/v1/payments (lines 679-701) with request params orderId, amount, paymentMethod, notifyUrl, idempotencyKey and param validation in step 3. But the specific concern — illegal characters, disallowed fields, or invalid values in the request payload — is only generically covered by canonical validation (all invalid cases map to amount mismatch or status codes); no explicit data-legality error code is defined, and expected result/recovery are 待需求确认.

### GEN-CE7541AED7：数据范围：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：数值超出允许范围

Evidence confirms GET /api/v1/orders/{orderId} order-detail flow (lines 726-746) with orderId format validation and errors INVALID_ORDER_ID, ORDER_ACCESS_DENIED, ORDER_NOT_FOUND, ORDER_SERVICE_TIMEOUT. But numeric-out-of-range specifically is not described; the only related handling is format-invalid (A1 400) and service timeout (A5 504), neither of which addresses range. Expected result and recovery are 待需求确认.

### GEN-CE9511DDF7：数据范围：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：数值超出允许范围

Evidence confirms logistics query API-L-IF2 GET /api/v1/orders/{orderId}/logistics with orderId param and format validation (lines 861-872), plus alternative flows for not-shipped, not-found, cache fallback, and adapter unavailable (lines 873-881). The specific concern of numeric-out-of-range in the request is not described; only format validation is mentioned. Expected result/recovery are 待需求确认.

### GEN-D08A883689：超时关注点：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：延时是否影响需求满足、后续行为执行或系统与环境协调

Evidence confirms PUT /api/v1/merchant/products/{productId} flow (lines 997-1017) with version-based optimistic locking, CategoryService validation, image checks, and errors PRODUCT_NOT_FOUND, INVALID_CATEGORY, INVALID_IMAGE, VERSION_CONFLICT, INVALID_PRODUCT_STATUS. Timeout/delay semantics are not explicitly addressed for this endpoint; no latency threshold or degradation behavior is given, and overall response/recovery are 待需求确认.

### GEN-D11418A07C：查询性能：Read or update SKU records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：大表联查超时

Evidence confirms product-detail flow API-S-IF2 GET /api/v1/products/{productId} reading the product table (lines 540-556) with errors for invalid id, not found, off-shelf, timeout, and service unavailable. The specific concern — large-table join query timeout — is only indirectly matched by A4 PRODUCT_SERVICE_TIMEOUT; no query-performance constraint, index, or latency budget is stated. Expected result/recovery are 待需求确认.

### GEN-D1432E6F2C：超时关注点：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：延时是否影响需求满足、后续行为执行或系统与环境协调

Evidence confirms create-product flow API-M-IF1 POST /api/v1/merchant/products (lines 954-972) with merchant qualification check, idempotency, and errors MERCHANT_NOT_QUALIFIED, PERMISSION_DENIED, duplicate-key idempotency, MERCHANT_SERVICE_UNAVAILABLE. Timeout/delay semantics are not explicitly defined for this endpoint; no latency threshold or timeout behavior or recovery policy is provided, and expected result/recovery remain 待需求确认.

### GEN-D39E225B32：并发一致性：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：并发更新冲突或后写覆盖前写

API-M-IF3 涉及 SKU 和库存价格的更新，设计采用乐观锁（version 一致校验）来处理并发更新冲突，备选流程 A4 定义了版本不一致时的 VERSION_CONFLICT 错误。但候选触发条件关注的是 'Read or update Category records' 的并发一致性，接口设计中并未涉及 Category 表的并发更新；接口详情也未明确定义并发写冲突下的具体恢复策略（如冲突时是否自动合并或提示重试）。因此虽有并发控制的上下文，但与候选所指的 Category 记录并发一致性不匹配，异常响应行为缺失。

### GEN-D61C6F7248：数据范围：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：数值超出允许范围

发布商品接口 API-M-IF4 的请求参数包含 version、publishAt，基本流程要求校验版本非空、发布时间格式合法。但候选关注点触发条件为'数值超出允许范围'，接口设计和备选流程 A1-A5 均未定义任何数值范围校验（如 publishAt 时间范围、version 上限等），该异常的具体响应行为在给定章节中无描述。支撑度仅来自接口有参数校验的上下文。

### GEN-D629BFE7E0：数据格式：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：数据不满足格式规范

填写商品信息接口 API-M-IF2 的基本流程第 3 步明确要求校验请求参数格式：name非空且长度合法、description长度合法、categoryId格式合法、imageUrls[]格式合法，这与'数据不满足格式规范'的触发条件直接相关。备选流程 A3 定义了图片URL格式或数量超限时返回 INVALID_IMAGE，但未全面定义其他字段（如 name、description 长度或类型）不满足格式规范时的统一错误码或恢复方式。因此有明确约束支撑该失败机制，但具体响应定义不完整。；支持度复核：证据仅说明基本流程第3步会校验 name/description/categoryId/imageUrls 的格式，属对接口操作的参数校验描述，但未给出任何针对“数据不满足格式规范”这一失败机制的具体格式规范（长度上限、正则、类型）或错误码/响应体/恢复路径。备选流程A3只覆盖图片URL格式或数量超限（INVALID_IMAGE），不覆盖 name/description 等其他字段的格式违规，故不足以支撑该失败机制，仅构成相关接口的上下文。

### GEN-D6967BBE26：数据格式：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：数据不满足格式规范

设置库存与价格接口 API-M-IF3 的基本流程第 3 步明确要求校验请求参数：skus[]非空、每项 skuId 格式合法、stock>=0、salePrice>=0、originalPrice>=0、version非空。备选流程 A2 定义了价格不合法时返回 INVALID_PRICE，但仅针对 salePrice/originalPrice 为负数或格式错误；对于其他字段（如 skuId 格式、version 类型）不满足格式规范时的系统响应未予定义。响应体格式（成功时返回 productId、skus[]、version）也已给出，但错误响应格式未涉及，异常处理行为不完整。；支持度复核：证据显示第3步校验 skus[]、skuId 格式、stock/salePrice/originalPrice/version 等，属接口层校验描述；但未给出具体格式规范或统一错误响应。备选流程仅 A2 定义 salePrice/originalPrice 负数或格式错误返回 INVALID_PRICE，未覆盖 skuId 格式、version 类型等格式违规，也未定义错误响应结构，故仅为上下文而非对“数据不满足格式规范”机制的显式约束。

### GEN-D7CA59C975：查询性能：Read or update Cart records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：大表联查超时

加入购物车流程涉及cart_item表读写（写入字段列表及幂等累加），提供了具体DB上下文，但全文未提任何查询性能、联查超时、索引或性能阈值，'大表联查超时'纯属关注点推导，无显式支撑。备选流程A1-A6均与性能无关。

### GEN-DBEBED3C54：数据类型：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：数据类型与接口定义不符

关注点api.data.type（数据类型与接口定义不符）与API-S-IF1的响应字段结构有交集：证据明确响应体包含page、pageSize、total、products[]及每个商品的productId、productName、categoryId、coverImageUrl、salePrice、originalPrice、stockQuantity、salesCount、status，前端展示结构为productId、name、coverImage、price、originalPrice、stockStatus、salesCount，且A7说明必要字段缺失（product_name、sale_price、cover_image_url为空）时采用缺省值或过滤异常商品。这提供了接口字段级上下文，但未就“数据类型不符”的判定标准、校验位置、响应与恢复方式作任何规定。

### GEN-DED59764CC：唯一性约束：Read or update Category records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：名称重复或唯一键冲突

关注点为internal_database.uniqueness（名称重复或唯一键冲突），目标是Category记录。证据显示发布商品流程会查询category表获取必填属性与发布规则并校验类目规则（A2 CATEGORY_RULE_VIOLATION 409进入审核队列），但Category记录在此流程中被读取用于规则校验，并非被创建或更新，故唯一性约束在该读取路径上不构成失败机制。此外商品唯一性相关约束如version乐观锁（A4 VERSION_CONFLICT 409）属于并发控制而非唯一键。接口路径为POST /api/v1/merchant/products/{productId}/publish，无category写入操作。

### GEN-E4BF289003：数据类型：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：数据类型与接口定义不符

关注点同为api.data.type，但主体为response_payload方向，与API-S-IF1响应字段定义直接相关：证据给出响应体page、pageSize、total、products[]及各商品字段类型化命名（salePrice、originalPrice、stockQuantity、salesCount、status），并说明在线商城系统过滤内部字段后转换为前端展示结构（productId、name、coverImage、price、originalPrice、stockStatus、salesCount），A7涉及必要字段缺失处理。提供了响应结构层面的具体接口上下文，但未规定类型不符（如数值被序列化为字符串、数组类型错误）的检测与响应行为。

### GEN-EE977E6747：数据大小：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：文件或请求体超过限制

Candidate concerns request-body size limit for PUT /api/v1/merchant/products/{productId}/skus. Design detail specifies the exact interface (skus[] per-item fields, version) and parameter validations (skus[] non-empty, stock>=0, price>=0, format legality), and alternate flows cover NEGATIVE_STOCK, INVALID_PRICE, DUPLICATE_SKU, VERSION_CONFLICT, PRODUCT_NOT_FOUND — establishing interface/SSD context but no explicit size or payload-limit constraint or its handling.

### GEN-F628F02B48：权限控制：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：水平越权或垂直越权

Assigned sections describe API-M-IF3 fully (path, parameters, precondition '商品草稿存在且至少定义一个SKU，属于当前商家', step 5 validates product belongs to current merchant, A5 PRODUCT_NOT_FOUND, A4 VERSION_CONFLICT). However, no alternate flow addresses 水平/垂直越权 (horizontal/vertical authorization bypass); the nearest flow is belong-merchant check and generic 403 handling not present in these excerpts. So the failure mechanism (authorization violation) is only generically supported by the ownership precondition, not by an explicit constraint.

### GEN-FF96158501：数据库可用性：Read or update Order records

推荐评分：0.6050；支持度：0.5000；缺失度：0.8500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：连接失败或数据库宕机

Candidate concerns internal_database.availability (connection failure/DB down) while reading or updating order records in order creation. Evidence documents order persistence via OrderService writing order and order_item tables and lists A1–A6 alternates (PRICE_CHANGED, OUT_OF_STOCK, INVALID_ADDRESS, idempotency, CART_EMPTY, PRODUCT_SERVICE_UNAVAILABLE), but no branch describes database outage, connection failure, retry, or degradation for order writes. Only the general persistence context supports the failure locus, so support is moderate; the missing explicit behavior is clear.

### GEN-066A77A957：并发与幂等性：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.6000；支持度：0.7500；缺失度：0.2500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：并发变更产生冲突，或重复请求导致重复变更

Concurrency/idempotency is explicitly covered for LOGI-EVT-01: the requirement branch 3.a states duplicate logistics nodes receive idempotent handling, and the design detail specifies eventId-based idempotency check (step 5, querying logistics_event for an existing eventId) with A4 returning HTTP 200, accepted=true, duplicate=true, and no duplicate write. This is a specific, verifiable constraint supporting the candidate's failure mechanism. The only weak part is the concurrency-conflict half of the trigger; the spec addresses duplicates (idempotency) but not concurrent-write conflicts explicitly.；支持度复核：The candidate concern (service.resource_mutation.concurrency_idempotency) is explicitly constrained for this exact operation. Cited evidence index 2 (design detail basic flow) states step 5 performs an eventId-based idempotency check against logistics_event, and evidence index 3's A4 specifies the concrete outcome: HTTP 200, accepted=true, duplicate=true, no duplicate write. Requirement evidence index 0 branch 3.a also states duplicate logistics nodes get idempotent handling. This directly supports the duplicate/idempotency half of the trigger with a specific verifiable mechanism. The concurrency-conflict half (concurrent writes producing conflicts) is not explicitly addressed with any locking/versioning constraint, so this is not direct — but the idempotency mechanism is a genuine explicit constraint on the same entity (LOGI-EVT-01) and same failure mode, not merely a field-format validation. Hence explicit_constraint=.75, not direct=1.

### GEN-0BA303A669：并发与幂等性：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.6000；支持度：0.7500；缺失度：0.2500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：并发变更产生冲突，或重复请求导致重复变更

Concurrency/idempotency for API-M-IF3 is explicitly specified: the flow uses an optimistic-lock version check on the product (step 5, version consistency), updates version +1 on success, and A4 documents VERSION_CONFLICT with HTTP 409 and the latest version returned for reload. The requirement section likewise lists 4.a 异常场景：商品版本已被其他操作更新 → 提示数据冲突并要求重新加载. This is explicit, verifiable evidence supporting the failure mechanism. Note the design detail's conflict handling is version-based optimistic locking rather than a generalized duplicate-request idempotency mechanism, which narrows the candidate's trigger wording.；支持度复核：Concurrency is explicitly constrained via optimistic locking: step 5 validates version 一致（乐观锁）, step 8 increments version, and A4 defines HTTP 409 VERSION_CONFLICT returning the latest version for reload. The requirement section independently lists 4.a 商品版本已被其他操作更新 → 提示数据冲突并要求重新加载. This directly supports the concurrent-conflict failure mechanism; only the duplicate-request idempotency half of the trigger lacks a documented mechanism.

### GEN-C76431EE89：数据完整性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.6000；支持度：0.7500；缺失度：0.2500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：必填数据缺失或请求体为空

功能设计明确把「必填数据缺失或请求体为空」纳入接口校验：步骤3逐项校验 cartItemIds 非空、addressId 格式合法、confirmedAmount>=0、idempotencyKey 非空，并以 CART_EMPTY 400 等备选流程收口，构成对数据完整性失败机制的显式约束。但候选生成的场景步骤将其归为「异常响应及恢复方式待需求确认」，而这些响应在源章节其实已被写出（400/CART_EMPTY），说明该候选在当前关注点(api.data.completeness)下仍属未经适用性审查的派生项，故支持度给 0.75 而非 1。；支持度复核：The candidate's failure mechanism is '必填数据缺失或请求体为空' (missing required data / empty request body) on POST /api/v1/orders, concern api.data.completeness. Cited evidence index 1 (SEC-43e7b5b4e88ec759, lines 629-640) contains design step 3 that explicitly constrains this exact interface's required-parameter presence: cartItemIds非空、idempotencyKey非空 (plus format/value checks on addressId and confirmedAmount). This is a concrete mechanism-level constraint on the same operation/entity (required fields of the create-order request body), going beyond mere topic or context. It is not direct(1) because the candidate's own scenario_steps/expected_result/recovery state '异常响应及恢复方式待需求确认' (responses and recovery undetermined), while the source section actually specifies concrete error responses (e.g., 400 CART_EMPTY in A5 and 400 INVALID_ADDRESS in A3 for step-3 failures); the derived scenario has not been reconciled/applicability-reviewed against those specified responses, so it is explicit_constraint rather than direct.

### GEN-1004A63E78：数据长度：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：字符串长度超过限制

The concern is api.data.length on the browse GET (API-S-IF1). Evidence explicitly constrains query param ranges (page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice) and lists INVALID_QUERY_PARAM for illegal parameters, providing a concrete validation frame in which an over-length string (e.g., keyword) could be rejected, but no string-length limit is stated and no length-specific error is defined.；支持度复核：The cited evidence explicitly defines parameter validation constraints (page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice, categoryId validity) and lists INVALID_QUERY_PARAM for illegal parameters, establishing a specific operation and validation frame in which an over-length string could be rejected. However, no numeric or string-length bound is stated for any field, nor is any length-specific error code or response defined; the generic parameter-validation context therefore does not explicitly support a string-length overflow mechanism. LEVEL: context.

### GEN-104F862031：数据范围：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：数值超出允许范围

The concern is api.data.range — value out of allowed range on the refund POST. Evidence shows amount validation (requestedAmount>=0, requestedAmount <= refundable amount, REFUND_AMOUNT_EXCEEDED) which supports range checking of monetary values, so the failure mechanism is partially described; however the candidate additionally ties the check to a different endpoint path and no numeric range/boundary constraint for other fields is specified.

### GEN-112683E654：并发与幂等性：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：并发变更产生冲突，或重复请求导致重复变更

The concern is service.resource_mutation.concurrency_idempotency on the shipment POST (API-L-IF1). Evidence shows order-state validation (must be PAID) and order status update to SHIPPED, which is a mutable resource, but no optimistic-lock/version check, idempotency key, or duplicate-request handling is defined for shipments; idempotency in the docs is only described for other use cases via idempotencyKey.

### GEN-1BE6AA7D6A：身份认证：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：无凭证、Token 无效或过期

Candidate asserts authentication failure (no credential, invalid/expired token) when calling GET /api/v1/products. Evidence explicitly states ACT-001 may access anonymously and, if logged in, may carry a valid Authorization Token (precondition), and A1 covers invalid query params but no explicit auth-failure branch is defined for this interface. This creates ambiguity: the interface is designed for anonymous access, so token-invalid/expired handling is not explicitly required here, weakening the candidate's premise.；支持度复核：The candidate asserts an authentication failure (no credential / invalid or expired token) on GET /api/v1/products. The cited evidence only states that ACT-001 may access anonymously and, if logged in, may carry a valid Authorization Token (a precondition, index 0). No branch defines token-invalid/expired handling, and the alternative flows (A1 invalid query params, A2 invalid category, A3 empty result, A4 timeout, A5 service unavailable) never address authorization failure. The evidence establishes a specific interface context but does not state any credential-validation constraint for this endpoint, so it cannot be explicit_constraint.

### GEN-1C6EAA0529：超时关注点：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：延时是否影响需求满足、后续行为执行或系统与环境协调

Candidate asserts a timeout concern on PUT /api/v1/merchant/products/{productId}/skus. Evidence shows validation and alternative flows (negative stock, invalid price, duplicate skuId, version conflict, product not found) but mentions no timeout behavior for this interface. The interface context is specific, giving moderate support that timing may matter, but no evidence describes timeout semantics for API-M-IF3 (timeout is evidenced elsewhere only for other services).

### GEN-31BDD2014D：数据长度：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：字符串长度超过限制

候选针对退款接口 API-R-IF1 请求体字符串长度超限。基本流程第3步只校验 orderId 格式、items[] 非空、reasonCode 合法、requestedAmount>=0、idempotencyKey 非空，未对 reasonDescription/字段长度上限给出任何具体约束，仅有笼统的参数校验语境。b) 备选流程（A1–A5）全是业务规则冲突，无长度校验失败分支。支持仅来自「存在请求参数校验步骤」，机制细节无显式证据。

### GEN-3200C77527：字段合法性：Read or update Cart records

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：类型错误、非法字符或超长

候选位于加入购物车请求校验步骤（步骤3），触发为类型错误/非法字符/超长。基本流程第3步明确校验 productId 和 skuId 格式合法、quantity>=1、idempotencyKey 非空，与「字段合法性」机制直接对应；该接口写入 cart_item 表，字段有效性对持久化成立。被分配章节未给出非法字符/超长时的具体错误码与恢复动作，仅有 INVALID_QUANTITY 等业务冲突分支，故缺失度较高。；支持度复核：The cited evidence (basic flow step 3, alt flows A1–A6) validates specific parameter properties on the add-to-cart interface: productId and skuId format legality, quantity>=1, idempotencyKey non-empty, plus business conflicts (off-sale, out-of-stock, purchase limit, idempotency). This is a specific operation/interface with validation, but it never states a mechanism constraint for type errors, illegal characters, or over-length fields. No length bound, type rule, or field-validity error code/response for cart_item persistence is given — only INVALID_QUANTITY covers quantity<1. The candidate's own branch explicitly defers response and recovery to requirement confirmation. Hence this is interface-level context, not an explicit constraint for the asserted failure mechanism.

### GEN-524CEF92E6：失败恢复：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：发布失败后未恢复或留下半成品状态

候选声称“发布失败后未恢复或留下半成品状态”。证据中有多处失败恢复语义与之相关：A5 记录待同步任务并自动重试（catalogSyncStatus=SYNC_PENDING，且商品状态仍更新为 ON_SALE）、以及 A4 version 不一致返回 VERSION_CONFLICT，说明存在乐观锁与重试机制；这构成对“失败恢复”主题的接口级上下文（0.5）。但这些条款均针对目录同步失败与版本冲突，而非“发布整体失败导致半成品/未回滚”的一般性失败恢复语义；需求侧同样未定义发布失败时的回滚或补偿策略，缺口明显。

### GEN-5A2E65117E：数据范围：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：数值超出允许范围

候选关注 API-S-IF2 请求中“数值超出允许范围”。功能设计显式要求在线商城系统校验 productId 的格式，并在 A1 规定格式错误返回 HTTP 400 INVALID_PRODUCT_ID，这为“请求参数范围校验”提供了明确的接口级约束与响应机制（0.75）。不过所提异常是“数值超出允许范围”，而现有证据仅覆盖格式错误与商品未找到、已下架、服务超时/不可用，并未给出 productId 之外的数值型请求参数范围（如阈值或长度上限）及其错误码；需求侧扩展路径也未覆盖该情形，故异常语义与恢复仍缺失。；支持度复核：证据仅对 productId 的格式校验及 A1 格式错误(HTTP 400 INVALID_PRODUCT_ID)作出约束，涉及的是格式合法性而非数值范围/阈值/长度上限；候选异常为“数值超出允许范围”。虽属同一接口的具体操作(context)，但没有支持该失败机制的显式范围约束或错误码，需求侧扩展路径也仅覆盖商品不存在/已下架/部分信息缺失，故不构成 explicit_constraint。

### GEN-647031FB7B：权限控制：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：水平越权或垂直越权

候选关注 API-O-IF1 请求中的水平/垂直越权。证据中确有访问控制相关内容：基本流程第 2 步校验 Authorization Token 确认顾客身份，且创建订单需校验地址归属当前顾客、订单归属概念在相关用例中出现，构成接口级上下文（0.5）。但创建订单接口自身并未定义越权相关的错误码或拒绝语义；相关的归属校验错误（INVALID_ADDRESS、ORDER_ACCESS_DENIED）分属其他接口（API-O-IF2）。候选的“水平越权或垂直越权”检测与响应在需求与设计中均未明确，属明显缺口。

### GEN-667D2D9853：资源存在性：Read or update OrderItem records

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：查询、修改或删除不存在资源

候选针对支付订单流程中「Read or update OrderItem records」的资源存在性异常（查询、修改或删除不存在资源）。证据仅具体描述了查询 order 表（第4步）与写入 payment 表（第8步），均属支付上下文的具体接口/SSD 上下文，但并未涉及 OrderItem 记录的读取/更新，也未定义资源不存在时的错误码或响应，故仅为上下文相关而非对失败机制的显式约束。

### GEN-6898B2BE77：数据合法性：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：非法字符、不允许字段或非法取值

API-M-IF2 (PUT /api/v1/merchant/products/{productId}) basic flow step 3 explicitly validates request parameter constraints including name non-empty/length-legal, description length-legal, categoryId format legal, imageUrls[] format legal, version non-empty. Alternate flows A2-A5 cover invalid category, invalid image URL/format, version conflict, and product status violations. However, the failure mechanism 'illegal characters, disallowed fields, or illegal values' is not explicitly enumerated; only length, format, and existence constraints are stated. There is no defined error code for illegal characters or disallowed fields. The trigger is therefore partially covered by generic format validation but not explicitly described for the character-level/content-level illegality.

### GEN-741ABFDB7C：权限控制：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：水平越权或垂直越权

场景为支付接口执行时的『水平越权或垂直越权』(human.authorization)。证据确证该支付接口在第2步校验 Authorization Token 确认顾客身份，并在第4步调用 OrderService 查询 order 表校验 order_id/customer_id/status/金额，且错误清单包含权限相关内容（如 ORDER_STATUS_INVALID、AMOUNT_MISMATCH 等）。这构成与授权语义直接相关的具体接口上下文，但仍未出现任何越权检测、资源归属校验失败或权限拒绝的错误码/响应分支。故失败机制本身未被明确描述，支持度中，缺失度偏高。

### GEN-7462BA37EE：数据范围：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：数值超出允许范围

Duplicate of GEN-649EF2E24D with an out-of-range trigger on the same API-M-IF1 request payload. Assigned sections do document request parameter validation (merchantId格式合法、idempotencyKey非空) and alternates A1-A4, giving specific interface context, but show no numeric range constraint or bound for merchantId/idempotencyKey and no error/recovery for a range violation. Support is interface context only; the described behavior is not explicitly described.

### GEN-77AB459B56：数据长度：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：字符串长度超过限制

场景关注请求体的『字符串长度超过限制』(api.data.length)。证据确证加入购物车接口为 POST /api/v1/cart/items，请求体含 productId、skuId、quantity、idempotencyKey，且基本流程第3步明确对请求参数做格式合法性与非空校验，备选流程 A1 给出 quantity 不合法（quantity<1）的错误 A1 INVALID_QUANTITY。这构成请求字段级校验的具体接口上下文，与数据约束条目直接相关。但数值范围校验不等同于字符串长度上限约束，证据中没有任何字段长度上限的定义，也无对应的长度超限错误码或响应分支。支持度中，缺失度高。

### GEN-9FC5EFBC18：数据范围：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：数值超出允许范围

Candidate claims '数值超出允许范围' (numeric out-of-range) at API-L-IF1 (shipment creation). The interface is well specified: request params orderId, carrierCode, trackingNumber, shippedItems[] and explicit validation of trackingNumber format (A2: INVALID_TRACKING_NUMBER, HTTP 400), plus A4 for shippedItems. However, no supplied evidence defines a numeric range constraint or a specific out-of-range value (no quantity boundary, no max length stated for trackingNumber). The closest explicit constraint is 'trackingNumber非空' and '校验 trackingNumber 格式（如长度、字符集、承运商编码规则）', which implies a length bound but does not state a numeric range with a threshold, so the trigger mechanism is only generically supported.

### GEN-A1D8671D23：资源存在性：Read or update SKU records

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：查询、修改或删除不存在资源

Candidate concerns resource existence on SKU records for view-product-detail (API-S-IF2). The design queries only the 'product' table ('ProductCatalogService根据 productId 查询 product 表'), not a 'sku' table; resource-existence handling (query/update/delete nonexistent resource) is explicitly covered for product via A2 (PRODUCT_NOT_FOUND, HTTP 404). The candidate's subject is SKU records, but no SKU read/update/delete is described in this use case, so the specific resource-existence mechanism for SKU has only generic interface context via the sibling PRODUCT_NOT_FOUND branch.

### GEN-A1DA416D3D：字段合法性：Read or update Refund records

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：类型错误、非法字符或超长

Candidate claims '字段合法性：类型错误、非法字符或超长' on Refund records within the query-logistics use case (API-L-IF2). The design for API-L-IF2 queries shipment and logistics_event tables and validates only 'orderId 格式合法'; it never mentions reading or updating Refund records, so the subject node (Refund records) does not appear in the source. Field-validity semantics are therefore at generic interface context: the orderId format check is an analogous legality check but does not cover Refund record fields (type error/illegal chars/over-length). No explicit field-validity constraint for Refund records exists.

### GEN-AFDBE39B08：数据库可用性：Read or update Payment records

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：连接失败或数据库宕机

查看订单详情流程步骤7明确查询 payment 表（payment_id、payment_method、provider_trade_no、payment_status、paid_at），构成对 Payment 记录读取的直接上下文；但 A1–A5 备选流程仅包含 INVALID_ORDER_ID、ORDER_ACCESS_DENIED、ORDER_NOT_FOUND、未发货空摘要、ORDER_SERVICE_TIMEOUT(504)，无任何关于数据库连接失败或宕机的错误码、降级或重试说明，数据库可用性失效机制未被显式定义。

### GEN-BF1265D365：数据大小：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：文件或请求体超过限制

候选关注点为 api.data.size，触发于调用 API-O-IF2（GET /api/v1/orders/{orderId}）时文件或请求体超过限制。证据明确了该接口的路径、请求参数 orderId 与响应结构，但请求为单路径参数、无请求体，证据中也无任何数据大小/体量限制定义或对应错误码，仅有 A1–A5（格式错误、越权、不存在、未发货、超时）。可确认具体接口与 SSD 上下文，但缺少支撑大小超限失效机制的证据。

### GEN-C0C19268A8：数据类型：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：数据类型与接口定义不符

候选关注点为 api.data.type，触发于调用 API-R-IF1 申请退款时数据类型与接口定义不符。证据包含请求体字段清单（orderId、items[]、reasonCode、reasonDescription、requestedAmount、idempotencyKey）及基本流程中的参数合法性校验，但 A1–A5 备选流程仅覆盖退款期限、金额超限、状态不符、PaymentService 不可用与幂等重复，未定义数据类型不符的判定或错误响应，且存在 SR 接口路径（/api/v1/refunds）与摘要中路径（/api/v1/orders/{orderId}/refunds）不一致之处。

### GEN-C0F5765232：数据类型：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：数据类型与接口定义不符

候选关注点为 api.data.type，触发于调用 API-L-IF2（GET /api/v1/orders/{orderId}/logistics）时数据类型与接口定义不符。证据明确了接口路径、响应结构（trackingNumber、status、events[]、lastUpdatedAt、dataSource）及事件字段（event_code、event_time、location），但 A1–A5 备选流程覆盖未发货、数据不存在、外部查询失败、已签收与适配器不可用，未涉及数据类型不符合定义的处理。属具体接口上下文，但无失效机制的直接证据。

### GEN-C20ED2EB65：并发一致性：Read or update Order records

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：并发更新冲突或后写覆盖前写

候选关注点为 internal_database.concurrency_consistency，触发于「Read or update Order records」并发更新冲突或后写覆盖前写。证据显示 OrderService 按 idempotencyKey 执行幂等校验后写入 order 表与 order_item 表，A4 覆盖 idempotencyKey 重复返回已有订单，但这是幂等语义而非并发更新冲突（如乐观锁/版本号/丢失更新）的处理规则，证据中无并发控制机制或冲突响应的明确描述。可确认涉及 Order 记录读写，但缺少并发一致性失效的直接支撑。

### GEN-C2170B9421：并发一致性：Read or update LogisticsEvent records

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：并发更新冲突或后写覆盖前写

候选关注点为 internal_database.concurrency_consistency，触发于「Read or update LogisticsEvent records」并发更新冲突或后写覆盖前写。证据中适配器按 eventId 执行幂等校验（A4 重复事件返回 duplicate=true 不重复写入），并更新 shipment 摘要字段，但幂等去重与并发写冲突（如并行事件导致的丢失更新或写偏序）并非同一机制；A3 仅处理 eventTime 乱序返回错误码，未定义并发一致性策略。可确认 LogisticsEvent 读写上下文，但无并发一致性的直接证据。

### GEN-C31A3EE6A4：数据格式：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：数据不满足格式规范

候选关注点为 api.data.format，触发于调用 API-L-IF1 商家发货时数据不满足格式规范。证据中基本流程第 6 步包含 OrderService 校验 trackingNumber 格式（长度、字符集、承运商编码规则），A2 定义格式非法返回 HTTP 400 INVALID_TRACKING_NUMBER，与关注点在语义上相关；但候选触发点表述为整个接口「数据不满足格式规范」，而证据仅覆盖物流单号单项格式，未对请求体其他字段（carrierCode、shippedItems[]）定义格式规范，且存在 SR 摘要路径/参数（carrier、trackingNo）与设计用例（carrierCode、trackingNumber）不一致。

### GEN-C582C81F8D：数据格式：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：数据不满足格式规范

设置库存与价格基本流程第3步显式校验请求参数格式（skus[]非空、skuId格式合法、stock>=0、salePrice>=0、originalPrice>=0、version非空），备选A1/A2给出NEGATIVE_STOCK、INVALID_PRICE，与'数据不满足格式规范'的API请求格式异常直接相关；但候选把检查点放在调用API-M-IF3的步骤上并要求'异常响应及恢复方式待需求确认'，而来源已给出具体校验与错误码，属未消解的重复/泛化，支持中等、缺失较高。

### GEN-C5D6D1ECB7：数据合法性：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：非法字符、不允许字段或非法取值

同一用例的响应侧校验在证据中有体现：A1负数库存、A2非法价格、A3重复skuId、A4版本冲突返回特定错误码，与'非法字符、不允许字段或非法取值'的合法性主题相关；但候选定位在'调用API-M-IF3'的响应载荷合法性，来源未描述响应体字段级合法性规则（仅请求校验与业务错误码），支持中等、缺失较高。

### GEN-C768757F0D：数据格式：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：数据不满足格式规范

查询物流信息基本流程第3步校验orderId格式合法、第7步读取logistics_event表事件节点，备选A2给出LOGISTICS_NOT_FOUND，与物流查询请求参数/数据格式主题相关；但候选把'数据不满足格式规范'置于调用API-L-IF2的检查点上，而来源给出的错误集为ORDER_NOT_SHIPPED、LOGISTICS_NOT_FOUND、LOGISTICS_SERVICE_UNAVAILABLE等，未明确请求格式违规的具体响应，支持中等、缺失较高。

### GEN-CAF11D090A：数据合法性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：非法字符、不允许字段或非法取值

发布商品章节含明确的参数校验步骤（version非空、publishAt格式合法）和响应体规格（productId、status、publishedAt、catalogSyncStatus），构成响应数据合法性话题的表面上下文；但无任何非法字符、不允许字段或非法取值校验规则及对应错误码被描述，失败机制证据缺失。

### GEN-D218F18258：数据类型：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数据类型与接口定义不符

创建订单的 API-O-IF1 接口定义（方法/路径、请求/响应字段）在给定章节中有详尽描述，且基本流程明确校验请求参数（cartItemIds/addressId/confirmedAmount/idempotencyKey），这为数据类型校验失败提供了上下文。但虽然基础流程要求校验字段格式（如 confirmedAmount>=0），备选流程 A1-A6 均只覆盖 PRICE_CHANGED、OUT_OF_STOCK、INVALID_ADDRESS、重复幂等键、CART_EMPTY、服务不可用，未定义请求体数据类型与接口定义不符（如字段类型错误/未知字段）时的系统响应、错误码或恢复方式。因此该异常行为在分配源章节中无明确描述，支撑度仅为具体接口上下文。

### GEN-D4B995F12C：数据合法性：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：非法字符、不允许字段或非法取值

接口存在且有参数校验点：步骤3「校验 orderId 格式合法」，备选流程 A1 给出 orderId 格式错误时的 INVALID_ORDER_ID/400。但候选触发条件为「非法字符、不允许字段或非法取值」，属于对请求体的泛化数据合法性关注点，源章节只描述了路径参数 orderId 的格式校验，未描述非法字符/不允许字段/非法取值的具体判定，也未给出该关注点下的响应与恢复，故支持度取中、缺失度较高。

### GEN-DDF5AD355C：数据合法性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5900；支持度：0.5000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：非法字符、不允许字段或非法取值

响应侧确有显式约束：步骤6 规定「过滤内部字段并转换为前端结构」，响应包含 productId、name、description、images[]、price、originalPrice、stockStatus、salesCount，备选流程 A6 规定缺失非关键字段的隐藏/缺省处理。但候选触发「非法字符、不允许字段或非法取值」针对响应载荷的数据合法性，源章节只描述了内部字段过滤与字段缺失降级，未界定响应字段的非法字符/非法取值，也未给出对应错误码，故支持度取中、缺失度较高。

### GEN-0B3F37F4F7：数据完整性：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5850；支持度：0.7500；缺失度：0.2000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：必填数据缺失或请求体为空

Candidate is an API data-completeness exception ('必填数据缺失或请求体为空') on LOGI-EVT-01 POST /api/v1/logistics/events. The assigned detail flow explicitly enumerates required request fields (eventId、trackingNumber、eventCode、eventTime、location、signature) and includes a specific alternative (A5) rejecting illegal eventCode with HTTP 400 INVALID_EVENT_CODE, plus validation of signature and trackingNumber. This explicit constraint supports the missing/empty-body failure mechanism (0.75). Missingness is low: input validation is well described, though a bare empty-body case and its error code are not stated verbatim, leaving that one residual gap.；支持度复核：The flow enumerates the mandatory request body fields (eventId、trackingNumber、eventCode、eventTime、location、signature) and shows validation rejecting malformed field content with HTTP 400, establishing that request-body field validation is a specified constraint on this operation. However, no error path is defined for a wholly empty body or missing required field, so the exact '必填数据缺失或请求体为空' mechanism is covered only by analogy, not verbatim — supporting rather than proving it.

### GEN-4D900C8F7C：数据范围：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.5850；支持度：0.7500；缺失度：0.2000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：数值超出允许范围

API-M-IF3 的分支流程明确给出数值越界约束：stock 为负数返回 NEGATIVE_STOCK，salePrice/originalPrice 非法返回 INVALID_PRICE，属于对所提「数值超出允许范围」的直接机制支持；触发点在 API-M-IF3 调用处，与 cand 定位一致。但候选仍未明确「允许范围」的统一上界/下界以及异常响应与恢复策略（候选自述为待需求确认），因此支持度略低于 1。；支持度复核：Concern is api.data.range (inventory/price numeric out of allowed range) at API-M-IF3. The alternatives list directly constrains numeric ranges: stock negative -> NEGATIVE_STOCK, and A2 salePrice/originalPrice illegal (negative or malformed) -> INVALID_PRICE. This is a concrete mechanism constraint on THIS payload entity (stock/price) and error mapping, not merely topic/context. It is explicit_constraint rather than direct because the exact allowed upper/lower bounds are not enumerated and the candidate's own response/recovery is deferred to requirement confirmation.

### GEN-5563DF48D0：数据合法性：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5850；支持度：0.7500；缺失度：0.2000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：非法字符、不允许字段或非法取值

LOGI-EVT-01 分支流程有明确合法性校验：signature 非法返回 INVALID_SIGNATURE，eventCode 不在允许事件编码范围返回 INVALID_EVENT_CODE，与 api.data.legality 关注点直接对应。候选的「非法字符、不允许字段或非法取值」在该章节可被验证为确实有约束。但候选标注的 concern_subject=response_payload 与源章节的校验多发生在请求入参侧，语义略显错位；且候选未确定恢复策略。；支持度复核：Concern is api.data.legality (illegal characters/fields/values) at LOGI-EVT-01. A1 (signature invalid -> INVALID_SIGNATURE) and especially A5 (eventCode outside allowed event-code range -> INVALID_EVENT_CODE) constrain illegal values for this interface with explicit codes. It counts as explicit_constraint, not direct, because the specific 'illegal character / disallowed field' enumeration and recovery handling are not fully specified, and the candidate's stated concern_subject=response_payload slightly mismatches the mostly request-side validation.

### GEN-5C083761AD：业务约束：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5850；支持度：0.7500；缺失度：0.2000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：当前业务条件不满足变更要求

PAYMENT-PAY-01 分支流程给出与业务条件不满足变更要求高度对应的约束：A1 订单状态不是 WAIT_PAY 返回 409 ORDER_STATUS_INVALID（对应前提前置已声明订单状态须为 WAIT_PAY）；A2 金额不一致返回 400 AMOUNT_MISMATCH。这些是可验证的 service.resource_mutation.business_constraint。缺失点在于候选触发点位于第 3 步「系统校验订单状态和应付金额」，标准流程第 3 步为参数校验、第 4 步才是 state/amount 校验，步骤编号存在轻微错位；且候选将响应/恢复归为待确认。；支持度复核：Concern is service.resource_mutation.business_constraint at PAYMENT-PAY-01. Alternatives A1 (order not WAIT_PAY -> ORDER_STATUS_INVALID) and A2 (amount mismatch -> AMOUNT_MISMATCH) directly constrain the business precondition for changing order state. It is explicit_constraint rather than direct because these B-alternatives validate request/state conditions rather than naming a single named failure element matching the vague trigger 'current business condition not satisfied', and the response/recovery is left as TBD.

### GEN-5C5A3FF406：数据完整性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.5850；支持度：0.7500；缺失度：0.2000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：必填数据缺失或请求体为空

API-M-IF4 备选流程 A1 明确覆盖「商品资料不完整」返回 409 PRODUCT_INCOMPLETE 并附缺失字段列表，直接支持 api.data.completeness 关注点。但候选触发的是 API-M-IF4 请求体本身为空/必填缺失，而源章节 A1 描述更偏向商品业务资料（name/description/image/SKU）维度；同时源章节未定义请求体为空时应返回的具体错误码，故缺失度不为 0。；支持度复核：Concern is api.data.completeness at API-M-IF4. A1 explicitly constrains incomplete product data (missing name/description/image/SKU) with PRODUCT_INCOMPLETE and a missing-field list, supporting the completeness mechanism. It is explicit_constraint not direct because the source frames incompleteness around business product data (name/description/image/SKU) rather than an empty/absent request body as literally triggered, and no error code is defined specifically for an empty request body.

### GEN-9FCFD67BBA：图片格式或大小不符合要求。

推荐评分：0.5850；支持度：0.7500；缺失度：0.2000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 3

建议补充：图片格式或大小不符合要求。

需求扩展路径 3.a 描述“图片格式或大小不符合要求→系统拒绝对应图片并显示限制条件”，功能设计备选流程 A3 明确失败机制：图片URL格式不合法或数量超限返回 INVALID_IMAGE。但需求侧仅提及格式/大小，设计侧校验的是URL格式与数量，二者语义存在轻微不一致，故缺失分略高。；支持度复核：需求 3.a 触发为“图片格式或大小不符合要求”，设计 A3 的机制覆盖图片URL格式与数量超限，核心实体与失败类别（非法图片输入被拒绝）一致并给出显式错误码 INVALID_IMAGE。差异仅在“大小”未在 A3 中重述，属细节缺口而非机制错配，故为 explicit_constraint。

### GEN-A94A4EE310：超时关注点：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5850；支持度：0.7500；缺失度：0.2000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：延时是否影响需求满足、后续行为执行或系统与环境协调

Timeout exception for API-S-IF2 is explicitly described: A4 states ProductCatalogService query timeout returns HTTP 504 Gateway Timeout with error code PRODUCT_SERVICE_TIMEOUT, and A5 covers service unavailability with 503. The trigger ('延时是否影响需求满足') maps directly to this documented timeout branch, so the failure mechanism and system response are concretely supported. The candidate's expected_result/recovery fields say '待需求确认', which conflicts with the explicit A4 response; the residual gap is that the candidate frames this as an open requirement while the design section already defines the response, and no retry/timeout threshold is specified.；支持度复核：The candidate is a timeout concern on API-S-IF2 (GET /api/v1/products/{productId}). Cited_evidence[2] explicitly defines the timeout branch for this exact interface and service (ProductCatalogService query timeout → HTTP 504 PRODUCT_SERVICE_TIMEOUT), and evidence[1] confirms the same interface's call flow (step 3: 在线商城系统调用ProductCatalogService的商品详情读取能力). This is a documented mechanism constraint with a concrete response, so it merits explicit_constraint (0.75), not direct, because the candidate's trigger is a generic '延时是否影响需求满足' framing with expected_result/recovery left '待需求确认' — it does not itself assert the specific timeout entity, and no retry/threshold is specified.

### GEN-DAA8D90358：收到重复物流节点。

推荐评分：0.5850；支持度：0.7500；缺失度：0.2000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 3

建议补充：收到重复物流节点。

需求扩展路径 3.a 描述“收到重复物流节点→系统进行幂等处理”，功能设计备选流程 A4 给出可验证机制：eventId 已存在时返回 HTTP 200，accepted=true、duplicate=true 且不重复写入。两处一致；轻微缺失在于候选步骤列表未直接给出 duplicate 标志语义，但机制本身已被显式描述。；支持度复核：需求 3.a 收到重复物流节点→幂等处理，设计 A4 对 eventId 重复这一同一幂等机制显式给出 HTTP 200、accepted=true、duplicate=true 且不重复写入，机制与候选期望一致，属显式约束；该约束证明的是幂等去重，非 DB 唯一键错误，与候选语义吻合。

### GEN-39D15BC889：并发与幂等性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5800；支持度：0.7000；缺失度：0.3000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：并发变更产生冲突，或重复请求导致重复变更

Candidate concerns concurrency and idempotency on PAYMENT-PAY-01. Sources explicitly specify idempotency handling: idempotencyKey duplication returns the existing payment without reprocessing (A5) and callback notifications are processed idempotently by paymentId (A6). This is an explicit, verifiable constraint on the duplicate-request/duplicate-update part; concurrent-conflict specifics remain unaddressed.

### GEN-03B4583D2B：数据完整性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：必填数据缺失或请求体为空

The candidate asserts a request-payload completeness exception on API-S-IF2 (必填数据缺失或请求体为空). The assigned evidence defines API-S-IF2 with the sole request parameter productId and enumerates alternatives A1-A6 (INVALID_PRODUCT_ID, PRODUCT_NOT_FOUND, PRODUCT_OFF_SHELF, PRODUCT_SERVICE_TIMEOUT, PRODUCT_SERVICE_UNAVAILABLE, missing non-critical display fields). No alternative covers a missing/empty request body, so only generic interface context supports the candidate. The requirement section lists 2.a 商品不存在 and 2.b 商品已下架 but nothing about payload completeness, making this behavior not explicitly described.

### GEN-0E90856B11：数据大小：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：文件或请求体超过限制

The candidate asserts a data-size exception (file or request body over limit) on the API-S-IF2 response. The API is a GET with only productId as request and returns product/detail fields including images[]; the design detail enumerates A1-A6 and none addresses a size limit, and the requirement section's extensions cover nonexistent, off-shelf, and missing non-critical display fields, not size. Only the general interface context (GET product detail returning images[] and a large description) provides weak topical support; the specific failure mechanism is not described.

### GEN-1559FF16D9：身份认证：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：无凭证、Token 无效或过期

认证失效异常被挂到退款接口调用上，但退款接口的设计证据只描述了正常校验 Authorization Token（步骤2），以及业务类备选流程（退款期限、金额、订单状态、PaymentService不可用、幂等重复），没有任何 401/凭证无效/Token 过期的错误码或恢复策略。因此仅有具体接口与步骤上下文支持该失败机制的存在性，缺乏明确约束。

### GEN-2940C9864A：身份认证：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：无凭证、Token 无效或过期

Concern 'human.authentication' (无凭证/Token 无效或过期) for the merchant-shipping path. Evidence explicitly states the request carries a valid Authorization Token and step 2 validates it, and A5 defines PERMISSION_DENIED for missing order-handling permission, giving specific interface context; however no expired/invalid-token response (e.g., 401) is specified for this API.

### GEN-34CFF8E551：数据格式：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：数据不满足格式规范

关注点为 api.data.format。证据明确列出 POST /payment/v1/payments 的请求参数并定义了基本校验（orderId 格式合法、amount>=0、paymentMethod 合法、notifyUrl 非空、idempotencyKey 非空），说明存在格式约束的接口上下文；但未定义格式不满足时的具体响应码或恢复策略，备选流程仅覆盖状态非法、金额不一致、服务不可用、取消、幂等重复，因此该异常处理缺失。

### GEN-388FDB168B：字段合法性：Read or update LogisticsEvent records

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：类型错误、非法字符或超长

关注点为 internal_database.field_validity（类型错误、非法字符或超长）。证据显示 LOGI-EVT-01 含 eventCode、eventTime、location 等字段校验：A3 定义 eventTime 不合理返回 400 INVALID_EVENT_TIME，A5 定义 eventCode 非法返回 400 INVALID_EVENT_CODE，构成字段合法性接口上下文；但未定义类型错误、非法字符、超长（长度上限）的处理及恢复策略，写入 logistics_event 表时也无字段合法性约束说明，故缺失度较高。

### GEN-5C220A24AF：数据类型：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：数据类型与接口定义不符

Candidate targets api.data.type on POST /api/v1/cart/items. Evidence supplies explicit interface context: request fields productId, skuId, quantity, idempotencyKey (375-382) and step 3 validating productId/skuId 格式合法、quantity>=1、idempotencyKey非空 (583), plus A1 INVALID_QUANTITY for quantity<1 (593). This is type/format-adjacent validation, but no explicit statement that a type mismatch with the interface definition is rejected, constrains the failure mechanism, or defines response/recovery; the specific type-mismatch scenario is under-specified.

### GEN-67053C4136：数据完整性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：必填数据缺失或请求体为空

候选针对调用 API-C-IF1（POST /api/v1/cart/items）请求体中必填数据缺失或请求体为空的数据完整性异常（关注点 api.data.completeness，payload_direction=request）。证据第1步列出请求体字段 productId、skuId、quantity、idempotencyKey，第3步明确「校验请求参数：productId和skuId格式合法、quantity>=1、idempotencyKey非空」，属具体接口层面的参数完整性校验上下文；但未将「请求体为空」这一情形单独定义，备选流程亦无对应错误码（仅 INVALID_QUANTITY 针对 quantity<1），故该异常的完整响应仍缺失。

### GEN-793EC23E15：数据合法性：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：非法字符、不允许字段或非法取值

Concern api.data.legality on API-M-IF3 PUT /api/v1/merchant/products/{productId}/skus. Evidence explicitly defines request validation: step 3 checks skus[] non-empty, skuId format, stock>=0, salePrice>=0, originalPrice>=0, version non-empty, and step 6/SKU checks (no duplicate skuId). This directly addresses illegal chars / disallowed fields / illegal values at the API boundary, giving concrete support. However the candidate's specific framing ('非法字符、不允许字段') is broader than the evidenced constraints (numeric ranges, duplicate skuId), and the candidate's expected_result/recovery is '待需求确认' though the design already lists alternative flows with HTTP 400/409 codes (NEGATIVE_STOCK, INVALID_PRICE, DUPLICATE_SKU, VERSION_CONFLICT). Missing is moderately high because the generic illegal-character/disallowed-field case is not explicitly enumerated, though recovery is documented.

### GEN-7CC14B6B29：数据类型：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：数据类型与接口定义不符

Concern api.data.type on API-M-IF3 PUT /api/v1/merchant/products/{productId}/skus. Same interface context as GEN-793EC23E15: step 3 checks skuId format, stock>=0, salePrice>=0, originalPrice>=0, version non-empty. No rule states a data-type mismatch (e.g., string where number expected) or defines its response; documented alternatives concern negative stock, invalid price values, duplicate skuId, version conflict, product not found. Support is interface context (.5); the type-mismatch failure mechanism and recovery remain undescribed (missing high), though slightly less than the legality case because numeric/format validation partially implies type checks.

### GEN-80245B2409：持久化能力：Read or update OrderItem records

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：写入失败或事务回滚

Candidate asserts persistence failure/transaction rollback on OrderItem records during payment. Assigned sections describe writes to payment and order tables and error handling for A1-A6 (lines 679-701) but contain no statement about write failure, transaction rollback, retry or persistence guarantees for OrderItem, nor any recovery policy. Support is limited to the same-operation interface context; the failure mechanism is not explicitly described and is in fact absent.

### GEN-80F0F4DF70：关联一致性：Read or update Category records

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：级联删除失效或子对象残留

Concern internal_database.referential_consistency (cascading delete failure or orphaned child objects) attached to 'Read or update Category records' within publish flow. Assigned sections do show the publish flow reading the category table for required attributes and rules (step 7) and its rule-violation handling (A2 CATEGORY_RULE_VIOLATION), giving specific context for the referenced category access; however, no cascade-delete or child-residual behavior, referential constraint or integrity error is described anywhere, so the failure mechanism itself is undocumented.

### GEN-9736014C36：数据长度：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：字符串长度超过限制

Candidate claims string length exceeding limit on LOGI-EVT-01 (POST /api/v1/logistics/events). The spec explicitly validates signature, trackingNumber existence, eventTime reasonableness and eventId idempotency (A1-A5), and request fields include trackingNumber/location/signature, giving specific interface context for length constraints. However, no explicit length constraint or error code for oversized strings exists in the cited sections, so the failure mechanism is not directly supported and the expected response remains 待需求确认.

### GEN-97BD90F9BA：数据格式：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数据不满足格式规范

Candidate claims data format noncompliance on API-O-IF1 (POST /api/v1/orders). The spec explicitly validates request parameters (cartItemIds非空、addressId格式合法、confirmedAmount>=0、idempotencyKey非空) at step 3, which is a format-validation context. But no alternative flow explicitly addresses generic format violations; A1-A6 cover price change, out-of-stock, invalid address, duplicate key, empty cart and service unavailability, none matching 'data format spec violation' generally, so the specific expected response/recovery is undescribed.

### GEN-98E2F204CD：数据大小：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：文件或请求体超过限制

Candidate claims file or request body size exceeding limits on LOGI-EVT-01. The spec enumerates request fields (eventId, trackingNumber, eventCode, eventTime, location, signature) and validations, providing specific interface context, but no size/body-limit constraint or error code is described anywhere in the cited alternatives (A1-A5) or the V5 call chain, so the failure mechanism is unsupported and the expected response is 待需求确认.

### GEN-98F6281E82：数据大小：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：文件或请求体超过限制

Candidate claims file/request-body size exceeding limits on API-M-IF2. The spec validates image URL format and count (step 7; A3 INVALID_IMAGE) and mentions imageUrls[] with 数量在允许范围内, which is loosely related to size constraints, but no explicit body-size or file-size limit or corresponding error code exists in the cited sections. The image-count constraint is the nearest relevant mechanism; the claimed failure mode remains undescribed and recovery unspecified.

### GEN-A384331BF8：数据完整性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：必填数据缺失或请求体为空

Candidate claims '数据完整性：必填数据缺失或请求体为空' on API-C-IF1 (POST /api/v1/cart/items, response direction). The design validates 'productId和skuId格式合法、quantity>=1、idempotencyKey非空', which supports non-empty required fields (idempotencyKey非空) and value constraints (quantity>=1 with A1: INVALID_QUANTITY). However, there is no explicit branch for a completely empty request body or for missing required data as a distinct completeness failure; quantity<1 is treated as an invalid-value case, not as completeness. So the completeness mechanism is generic; a specific empty-body constraint is absent.

### GEN-C4D9F57F38：查询性能：Read or update Payment records

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：大表联查超时

查看订单详情备选流程A5明确OrderService查询超时返回504 ORDER_SERVICE_TIMEOUT，基本流程第7步查payment表，与'Payment records查询性能'主题直接相关；但候选触发条件表述为'大表联查超时'，来源中只给出服务查询超时，未描述联查规模、超时阈值或任何性能约束，因此支持为中等、缺失较明显。

### GEN-C679E18DAD：资源存在性：Read or update Shipment records

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：查询、修改或删除不存在资源

商家发货基本流程第7步写入shipment表、第4步查询order表，备选A1给出ORDER_STATUS_INVALID，与Shipment记录读写相关；但来源已通过订单状态、权限、shippedItems归属等前置校验覆盖了不存在/不合法资源的主要场景，候选提出的'查询、修改或删除不存在资源'的具体机制（如404语义）在证据中未直接表述，支持中等、缺失中高。

### GEN-C7D76AAAF5：身份认证：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：无凭证、Token 无效或过期

发布商品流程明确绑定接口 POST /api/v1/merchant/products/{productId}/publish 并列出 Authorization Token 校验步骤和前置条件，提供身份相关 SSD 上下文；但备选流程 A1-A5 均未描述无凭证/Token 无效或过期的失败分支，认证失败机制在给定章节中未被明示。

### GEN-CB57E74916：数据大小：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：文件或请求体超过限制

查询物流信息章节定义响应体包含 trackingNumber、status、events[]、lastUpdatedAt、dataSource，并含外部查询失败降级为 CACHE 的备选流程，与响应载荷大小话题相关；但无文件或请求体大小限制、阈值或超限响应的任何规定。

### GEN-CC191D6F91：持久化一致性：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：操作结果未可靠持久化或局部成功

申请退款流程描述对 refund 表的写入（含 refund_id、status、created_at 等字段）、idempotencyKey 幂等校验与 PaymentService 调用，涉及持久化主题；但备选流程仅覆盖时限、金额、状态、PaymentService 不可用与幂等重复，未描述写入未可靠持久化或局部成功的失败机制及补偿方式。

### GEN-DB80CDDFA5：权限控制：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：水平越权或垂直越权

查询物流流程第4步调用OrderService校验订单归属与状态，属授权/归属校验上下文，间接支撑越权失败机制。但文档未定义水平/垂直越权检测及对应响应（无403/授权错误码），仅有A1未发货409、A5服务不可用503，故仅部分支撑。

### GEN-E4EBEAB4E2：数据范围：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：数值超出允许范围

候选针对API-R-IF1的api.data.range异常（数值超出允许范围）。证据中确有明确的数值约束：requestedAmount>=0（基本流程第3步）、requestedAmount <= 可退款金额（第7步）、A2备选流程退款金额超过可退款金额返回HTTP 409 REFUND_AMOUNT_EXCEEDED。这些约束确实支持“数值范围越界”的失败机制，故支持度取中上。但候选的source_location与target_sections将该步骤锚定在功能设计Delta_spec.md:API-R-IF1（line 431-438），该段落仅列出关键请求参数，未给出范围约束；同时候选场景步骤与行文采用另一路径POST /api/v1/orders/{orderId}/refunds，而功能设计详情段落使用POST /api/v1/refunds，存在文档内接口不一致，无法在该锚点直接验证该异常行为。

### GEN-E637EE2685：显示正确性：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：展示内容与业务结果不一致

候选针对API-S-IF1的service.display_interaction.display_correctness（展示内容与业务结果不一致）。证据给出浏览商品接口的完整响应结构与逐层转换：ProductCatalogService返回products[]（含productId、productName…status），再由商城转换为前端展示结构items[]（productId、name、coverImage、price、originalPrice、stockStatus、salesCount），并有A6“返回结果前过滤失效商品”与A7“必要字段缺失时采用缺省值或过滤”。这些都是与展示正确性直接相关的具体上下文，但没有任何一条把“展示内容与业务结果不一致”作为异常/约束写出，故支持度中等。缺失度高：目标锚点（line 359-366）仅为接口摘要，无展示一致性约束，异常响应与恢复均为待确认。

### GEN-F4C6A9A661：数据类型：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：数据类型与接口定义不符

API-O-IF2 关键响应列出 orderId、status、items[]、amountSummary、paymentSummary、shipmentSummary，流程第5-8步描述了从 order/order_item/payment/shipment 表组装响应的字段级来源，提供了响应字段的具体接口上下文；但备选流程 A1-A5 仅覆盖 orderId 格式错、越权、不存在、未发货、查询超时，未定义「数据类型与接口定义不符」的错误码或响应，故该异常的具体语义与恢复策略未描述。

### GEN-F56ADD8C97：数据大小：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：文件或请求体超过限制

PAYMENT-PAY-01 流程第3步明确校验 orderId 格式、amount>=0、paymentMethod 合法、notifyUrl 非空、idempotencyKey 非空，请求体字段有具体定义，构成请求体结构的具体接口上下文；但备选流程 A1-A6 覆盖状态非法、金额不符、服务不可用、取消、幂等，未定义任何「请求体/文件超过大小限制」的阈值或错误码，故该异常响应与恢复未描述。

### GEN-F5BAC8C3F4：结果正确性：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：查询结果错误、遗漏或分页重复

API-O-IF2 流程第5-9步具体描述响应由 order、order_item、payment、shipment 四表组合而成，并定义 items[]、amountSummary、paymentSummary、shipmentSummary 的字段构成，提供了结果正确性（组合与完整性）的接口级上下文；但备选流程 A1-A5 未定义结果错误、遗漏、分页重复的错误码或校验方式，且该接口为单订单详情查询、无分页语义，故该异常的具体判定与恢复未描述。

### GEN-F62525FA8C：数据类型：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数据类型与接口定义不符

API-O-IF1 流程第1、3步明确请求体包含 cartItemIds、addressId、couponId、idempotencyKey、confirmedAmount，并对各字段做非空/格式/>=0 校验，构成请求数据类型的具体接口上下文；但备选流程 A1-A6 覆盖价格变动、库存不足、地址无效、幂等重复、购物车为空、服务不可用，未定义「数据类型与接口定义不符」的错误码或响应，故该异常响应与恢复策略未描述。

### GEN-F9C097B077：数据范围：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数值超出允许范围

Request parameters and validations are documented (cartItemIds非空, addressId格式合法, confirmedAmount>=0, idempotencyKey非空; A flows). confirmedAmount>=0 gives explicit range constraint on an amount, supporting an 'out-of-range numeric' failure. But the evidence does not specify an upper bound for amounts, so exceeding the allowed range is only partially constrained.

### GEN-FA900161EC：必填字段完整性：Read or update Cart records

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：必要字段缺失

Cart item write fields and validations are explicit (productId/skuId格式合法, quantity>=1, idempotencyKey非空; cart_item fields list). Preconditions require an authenticated customer. This supplies concrete interface/field context, but the candidate's failure mechanism '必要字段缺失' on Cart records is only implied by step 3 parameter checks; no explicit DB-level required-field rule for cart_item is stated.

### GEN-FD8C23DF6E：数据完整性：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：必填数据缺失或请求体为空

Candidate concerns api.data.completeness (missing required data or empty request body) on PUT /api/v1/merchant/products/{productId}/skus. Evidence explicitly describes required request body fields (skus[] with skuId/attributes/stock/salePrice/originalPrice plus version) and step 3 validates skus[] non-empty, skuId format, stock>=0, price>=0, version non-empty. However the listed 备选流程 A1–A5 cover NEGATIVE_STOCK, INVALID_PRICE, DUPLICATE_SKU, VERSION_CONFLICT and PRODUCT_NOT_FOUND only — no explicit branch for missing required fields/empty body or its error code/HTTP status. So the validation intent is documented but the specific exception response and recovery are genuinely absent, matching the candidate's 待需求确认 placeholder.；支持度复核：The evidence documents the PUT /api/v1/merchant/products/{productId}/skus operation and lists required body fields skus[] (skuId/attributes/stock/salePrice/originalPrice) and version, and step 3 states validation rules (skus[]非空、stock>=0、salePrice>=0、version非空). However, these validations are normal-flow field rules and alternate flows A1–A5 cover NEGATIVE_STOCK, INVALID_PRICE, DUPLICATE_SKU, VERSION_CONFLICT and PRODUCT_NOT_FOUND only. No explicit constraint prescribes the response (HTTP status/error code) or recovery for the candidate's specific trigger '必填数据缺失或请求体为空'; the exception response and recovery are genuinely 待需求确认. This is a specific interface/topic context, not an explicit_constraint for the missing-data/empty-body failure path.

### GEN-FE41FAD06A：字段合法性：Read or update Category records

推荐评分：0.5750；支持度：0.5000；缺失度：0.7500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：类型错误、非法字符或超长

候选围绕类目记录读写中的字段合法性（类型错误、非法字符、超长）。证据中确有与 Category 记录相关的语义活动：发布流程第 7 步查询 category 表获取分类必填属性与发布规则并校验商品是否满足类目要求（1087-1098），以及类目规则不符时返回 CATEGORY_RULE_VIOLATION 并进入审核队列（1099-1109）。但该接口的显式参数校验仅覆盖 version 非空、publishAt 格式（1087-1098），类目记录的字段类型/字符/长度约束及对应错误码、恢复方式均未描述，缺失度高。

### GEN-64CDB603C5：商品目录索引刷新失败。

推荐评分：0.5700；支持度：0.7500；缺失度：0.1500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 5

建议补充：商品目录索引刷新失败。

该场景是唯一的 requirement_exception 显式分支：「5.a 商品目录索引刷新失败 → 系统记录待同步任务并自动重试」，并被 API-M-IF4 备选 A5 具体化为 ProductCatalogService 同步失败记录待同步任务、自动重试、catalogSyncStatus=SYNC_PENDING、商品状态仍为 ON_SALE，属可直接验证的显式约束。缺失度低，理由为前置/后置条件标注「未单独描述」以及重试次数/退避策略未定义。；支持度复核：This requirement_exception branch is '商品目录索引刷新失败' with expected result '记录待同步任务并自动重试'. Design alternative A5 specifies exactly this failure (ProductCatalogService sync failure), the recovery mechanism (record pending-sync task, auto-retry), and the resulting state (SYNC_PENDING, product still ON_SALE), matching trigger and expected_result. Direct because the evidence specifies the same failure entity and its concrete response/recovery, not just a related constraint.

### GEN-7B805E063F：部分非关键展示信息缺失。

推荐评分：0.5700；支持度：0.7500；缺失度：0.1500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 3

建议补充：部分非关键展示信息缺失。

场景对应主成功路径 3.a「部分非关键展示信息缺失 → 展示已有信息并隐藏缺失区域」，并被 API-S-IF2 备选 A6 明确落实：description、image_urls 等非关键展示字段缺失时返回已有字段并隐藏/缺省处理，属显式且可验证的行为。缺失度低，仅在前置/后置条件未单独描述上存在轻微信息空缺。；支持度复核：This requirement_exception branch is '部分非关键展示信息缺失' expected '系统展示已有信息并隐藏缺失区域'. Design alternative A6 specifies exactly this: missing non-critical display fields (description, image_urls) lead to returning available fields and hiding/defaulting the missing region, matching trigger and expected_result. Direct because the evidence names the same failure entity and its concrete response behavior.

### GEN-88352D1CC0：PaymentService不可用。

推荐评分：0.5700；支持度：0.7500；缺失度：0.1500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：PaymentService不可用。

场景是显式分支 3.a「PaymentService 不可用 → 系统保留待支付状态并提示稍后重试」，且 API 备选 A3 明确：PaymentService 不可用或超时返回 503 PAYMENT_SERVICE_UNAVAILABLE、订单保持 WAIT_PAY，与候选触发/预期结果一致，可验证。缺失度低，仅在前置/后置条件未单独描述与重试/降级细节未定义。；支持度复核：The requirement_exception branch is 'PaymentService不可用' expected '系统保留待支付状态并提示稍后重试'. Design alternative A3 specifies the exact failure (PaymentService unavailable/timeout), response (HTTP 503, PAYMENT_SERVICE_UNAVAILABLE) and recovery state (order stays WAIT_PAY), matching both trigger and expected_result. Direct because it names the same failure entity and gives concrete response and recovery, not just a related constraint.

### GEN-9CD781DEB4：查询参数非法。

推荐评分：0.5700；支持度：0.7500；缺失度：0.1500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 4

建议补充：查询参数非法。

需求扩展路径 4.b 明确描述“查询参数非法→系统提示顾客修正查询条件”，且功能设计备选流程 A1 给出可验证的失败机制：查询参数非法时返回 HTTP 400，错误码 INVALID_QUERY_PARAM。候选场景与所分配源章节中的显式约束一致，支撑失败机制明确。；支持度复核：需求 4.b 与功能设计 A1 均针对同一失败机制（查询参数非法）。A1 给出具体边界条件（minPrice>maxPrice、page<1、sortBy 非法）并规定 HTTP 400 / INVALID_QUERY_PARAM 响应，属于对 THIS 非法参数机制的显式可验证约束，但非直接逐字实现验证，故为 explicit_constraint。

### GEN-A80786BF86：顾客取消支付。

推荐评分：0.5700；支持度：0.7500；缺失度：0.1500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 4

建议补充：顾客取消支付。

需求扩展路径 4.a 描述“顾客取消支付→系统返回订单详情，订单保持 WAIT_PAY”，功能设计备选流程 A4 给出对应机制：PaymentService 返回取消状态，系统返回 HTTP 200，错误码 PAYMENT_CANCELLED，订单保持 WAIT_PAY。注意候选的 source_step_index=4 与需求 4.a 的行号一致，机制为显式可验证约束。；支持度复核：需求 4.a 与设计 A4 针对同一取消支付机制，A4 显式规定 PaymentService 返回取消状态、系统返回 HTTP 200/PAYMENT_CANCELLED 且订单保持 WAIT_PAY，与候选期望结果一致，属显式可验证约束。

### GEN-B461A3A569：数据格式：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5700；支持度：0.6000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：数据不满足格式规范

The response_payload data-format concern is only partially supported. Design sections define the response structure (productId, name, description, images[], price, originalPrice, stockStatus, salesCount) and A6 addresses missing non-critical display fields, but there is no explicit constraint on response data format validity/normalization, and the trigger '数据不满足格式规范' has no direct documented failure branch beyond missing-field handling. So the topic is interface-specific (responses are described) but the exact failure mechanism (format non-conformance) is not explicitly covered.

### GEN-BFA4B43762：业务约束：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.5700；支持度：0.6000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：当前业务条件不满足变更要求

Business-constraint concern for API-M-IF1 is supported at interface/steps level. Requirements 2.a covers '商家资质已失效 → 系统拒绝创建并提示重新认证'; design A1 (403 MERCHANT_NOT_QUALIFIED) and A2 (403 PERMISSION_DENIED) describe concrete business-condition rejections, and step 5 validates qualification and product permission. However, the candidate's trigger '当前业务条件不满足变更要求' is broader than the documented branches, and there is no explicit branch for arbitrary business-condition failure, so the specific failure mechanism cited is only partially matched.

### GEN-CDEB6D42D0：重复提交。

推荐评分：0.5700；支持度：0.7500；缺失度：0.1500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：重复提交。

需求扩展路径 3.a 明确“重复提交→系统根据幂等标识返回已有草稿”，功能设计备选流程 A3 给出可验证机制：idempotencyKey 重复时 MerchantProductService 返回已有商品草稿，不重复创建。SR 层交互与 API-M-IF1 上下文一致，失败机制显式。；支持度复核：需求 3.a 重复提交→按幂等标识返回已有草稿，设计 A3 对同一幂等机制显式规定 idempotencyKey 重复时由 MerchantProductService 返回已有草稿且不重复创建，实体（商品草稿创建）与触发条件匹配，属显式约束。

### GEN-FFF4ABBA38：订单尚未发货。

推荐评分：0.5700；支持度：0.7500；缺失度：0.1500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 4

建议补充：订单尚未发货。

场景为可选分支『4.a 订单尚未发货 → 系统不展示物流轨迹』。系统需求扩展路径逐字给出该分支及期望结果，功能设计详情备选流程 A4 明确：订单未发货时 shipmentSummary 中物流字段为空，不展示物流轨迹，基本流程第 8 步亦说明 shipment 数据仅在已发货时获取。行为在两个层级均有显式、一致描述，缺失度低；仅其独立前置/后置条件未被单列（候选标注『待需求确认』），属描述完整性上的轻微缺口，不影响行为本身的可判定性。；支持度复核：The candidate's condition is 'order not yet shipped → system does not display logistics tracking'. The requirement-layer extension 4.a states verbatim 订单尚未发货 → 系统不展示物流轨迹, and design detail A4 explicitly constrains the same behaviour: shipmentSummary logistics fields are empty and no tracking is shown, corroborated by base flow step 8 which queries the shipment table only 若已发货. Same entity (shipment/logistics summary of the order) and same trigger, explicitly documented at both layers — an explicit constraint (0.75). Not direct because the candidate's own pre/postconditions are 待需求确认 and the quoted clause constrains the presentation of the summary rather than specifying the full endpoint response contract.

### GEN-0614F4A82F：数据格式：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：数据不满足格式规范

Concern is api.data.format on API-M-IF2 PUT product info. Assigned sections explicitly validate name non-empty/length, description length, categoryId format, imageUrls format, and image format/count constraints, giving specific evidence. However no defined handling of format mismatch beyond listing is given, so missing is moderate.

### GEN-062B16EA89：发布前置条件：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：发布前置条件未满足仍执行发布

Concern is '发布前置条件未满足仍执行发布'. The design enumerates specific prerequisite-failure alternative flows: A1 PRODUCT_INCOMPLETE, A2 CATEGORY_RULE_VIOLATION, A3 INVALID_PRODUCT_STATUS, A4 VERSION_CONFLICT — these partially cover prerequisite violations during publish. However the candidate's framed trigger is generic ('前置条件未满足仍执行发布') and the preconditions restated are the normal-case ones; the specific mapping to a single failure mechanism is ambiguous, and expected_result/recovery are 待需求确认.

### GEN-06613888BB：必填字段完整性：Read or update LogisticsEvent records

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：必要字段缺失

Concern is internal_database.required_field_completeness on LOGI-EVT-01. Assigned sections define required request fields (eventId, trackingNumber, eventCode, eventTime, location, signature) and validation, but no explicit behavior for missing required fields is given (only signature, tracking, eventTime, eventCode checks). Partially supported.

### GEN-183BAFCCC3：数据格式：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：数据不满足格式规范

响应数据格式违规被挂在退款接口上，设计证据确实列出请求参数校验（orderId格式、items[]非空、reasonCode合法、requestedAmount>=0、idempotencyKey非空）与响应体字段，但备选流程只覆盖退款业务失败，没有任何格式/契约违规的错误码或响应处理约定，且请求校验与响应格式之间也存在方向不一致。属具体接口上下文支撑。

### GEN-18C3B8EFEE：数据类型：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：数据类型与接口定义不符

数据类型不符被挂在 LOGI-EVT-01 响应侧，设计证据明确定义了请求字段 eventId、trackingNumber、eventCode、eventTime、location、signature 与响应 accepted、duplicate，并有 A3（eventTime 非法）与 A5（eventCode 非法）的类型/取值校验备选流程，支撑部分类型约束。但备选流程是请求侧校验，并非响应数据类型不符，响应类型违规的错误码与恢复均无描述。

### GEN-20C05FFEED：数据范围：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：数值超出允许范围

Concern is '数值超出允许范围' at LOGI-EVT-01. The design detail specifies concrete range validations and error responses: eventTime must not precede shipment time or exceed current time → HTTP 400 INVALID_EVENT_TIME; eventCode must be within allowed codes → HTTP 400 INVALID_EVENT_CODE. These are explicit, verifiable range constraints, so partial support exists. However, the assigned sections do not declare the bounds for every numeric/encoded field (e.g., location, signature format, eventId constraints), and the candidate's own expected_result/recovery remain '待需求确认', so the general 'out-of-range' behavior is only partially pinned down.

### GEN-216F7CA856：唯一性约束：Read or update Order records

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：名称重复或唯一键冲突

Concern is a uniqueness/key-collision failure on Order records during order creation. Assigned design detail explicitly enumerates OrderService handling of idempotencyKey (idempotency check; duplicate idempotencyKey returns the existing order without re-creating) and provides A4 covering repeated submissions. This is the closest verifiable uniqueness-related mechanism. But the candidate phrases the concern as '名称重复或唯一键冲突' over 'Read or update Order records', and the sections give no Order-table unique key definition, no behavior for an internal unique-constraint violation distinct from idempotencyKey, and no error code/recovery for that case — so support is partial and the gap remains explicit.

### GEN-255C6B4A40：发布结果一致性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：发布状态与实际生效状态不一致

Concern is result consistency between declared publish status and actual effective status. The design explicitly covers a related but distinct case: A5 ProductCatalogService sync failure keeps product status ON_SALE while catalogSyncStatus=SYNC_PENDING, recorded as a retry task. This is the closest concrete evidence for 'publish declared vs effective inconsistent', but the candidate frames a broader status-consistency failure not directly stated; expected_result and recovery are 待需求确认.

### GEN-294B4AEFC2：业务约束：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：当前业务条件不满足变更要求

候选针对API-L-IF1的通用业务约束异常，但设计文档已列出具体备选流程A1-A5（订单状态无效、单号格式非法、物流服务不可用、发货项非法、无权限），并未出现笼统的“业务条件不满足变更要求”条目，且其期望结果与恢复方式均标注待需求确认。

### GEN-4414FB106B：数据范围：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数值超出允许范围

候选关注response_payload的数据范围（api.data.range）于API-O-IF1。证据中创建订单流程第3步校验'confirmedAmount>=0'，第7步校验'confirmedAmount与当前价格一致'，备选A1覆盖PRICE_CHANGED（含最新价格），说明金额取值约束被部分涉及；响应体字段orderId、orderStatus、payableAmount、expireAt被明确列出。但无任何关于响应数值超范围（如payableAmount或expireAt越界）的显式约束、错误码或处理。接口/SSD上下文具体使支持达0.5，行为本身未被描述使缺失偏高。

### GEN-5406886B89：数据范围：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：数值超出允许范围

For 支付订单 the evidence explicitly includes parameter validation (step 3: orderId格式合法、amount>=0、paymentMethod合法) and A2 AMOUNT_MISMATCH, which plausibly grounds an api.data.range concern on the PAYMENT-PAY-01 request. However the cited sections specify only amount>=0 and equality-to-payable checks; they do not define an out-of-range numeric bound or any range-exceeded response, so the specific trigger and response remain undescribed.

### GEN-5FA4F82032：数据格式：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：数据不满足格式规范

Candidate asserts api.data.format on POST /api/v1/orders. Evidence provides explicit contract context: request fields cartItemIds, addressId, couponId, idempotencyKey, confirmedAmount (383-390) and step 3 validating cartItemIds非空、addressId格式合法、confirmedAmount>=0、idempotencyKey非空 (631), with A3 INVALID_ADDRESS for a bad address and A5 CART_EMPTY (644, 652). General format validation is thus spec-supported, but no constraint defines a general '数据不满足格式规范' rejection, its error code, or recovery; the specific format-failure case remains to be confirmed.

### GEN-6B2E228FF9：数据完整性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：必填数据缺失或请求体为空

Candidate asserts api.data.completeness failure (missing required data / empty request body) on POST /payment/v1/payments. The design-detail section does specify which request fields are required (orderId, amount, paymentMethod, notifyUrl, idempotencyKey) and step 3 says the system validates them, but no备选流程 branch covers missing-required-field or empty-body requests; A1–A6 cover status conflict, amount mismatch, service unavailable, cancel, idempotency duplicate and callback idempotency only. Hence specific interface context supports the concern, but the required-field completeness behavior itself is not explicitly described.

### GEN-6E23D85EF3：持久化能力：Read or update Category records

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：写入失败或事务回滚

Candidate asserts internal_database.persistence failure (write failure / transaction rollback) at 'Read or update Category records' for API-M-IF3. The section describes writes to sku table and product version bump (steps 7–8), but nowhere specifies transaction boundaries, rollback semantics or persistence-failure handling; A1–A5 cover validation/conflict cases only. Concrete write context supports relevance, no explicit persistence guarantee.

### GEN-6F8D33F3F4：超时关注点：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：延时是否影响需求满足、后续行为执行或系统与环境协调

Candidate asserts common.timeout on POST /api/v1/orders/{orderId}/refunds. The section describes synchronous submission to PaymentService (step 9) and an unavailable-service branch (A4: PENDING + async retry, refundStatus PROCESSING), but states no timeout threshold, timeout handling or deadline for the refund API itself. Related failure handling exists for availability, not for latency.

### GEN-7B0CC087C9：数据类型：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：数据类型与接口定义不符

Concern api.data.type on LOGI-EVT-01 POST /api/v1/logistics/events. Evidence defines request body fields (eventId, trackingNumber, eventCode, eventTime, location, signature) and validation of signature, trackingNumber existence, eventTime reasonableness, eventId idempotency, eventCode legality. These address semantics/legality and ordering, giving specific interface context, but no rule states a value's data TYPE mismatching the interface definition (e.g., numeric string vs number). The documented alternatives cover invalid signature, not-found tracking number, invalid event time, duplicate, invalid event code — none is a generic 'type mismatch'. Support is therefore interface-context level (.5) with high missing for the actual type-mismatch response.

### GEN-995F875E0B：并发与幂等性：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：并发变更产生冲突，或重复请求导致重复变更

Candidate claims concurrency conflict or duplicate-request duplicate mutation on API-M-IF1 (POST /api/v1/merchant/products). The spec provides idempotencyKey handling (step 6 幂等校验; A3 idempotencyKey重复返回已有草稿) which directly maps to the duplicate-request half of the claim, giving explicit procedural context. However, no concurrency conflict (e.g., version lock) semantics are described for create, and no explicit response/recovery for general concurrent mutation is given; half the claimed mechanism is unsupported.

### GEN-9F3192BC84：数据长度：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：字符串长度超过限制

候选场景为 GET /api/v1/products/{productId} 响应载荷中字符串长度超过限制（api.data.length）。所引段落仅描述 productId 格式校验、查询字段、状态过滤与『非关键展示字段缺失』（A6）及超时/不可用错误码，未定义任何字段长度上限、超长截断或超长报错行为；仅有『响应包含 name、description 等文本字段』的接口上下文，对长度约束这一失败机制无直接支持，缺失度高。

### GEN-9F8F199760：唯一性约束：Read or update Cart records

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：名称重复或唯一键冲突

Candidate concerns a uniqueness conflict on 'Read or update Cart records' (duplicate name / unique key collision) for the cart write. The design detail describes cart_item persistence with a cart_item_id, idempotencyKey handling, and merging duplicate SKUs by accumulating quantity (A4->PURCHASE_LIMIT_EXCEEDED, A5 idempotent duplicate returns existing item), which is functionally adjacent to duplicate handling. However, uniqueness is not framed as a database constraint violation: duplicate SKUs are resolved by accumulation, and no unique-key conflict error or constraint for cart records is defined. So the topic (cart record duplicate handling) is specific but the uniqueness-violation mechanism itself is not directly supported.

### GEN-A1AD07D988：数据库可用性：Read or update Category records

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：连接失败或数据库宕机

Candidate concerns database availability ('连接失败或数据库宕机') for CategoryService while editing product info. The interface explicitly requires CategoryService availability as a precondition ('MerchantProductService和CategoryService服务可用'), and A2 gives the INVALID_CATEGORY case, but no alternative branch describes CategoryService/DB outage, connection failure, or database-down behavior for this use case (unlike other APIs which have PRODUCT_SERVICE_UNAVAILABLE / MERCHANT_SERVICE_UNAVAILABLE). The precondition constrains availability, which partially supports the mechanism, but the failure-handling behavior is unspecified.

### GEN-C9AD1AE5AC：数据完整性：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：必填数据缺失或请求体为空

填写商品信息用例含请求参数规格与请求参数校验步骤（name非空、长度、imageUrls 格式、version 非空），与'必填数据缺失或请求体为空'在接口上下文层面对应；但备选流程 A1-A5 未定义请求体为空或必填字段缺失的错误码与响应（例如无 MISSING_REQUIRED_FIELD 之类），失败机制未被显式描述。

### GEN-D6D180C693：数据合法性：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：非法字符、不允许字段或非法取值

申请退款详情流程第3步明确列出请求参数校验规则：orderId格式合法、items[]非空、reasonCode合法、requestedAmount>=0、idempotencyKey非空，直接构成'非法字符、不允许字段或非法取值'失败机制的具体约束证据。但备选流程A1-A5仅覆盖超期、超额、状态无效、支付不可用、幂等重复，未定义数据合法性违规时的响应码/错误码与恢复方式，故缺失度较高。；支持度复核：该候选关注点为 api.data.legality（非法字符、不允许字段或非法取值），证据中基本流程第3步只列出 orderId 格式合法、items[]非空、reasonCode合法、requestedAmount>=0、idempotencyKey非空等校验要求，属操作上下文；备选流程 A1–A5 分别覆盖超期、超额、状态无效、支付不可用、幂等重复，均未定义数据合法性违规（非法字符/不允许字段/非法取值）对应的错误码与恢复方式，无法支撑该失败机制。

### GEN-D91177F57F：数据类型：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：数据类型与接口定义不符

详情流程第3步参数校验与第1步请求体字段（orderId、items[]、reasonCode、reasonDescription、requestedAmount、idempotencyKey）构成接口数据类型契约的显式依据，数据类型不符即违反这些字段约定。但该异常对应的响应定义缺失，备选流程未涵盖数据类型错误场景。；支持度复核：The cited evidence describes the refund request payload fields (orderId, items[], reasonCode, reasonDescription, requestedAmount, idempotencyKey) and step 3 validates these parameters being non-empty/well-formed. This is a specific operation/interface contract, which qualifies as context. However, the concern is a mismatch between API data types and the interface definition, and the evidence does not define the actual data types (e.g., string vs integer for requestedAmount) nor any explicit type enforcement/validation rule for the request payload. No verbatim constraint stating a specific data type obligation for these fields exists; step 3 only checks formato/legality/non-emptiness, not type conformance. Hence no explicit_constraint. Additionally no alternative-flow response covers data type errors, reinforcing that the mechanism is unspecified.

### GEN-ECC73CF0E9：资源存在性：Read or update Category records

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：查询、修改或删除不存在资源

候选针对“Read or update Category records”的internal_database.resource_existence（查询、修改或删除不存在资源）。证据明确写出对category表的读取与依赖：第7步“查询category表获取分类的必填属性和发布规则”，前置条件要求“类目规则”有效，备选A2对不满足类目发布规则给出CATEGORY_RULE_VIOLATION并进入审核队列。这构成与类别记录读取直接相关的具体接口上下文，支持度取0.5；但没有任何“类别不存在/已被删除”的处理说明或错误码（如CATEGORY_NOT_FOUND），失败机制缺少可验证约束。缺失度中高：候选仅检查存在性，而A2针对的是规则违反而非资源缺失，两者语义不同，异常响应与恢复待确认。

### GEN-ECFFB1D2C3：业务约束：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：当前业务条件不满足变更要求

候选为API-M-IF3的通用业务约束异常，设计文档备选流程已具体化A1-A5（负库存、价格非法、重复SKU、版本冲突、商品不存在），并未出现笼统的“当前业务条件不满足变更要求”条目，期望结果与恢复方式均待需求确认。

### GEN-F6A6B19570：数据类型：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：数据类型与接口定义不符

Assigned sections specify request/response payload shapes (carrierCode, trackingNumber, shippedItems[], response shipmentId/orderStatus/trackingNumber) and type-ish validations (orderId格式合法, carrierCode合法, trackingNumber非空) plus A2 INVALID_TRACKING_NUMBER. This gives evidence for data-type conformance at the payload level, but the interface definitions do not state field types explicitly, so the exact type-mismatch behavior remains undescribed.

### GEN-F7B2AD9B71：字段合法性：Read or update Category records

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：类型错误、非法字符或超长

Steps validate name length, description length, categoryId validity, imageUrls format/count (steps 3,7 and A2/A3), which evidences field-validity concerns. However these are request-parameter validations; the candidate's target is 'Read or update Category records' and no evidence defines validity constraints, illegal-character or over-length rules on Category records themselves. Category flow only checks existence/status.

### GEN-FC09184269：数据格式：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：数据不满足格式规范

The publish interface is documented with version and publishAt, and step 3 validates 'version非空、publishAt格式合法'. This gives explicit format-conformance context for the request. However no evidence defines the publishAt date-time format syntax or a specific format-error alternative flow, so the exact format-mismatch response is undescribed.

### GEN-FF204E7272：数据完整性：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5600；支持度：0.5000；缺失度：0.7000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：必填数据缺失或请求体为空

Candidate concerns api.data.completeness (missing required data/empty body) on the refund creation interface. Evidence specifies required request fields orderId, items[], reasonCode, reasonDescription, requestedAmount, idempotencyKey and step 3 validates orderId format, items[] non-empty, reasonCode legality, requestedAmount>=0, idempotencyKey non-empty. Yet the alternate flows A1–A5 cover REFUND_WINDOW_EXPIRED, REFUND_AMOUNT_EXCEEDED, ORDER_STATUS_INVALID, PaymentService unavailability and idempotency, with no explicit branch/error code for missing required fields or empty body. Note also the path discrepancy between the candidate/design detail (POST /api/v1/refunds) and the V5 chain (POST /api/v1/orders/{orderId}/refunds), an ambiguity affecting the exception trigger.；支持度复核：The evidence names the refund creation interface and enumerates required request fields (orderId、items[]、reasonCode、reasonDescription、requestedAmount、idempotencyKey), with step 3 validating items[]非空 and idempotencyKey非空. But alternate flows A1–A5 cover REFUND_WINDOW_EXPIRED, REFUND_AMOUNT_EXCEEDED, ORDER_STATUS_INVALID, PaymentService unavailable and idempotency handling — none specifies the response/recovery for the candidate trigger '必填数据缺失或请求体为空'. Additionally there is an interface path discrepancy between the candidate/design detail (POST /api/v1/refunds) and the V5 chain (POST /api/v1/orders/{orderId}/refunds), so the failure-path constraint is not explicitly fixed. The context is specific to the operation but lacks an explicit constraint for this failure mechanism.

### GEN-A00696170B：商品目录服务超时。

推荐评分：0.5550；支持度：0.7500；缺失度：0.1000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 4

建议补充：商品目录服务超时。

需求扩展路径 4.c 直接给出“商品目录服务超时→系统提示‘商品加载失败，请稍后重试’”，功能设计备选流程 A4 给出可验证失败机制：ProductCatalogService 查询超时返回 HTTP 504，错误码 PRODUCT_SERVICE_TIMEOUT。源章节对该异常的描述清晰完整。；支持度复核：需求 4.c 与设计 A4 对同一超时机制均给出显式描述：调用 ProductCatalogService 查询超时，返回 HTTP 504 及 PRODUCT_SERVICE_TIMEOUT，响应码/错误码可验证，构成显式约束而非仅上下文。

### GEN-C52071CA71：数据完整性：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5550；支持度：0.6000；缺失度：0.4500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：必填数据缺失或请求体为空

Request-payload data-completeness for API-S-IF1 is partly supported. Design precondition states query parameters '若存在，应满足接口约束', and step 2/A1 give INVALID_QUERY_PARAM for illegal parameters (minPrice>maxPrice, page<1, bad sortBy), while A7 addresses missing mandatory product fields. But the candidate trigger '必填数据缺失或请求体为空' does not map cleanly onto a GET endpoint with optional query parameters; there is no explicit branch for missing required data or empty body, so only adjacent query-validation evidence supports this concern.

### GEN-43DE8E309C：字段合法性：Read or update Shipment records

推荐评分：0.5450；支持度：0.5000；缺失度：0.6500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：类型错误、非法字符或超长

候选涉及Shipment记录字段合法性（类型/字符/超长），设计文档确有参数校验步骤（trackingNumber格式、shippedItems非空）与INVALID_TRACKING_NUMBER等错误码，但未覆盖“类型错误、非法字符、超长”的数据库字段级验证，内部数据库关注点未被显式描述。

### GEN-44FFAC49C0：超时关注点：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5450；支持度：0.5000；缺失度：0.6500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：延时是否影响需求满足、后续行为执行或系统与环境协调

超时关注点在API-C-IF1上下文中有部分间接支撑：备选流程A6定义'ProductCatalogService不可用，返回 HTTP 503，错误码 PRODUCT_SERVICE_UNAVAILABLE'，属于依赖服务故障语义；第9步涉及cart_item表写入。但没有任何显式超时约束、超时时限或超时错误码（如504）用于API-C-IF1本身。候选问题'延时是否影响需求满足、后续行为执行或系统与环境协调'表述为通用探查而非具体约束，故支持仅达接口上下文层级；缺失明显。注意对比证据中API-S-IF2和API-O-IF2均显式定义了504超时错误码，说明该规范在同文档中存在但未覆盖本接口，进一步支撑缺失判断。

### GEN-56601C9482：持久化能力：Read or update Category records

推荐评分：0.5450；支持度：0.5000；缺失度：0.6500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：写入失败或事务回滚

For 填写商品信息 the cited flow calls MerchantProductService which updates the product table (step 8: name, description, category_id, image_urls, version+1, updated_at), establishing write context for a persistence concern; A4 also describes a version conflict with reload recovery. But no cited alternative addresses write failure or transaction rollback, and the visible DB write is on product rather than the candidate's 'Category records' target, so the specific persistence-failure mechanism remains unstipulated.

### GEN-56C59B41F1：唯一性约束：Read or update Category records

推荐评分：0.5450；支持度：0.5000；缺失度：0.6500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：名称重复或唯一键冲突

For 创建商品 the evidence covers idempotency-key-driven duplicate handling (A3 idempotencyKey重复返回已有商品草稿) and merchant qualification/permission checks, and step 7 writes a new product row. This provides partial DB-constraint context, but the candidate's uniqueness mechanism (name duplication or unique-key conflict) is not described in any cited step, and the target is stated as 'Category records' while the described write is to the product table. No unique-name rule or conflict error exists in the assigned sections.

### GEN-14AE26863A：数据完整性：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：必填数据缺失或请求体为空

The basic flow explicitly validates 'name非空、version非空' and A2/A3 cover category/image, but the 备选流程 does NOT include an error for missing required fields or empty request body. Thus required-data-missing is a recognized validation concern (name non-empty, version non-empty) but no explicit error code/response exists, so the completeness exception response remains unspecified.；支持度复核：The design validates name non-empty and version non-empty (step 3 of the basic flow) and A2/A3 cover category/image errors, but no 备选流程 entry addresses missing required fields or an empty request body, and no error code/response is defined. Field-presence validation of other fields is context; the missing-required-data exception response remains unspecified, so at most the interface/operation context is established.

### GEN-51A024EF4D：数据合法性：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：非法字符、不允许字段或非法取值

候选针对 API-R-IF1（POST /api/v1/orders/{orderId}/refunds）的响应数据合法性（非法字符、不允许字段、非法取值）。证据显示基本流程第3步存在请求参数校验（orderId 格式合法、items[] 非空、reasonCode 合法、requestedAmount>=0、idempotencyKey 非空），但备选流程列出的失败为业务性错误（REFUND_WINDOW_EXPIRED、REFUND_AMOUNT_EXCEEDED、ORDER_STATUS_INVALID、幂等、PaymentService 不可用），没有任何针对数据合法性/非法字段的错误码或响应定义，且候选关注的是响应载荷而非请求校验。存在具体接口上下文支持输入校验机制，但所提失败细节未在证据中体现。

### GEN-527E3DBA70：数据类型：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：数据类型与接口定义不符

候选针对 PAYMENT-PAY-01 请求数据“类型与接口定义不符”。证据中基本流程第3步明确校验 amount>=0、paymentMethod 合法等参数约束，但错误码均为业务/状态/服务类（ORDER_STATUS_INVALID、AMOUNT_MISMATCH、PAYMENT_SERVICE_UNAVAILABLE、PAYMENT_CANCELLED、幂等），未定义任何“数据类型不符”的错误码或响应；接口定义中 amount/paymentMethod 具体类型亦未给出。存在具体校验上下文，但所提失败类型未在证据中明确。

### GEN-54EF0D36E9：数据完整性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：必填数据缺失或请求体为空

For 支付订单 the evidence explicitly validates required request parameters (orderId、amount、paymentMethod、notifyUrl非空、idempotencyKey非空), directly grounding an api.data.completeness concern on the PAYMENT-PAY-01 request. However the assigned sections do not define a distinct error/response for a missing required field or an empty request body; A1/A2 cover order status and amount mismatch only. So the concern applies but the exception behavior is not explicitly described.

### GEN-5F40FFAA47：身份认证：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：无凭证、Token 无效或过期

Candidate asserts human.authentication on PUT /api/v1/merchant/products/{productId}. Evidence directly supports the precondition '请求携带合法 Authorization Token' (985-996) and basic flow step 2 '在线商城系统校验 Authorization Token，确认商家身份' (999). Thus authentication is a real, spec-described check on this operation; however, the specific failure modes (无凭证/Token 无效或过期) and their error responses are not enumerated in A1-A5 (1009-1017), so recovery/response for invalid or expired credentials is unspecified.

### GEN-8A97BD7401：数据范围：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：数值超出允许范围

api.data.range is partially supported because the logistics flow defines value-domain checks for specific fields: eventTime must not precede shipment time nor exceed current time (A3 INVALID_EVENT_TIME) and eventCode must be within allowed codes (A5 INVALID_EVENT_CODE). These are explicit range/enumeration constraints on request payload fields. However, the candidate's trigger is a generic '数值超出允许范围' rather than a specific field, and no numeric/coordinate bound on location or other payload values is defined, so support is specific-context but not a direct match to the stated failure mechanism.

### GEN-8ABE773E72：数据范围：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：数值超出允许范围

api.data.range is partially supported: the publish flow defines explicit value constraints (stock_quantity>0, sale_price>0, version optimistic-lock consistency, publishAt format), and A4 defines VERSION_CONFLICT. These are bounds on request/entity values relevant to a range check on publish. However the candidate trigger '数值超出允许范围' is generic and no explicit numeric upper/lower bound or max-length/range limit is stated for publish parameters, so the evidence gives interface-level context but not direct support for the specific failure mechanism.

### GEN-9392088419：并发与幂等性：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：并发变更产生冲突，或重复请求导致重复变更

候选场景为 PUT /api/v1/merchant/products/{productId} 的并发变更冲突或重复请求重复变更（service.resource_mutation.concurrency_idempotency）。所引段落明确包含乐观锁 version 校验与 A4『version 不一致（商品已被其他操作修改），返回 HTTP 409 Conflict，错误码 VERSION_CONFLICT』，对并发冲突机制构成具体接口级支持；但需求文档扩展路径只描述 2.a 分类与 3.a 图片格式异常，未覆盖并发/幂等语义，重复请求的幂等处理在本用例中无明确描述，故缺失度中高。

### GEN-9DAF9DCBEA：数据合法性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：非法字符、不允许字段或非法取值

Candidate targets request-payload data legality (illegal characters, disallowed fields, illegal values) at POST /api/v1/orders. The design detail explicitly lists field-format validation of request parameters (cartItemIds non-empty, addressId format legal, confirmedAmount>=0, idempotencyKey non-empty), giving concrete generic support for a data-legality failure mechanism. However, the specific trigger categories (illegal characters, disallowed/unknown fields) are not separately constrained; the stated checks are only non-emptiness, format and numeric-sign checks, with no allowed-character or allowed-field specification. So the interface context is specific and the validation step exists, but the exact failure class is only partially described.；支持度复核：The candidate's failure mechanism is request-payload data legality covering illegal characters, disallowed/unknown fields, and illegal values. The cited evidence does describe a request-parameter validation step for this specific API ('校验请求参数：cartItemIds非空、addressId格式合法、confirmedAmount>=0、idempotencyKey非空'), so there is a concrete validation context on the exact interface. However, the stated checks only cover non-emptiness, a format check, and a numeric-sign check. Nothing in the evidence constrains allowed characters or defines a set of allowed/permitted fields, so the 'illegal characters' and 'disallowed fields' failure classes are not supported as explicit constraints, and the exact validation semantics for '非法取值' are not specified. This is therefore a validation context on the right interface but without a constraint that governs the specific legality mechanism.

### GEN-B8096B8140：数据完整性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：必填数据缺失或请求体为空

The data-completeness concern for API-O-IF1 is only generically supported. Design step 3 describes parameter validation ('cartItemIds非空、addressId格式合法、confirmedAmount>=0、idempotencyKey非空'), and A3/A5 cover specific invalid-address and empty-cart branches, but there is no explicit branch for '必填数据缺失或请求体为空' as a distinct failure mechanism, and no documented recovery for an empty request body. This is interface/SSD-specific context without an explicit constraint describing the cited failure.

### GEN-B8B9049E64：数据类型：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：数据类型与接口定义不符

The payment flow explicitly validates request parameters (orderId format, amount>=0, paymentMethod, notifyUrl non-empty, idempotencyKey non-empty) and returns AMOUNT_MISMATCH on value mismatch, directly supporting a data-type/definition mismatch failure, though type mismatch itself is not enumerated.；支持度复核：The cited evidence shows parameter validation (orderId format, amount bounds, non-empty fields) and a value-mismatch error (A2: AMOUNT_MISMATCH), which is a specific operation/interface with validation context. However, no source states a data-type-mismatch mechanism (e.g., a non-numeric value or wrong-typed field being rejected with a defined type error). Value and format checks are context, not explicit constraints on the data-type mechanism the candidate claims, so evidence level is context, below the initial explicit_constraint-equivalent proposal.

### GEN-D974AA2834：身份认证：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：无凭证、Token 无效或过期

创建订单基本流程第2步及前置条件均明确要求校验Authorization Token确认顾客身份、idempotencyKey非空，直接支撑'无凭证、Token无效或过期'失败机制。但备选流程A1-A6中没有认证失败（401）对应的错误码或恢复路径，需补需求。；支持度复核：Candidate concern is authentication failure (missing credentials, invalid/expired Token) on POST /api/v1/orders. Evidence does show step 2 validates the Authorization Token to confirm customer identity, and preconditions require login. This is a specific operation/interface context for identity verification. But the evidence provides no explicit constraint on how missing/invalid/expired credentials are detected or what response is produced — the alternative flows A1-A5 do not include an authentication/401 error path. There is no verbatim requirement establishing a criterion for this failure mode, so the level is context rather than explicit_constraint.

### GEN-E78C46C637：数据格式：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.5300；支持度：0.5000；缺失度：0.6000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：数据不满足格式规范

候选针对LOGI-EVT-01的api.data.format（数据不满足格式规范）。证据对入参格式有明确校验语境：请求体含eventId、trackingNumber、eventCode、eventTime、location、signature，流程第4步校验eventTime合理性，备选流程给出INVALID_SIGNATURE(401)、INVALID_EVENT_TIME(400)、INVALID_EVENT_CODE(400)等格式/取值校验错误码，构成与该失败机制相关的具体接口上下文，故取0.5。但该候选的source_step_index=5将其挂在“系统保存新的物流节点”之后，而定位段落实际是system的格式校验环节（第3–5步），锚点与机制错位；且没有针对请求体整体格式（如字段结构/schema）违反的统一错误码，异常响应与恢复待确认，缺失度中高。

### GEN-125159DDD8：数据范围：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5200；支持度：0.4000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：数值超出允许范围

API-M-IF2 request params include categoryId and imageUrls whose format is validated, but there is no numeric field (price/stock) on this endpoint and no explicit '数值超出允许范围' validation. A2 (categoryId invalid) is a business-validity check, not a numeric-range check. Range-exceeded exception is therefore weakly grounded and largely unspecified; response/recovery remains '待需求确认'.

### GEN-142515D67A：数据大小：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5200；支持度：0.4000；缺失度：0.8000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：文件或请求体超过限制

POST /api/v1/cart/items payload (productId, skuId, quantity, idempotencyKey) is validated but no file/body-size limit is specified; constraints cited are quantity>=1, format legality, idempotency. No '文件或请求体超过限制' constraint or error exists, so the data-size exception is largely unsupported and its response/recovery unspecified.

### GEN-5FF97FFAE7：身份认证：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.5150；支持度：0.5000；缺失度：0.5500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：无凭证、Token 无效或过期

Candidate asserts human.authentication on GET /api/v1/orders/{orderId}. Evidence directly supports the precondition '请求携带合法 Authorization Token' (714-725) and basic flow step 2 '在线商城系统校验 Authorization Token，确认顾客身份' (727). A2 covers ORDER_ACCESS_DENIED for ownership mismatch but no alternative flow addresses missing/invalid/expired credentials, so the specific authentication-failure response and recovery are not specified in the assigned sections.

### GEN-67FC2CF80A：数据格式：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5150；支持度：0.5000；缺失度：0.5500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：数据不满足格式规范

API-C-IF1 (POST /api/v1/cart/items) basic flow step 3 explicitly validates request parameter formats (productId/skuId legality, quantity>=1, idempotencyKey non-empty), and alternate flow A1 handles invalid quantity with HTTP 400/INVALID_QUANTITY. However, the specific failure mechanism 'data does not satisfy format specification' in the gener...er than quantity is not explicitly enumerated; the spec only calls out quantity and idempotencyKey as format-checked fields. No explicit format-spec document or error code for general formatting violations is provided, leaving response behavior for non-quantity format breaches unspecified.；支持度复核：The evidence for API-C-IF1 (POST /api/v1/cart/items) includes basic flow step 3 '校验请求参数：productId和skuId格式合法、quantity>=1、idempotencyKey非空' and alternate flow A1 'quantity不合法（例如 quantity<1）...HTTP 400 Bad Request，错误码 INVALID_QUANTITY'. This names a specific interface and field-level format validation, but the trigger is a generic '数据不满足格式规范' whose broad mechanism (format-spec violation for fields other than quantity) is not explicitly constrained beyond the enumerated checks. Field-format checks for quantity/idempotencyKey/products/skuId do not prove a general format-violation response. Hence context.

### GEN-6948F60E61：数据合法性：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5150；支持度：0.5000；缺失度：0.5500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：非法字符、不允许字段或非法取值

API-S-IF1 (GET /api/v1/products) basic flow step 2 explicitly validates query parameters (page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice, categoryId validity), and alternate flow A1 handles invalid query parameters with HTTP 400/INVALID_QUERY_PARAM, including examples of minPrice>maxPrice, page<1, and disallowed sortBy. The failure mechanism (illegal characters, disallowed fields, illegal values) is partially covered by A1's enumerated examples and step 2's validation rules, but the spec does not explicitly address illegal characters or disallowed fields beyond sortBy domain restriction. Response behavior for character-level illegality is not separately specified.；支持度复核：API-S-IF1 (GET /api/v1/products) basic flow step 2 validates specific numeric/domain constraints (page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice, categoryId validity) and alternate flow A1 handles invalid query params with HTTP 400/INVALID_QUERY_PARAM for cases like minPrice>maxPrice, page<1, or sortBy out of range. The trigger '非法字符、不允许字段或非法取值' is broader than the enumerated constraints; there is no explicit constraint on illegal characters or disallowed fields. The interface and some parameter checks are present, but the specific mechanism (illegal characters/disallowed fields) is not directly constrained, so context, not explicit_constraint.

### GEN-BDCCA13EFF：数据类型：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.5150；支持度：0.5000；缺失度：0.5500；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：数据类型与接口定义不符

The shipment flow explicitly validates request parameters (orderId format, carrierCode, non-empty trackingNumber, non-empty shippedItems[]) and returns INVALID_TRACKING_NUMBER / INVALID_SHIPPED_ITEMS on malformed data, directly supporting a data-type-mismatch failure mechanism. Type mismatch as such is not separately stated, so it remains inferred.；支持度复核：The shipment flow validates request parameters and returns INVALID_TRACKING_NUMBER and INVALID_SHIPPED_ITEMS on malformed/empty data, which is a specific operation with validation context. But no source expresses an explicit constraint on a data-type mismatch (e.g., a non-string trackingNumber or wrong-typed field with a defined rejection). Validation of other field properties is context, not an explicit constraint on the claimed type-mismatch mechanism.

### GEN-06071A4EE9：业务约束：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：当前业务条件不满足变更要求

The candidate routes a 'business constraint not satisfied for mutation' exception onto API-M-IF2. The assigned evidence does specify business constraints controlling this mutation: the product must belong to the merchant, be in DRAFT status, and the supplied version must match for optimistic locking (A4 VERSION_CONFLICT, A5 INVALID_PRODUCT_STATUS), and category validity (A1/A2). These are concrete constraint mechanisms, but the candidate's generic wording ('当前业务条件不满足变更要求') does not identify which constraint, so support is at interface/business-rule level rather than a directly matching verifiable failure. The requirement-level extensions (2.a category invalid, 3.a image invalid) partially overlap but do not name the DRAFT/version constraints described only in the design detail.

### GEN-0A2E0D655B：超时关注点：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：延时是否影响需求满足、后续行为执行或系统与环境协调

The candidate raises a timeout concern on API-O-IF2. The assigned evidence does cover a timeout alternative (A5: OrderService query timeout → HTTP 504 Gateway Timeout, error ORDER_SERVICE_TIMEOUT), giving specific interface-level support for the failure mechanism. However, the candidate frames the trigger generically as whether latency affects requirement satisfaction, which is broader than and not identical to the documented OrderService timeout; the requirement section (2.a, 3.a, 4.a) contains no latency concern at all. Support is at specific-interface-context level rather than a directly matching explicit requirement constraint.

### GEN-12E1480B79：持久化一致性：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：操作结果未可靠持久化或局部成功

UCG-003-UC001 writes shipment and updates order status; design step 7-8 describes ordered writes (shipment insert then order update) with no atomicity/transaction boundary, and A3 explicitly leaves an asynchronous retry for LogisticsService unavailability while order still set to SHIPPED. This partial-success scenario is thus grounded in the design. However, the specific '操作结果未可靠持久化或局部成功' failure mechanism and its required atomicity/recovery are not directly constrained or reconciled with A3, leaving the exception response '待需求确认'.；支持度复核：Evidence shows ordered writes (shipment insert in step 7, then order status update to SHIPPED in step 8) with no transaction/atomicity boundary, and A3 leaves LogisticsService registration as an asynchronous retry while the order is still set to SHIPPED. These facts describe the specific operation but do not explicitly constrain a persistence-consistency guarantee or a partial-success failure/recovery mechanism for the shipment write, so this remains context only.

### GEN-195E413858：资源存在性：Read or update Product records

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：查询、修改或删除不存在资源

浏览商品的资源存在性有直接对应约束：A2 说明 categoryId 不存在或失效返回 HTTP 400 INVALID_CATEGORY，A3 说明未查询到符合条件的商品返回 total=0/products=[]，A6/A7 处理状态变更与字段缺失，均为可验证的显式约束。但候选触发语「查询、修改或删除不存在资源」中的修改/删除语义在该只读接口中无对应描述，故存在语义超出。；支持度复核：Candidate trigger is 'query, modify, or delete non-existent resource' on the Product read/update concern. Evidence does provide resource-existence handling for the read side: A2 returns 400 INVALID_CATEGORY when categoryId does not exist, A3 returns total=0/products=[] for no matches, and A6/A7 handle state change and missing fields. However this is a read-only browse endpoint (GET /api/v1/products) with no update/delete operation described, and the candidate's 'modify or delete non-existent resource' semantics have no mechanism evidence. The existence checks shown (category validation, empty result) are a specific interface but do not establish the asserted modify/delete-non-existent-resource failure mechanism. Hence context, not explicit_constraint.

### GEN-4525B6D283：字段合法性：Read or update SKU records

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：类型错误、非法字符或超长

字段合法性关注点（internal_database.field_validity）在API-S-IF2有部分支撑：基本流程第2步'校验 productId 的格式'，第4步读取product表具体字段（product_id、product_name、description、image_urls、sale_price、original_price、stock_quantity、sales_count、status、merchant_id、updated_at），备选A1定义'productId 格式错误，返回 HTTP 400，错误码 INVALID_PRODUCT_ID'，A6涉及description/image_urls缺失的缺省处理。但候选触发为'SKU records的类型错误、非法字符或超长'，证据中SKU字段及其合法性校验并未在API-S-IF2中描述（该接口仅查询product表）。因此存在部分相关字段项但与SKU及超长/非法字符约束不匹配，支持与缺失各半。

### GEN-72F0043513：并发一致性：Read or update Shipment records

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：并发更新冲突或后写覆盖前写

Candidate asserts internal_database.concurrency_consistency on Shipment records in API-L-IF1. The section describes querying order status PAID, writing shipment table rows, and updating order status to SHIPPED (steps 4–8), with A1 returning ORDER_STATUS_INVALID when status is not PAID, which implicitly guards double shipment. No explicit optimistic lock, version field or lost-update rule for the shipment/order write is defined, so the failure mechanism is only partially constrained.；支持度复核：The cited sections (功能设计Delta_spec.md steps 4–8, A1 备选流程, 调用链) describe the shipment write/update interface and order-status guard but contain no constraint on concurrency: no optimistic lock, version column, lock scope, lost-update rule, or conflict response is specified for concurrent reads/updates of Shipment/Order records. A1's ORDER_STATUS_INVALID check only guards against non-PAID status re-submission (a state check), not a concurrent-update or lost-update mechanism; this remains an unspecified implementation possibility, so evidence is limited to the specific operation/interface (context), not an explicit constraint.

### GEN-814CDDDEB8：数据范围：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：数值超出允许范围

Concern api.data.range (numeric value out of allowed range) for POST /api/v1/cart/items. Assigned sections explicitly bound quantity (quantity>=1) and enforce stock and limit_per_order, with A1 INVALID_QUANTITY and A4 PURCHASE_LIMIT_EXCEEDED. The out-of-range checks are thus largely covered by existing constraints and outcomes, though no explicit generic range exception beyond these enumerated ones is defined.

### GEN-8543765468：身份认证：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：无凭证、Token 无效或过期

Concern human.authentication (missing, invalid or expired token) for GET /api/v1/orders/{orderId}/logistics. Assigned sections explicitly list token validation as step 2 of the basic flow and state preconditions requiring a valid Authorization Token, giving clear contextual support; however, no dedicated authentication-failure alternative (error code/status for invalid or expired token) is enumerated, so the exact response remains undocumented.

### GEN-983554CCFF：超时关注点：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：延时是否影响需求满足、后续行为执行或系统与环境协调

候选场景为 GET /api/v1/orders/{orderId}/logistics 的超时关注点（common.timeout）。所引段落含 A3『ACT-004（LogisticsService）查询失败或超时，LogisticsServiceAdapter返回本地最近一次同步数据，dataSource 标记为 CACHE』这一明确的超时降级机制，构成具体接口级支持；但需求文档扩展路径仅言『外部物流服务查询失败』，未定义超时阈值或超时判定，V5 调用链章节错误码写作 LOGISTICS_SERVICE_TIMEOUT 而详情章节 A5 为 LOGISTICS_SERVICE_UNAVAILABLE，存在命名不一致的模糊性，故缺失度中等。

### GEN-9F571B285A：数据长度：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：字符串长度超过限制

Candidate targets data-length overflow on request parameters for GET /api/v1/products. Step 2 explicitly validates page/pageSize/price bounds and categoryId validity, and the preconditions state query parameters must satisfy interface constraints; the alternate A1 covers invalid query parameters via INVALID_QUERY_PARAM. This gives explicit, specific validation evidence for a range/constraint failure. Notably, however, no maximum string-length limit is defined for keyword or sortBy anywhere in the source, so the length-specific variant is inferred from generic parameter-constraint wording rather than concretely specified.；支持度复核：Candidate concerns a string-LENGTH overflow on request_payload of GET /api/v1/products (concern api.data.length). Sources specify bounds only for numeric params (page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice) and categoryId validity; A1 covers invalid query params generally, not length. No maximum string length for keyword or sortBy is defined anywhere in the cited evidence, so the length-limited mechanism for THIS failure is not concretely constrained. Parameter validation of other field properties only provides context, not the specific length-overflow constraint.

### GEN-BCC3E27560：数据完整性：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.5000；支持度：0.5000；缺失度：0.5000；等级：medium

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：必填数据缺失或请求体为空

The order-detail flow enumerates every response field and the alternative paths return specific errors (INVALID_ORDER_ID, ORDER_NOT_FOUND) when input is malformed or absent, supporting the missing-required-data failure mechanism for the response payload. However, the sources do not describe a response-side completeness defect per se, so support is inferred rather than direct.；支持度复核：The evidence enumerates the response fields for GET /api/v1/orders/{orderId} and the alternative flows define errors only for malformed or absent orderId input (INVALID_ORDER_ID, ORDER_NOT_FOUND) and for OrderService timeout. The candidate concern is a response-side completeness defect (required data missing in response), which the sources never describe as a mechanism or constraint. Field enumeration is descriptive; error codes address request arguments, not response completeness, so this is context rather than explicit_constraint.

### GEN-8904B87C4B：数据大小：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.4950；支持度：0.3000；缺失度：0.9500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：文件或请求体超过限制

UCG-001-UC001 has explicit query-parameter bounds (page>=1, 1<=pageSize<=100, minPrice>=0, maxPrice>=minPrice) with A1 INVALID_QUERY_PARAM 400, showing size/range-style validation exists. However the scenario is scoped to the response payload of GET /api/v1/products being over a file/request-body size limit; no response-size or payload-size limit is defined anywhere in the assigned sections, so support is weak and coverage clearly missing.

### GEN-15180B7015：持久化一致性：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.4850；支持度：0.5000；缺失度：0.4500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：操作结果未可靠持久化或局部成功

LOGI-EVT-01 writes logistics_event (step 6) then updates shipment summary (step 7) as two separate mutations, and idempotency/signature checks are explicit. This supports the persistence-consistency/partial-success concern (two writes without stated transaction boundary). However, no explicit atomicity/transaction or rollback requirement is stated; error handling (A1-A5) does not address non-persistence, so the exception handling remains '待需求确认'.；支持度复核：Steps 6 and 7 in the basic flow perform two separate mutations (insert logistics_event, update shipment summary), which is the operation context for a partial-success concern, but the design states no transaction boundary, atomicity requirement, or rollback behavior, and the 备选流程 A1-A5 do not address non-persistence or partial success. No explicit persistence-consistency constraint exists, so this is context only.

### GEN-42433AC82F：幂等性：Read or update Cart records

推荐评分：0.4850；支持度：0.5000；缺失度：0.4500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：重复请求导致重复操作异常

幂等性关注点在API-C-IF1有明确接口级支撑：请求参数含idempotencyKey，基本流程第8步'CartService按idempotencyKey执行幂等校验'，备选流程A5'idempotencyKey重复，CartService返回已有购物车条目，不重复写入'。但候选触发描述为'重复请求导致重复操作异常'，语义与证据相反——证据表明重复请求是已按幂等键正确处理的正常路径（返回已有条目），而非异常；且候选将'Read or update Cart records'描述为目标节点操作，而证据中幂等判定由CartService基于idempotencyKey完成。候选未引用A5，仅覆盖通用主题，故支持中等。缺失主要在于：A5已描述幂等行为，候选却标注'异常响应及恢复方式待需求确认'，与已有描述存在张力；未明确无idempotencyKey或键冲突时的响应。

### GEN-4574A3F4FC：持久化能力：Read or update Order records

推荐评分：0.4850；支持度：0.5000；缺失度：0.4500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：写入失败或事务回滚

持久化能力关注点（internal_database.persistence）于API-O-IF1有接口级支撑：第10步明确'OrderService...创建订单并锁定库存，写入 order 表（含字段清单）和 order_item 表（含字段清单）'，第9步传入idempotencyKey，备选A4定义幂等返回已有订单。因此写入语义与事务参与对象已被具体描述。但候选触发'写入失败或事务回滚'本身未被显式描述：没有任何关于事务回滚、写入失败或补偿（如库存解锁）的错误码与响应。故接口上下文支撑成立而失败机制无显式约束，支持0.5、缺失约0.45。

### GEN-9B94AA0425：资源存在性：Read or update Category records

推荐评分：0.4850；支持度：0.5000；缺失度：0.4500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：查询、修改或删除不存在资源

候选场景为读取/更新 Category 记录时资源不存在（internal_database.resource_existence）。所引段落有明确支持：主流程第6步调用 CategoryService 校验 categoryId 并查询 category 表确认分类有效且未停用；A2『categoryId 不存在或已停用，返回 HTTP 400 Bad Request，错误码 INVALID_CATEGORY』。故该行为在功能设计层已被具体描述，缺失度较低；仅存在错误码命名差异（需求侧写 CATEGORY_NOT_FOUND，详情侧写 INVALID_CATEGORY）带来的轻微模糊。

### GEN-F872707739：数据合法性：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.4850；支持度：0.5000；缺失度：0.4500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：非法字符、不允许字段或非法取值

场景为『调用 LOGI-EVT-01：POST /api/v1/logistics/events 时非法字符、不允许字段或非法取值』的数据合法性异常。设计详情备选流程 A5 显式规定 eventCode 不在允许范围内时返回 HTTP 400 Bad Request / INVALID_EVENT_CODE，A3 对 eventTime 取值合理性校验返回 INVALID_EVENT_TIME，直接支持『非法取值』的失败机制，支持度较高。但『非法字符』与『不允许字段』两类子情形在系统需求扩展路径中并无对应条目（需求层仅覆盖签名失败 2.a、重复节点 3.a、时间倒序 3.b），且候选 expected_result/recovery 标注为『待需求确认』，说明该异常在需求层描述明显缺失。；支持度复核：The candidate's mechanism is broad: illegal characters, disallowed fields, or illegal values on the logistics event payload. Design details only constrain two specific fields — eventCode outside an allowed enumeration (A5, INVALID_EVENT_CODE) and eventTime reasonableness (A3, INVALID_EVENT_TIME). Both A3 and A5 match the 'illegal value' sub-case for those specific fields and provide a mechanism constraint, which supports the topic of payload legality. However, no evidence covers illegal characters or disallowed/unknown fields at all; the cited A5 is therefore a specific operation/interface with a constraint on a different (enumeration) property than character/field-level legality, and the requirements layer's extension paths cover only signature failure, duplicate nodes, and time ordering. Per the rule that other field-property validations count only as context, this is context (0.5), not an explicit constraint for the claimed mechanism.

### GEN-2C2A29EE38：查询性能：Read or update OrderItem records

推荐评分：0.4750；支持度：0.2500；缺失度：1.0000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：大表联查超时

Candidate targets an internal_database.query_performance exception ('大表联查超时') on 'Read or update OrderItem records' during 支付订单. Assigned source sections only describe the payment business flow (order status/amount validation, PaymentAdapter/PaymentService interaction, order status update to PAID) and never reference OrderItem record access or database query performance. Only the generic payment-order topic overlaps; no evidence supports the query-timeout failure mechanism. Expected result and recovery are explicitly '待需求确认', so the behavior is clearly undescribed.

### GEN-2FD927932E：字段合法性：Read or update Category records

推荐评分：0.4750；支持度：0.2500；缺失度：1.0000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：类型错误、非法字符或超长

Candidate targets internal_database.field_validity ('类型错误、非法字符或超长') on 'Read or update Category records' during 创建商品. Assigned sections cover product creation, merchant qualification lookup and idempotency, and never reference Category record access or database field-validity rules. Only the generic create-product topic overlaps; no evidence supports the field-validity failure mechanism. Expected result and recovery are '待需求确认'.

### GEN-8F8B8BC748：数据库可用性：Read or update Category records

推荐评分：0.4750；支持度：0.2500；缺失度：1.0000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：连接失败或数据库宕机

Candidate concerns 'Read or update Category records' database availability during 申请退款 (UCG-003-UC004/API-R-IF1). Evidence for this same use case describes refund flow touching order/order_item tables, refund table, and PaymentService (steps 4, 8, 9), and A4 covers PaymentService unavailability. No supplied evidence mentions a 'Category records' resource or DB-unavailability behavior in the refund flow; support is only generic topical linkage to the refund interaction. Behavior is entirely undefined — the candidate itself states '异常响应及恢复方式待需求确认', and no evidence assigns error codes or recovery for DB failure.

### GEN-943C97A7EC：并发一致性：Read or update Category records

推荐评分：0.4750；支持度：0.2500；缺失度：1.0000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：并发更新冲突或后写覆盖前写

Candidate concerns internal_database.concurrency_consistency ('并发更新冲突或后写覆盖前写') on 'Read or update Category records' during 申请退款. Evidence for this refusal flow covers OrderService reads, idempotency-key handling (step 6), and refund-table writes (step 8), but never mentions category records or concurrency/optimistic-locking semantics for this use case; support is only generic topical association with the refund interaction. Expected response and recovery are undeclared ('异常响应及恢复方式待需求确认').

### GEN-0CD498E876：数据范围：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.4700；支持度：0.5000；缺失度：0.4000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：数值超出允许范围

Candidate is an API data-range exception ('数值超出允许范围') on API-L-IF2 GET /api/v1/orders/{orderId}/logistics. The assigned flow explicitly validates that orderId format is legal and checks the order belongs to the current customer with status SHIPPED or later, with a specific alternative A1 returning HTTP 409 ORDER_NOT_SHIPPED — concrete interface context for range/validity checking (0.5). Missingness moderate: the section specifies format/status validation but no numeric field ranges or out-of-range value error code, so the precise range failure is not described.

### GEN-6F443B1F6B：必填字段完整性：Read or update Category records

推荐评分：0.4700；支持度：0.5000；缺失度：0.4000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：必要字段缺失

Candidate asserts internal_database.required_field_completeness (required field missing) for API-M-IF3. Design detail step 3 explicitly enumerates required fields and constraints (skus[]非空, skuId format, stock>=0, salePrice>=0, originalPrice>=0, version非空), and A1/A2 give negative stock and invalid price responses. However, no branch explicitly covers an entirely absent required field (e.g. missing version or empty skus[]) with a defined error code, so partial explicit support with residual gap.；支持度复核：The candidate asserts required-field completeness (a missing mandatory field). The design detail step 3 enumerates checks (skus[]非空, skuId format, stock>=0, salePrice>=0, originalPrice>=0, version非空) but no branch defines a response for an absent required field; A1–A5 cover negative stock, invalid price, duplicate skuId, version conflict, and product-not-found only. Enumerating a field's validity constraints is context for the interface, not an explicit constraint on the missing-required-field failure mechanism, and no error code or response for omission is specified.

### GEN-802AF95D0E：数据完整性：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4700；支持度：0.5000；缺失度：0.4000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：必填数据缺失或请求体为空

Candidate asserts missing mandatory data or empty body on the API-M-IF1 request. Assigned sections explicitly require idempotencyKey非空 and merchantId格式合法 as validated parameters (lines 954-965) and list alternates A1-A4, giving an explicit completeness constraint that supports the missing-required-field mechanism. However, no error code or response is documented for a missing/empty request body (the client-supplied keys are treated as preconditions, lines 942-953), so the exact anomalous behavior and recovery remain unspecified.；支持度复核：The candidate's mechanism is missing mandatory data or an empty request body. The cited flow does show an explicit non-empty constraint on idempotencyKey ('idempotencyKey非空') and a format check on merchantId, which is more than a bare topic mention but still only constrains one enumerated field's emptiness within the normal happy-path validation step, not the full request-body completeness failure the candidate describes. No error code, HTTP status, or response behavior is documented for a missing/empty body (alternates A1–A4 cover qualification, permission, idempotency repeat, and service unavailability only), and the preconditions treat idempotencyKey as client-supplied. So this is a specific interface with partial field-level validation context, but no explicit constraint supporting the missing-body/required-field acquisition mechanism as such; per the rubric, validating other field properties remains context, so explicit_constraint was not warranted.

### GEN-854696338A：数据完整性：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.4700；支持度：0.5000；缺失度：0.4000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：必填数据缺失或请求体为空

Concern api.data.completeness (missing required data or empty request body) for PUT /api/v1/merchant/products/{productId}/skus. Assigned sections explicitly require skus[] non-empty and version non-empty (step 3), with alternatives covering negative stock, invalid price, duplicate SKU, version conflict and product-not-found. Missing/empty payload rejection is thus substantially implied by the stated validation, though no dedicated completeness error code for empty request body is given.

### GEN-BA08DD9531：身份认证：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.4700；支持度：0.3500；缺失度：0.7500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：无凭证、Token 无效或过期

Authentication evidence conflicts with the candidate's premise. The design preconditions explicitly state 'ACT-001可匿名访问；若已登录，则请求可携带合法 Authorization Token', and basic flow step 2 merely retains a valid token if present rather than requiring authentication. No branch for '无凭证、Token 无效或过期' exists; the documented error branches are INVALID_PRODUCT_ID, PRODUCT_NOT_FOUND, PRODUCT_OFF_SHELF, PRODUCT_SERVICE_TIMEOUT, PRODUCT_SERVICE_UNAVAILABLE. Thus the concern_subject source_node authentication failure is essentially unsupported for this anonymous-access use case and is largely not described.

### GEN-CC2857D09A：数据可见性：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.4700；支持度：0.5000；缺失度：0.4000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：数据越过用户、租户或权限范围被访问或返回

查看订单详情章节事实上已描述越权访问机制：系统校验订单归属关系，备选流程 A2 明确订单不属于当前顾客返回 HTTP 403 ORDER_ACCESS_DENIED（系统需求扩展路径 2.a 亦规定拒绝访问并记录安全事件）；因此'数据越权'行为的核心响应已存在，候选将其标为待需求确认与现有描述存在冲突。

### GEN-DCA7585256：数据范围：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.4700；支持度：0.5000；缺失度：0.4000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：数值超出允许范围

场景为『调用 API-C-IF1：POST /api/v1/cart/items 时数值超出允许范围』的异常。设计详情明确给出参数校验约束 quantity>=1，并将 quantity 不合法映射为备选流程 A1：HTTP 400 Bad Request / INVALID_QUANTITY，且限购上限超出映射为 A4：HTTP 409 Conflict / PURCHASE_LIMIT_EXCEEDED。这些显式约束直接支持『数值超出允许范围』的失败机制，故支持度较高。但候选自身 expected_result/recovery 标注为『待需求确认』，且系统需求层主成功路径与扩展路径（2.a库存不足、2.b已下架、3.a同SKU累加）并未单列 quantity 越界的独立分支，说明需求文档对该异常描述不完整。；支持度复核：The candidate's failure mechanism is a numeric value exceeding an allowed range (数值超出允许范围) on the add-to-cart request payload. The design detail A1 covers only the lower-bound violation quantity<1 (INVALID_QUANTITY), and A4 covers exceeding the purchase-limit cap (PURCHASE_LIMIT_EXCEEDED). A4 is an explicit constraint whose mechanism (累加后超出限购上限 → 409) does match an exceeded-range failure, but the specification gives no upper bound, no length/range numeric bound, and no field-level range check apart from the lower bound; the candidate itself marks expected_result/recovery as 待需求确认 and no concrete bound is derivable. A1 is only a specific operation/interface with a mechanism constraint on a different direction (below-minimum), so at best this is context; the claimed range-exceedance mechanism is not explicitly specified. Upgrade to explicit_constraint/direct is not warranted because the quoted clause does not state the triggering bound for the candidate's out-of-range condition.

### GEN-128A74F22C：数据长度：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.4650；支持度：0.3000；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：字符串长度超过限制

GET /api/v1/orders/{orderId} request payload is just orderId; the design only validates orderId格式 (format), A1 INVALID_ORDER_ID. There is no stated string-length-limit for orderId, so a length-exceeds-limit exception is not described. Interface/SSD context is present (0.3) but no explicit length constraint, and response/recovery is unspecified.

### GEN-13471D5938：数据完整性：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.4600；支持度：0.4000；缺失度：0.6000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：必填数据缺失或请求体为空

Candidate asserts required response data missing/empty body on API-S-IF1. Source A7 explicitly addresses missing mandatory product fields (product_name, sale_price, cover_image_url empty), where the system substitutes defaults or filters abnormal products — this is a specific constraint partly matching the 'required data missing' mechanism, though it is about missing field values rather than an empty response body; no empty-body case is defined.

### GEN-33994B884D：必填字段完整性：Read or update Payment records

推荐评分：0.4600；支持度：0.2500；缺失度：0.9500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：必要字段缺失

关注点为 internal_database.required_field_completeness（Read or update Payment records 时必要字段缺失）。所给证据仅描述查看订单详情对 payment 表的读取（第7步获取 payment_id、payment_method、provider_trade_no、payment_status、paid_at），属于正常查询路径，未定义任何字段完整性约束或缺失处理；备选流程只覆盖 INVALID_ORDER_ID、ORDER_ACCESS_DENIED、ORDER_NOT_FOUND、未发货、ORDER_SERVICE_TIMEOUT，均与本异常无关。该行为在分配章节中完全没有描述，故仅泛泛相关。

### GEN-344F0C6370：数据大小：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.4600；支持度：0.2500；缺失度：0.9500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：文件或请求体超过限制

关注点为 api.data.size（文件或请求体超过限制）。证据显示 POST /api/v1/refunds 请求体仅含 orderId、items[]、reasonCode、reasonDescription、requestedAmount、idempotencyKey，且参数校验只涉及格式合法、非空、金额范围，完全没有请求体大小上限或超限响应定义。备选流程 A1–A5 均不涉及大小限制，故仅存在接口级泛化关联。

### GEN-42223EA7E3：持久化能力：Read or update Payment records

推荐评分：0.4600；支持度：0.2500；缺失度：0.9500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：写入失败或事务回滚

关注点为 internal_database.persistence（写入失败或事务回滚）。查看订单详情为只读查询路径（查询 order、order_item、payment、shipment 表并组合返回），证据未涉及写入、事务边界或回滚处理；异常处理仅覆盖格式错误、越权、订单不存在、未发货、查询超时。故该行为在分配章节中无描述，仅主题层面相关。

### GEN-910ED085EA：数据范围：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4600；支持度：0.2500；缺失度：0.9500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：数值超出允许范围

Candidate concerns api.data.range on POST /api/v1/merchant/products (创建商品). Evidence describes the exact interface and its request/response and alternative flows (A1-A4: qualification, permission, idempotency, service unavailable), but none of them address numeric range limits or out-of-range data; the standard flow validates only merchantId format and idempotencyKey non-empty. No field-level range constraints are provided, so the specific failure is unsupported and expected behavior is undeclared.

### GEN-0895BB4597：持久化一致性：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4550；支持度：0.5000；缺失度：0.3500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：操作结果未可靠持久化或局部成功

Candidate is a persistence-consistency exception on API-M-IF1 (POST /api/v1/merchant/products). The assigned detail section specifies a write to product 表 with generated productId/version and idempotencyKey-based idempotency (A3), but contains no statement about partial persistence or recovery. Interface and write context are concrete, so 0.5. Missingness moderate: the operation is a single-table write with idempotency, which reduces ambiguity about expected behavior, but no rollback/consistency behavior is documented.

### GEN-67D9769AD5：数据长度：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.4550；支持度：0.5000；缺失度：0.3500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：字符串长度超过限制

API-O-IF2 is (GET /api/v1/orders/{orderId}) with request parameter orderId, and the detailed flow step 3 explicitly validates orderId format/legality. The failure mechanism (string length exceeding limit) is a concrete input-validity constraint plausibly covered by basic flow step 3's format validation, but no explicit length limit or length-specific error code is stated. The alternate flow A1 addresses incorrect orderId format with HTTP 400/INVALID_ORDER_ID, but does not mention string length limits. The gap is a specific max-length threshold and the differentiation between illegal-format and length-exceeded responses.；支持度复核：The cited evidence shows API-O-IF2 (GET /api/v1/orders/{orderId}) with parameter orderId and basic flow step 3 '校验 orderId 格式合法' plus alternate flow A1 handling 'orderId 格式错误' with HTTP 400/INVALID_ORDER_ID. This is a specific interface with a format-legality constraint on orderId, but no maximum-length threshold or length-overflow mechanism is stated. A format-legality check does not prove a string-length-limit mechanism; the concern is '字符串长度超过限制', which is an implementation-specific bound that is absent. Therefore only context (specific operation/interface, no mechanism constraint for THIS failure).

### GEN-00614820AF：数据类型：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：数据类型与接口定义不符

Concern is api.data.type (data type mismatch) for POST /api/v1/merchant/products/{productId}/publish (API-M-IF4). The assigned source sections list request params (productId, version, publishAt) and alternative flows A1-A5, but none address type mismatches; only generic field-format mentions exist. Since no explicit typing constraint is documented, missing is high.

### GEN-028787EB7C：超时关注点：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：延时是否影响需求满足、后续行为执行或系统与环境协调

Concern is common.timeout for API-L-IF1 POST /api/v1/orders/{orderId}/shipments. Assigned sections cover request/response and error alternatives (ORDER_STATUS_INVALID, INVALID_TRACKING_NUMBER, PERMISSION_DENIED) but no timeout/latency handling is defined. Topic is present but no supporting constraint, so missing is high.

### GEN-0347D25708：持久化能力：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：写入失败或事务回滚

Concern is internal_database.persistence (write failure/rollback) on refund (API-R-IF1). Assigned sections describe a refund table write and idempotency but no write-failure/transaction-rollback behavior is specified. Relevance is topical only.

### GEN-04EED632EB：数据长度：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：字符串长度超过限制

Concern is api.data.length on product creation (API-M-IF1). Assigned sections describe flow and alternatives (MERCHANT_NOT_QUALIFIED, PERMISSION_DENIED, duplicate idempotencyKey, service unavailable) but no string-length limits are defined. No explicit constraint supports the failure mechanism.

### GEN-073716B04B：数据大小：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：文件或请求体超过限制

Concern is api.data.size on PAYMENT-PAY-01. Assigned sections define payment flow and error alternatives (ORDER_STATUS_INVALID, AMOUNT_MISMATCH, payment unavailable, cancelled, idempotency) but no payload/file size limits are documented. No explicit constraint supports the failure mechanism.

### GEN-11AD7119BB：数据类型：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：数据类型与接口定义不符

The candidate posits a data-type mismatch on request payload to API-S-IF2 (GET /api/v1/products/{productId}). The assigned sources define the endpoint and that productId format is validated (permitting INVALID_PRODUCT_ID), but nowhere is 'data type does not conform to interface definition' enumerated as a failure. Only generic interface context; no explicit constraint covering a data-type mismatch on this request.

### GEN-15AF457EE1：唯一性约束：Read or update Refund records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：名称重复或唯一键冲突

唯一性约束异常被绑在物流查询用例的「Read or update Refund records」上，但查询物流是只读 GET 流程，设计证据中的读取对象是 shipment 表与 logistics_event 表，全程没有对 Refund 记录的写入或唯一键约束，也没有名称重复/唯一键冲突的错误码。异常项与宿主用例语义不匹配，仅共享数据库访问这一泛化主题。

### GEN-17344844ED：超时关注点：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：延时是否影响需求满足、后续行为执行或系统与环境协调

超时关注点被挂到 LOGI-EVT-01 的入站事件推送调用上，但设计证据中该接口的备选流程只覆盖签名失败、单号不存在、事件时间非法、幂等重复、事件码非法，没有超时、重试或时限阈值描述；延迟对需求满足的影响完全未定义。仅有接口上下文与泛化时间主题。

### GEN-24E83907B6：资源存在性：Read or update Cart records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：查询、修改或删除不存在资源

Concern is 'internal_database.resource_existence' for 'Read or update Cart records' in 加入购物车. Evidence describes cart_item write and idempotency handling (A5 returns existing entry) but never addresses querying/updating/deleting a non-existent resource, and no error code for missing cart resource exists. Only generic interface context (POST /api/v1/cart/items) supports topic relevance.

### GEN-24F6E7D2F4：数据完整性：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：必填数据缺失或请求体为空

Concern 'api.data.completeness' (必填数据缺失或请求体为空) for POST /api/v1/merchant/products. Evidence shows parameter validation of merchantId/idempotencyKey and no error code covering empty/missing body; only generic interface context supports relevance.

### GEN-252DEF68FD：数据完整性：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：必填数据缺失或请求体为空

Concern 'api.data.completeness' for POST /api/v1/orders/{orderId}/shipments. Evidence validates carrierCode/trackingNumber/shippedItems[] non-empty but its alternative flows only cover order status, tracking format, service unavailability, item ownership and permissions — not a dedicated missing-required-data/empty-body response.

### GEN-280CF8A581：数据大小：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：文件或请求体超过限制

Concern 'api.data.size' (请求体超过限制) for POST /api/v1/orders. Evidence's alternative flows cover price change, stock, address, idempotency, empty cart and service down; no payload-size limit or response is described. Only generic interface context supports relevance.

### GEN-28776040F7：数据长度：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：字符串长度超过限制

Concern 'api.data.length' (字符串长度超过限制) for GET /api/v1/orders/{orderId}/logistics. Evidence only checks orderId format and describes not-shipped/not-found/cache/timeout alternatives; no string-length constraint or its error handling appears.

### GEN-291A7E5B95：数据完整性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：必填数据缺失或请求体为空

Concern 'api.data.completeness' for POST /api/v1/merchant/products/{productId}/publish. Step 6 validates completeness fields (name/description/category/images/SKU) and A1 returns PRODUCT_INCOMPLETE, which is incomplete-data handling on the publish path, but that flow describes product data completeness rather than missing request body/required parameters, so only partial topical support.

### GEN-2B48907944：数据长度：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：字符串长度超过限制

Concern 'api.data.length' (字符串长度超过限制) for LOGI-EVT-01 POST /api/v1/logistics/events. Evidence covers signature validation, trackingNumber existence, eventTime sanity, eventId idempotency and eventCode validity, but no field length constraint or corresponding error is defined.

### GEN-2C31540106：数据格式：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：数据不满足格式规范

Candidate is an api.data.format exception on POST /api/v1/merchant/products for 创建商品. Assigned sections describe parameter validation (merchantId格式合法、idempotencyKey非空) but not a dedicated data-format/规范 check mechanism; no error code for malformed data is defined. The back-alternative flows cover qualification, permission, idempotency and service unavailability only. Generic format-validation topic overlaps, but no explicit constraint supports the format-violation failure; response/recovery remain '待需求确认'.

### GEN-2CF44AD1EB：数据格式：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：数据不满足格式规范

Candidate is an api.data.format exception on POST /api/v1/merchant/products/{productId}/publish for 发布商品. Assigned sections describe version非空、publishAt格式合法 checks and completeness/category-rule alternatives, but no explicit data-format failure, error code or response for the publish request is defined. Only generic request-validation topic overlaps; the failure mechanism and recovery are not supported, remaining '待需求确认'.

### GEN-2D2E542386：数据格式：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：数据不满足格式规范

Candidate is an api.data.format exception on POST /payment/v1/payments for 支付订单. Assigned sections include parameter checks (orderId格式合法、amount>=0、paymentMethod合法、notifyUrl非空、idempotencyKey非空) and alternatives A1-A6 (status, amount mismatch, service unavailability, cancellation, idempotency), but none explicitly covers malformed/format-nonconforming payload with a defined response. Generic request-validation topic overlaps; the format-failure behavior and recovery remain '待需求确认'.

### GEN-2E4C702771：数据合法性：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：非法字符、不允许字段或非法取值

Candidate is an api.data.legality exception (非法字符、不允许字段或非法取值) on POST /api/v1/merchant/products/{productId}/publish for 发布商品. Assigned sections validate version非空 and publishAt格式合法 and define completeness, category-rule, status and version-conflict alternatives, but never reference illegal characters, disallowed fields or illegal values with a defined response. Generic request-validation topic only; behavior and recovery are '待需求确认'.

### GEN-2F24462982：数据完整性：调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「调用 API-R-IF1：POST /api/v1/orders/{orderId}/refunds」时：必填数据缺失或请求体为空

Candidate is an api.data.completeness exception (必填数据缺失或请求体为空) on the refund application call for 申请退款. Assigned sections check orderId格式合法、items[]非空、reasonCode合法、requestedAmount>=0、idempotencyKey非空 and define alternatives A1-A5 (window, amount, order status, service availability, idempotency), but no explicit missing-required-data/empty-body error or response is described. Generic request-validation topic overlaps; response and recovery remain '待需求确认'.

### GEN-2FF8201A3B：数据格式：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：数据不满足格式规范

Candidate is an api.data.format exception on POST /api/v1/orders/{orderId}/shipments for 商家发货. Assigned sections check orderId格式合法、carrierCode合法、trackingNumber非空、shippedItems[]非空 and define INVALID_TRACKING_NUMBER for tracking number format, but no explicit failure mechanism or response for format-nonconforming shipment payload beyond tracking number is described. Generic request-validation topic overlaps; behavior and recovery remain '待需求确认'.

### GEN-32EB226631：数据完整性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：必填数据缺失或请求体为空

候选针对 API-L-IF2（GET /api/v1/orders/{orderId}/logistics）请求体数据完整性问题（「必填数据缺失或请求体为空」）。该接口是 GET 且路径参数仅 orderId，基本流程与备选流程只涉及订单未发货、本地物流不存在、外部服务失败等情形，既无请求体也无必填数据缺失分支；请求体为空的假设与该接口语义冲突。

### GEN-5F310AFEA0：数据库可用性：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：连接失败或数据库宕机

Candidate asserts internal_database.availability (connection failure/DB outage) when reading or updating Category records in POST /api/v1/merchant/products. Evidence for UCG-004-UC001 (439-446, 930-972, 1176-1181) shows only merchant qualification and idempotency handling on the product/merchant tables; no category access is described at all, and A1-A4 cover 403/503 service unavailability (MERCHANT_SERVICE_UNAVAILABLE) but not database-level availability on matching records. The asserted DB-availability behavior is essentially absent from the assigned sections.

### GEN-5F9827876B：持久化能力：Read or update SKU records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：写入失败或事务回滚

Candidate asserts internal_database.persistence (write failure/transaction rollback) on 'Read or update SKU records' within GET /api/v1/products/{productId}. Evidence (516-556, 1122-1127) describes a pure read path: ProductCatalogService queries the product table and returns details; no SKU write or transaction is described, and A1-A6 cover INVALID_PRODUCT_ID, PRODUCT_NOT_FOUND, PRODUCT_OFF_SHELF, timeouts and service unavailable — none involving write persistence or rollback. The asserted persistence-failure mechanism has no explicit basis here.

### GEN-61B6E05B7A：唯一性约束：Read or update OrderItem records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：名称重复或唯一键冲突

候选针对支付订单流程中「Read or update OrderItem records」的唯一性约束异常。所分配证据仅描述 order 表查询、payment 表写入、order 状态更新及幂等处理（idempotencyKey、paymentId 幂等），未提及 OrderItem 记录的读取/更新，也未定义任何唯一性约束或名称重复/唯一键冲突的处理。属通用支付主题关联，无具体接口或约束证据支持该失败机制。

### GEN-62024FBD12：查询性能：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：大表联查超时

候选针对设置库存与价格流程中「Read or update Category records」的大表联查超时。证据仅覆盖 sku 表写入、product 表 version 乐观锁、SKU 校验与备选流程（NEGATIVE_STOCK、INVALID_PRICE、DUPLICATE_SKU、VERSION_CONFLICT、PRODUCT_NOT_FOUND），完全未涉及 Category 记录的读取/更新，也无任何查询性能或超时约束描述。仅主题（库存价格维护）相关。

### GEN-67A9C8BE47：必填字段完整性：Read or update Refund records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：必要字段缺失

候选针对查询物流信息流程中「Read or update Refund records」的必填字段完整性异常。证据仅描述 shipment 表与 logistics_event 表的查询、本地数据过期判定及 LogisticsService 回退，完全未涉及 Refund 记录的读取/更新，也无任何必填字段缺失的约束或错误定义（备选流程仅含 ORDER_NOT_SHIPPED、LOGISTICS_NOT_FOUND、CACHE 回退、LOGISTICS_SERVICE_UNAVAILABLE）。仅主题相关，缺乏对失败机制的支持。

### GEN-6A05A922D8：持久化一致性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：操作结果未可靠持久化或局部成功

The candidate concerns persistence consistency failure (operation result not reliably persisted or partial success) during the API-C-IF1 add-to-cart flow, which writes to the cart_item table (step 9). The evidence describes the write operation and idempotency check but never addresses transactional guarantees, partial-success scenarios, retry semantics, or rollback behavior. No explicit constraint or failure mechanism for persistence inconsistency is stated. The concern is only generically about data persistence on CartService with no supporting detail for the failure scenario.

### GEN-6A8823FAD3：数据完整性：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：必填数据缺失或请求体为空

The candidate concerns data completeness (missing required data or empty request body) for LOGI-EVT-01 (POST /api/v1/logistics/events), whose basic flow validates signature, trackingNumber, eventTime reasonableness, and eventId idempotency. There is no explicit required-field completeness constraint or empty-request-body validation described. The alternate flows A1-A5 cover signature, tracking number, event time, eventId duplication, and invalid event code—but not missing required fields or empty body. The evidence only generically lists request body fields without a completeness rule for the failure mechanism.

### GEN-735FF66A37：渲染性能：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：渲染耗时影响用户后续操作

场景关注点为『渲染耗时影响用户后续操作』(service.display_interaction.render_performance)，触发节点为调用 GET /api/v1/products。证据确证该接口存在、参数与响应结构，以及第6步系统『将结果转换为前端展示结构』返回 items[]（存在展示转换，因此与展示层有一般性关联）。但所有备选流程 A1–A7 只涉及参数非法、分类失效、空结果、超时、服务不可用、状态变更过滤与字段缺失，没有任何关于渲染耗时的定义，也没有该关注点对应的交互/前端章节证据，仅有通用展示转换上下文。支持度仅停留在泛主题层面，缺失度极高。

### GEN-7DBFAC465E：数据大小：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：文件或请求体超过限制

Concern api.data.size (request body exceeds limit) applied to POST /api/v1/orders/{orderId}/shipments. The assigned detail section fully enumerates alternative flows A1-A5 (order status, tracking number format, LogisticsService unavailability, invalid shippedItems, permission denied) and none addresses request/body size limits; the SR section likewise covers only state/format/service errors. No max size, HTTP status or error code for oversized payloads is stated, so the behavior is essentially unspecified for this interface.

### GEN-8C1871BEFC：关联一致性：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：级联删除失效或子对象残留

Concern internal_database.referential_consistency for 'Read or update Category records' is only topically adjacent: the refund flow reads order and order_item tables and writes the refund table (with order_id/customer_id references), but the nominated target 'Category records' is not read or written anywhere in the refund detail flow. No cascade-delete or orphan-residual behavior is described for any table in this use case; extension paths cover only refund window, amount, order status, PaymentService availability and idempotency.

### GEN-B0214B43DC：唯一性约束：Read or update SKU records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：名称重复或唯一键冲突

关注点为 internal_database.uniqueness（SKU 唯一/名称重复），但分配给 UCG-001-UC002 查看商品详情（API-S-IF2，GET /api/v1/products/{productId}）的章节只描述商品详情只读查询与 product 表字段读取，从未提到 SKU 记录写入、名称唯一键或唯一性冲突。异常与恢复方式确实为“待需求确认”，但该用例本身不含任何支持唯一性失败机制的证据，仅共享“商品/SKU”这一泛化主题。

### GEN-B13CF70E86：数据长度：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：字符串长度超过限制

关注点 api.data.length 被挂到 API-L-IF2 物流查询调用上。分配的章节确实给出该接口路径、请求参数 orderId 与响应字段 trackingNumber/status/events[]/lastUpdatedAt/dataSource，并列出 ORDER_NOT_SHIPPED、LOGISTICS_NOT_FOUND、CACHE、LOGISTICS_SERVICE_UNAVAILABLE 等备选流程，但从未规定任何字符串长度限制，也未描述长度超限的响应。属仅共享特定接口上下文的泛化约束。

### GEN-B15CF36573：数据合法性：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：非法字符、不允许字段或非法取值

关注点 api.data.legality 断言于 API-O-IF1 创建订单。分配章节确有请求参数校验步骤（cartItemIds 非空、addressId 格式、confirmedAmount>=0、idempotencyKey 非空）及 A1–A6 备选流程，但其中未出现“非法字符、不允许字段或非法取值”的字段合法性规则，也无对应错误码或恢复策略；触发条件与文档描述不一致。

### GEN-B1BBA0BBD4：必填字段完整性：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：必要字段缺失

关注点 internal_database.required_field_completeness 被指派到“Read or update Category records”，但分配章节显示 UCG-004-UC001 创建商品流程只写 product 表（product_id、merchant_id、name、description、category_id、status、version 等），未描述 category 表记录的必填字段完整性校验，也无该异常的错误码与恢复方式。

### GEN-B2A9ED0EF8：数据库可用性：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：连接失败或数据库宕机

关注点 internal_database.availability（连接失败/数据库宕机）挂到发布商品流程中的“Read or update Category records”。分配的 UCG-004-UC004 章节虽含 category 表查询（步骤7）与 PRODUCT_INCOMPLETE、CATEGORY_RULE_VIOLATION、VERSION_CONFLICT、SYNC_PENDING 等备选流程，但均针对资料/规则/版本冲突，未描述数据库不可用或连接失败场景。

### GEN-B2A9FBC71E：资源存在性：Read or update Payment records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：查询、修改或删除不存在资源

关注点 internal_database.resource_existence 被指派到“Read or update Payment records”，而分配的 UCG-002-UC003 查看订单详情章节只读查询 order、order_item、payment、shipment 表并组合展示；备选流程覆盖 orderId 格式错误、越权、订单不存在（ORDER_NOT_FOUND）、未发货与超时，但未涉及 payment 记录不存在或对其修改/删除的场景。

### GEN-B334B476D1：持久化能力：Read or update Shipment records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：写入失败或事务回滚

关注点 internal_database.persistence（写入失败/事务回滚）挂到 UCG-003-UC001 商家发货的“Read or update Shipment records”。分配章节确有 shipment 表写入（步骤7）、order 状态更新（步骤8）与 LogisticsService 不可用时的待同步重试（A3），但未描述 shipment 写入失败或事务回滚的检测、响应与恢复策略，异常仍为待需求确认。

### GEN-B3B8DFC01C：资源存在性：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：查询、修改或删除不存在资源

关注点 internal_database.resource_existence 复用于同一交换 EXCH-010DB12E2B（API-M-IF1 创建商品）的“Read or update Category records”。分配章节仅描述 merchant 表资质校验、幂等校验与 product 表写入，未出现 category 记录查询/修改/删除不存在资源的判定，也无该情形下的错误码与恢复方式。

### GEN-BDFE7023D6：必填字段完整性：Read or update OrderItem records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：必要字段缺失

候选关注点为 internal_database.required_field_completeness，触发于「Read or update OrderItem records」必要字段缺失。但分配证据中 UCG-002-UC002 支付订单流程只涉及 order 表（order_id、customer_id、status、payable_amount、expire_at）与 payment 表字段，全程未出现 OrderItem 记录的读写步骤，备选流程 A1–A6 也无任何必填字段完整性校验条目。仅能确认该用例属于支付主题，缺少直接支撑该失效机制的证据。

### GEN-C4F606A5C7：并发一致性：Read or update OrderItem records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：并发更新冲突或后写覆盖前写

支付订单用例通过idempotencyKey与支付回调幂等处理（A5、A6）处理重复通知，但证据中从未出现OrderItem记录的并发更新、乐观锁或后写覆盖前写的机制；候选将并发一致性关联到'Read or update OrderItem records'，来源仅支持幂等主题，属泛化关联，支持度低、缺失度高。

### GEN-C661DBEB6B：唯一性约束：Read or update Payment records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：名称重复或唯一键冲突

查看订单详情证据仅涉及订单/条目/支付/物流表查询与ORDER_NOT_FOUND、ORDER_ACCESS_DENIED、ORDER_SERVICE_TIMEOUT等错误，查询型用例不涉及写入或唯一键约束；候选将'名称重复或唯一键冲突'关联到payment记录的读操作，来源无任何唯一性约束描述，支持度低、缺失度高。

### GEN-D0CCAFB1EE：关联一致性：Read or update Refund records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：级联删除失效或子对象残留

Evidence covers the logistics-query use case and its DB reads (shipment, logistics_event tables via LogisticsServiceAdapter), which establishes the general data context. However, the specific concern — cascade delete failure or orphan child rows (referential consistency on Refund records) — is not addressed anywhere; no refund-table operations, cascade semantics, or FK integrity rules appear in the supplied sections. Only generic topic-level relevance.

### GEN-D560AD285F：数据长度：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：字符串长度超过限制

触发条件为「字符串长度超过限制」，但源章节对 GET /api/v1/products/{productId} 只写了 productId 格式校验与 INVALID_PRODUCT_ID/PRODUCT_NOT_FOUND/PRODUCT_OFF_SHELF 等备选流程，未提及任何长度上限、字段长度规则或长度相关的错误码与响应。候选仅与「查看商品详情接口的输入校验」这一泛化主题相关，缺乏对长度失败机制的显式约束。

### GEN-DA6C881968：关联一致性：Read or update Payment records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：级联删除失效或子对象残留

查看订单详情流程确有查询payment表（第7步）及shipment表（第8步），属于读操作上下文，但'级联删除失效或子对象残留'涉及写路径与删除语义，用例全程只读、无删除或子对象清理描述，仅为泛化的数据库关联一致性话题，缺乏具体支撑。

### GEN-DB928F534A：数据大小：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：文件或请求体超过限制

关注点为api.data.size（请求体/文件超限），但所给证据只描述UCG-003-UC003查询物流信息的GET接口API-L-IF2（路径参数orderId，无请求体），基本流程为token校验、orderId格式校验、查order表、LogisticsServiceAdapter查shipment与logistics_event、过期则调用外部、返回trackingNumber/status/events[]/lastUpdatedAt/dataSource。备选流程仅覆盖A1订单未发货409、A2本地数据不存在404、A3外部失败回退缓存、A4已签收、A5适配器不可用503，均与数据大小限制无关。GET请求无请求体，故该关注点与接口语义基本不匹配，仅共享同一接口的通用话题。

### GEN-E370ED9096：超时关注点：调用 API-O-IF1：POST /api/v1/orders

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「调用 API-O-IF1：POST /api/v1/orders」时：延时是否影响需求满足、后续行为执行或系统与环境协调

关注点为 common.timeout（调用 POST /api/v1/orders 时的延时），但所属章节的扩展路径仅覆盖价格变化、库存不足、重复提交（170-181），接口详情备选流程仅覆盖 PRICE_CHANGED、OUT_OF_STOCK、INVALID_ADDRESS、幂等重复、CART_EMPTY、PRODUCT_SERVICE_UNAVAILABLE（641-654），均未描述超时/延时场景的响应或恢复方式。支持仅停留在该 SSD 交换与接口存在这一通用层面，无任何超时约束、超时阈值或超时处理行为的语义证据。

### GEN-E3D63F9584：关联一致性：Read or update Cart records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：级联删除失效或子对象残留

关注点为internal_database.referential_consistency（级联删除失效或子对象残留），目标是Cart记录。证据中该流程为写cart_item表并计算购物车总数与金额汇总（第9步），备选流程涉及数量非法400、商品下架410、库存不足409、同SKU累加并校验限购上限409、idempotencyKey重复返回已有条目、ProductCatalogService不可用503。全部内容均为写入与校验，没有任何删除操作、外键级联或子对象清理语义，故与关注点仅共享“购物车数据操作”这一泛化话题，无实质支撑。

### GEN-EDB6A97EF5：持久化能力：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：写入失败或事务回滚

Candidate concerns persistence failure of 'Read or update Category records' during 发布商品. Assigned design detail evidence shows category table access only as a read for rule validation (step 7), and alternate flows enumerate PRODUCT_INCOMPLETE, CATEGORY_RULE_VIOLATION, INVALID_PRODUCT_STATUS, VERSION_CONFLICT, CATALOG_SYNC_FAILED — none covering database write failure or transaction rollback on category records. Only generic topical match (category data access exists, write-failure behavior unspecified).

### GEN-EEE3F596EA：唯一性约束：Read or update Category records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：名称重复或唯一键冲突

Candidate concerns uniqueness/label-duplication failure on 'Read or update Category records' during 申请退款. Assigned evidence describes refund persistence into refund table with idempotencyKey-based idempotency and alternate flows about refund window, amount, order status, PaymentService availability — no category record write, no name/uniqueness constraint conflict. Only generic topical overlap (DB writes and uniqueness-like idempotency concepts exist).

### GEN-F0064F1F05：数据长度：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：字符串长度超过限制

Candidate concerns string-length overflow on the payment response payload of POST /payment/v1/payments. Assigned evidence defines response fields (paymentId, paymentStatus, paidAt, providerTradeNo) and alternate flows addressing order status, amount mismatch, service unavailability, cancellation, idempotency — no length constraint, no field length handling. Generic topical match only (response payload described).

### GEN-F0B79B061E：字段合法性：Read or update Payment records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：类型错误、非法字符或超长

Candidate concerns field validity (wrong type, illegal chars, overlong) on 'Read or update Payment records' during 查看订单详情. Assigned evidence covers order-detail query path with payment table read (payment_id, method, provider_trade_no, status, paid_at) and alternate flows INVALID_ORDER_ID, ORDER_ACCESS_DENIED, ORDER_NOT_FOUND, empty shipment, timeout — all about orderId and access, not payment field type/charset/length validation. Generic topic only (payment records are read).

### GEN-F1F4E0081C：数据合法性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：非法字符、不允许字段或非法取值

Candidate concerns request-payload legality (illegal chars, disallowed fields, illegal values) for GET /api/v1/orders/{orderId}/logistics. Assigned evidence describes the interface with only orderId parameter validated for format legality, and alternate flows about unshipped order, missing local data, external timeout, delivered, adapter unavailable — no illegal-character/disallowed-field/illegal-value checks on the request. Generic interface context only.

### GEN-F25B4A4775：数据合法性：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：非法字符、不允许字段或非法取值

Candidate concerns response-payload legality (illegal chars, disallowed fields, illegal values) on POST /api/v1/cart/items. Assigned evidence defines the request validations (productId/skuId format, quantity>=1, idempotencyKey non-empty) and alternate flows INVALID_QUANTITY, PRODUCT_OFF_SHELF, OUT_OF_STOCK, PURCHASE_LIMIT_EXCEEDED, duplicate key, service unavailable; the response legality failure mode is not described. Generic topic (response body exists) only.

### GEN-F3E9616DBE：持久化能力：Read or update LogisticsEvent records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：写入失败或事务回滚

Candidate concerns persistence failure of 'Read or update LogisticsEvent records' on LOGI-EVT-01. Assigned evidence shows logistics_event table write with eventId idempotency and shipment summary update, with alternate flows INVALID_SIGNATURE, TRACKING_NUMBER_NOT_FOUND, INVALID_EVENT_TIME, duplicate event, INVALID_EVENT_CODE — none covering write failure or transaction rollback on LogisticsEvent records. Generic topical match (record writes are described).

### GEN-F66EEEE418：关联一致性：Read or update Shipment records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：级联删除失效或子对象残留

Sections describe shipment creation writing shipment table and updating order status; there is no cascade-delete or orphaned-child-object semantics anywhere in the assigned evidence. 'Read or update Shipment records' is inferred at AR level. The proposed failure mechanism (级联删除失效或子对象残留) is not addressed at all.

### GEN-F6B6716AB1：并发一致性：Read or update Product records

推荐评分：0.4450；支持度：0.2500；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：并发更新冲突或后写覆盖前写

The browse-products design is a read-only GET with no write path; no concurrency-control (lock/version) description exists for Product records. Assigned evidence mentions A6 (status changed to OFF_SALE during query) which is an incidental-change note, not a concurrency-consistency guarantee. The scenario's concurrency conflict mechanism is unsupported.

### GEN-0807CDC1A9：并发一致性：Read or update Cart records

推荐评分：0.4400；支持度：0.5000；缺失度：0.3000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「Read or update Cart records」时：并发更新冲突或后写覆盖前写

Candidate is a generic DB concurrency exception (concurrent update conflict / lost update) on 'Read or update Cart records' produced by the concern registry. The assigned sections describe cart_item writes and same-SKU accumulation, and include idempotency handling by idempotencyKey (A5) which covers duplicate-request idempotency, but they neither state nor exclude concurrent-update/lost-update controls. The no-full/partial-match precondition plus a concrete interface and table-write context justifies 0.5 support. Missingness is moderate: while no concurrency mechanism is documented, the section labels the topic with an explicit '待需求确认' style exception, and idempotency partially addresses near-domain cases, so the behavior is not described but is also not contradicted.

### GEN-265E452FD4：资源存在性：Read or update Category records

推荐评分：0.4400；支持度：0.5000；缺失度：0.3000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：查询、修改或删除不存在资源

Concern is resource existence for the Category/SKU read-update during 设置库存与价格. Design directly specifies A5: 商品不存在 → PRODUCT_NOT_FOUND (HTTP 404), and basic flow step 5 queries the product table validating SKU data, while the resource-存在性 mechanism (querying/updating a nonexistent record) is concretely evidenced. Applicability slightly loose because the concrete error is framed around 商品 rather than Category table, but the resource-existence mechanism is well supported.；支持度复核：Candidate concern is 'internal_database.resource_existence' for Category records, trigger '查询、修改或删除不存在资源'. Cited evidence index 1 gives A5 商品不存在 → PRODUCT_NOT_FOUND (404) and basic flow step 5 queries the product table, but the constraint addresses the product entity, not the Category table the concern names. The resource-existence mechanism (operating on a nonexistent record) is touched only by analogy; the document never specifies Category record existence, a Category-specific 404, or Category read/update handling. This is a related operation/interface without an entity-matching mechanism constraint, i.e., context. Also the candidate itself is unreviewed and its expected_result/recovery are 待需求确认, so no constraint closes the Category-specific failure. Cannot upgrade to explicit_constraint by inferring Category behavior from the product rule.

### GEN-02F1D20F6A：幂等性：Read or update Category records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：重复请求导致重复操作异常

Concern is internal_database.idempotency on SKU/price update (API-M-IF3). Assigned sections describe version/optimistic-lock and SKU uniqueness/DUPLICATE_SKU but no idempotency key or duplicate-request behavior is specified. Evidence is partially relevant yet non-supporting for idempotency.

### GEN-095279A263：查询性能：Read or update Refund records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：大表联查超时

Candidate claims a query-performance exception ('大表联查超时') on 'Read or update Refund records' during 查询物流信息. The assigned sections describe a logistics query that reads shipment and logistics_event tables (with ordering and freshness/threshold logic) and an adapter timeout alternative (A3/A5), but never reference 'Refund records' nor any large-join timeout on refunds. The topic is generic performance rather than specific supported content, so 0.25. Missingness high: the cited failing operation appears unrelated to this use case, and no assigned line addresses refund record queries or join timeouts.

### GEN-0C3FC4D752：数据大小：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：文件或请求体超过限制

Candidate is an API data-size exception ('文件或请求体超过限制') on API-S-IF1 GET /api/v1/products. The assigned sections are a read-only product listing with query-parameter validation (page>=1, pageSize<=100, minPrice/maxPrice) and explicitly address invalid query parameters, invalid category, timeouts and unavailability — none of which is a file/body size limit. Size limits are not mentioned; the interface uses query parameters rather than a body, making the described mechanism only generically related. Support 0.25. Missingness high: no assigned line addresses size constraints for this endpoint.

### GEN-1220FCB729：数据格式：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：数据不满足格式规范

Candidate describes response data that does not conform to a format spec on API-S-IF1. Sources define the response schema and an A7 branch for missing mandatory fields, but there is no specification of a 'format violation' fault class on the response. Only generic response-format context; precise violation behavior is absent.

### GEN-20599B6077：数据类型：调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「调用 API-M-IF3：PUT /api/v1/merchant/products/{productId}/skus」时：数据类型与接口定义不符

Scenario asserts a 'data type mismatch' exception at API-M-IF3 (PUT /api/v1/merchant/products/{productId}/skus). The SR detail section defines parameter presence/format checks (skus[] non-empty, skuId format, stock>=0, salePrice>=0, originalPrice>=0, version non-empty) and alternative flows for NEGATIVE_STOCK, INVALID_PRICE, DUPLICATE_SKU, VERSION_CONFLICT, PRODUCT_NOT_FOUND — but none of these is a type-mismatch rule (e.g., non-integer stock), and no error code, response shape or recovery is specified for that case. Only generic interface context (path, key params) is supplied, so support is weak while the gap is explicit ('待需求确认').

### GEN-217F34CBEA：资源存在性：Read or update Category records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：查询、修改或删除不存在资源

Candidate asserts a resource-existence failure for 'Read or update Category records' inside 申请退款 (API-R-IF1). The assigned refund design detail never touches Category records; it describes RefundService reading order/order_item, refund-window and amount checks, refund table writes, and PaymentService interaction. No category table is referenced in any assigned section, so there is no supporting evidence for the claimed entity; the required existence-failure behavior for Category records is wholly undescribed (expected_result/recovery '待需求确认'). Support is effectively generic topic routing only.

### GEN-233718120A：数据大小：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：文件或请求体超过限制

Candidate asserts a 'file or request body exceeds limit' (data size) failure on API-O-IF2 (GET /api/v1/orders/{orderId}) during 查看订单详情. The assigned detail defines only the orderId format check and alternative flows (INVALID_ORDER_ID, ORDER_ACCESS_DENIED, ORDER_NOT_FOUND, empty shipment summary, ORDER_SERVICE_TIMEOUT); there is no request-body size limit, payload-cap rule, or size-check step anywhere in the assigned sections. Since the operation is a path-parameter GET, the premise is also conceptually weak. No explicit evidence supports this failure mechanism.

### GEN-24C22B75A5：数据大小：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：文件或请求体超过限制

Candidate asserts a 'file or request body exceeds limit' (data size) failure on API-M-IF1 (POST /api/v1/merchant/products) during 创建商品. The assigned detail validates merchantId format and non-empty idempotencyKey and lists alternative flows (MERCHANT_NOT_QUALIFIED, PERMISSION_DENIED, idempotent duplicate, MERCHANT_SERVICE_UNAVAILABLE), with product fields including name/description/category_id. No imageUrls[] size rule, request-body limit, or payload-cap check appears in the assigned sections (the V5 chain line merely lists request fields). Note the interface description at one source includes imageUrls[] while the detail flow only passes merchantId/idempotencyKey — an internal inconsistency, but neither mentions size constraints. Support is topical only.

### GEN-300C1C77E1：持久化能力：Read or update Product records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：写入失败或事务回滚

候选把「写入失败或事务回滚」挂在 API-S-IF1（GET /api/v1/products，SR 步骤2）的 Product 持久化上，但该接口语义是只读检索产品表，扩展路径 A4/A5 描述的是目录服务超时/不可用，A6 是查询期间状态被改；没有任何写入或事务证据。被分配章节完全未描述持久化写入失败的事务回滚行为，属于对只读路径强加写事务异常。

### GEN-50CF959F96：数据库可用性：Read or update SKU records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：连接失败或数据库宕机

候选针对 API-S-IF2 中“Read or update SKU records”的数据库可用性（连接失败或宕机）。证据中该用例明确记录的是 ProductCatalogService 层面的可用性/超时：A4 PRODUCT_SERVICE_TIMEOUT(504)、A5 PRODUCT_SERVICE_UNAVAILABLE(503)；对底层数据库连接失败、宕机没有任何描述，SR 需求章节亦无数据库可用性约束。该候选仅与本用例主题相关，缺乏针对数据库可用性失败机制的具体支持。

### GEN-5215C5FEB6：关联一致性：Read or update LogisticsEvent records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：级联删除失效或子对象残留

候选检查“Read or update LogisticsEvent records”的关联一致性（级联删除失效或子对象残留）。证据显示流程为 logistics_event 与 shipment 的写入及摘要更新（含 eventId 幂等、trackingNumber 存在性校验），但没有任何删除操作、级联规则或子对象残留检测的描述；备选流程仅覆盖签名、单号不存在、时间不合理、重复事件与非法 eventCode。仅与持久化主题相关，无一致性失败机制证据。

### GEN-533C8BD9C0：必填字段完整性：Read or update SKU records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：必要字段缺失

Candidate injects a required-field-completeness exception on 'Read or update SKU records' into 查看商品详情 (API-S-IF2). The assigned SR/design evidence for UCG-001-UC002 describes a GET product-detail read path (productId, name, description, price, stockStatus, images[]) and its alternatives only cover INVALID_PRODUCT_ID, PRODUCT_NOT_FOUND, PRODUCT_OFF_SHELF, service timeout/unavailable, and non-critical display field absence. No SKU record read/update, no required-field check, and no SKU persistence step appear, so the failure mechanism is not supported by the cited steps—only the generic '商品详情查询' topic overlaps.

### GEN-54259CC79E：字段合法性：Read or update OrderItem records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：类型错误、非法字符或超长

Candidate places an internal_database.field_validity exception on 'Read or update OrderItem records'. The payment-order evidence does mention OrderService querying the order table (order_id, customer_id, status, payable_amount, expire_at) but never describes reading/updating order_item records nor type/charset/length validation on them. Field-format validation in the cited flow concerns request parameters (orderId, paymentMethod, notifyUrl, idempotencyKey), not OrderItem columns, so no explicit constraint supports this failure mechanism.

### GEN-5472ADDF19：数据库可用性：Read or update Shipment records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：连接失败或数据库宕机

Candidate asserts an internal_database.availability failure on 'Read or update Shipment records' for 商家发货. The assigned evidence does describe OrderService writing the shipment table (step 7: shipment_id, order_id, carrier_code, tracking_number, ...) and updating order status, and A3 covers external LogisticsService unavailability, but nowhere does it describe DB connection failure or database downtime, nor the resulting response. Generic persistence context exists, but the specific availability-triggered failure is unstated.

### GEN-54D7CBE58D：幂等性：Read or update Category records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：重复请求导致重复操作异常

Candidate raises an internal_database.idempotency exception on 'Read or update Category records' in 申请退款. The cited refund evidence does contain idempotency handling (RefundService按 idempotencyKey 执行幂等校验; A5 idempotencyKey重复返回已有退款单), giving topical overlap, but it is tied to the RefundService/refund table and never to Category record read/update. No Category access occurs in the described flow, so the failure mechanism and its target node are not supported.

### GEN-578E0E5F05：数据长度：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：字符串长度超过限制

Candidate asserts an api.data.length exception on POST /api/v1/merchant/products/{productId}/publish (publishAt/version). The supplied evidence for UCG-004-UC004 details parameter checks (version非空、publishAt格式合法) at lines 1089-1090 and alternative flows A1-A5 (1099-1109), but none mention any length limit or overflow on publish parameters; the failure mechanism (string length exceeding a limit) is only generically related to API parameter description conventions absent the domain schema.

### GEN-6799F1828B：数据范围：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：数值超出允许范围

Candidate asserts a numeric-out-of-range failure in the GET /api/v1/products/{productId} response. Assigned evidence shows only productId format validation and alternates for invalid id, not found, off-sale, timeout, unavailability, and missing non-critical display fields (lines 540-556); no numeric range constraint on response values is described anywhere. Relevance to the interface is generic (same API surfaced), but the failure mechanism is unsupported and unambiguously absent from the assigned sections.

### GEN-6EBA9383BA：查询性能：Read or update Category records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：大表联查超时

Candidate asserts internal_database.query_performance failure (large-table join timeout) at the Category read path of API-M-IF2. The section only mentions querying category table for category_id and status; no join shape, index, latency budget or timeout threshold is given, and no备选流程 branch addresses slow queries. Only generic topical overlap with a database read exists.

### GEN-70E1A2766D：数据完整性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：必填数据缺失或请求体为空

Candidate asserts api.data.completeness failure on GET /api/v1/orders/{orderId}/logistics with trigger '必填数据缺失或请求体为空'. The API is a GET with a single path parameter (orderId); no request body exists, so the trigger is semantically mismatched. The section specifies orderId format validation and a LOGISTICS_NOT_FOUND branch for absent local data, which addresses responses rather than request completeness; missing-data semantics for the response fields remain unspecified.

### GEN-74E776479F：资源存在性：Read or update Refund records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：查询、修改或删除不存在资源

场景声称在物流查询用例中对「Read or update Refund records」触发『查询、修改或删除不存在资源』(internal_database.resource_existence)。物流查询接口证据确实描述了读取 shipment 表与 logistics_event 表并在本地数据缺失/过期时行为，且备选流程 A2 存在 LOGISTICS_NOT_FOUND（本地物流数据不存在）——与『资源不存在』类语义在概念上有弱关联。但该分支针对的是 logistics 数据，而非候选步骤所写的 Refund records；物流查询用例中根本没有对 Refund 记录的读/改/删操作，关注点对象与用例语义错配。仅能算泛主题关联，支持度低，缺失度高。

### GEN-758A23C15F：资源存在性：Read or update Order records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC001：创建订单（158-182行） → UCG-002-UC001 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC001-API-O-IF1 创建订单（383-390行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC001-API-O-IF1 创建订单（605-654行） → UCG-002-UC001 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC001：创建订单（1134-1139行） → UCG-002-UC001 / 步骤 4

建议补充：执行「Read or update Order records」时：查询、修改或删除不存在资源

场景为创建订单时对「Read or update Order records」触发『查询、修改或删除不存在资源』(internal_database.resource_existence)。证据确证创建订单流程会写入 order 表与 order_item 表，并以 orderId 返回、可按 idempotencyKey 幂等返回已有订单（A4）。这与订单记录的存在性有一定接触，但候选触发点是读取/更新不存在的 Order 记录，而源证据中的备选流程 A1–A6 全部涉及价格、库存、地址、购物车为空、幂等与服务不可用，没有『订单不存在』的错误码或响应。接口仅为写入语义，与所述失败机制不匹配。支持度低，缺失度高。

### GEN-758EFD5D32：并发一致性：Read or update Category records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：并发更新冲突或后写覆盖前写

场景关注『并发更新冲突或后写覆盖前写』(internal_database.concurrency_consistency)，触发节点为对「Read or update Category records」的读写。证据确证创建商品接口存在且商品表含 version 字段（第7步生成 productId 和初始 version），version 字段是乐观并发的常见载体，构成非常间接的关联。但证据中没有 category 记录的读/改语义，也没有任何并发控制、冲突检测或 version 比较失败的分支（备选流程 A1–A4 仅覆盖资质、权限、幂等与服务不可用）。所述失败机制未被描述。支持度低，缺失度高。

### GEN-764C8A64DC：关联一致性：Read or update Product records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：级联删除失效或子对象残留

场景关注『级联删除失效或子对象残留』(internal_database.referential_consistency)，触发节点为对「Read or update Product records」的读写。证据确证浏览商品流程读取 product 表并返回字段集（不含删除语义），备选流程 A6/A7 仅在返回前过滤下架商品或采用缺省值展示。浏览商品用例本身不涉及任何删除、级联或子对象关联操作，源证据中无引用完整性、外键或级联删除的任何描述。支持度仅泛主题级，缺失度高。

### GEN-80BBDBE2D7：数据合法性：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：非法字符、不允许字段或非法取值

Concern api.data.legality (illegal characters, disallowed fields, illegal values) for PUT /api/v1/merchant/products/{productId}. Assigned sections describe field-level validation of name/description length, categoryId format, imageUrls[] format/count, and optimistic-lock version conflicts (A1-A5), but do not define a general legality rule set for characters/disallowed fields or an associated error response. Partially covered by existing validation descriptions while the specific failure mechanism remains undefined.

### GEN-8374E4EDBB：数据完整性：调用 API-O-IF2：GET /api/v1/orders/{orderId}

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「调用 API-O-IF2：GET /api/v1/orders/{orderId}」时：必填数据缺失或请求体为空

Concern api.data.completeness (missing required data or empty request body) attached to GET /api/v1/orders/{orderId}. The only request parameter is the path orderId, and assigned sections define INVALID_ORDER_ID (format) and ORDER_NOT_FOUND but never describe an empty body or missing-required-field case for this GET; the concern appears weakly applicable and its handling is unspecified.

### GEN-84AE56AE64：权限控制：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：水平越权或垂直越权

Concern human.authorization (horizontal/vertical privilege escalation) attached to GET /api/v1/products/{productId}. Assigned sections state the interface permits anonymous access and optionally accepts a valid token, with alternatives limited to format, not-found, off-shelf and service errors; no authorization or privilege-escalation check or error response is defined. The behavior is effectively unaddressed for this interface.

### GEN-8D10EB9190：查询性能：Read or update Category records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「Read or update Category records」时：大表联查超时

internal_database.query_performance (大表联查超时) for 'Read or update Category records' is only topically adjacent. The create-product detail flow references the merchant table and writes the product table with category_id, but the nominated target 'Category records' is not queried in this use case, and no join table, index, timeout threshold, or slow-query behavior is described. A4 addresses MerchantProductService unavailability (503), not a database query timeout, so no explicit performance constraint supports the failure mechanism.

### GEN-8E48196DDC：数据库可用性：Read or update OrderItem records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「Read or update OrderItem records」时：连接失败或数据库宕机

候选场景为「Read or update OrderItem records」时数据库连接失败/宕机（internal_database.availability）。所引段落仅描述支付订单主流程与 PaymentService/PaymentAdapter 相关的 HTTP 409/400/503 与幂等分支（A1-A6），未提及任何数据库可用性、连接失败或 OrderItem 表读写失败的机制；OrderItem 仅在创建订单流程的 order_item 表写入中被间接触及，本用例段落中无对应描述。故仅有泛化的『订单相关数据操作』主题相关性，缺失度高。

### GEN-964A3CB67B：数据完整性：调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「调用 API-L-IF1：POST /api/v1/orders/{orderId}/shipments」时：必填数据缺失或请求体为空

Candidate claims 'required data missing or empty request body' on API-L-IF1 (POST /api/v1/orders/{orderId}/shipments). Evidence only shows parameter validation at step 3 ('orderId格式合法、carrierCode合法、trackingNumber非空、shippedItems[]非空') and alternative flows A2 (INVALID_TRACKING_NUMBER) and A4 (INVALID_SHIPPED_ITEMS); none of these address an entirely empty request body or a general 'missing required data' condition, and no error code or recovery is given for that condition, so support is only generic interface context. The required behavior is not explicitly described and remains 待需求确认.

### GEN-96BBA11BB2：权限控制：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：水平越权或垂直越权

Candidate claims horizontal/vertical privilege escalation on API-M-IF2 (PUT /api/v1/merchant/products/{productId}). Evidence includes own-product check (step 5: 校验商品属于当前商家、状态为 DRAFT) and token validation (step 2), and A5 covers non-DRAFT status, but no alternative flow or error code is defined for privilege escalation/越权; the scenario is routed by concern (human.authorization) without explicit authorization-failure response or recovery semantics. Support is limited to generic interface context.

### GEN-B3BCB44D21：结果正确性：调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「调用 API-L-IF2：GET /api/v1/orders/{orderId}/logistics」时：查询结果错误、遗漏或分页重复

Assigned sources describe the query-logistics flow and alternative paths (order not shipped, service failure, cache) but never address wrong/omitted/paginated-duplicate query results; the trigger targets a result-correctness failure the sources do not characterize, so only generic retrieval-correctness topic is available.

### GEN-B68A400EE4：关联一致性：Read or update Category records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：级联删除失效或子对象残留

The assigned sections describe SKU stock/price validation, version conflict, and product/merchant ownership, but 'Read or update Category records' with cascade-delete/sub-object-residue is not present in any cited section; only the generic persistence topic overlaps.

### GEN-BA750716F6：权限控制：调用 API-S-IF1：GET /api/v1/products

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「调用 API-S-IF1：GET /api/v1/products」时：水平越权或垂直越权

The browse-products section supports anonymous/low-privilege access and describes query-parameter, category, timeout and unavailability handling, but contains no horizontal or vertical authorization check at all; authorization is a generic topic with no supporting evidence in the assigned sections.

### GEN-BE0AD4D45C：唯一性约束：Read or update Product records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC001：浏览商品（85-110行） → UCG-001-UC001 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC001-API-S-IF1 浏览商品（359-366行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC001-API-S-IF1 浏览商品（473-515行） → UCG-001-UC001 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC001：浏览商品（1116-1121行） → UCG-001-UC001 / 步骤 2

建议补充：执行「Read or update Product records」时：名称重复或唯一键冲突

候选关注点为 internal_database.uniqueness，触发于「Read or update Product records」名称重复或唯一键冲突。证据中浏览商品的 product 表字段清单（product_id、product_name 等）为只读检索，A1–A7 备选流程覆盖非法查询参数、无效分类、空结果、超时、不可用、状态失效与必填字段缺失，均无唯一性约束冲突项。仅主题相关（product 表读写），缺少具体唯一键约束或冲突响应证据。

### GEN-DA7E800AAD：数据格式：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：数据不满足格式规范

物流事件流程涉及事件协议与signature、eventCode校验，但'数据不满足格式规范'更接近请求体结构/格式约束；文档显式校验的是签名、单号存在性、eventTime合理性与eventCode合法性（A5 INVALID_EVENT_CODE），未定义通用格式规范校验规则，属泛化支撑。

### GEN-DB2FFF029B：数据大小：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：文件或请求体超过限制

创建商品流程仅校验merchantId格式与idempotencyKey非空，未定义文件上传或请求体大小上限；备选流程A1-A4也不含大小限制错误码（如413），'文件或请求体超过限制'无显式依据，属泛化话题。

### GEN-E715FF2075：查询性能：Read or update Shipment records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：大表联查超时

候选针对“Read or update Shipment records”的internal_database.query_performance（大表联查超时）。供货证据中商家发货流程确有对shipment表与order表的读写（写入shipment表、更新order状态为SHIPPED），属于该查询的通用上下文；但没有任何性能约束、超时阈值、索引或分页要求，也没有“查询超时”类异常码，故仅能算generic topic，支持度低。缺失度高：功能设计行747-792的备选流程A1–A5全部是与性能无关的业务/权限错误（ORDER_STATUS_INVALID、INVALID_TRACKING_NUMBER、INVALID_SHIPPED_ITEMS、PERMISSION_DENIED及LogisticsService不可用），无一条覆盖查询性能超时，异常响应与恢复待确认。

### GEN-E8BEE00CCC：数据大小：调用 LOGI-EVT-01：POST /api/v1/logistics/events

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「调用 LOGI-EVT-01：POST /api/v1/logistics/events」时：文件或请求体超过限制

候选针对LOGI-EVT-01的api.data.size（文件或请求体超过限制）。证据描述了该接口的请求体字段与校验流程，但通篇没有任何体积/长度/批量上限、载荷大小限制或413类错误码，故仅与主题（该接口的请求载荷）相关，属generic topic，支持度低。缺失度高：备选流程A1–A5覆盖签名、单号不存在、时间不合理、幂等重复、事件码非法，均未涉及请求体超限，异常响应与恢复待确认。

### GEN-EB5F2E6E15：数据大小：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：文件或请求体超过限制

候选针对API-M-IF4发布商品的api.data.size（文件或请求体超过限制）。证据中该接口请求体为version、publishAt，且前置条件涉及图片（image_urls）等资料完整性，属于载荷相关的通用语境；但没有任何大小/数量/体积上限或超限错误码，故仅为topic级支持。缺失度高：备选流程A1–A5为PRODUCT_INCOMPLETE、CATEGORY_RULE_VIOLATION、INVALID_PRODUCT_STATUS、VERSION_CONFLICT、同步失败重试，均不涉及请求体超限，异常响应与恢复待确认。

### GEN-EB77A47FDE：数据完整性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：必填数据缺失或请求体为空

候选触发为“必填数据缺失或请求体为空”，落在 GET /api/v1/products/{productId} 响应侧数据完整性关注点。证据中与该接口相关的校验仅涉及 productId 格式（错误码 INVALID_PRODUCT_ID，540-551），而“非关键展示字段缺失”的备选流程 A6 明确将其视为非关键字段缺失并按已有字段/缺省值处理（552-556），语义上恰与“必填数据缺失”的失败机制相矛盾；接口无请求体（GET），响应字段集（productId、name、description、images[]、price、stockStatus，367-374）亦未给出必填/可空约束。因此该异常行为在所属章节中无明确对应描述，仅存在接口层面的通用关联。

### GEN-ECEBB52E63：查询性能：Read or update Category records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC004：申请退款（306-330行） → UCG-003-UC004 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC004-API-R-IF1 申请退款（431-438行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC004-API-R-IF1 申请退款（882-929行） → UCG-003-UC004 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC004：申请退款（1170-1175行） → UCG-003-UC004 / 步骤 2

建议补充：执行「Read or update Category records」时：大表联查超时

候选针对“Read or update Category records”的internal_database.query_performance（大表联查超时）。证据在退款用例中确有跨order/order_item/refund表的读写与退款金额校验，但类别（Category）记录读取的任何性能约束、联查复杂度、超时或索引要求均未出现，故仅属generic topic，支持度低。缺失度高：备选流程A1–A5覆盖退款时限、金额超限、订单状态、PaymentService不可用、幂等重复，均无性能相关异常；且目标锚点（line 431-438）仅为接口参数摘要，异常响应与恢复待确认。

### GEN-F4717691CF：数据范围：调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「调用 API-M-IF2：PUT /api/v1/merchant/products/{productId}」时：数值超出允许范围

API-M-IF2 参数说明仅列出 productId、name、description、categoryId、imageUrls[]、version，流程校验均为格式/长度/有效性，未提及任何数值范围约束（如数值型字段上下界）；触发条件「数值超出允许范围」在接口定义中无对应字段与约束，仅属通用数据范围话题。备选流程 A1-A5 亦无相应错误码，需求缺失明显。

### GEN-F4DDB5757B：持久化能力：Read or update Refund records

推荐评分：0.4300；支持度：0.2500；缺失度：0.8500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：写入失败或事务回滚

该候选关注点为 internal_database.persistence，但 UCG-003-UC003 物流查询流程仅对 shipment、logistics_event 表做只读查询（第6、7步），未涉及 Refund 记录的读取或更新写入，也无事务/回滚语义描述；支撑仅停留在「存在数据库访问」这一通用话题层面。备选流程 A1-A5 亦无持久化失败相关错误码或恢复策略。

### GEN-0858C2EEC3：持久化一致性：调用 PAYMENT-PAY-01：POST /payment/v1/payments

推荐评分：0.4250；支持度：0.5000；缺失度：0.2500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC002：支付订单（183-208行） → UCG-002-UC002 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（391-398行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC002-PAYMENT-PAY-01 支付订单（655-701行） → UCG-002-UC002 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC002：支付订单（1140-1145行） → UCG-002-UC002 / 步骤 3

建议补充：执行「调用 PAYMENT-PAY-01：POST /payment/v1/payments」时：操作结果未可靠持久化或局部成功

Candidate is a persistence-consistency exception ('操作结果未可靠持久化或局部成功') on PAYMENT-PAY-01. The assigned detail flow explicitly writes payment 表 then updates order 表 to PAID — a two-write sequence where partial success is a concrete mechanism, and idempotency handling for duplicate payment callbacks (A6) and repeated idempotencyKey (A5) is explicitly constrained. This gives explicit constraint support for the failure mechanism (0.75). Missingness is low: while no distributed-consistency/rollback policy is stated, the assigned sections do delineate the multi-write boundary and idempotent recovery, leaving only the exact 'partially persisted' handling as undescribed.；支持度复核：The candidate concern is persistence_consistency ('操作结果未可靠持久化或局部成功') on PAYMENT-PAY-01. The cited flow does describe a concrete multi-write boundary (write payment table in step 8, then update order to PAID in step 9), which is a specific operation/interface where partial success could occur — so it rises above mere topic to context (.5). However, no explicit constraint governs the persistence consistency mechanism itself: there is no stated transaction boundary, no rollback/compensation policy, no atomicity requirement, and no defined response for the 'partially persisted' case. A5/A6 idempotency constraints address duplicate request handling, not reliable persistence of a single payment operation, and per the guidance idempotent handling of duplicate keys does not demonstrate a persistence/partial-write constraint. Therefore this is context, not explicit_constraint.

### GEN-0C08B9C8B0：身份认证：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.4250；支持度：0.5000；缺失度：0.2500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：无凭证、Token 无效或过期

Candidate is an authentication exception ('无凭证、Token 无效或过期') on API-C-IF1 POST /api/v1/cart/items. The assigned flow explicitly states the system validates the Authorization Token to confirm customer identity, with a precondition that the request carries a合法 Authorization Token — an explicit constraint governing the failure mechanism (0.75). Missingness moderate-low: the token-validation step is documented, but the specific 401/negative outcomes for missing/invalid/expired tokens are not enumerated in the assigned sections.；支持度复核：The flow and preconditions state that the Authorization Token is validated and that a 合法 Authorization Token is required, which is a specific authentication step for API-C-IF1. But no alternative flow defines the negative outcome (401/403 or an auth error code) for missing, invalid, or expired credentials, so only the general authentication context is documented, not the failure behavior itself.

### GEN-13A4A7D15D：数据大小：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.4250；支持度：0.2000；缺失度：0.9500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：文件或请求体超过限制

Candidate claims an oversized file/request body fault on API-S-IF2 request. Sources define only a single productId path parameter with no body and give no size limit or payload-limit constraint. No relevant failure mechanism is described; the assertion conflicts with a GET endpoint carrying no request body.

### GEN-22CFCD08BE：必填字段完整性：Read or update Shipment records

推荐评分：0.4150；支持度：0.2500；缺失度：0.8000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC001：商家发货（233-257行） → UCG-003-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC001-API-L-IF1 商家发货（407-414行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC001-API-L-IF1 商家发货（747-792行） → UCG-003-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC001：商家发货（1152-1157行） → UCG-003-UC001 / 步骤 3

建议补充：执行「Read or update Shipment records」时：必要字段缺失

Candidate claims a 'required field missing' failure on 'Read or update Shipment records' during 商家发货. The assigned design detail specifies request validation (orderId format, carrierCode legal, trackingNumber non-empty, shippedItems[] non-empty) and alternative flows (ORDER_STATUS_INVALID, INVALID_TRACKING_NUMBER, LogisticsService unavailable, INVALID_SHIPPED_ITEMS, PERMISSION_DENIED), which touch field validity but never frame it as a required-field-completeness violation at the Shipment-record write layer, and the shipment table field list is given without nullability/DB-level constraint statements. No error code or recovery is defined for a missing mandatory field, so support is only topical.

### GEN-242695AE04：数据库可用性：Read or update LogisticsEvent records

推荐评分：0.4150；支持度：0.2500；缺失度：0.8000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：连接失败或数据库宕机

Candidate asserts a database-availability failure ('连接失败或数据库宕机') when reading/updating LogisticsEvent records during 更新物流信息. The assigned detail enumerates functional alternative flows only (INVALID_SIGNATURE 401, TRACKING_NUMBER_NOT_FOUND 404, INVALID_EVENT_TIME 400, duplicate eventId idempotent 200, INVALID_EVENT_CODE 400) plus a timeout-style flow for a different use case; no database-unavailable branch, persistence error mapping, or recovery policy for logistics_event writes is described. The primitive is plausible for the write steps but has no explicit supporting text, and response/recovery are '待需求确认'.

### GEN-33DC8BF192：数据长度：调用 API-M-IF1：POST /api/v1/merchant/products

推荐评分：0.4150；支持度：0.2500；缺失度：0.8000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC001：创建商品（331-352行） → UCG-004-UC001 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC001-API-M-IF1 创建商品（439-446行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC001-API-M-IF1 创建商品（930-972行） → UCG-004-UC001 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC001：创建商品（1176-1181行） → UCG-004-UC001 / 步骤 3

建议补充：执行「调用 API-M-IF1：POST /api/v1/merchant/products」时：字符串长度超过限制

Candidate posits a string-length-over-limit fault on API-M-IF1 create-product request. Sources validate merchantId format and idempotencyKey non-empty but state no length limits and no length-error branch. Only generic request-validation context; no explicit constraint supports an over-length failure.

### GEN-5928D0E6F9：唯一性约束：Read or update Category records

推荐评分：0.4150；支持度：0.2500；缺失度：0.8000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC002：填写商品信息（353-376行） → UCG-004-UC002 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC002-API-M-IF2 填写商品信息（447-454行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC002-API-M-IF2 填写商品信息（973-1017行） → UCG-004-UC002 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC002：填写商品信息（1182-1187行） → UCG-004-UC002 / 步骤 4

建议补充：执行「Read or update Category records」时：名称重复或唯一键冲突

Candidate asserts internal_database.uniqueness (duplicate name/unique key conflict) on 'Read or update Category records' within PUT /api/v1/merchant/products/{productId}. Evidence at 1003-1008 covers validating categoryId via category table (category_id, status) i.e. existence/active check, not uniqueness constraints; alternatives A1-A5 (1009-1017) list PRODUCT_NOT_FOUND, INVALID_CATEGORY, INVALID_IMAGE, VERSION_CONFLICT, INVALID_PRODUCT_STATUS and no duplicate/uniqueness failure. Uniqueness behavior on the category record is not described, though 'Read or update Category records' wording generically matches a DB write.

### GEN-9F61BDCA50：数据大小：调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish

推荐评分：0.4150；支持度：0.2500；缺失度：0.8000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「调用 API-M-IF4：POST /api/v1/merchant/products/{productId}/publish」时：文件或请求体超过限制

Candidate asserts response-payload size overflow (file or request body exceeding limits) on POST /api/v1/merchant/products/{productId}/publish. The design detail validates version non-emptiness, publishAt format, completeness of name/description/category/images/SKU and category rules, but never mentions any file size, request body size, or bytes limit, nor a size-related error code. Only generic product-payload content is described; the size-overflow mechanism is not supported by any constraint in the sources.

### GEN-5106A0576E：关联一致性：Read or update SKU records

推荐评分：0.4100；支持度：0.2000；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：级联删除失效或子对象残留

候选检查“Read or update SKU records”的关联一致性（级联删除失效或子对象残留）。所引证据中，该用例为只读查询流程（第4步 ProductCatalogService 查询 product 表并返回详情），未涉及任何写入、删除或级联操作，也没有外键/引用完整性约束或清理失败的描述；系统需求扩展路径仅覆盖商品不存在、已下架、展示字段缺失。该候选为通用数据一致性话题，无具体证据支持此失败机制。

### GEN-51FE655D68：数据大小：调用 API-C-IF1：POST /api/v1/cart/items

推荐评分：0.4100；支持度：0.2000；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC003：加入购物车（134-157行） → UCG-001-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC003-API-C-IF1 加入购物车（375-382行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC003-API-C-IF1 加入购物车（557-604行） → UCG-001-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC003：加入购物车（1128-1133行） → UCG-001-UC003 / 步骤 3

建议补充：执行「调用 API-C-IF1：POST /api/v1/cart/items」时：文件或请求体超过限制

候选针对 API-C-IF1 响应载荷的“数据大小：文件或请求体超过限制”。API-C-IF1 请求体为 productId、skuId、quantity、idempotencyKey 等小字段，证据中无任何大小上限、请求体/文件限额或 413 类响应定义；备选流程仅定义 INVALID_QUANTITY、PRODUCT_OFF_SHELF、OUT_OF_STOCK、PURCHASE_LIMIT_EXCEEDED、幂等及服务不可用。仅接口主题相关，缺具体支持。

### GEN-2621CFFA34：字段合法性：Read or update Category records

推荐评分：0.4100；支持度：0.3500；缺失度：0.5500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC003：设置库存与价格（377-400行） → UCG-004-UC003 / 步骤 4
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC003-API-M-IF3 设置库存与价格（455-462行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC003-API-M-IF3 设置库存与价格（1018-1062行） → UCG-004-UC003 / 步骤 4；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC003：设置库存与价格（1188-1193行） → UCG-004-UC003 / 步骤 4

建议补充：执行「Read or update Category records」时：类型错误、非法字符或超长

Candidate targets a database-layer 'Category records' read/update with illegal characters or over-length. The assigned sources for UC-003 cover the SKU stock/price PUT and its validations (negative stock, bad price, duplicate skuId, version conflict) — they do not describe category-record field validity, long strings or illegal-character checks in this flow. The DB-step context is only partially aligned; the specific field-validity mechanism is not supported.

### GEN-0FD03C3336：数据库可用性：Read or update Refund records

推荐评分：0.4000；支持度：0.2500；缺失度：0.7500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：连接失败或数据库宕机

The candidate names a database-availability concern for UCG-003-UC003 (query logistics), but its scenario_steps and source_location are confused: it cites API-L-IF2 yet its trigger text references 'Read or update Refund records', which belongs to the refund use case, not logistics. The assigned evidence for this candidate describes LogisticsServiceAdapter reading shipment and logistics_event tables and enumerates alternatives A1-A5 (ORDER_NOT_SHIPPED, LOGISTICS_NOT_FOUND, external LogisticsService timeout/failure, delivered, adapter unavailable) — none mentions database connection failure or database downtime. Support is therefore only generic topical (a table-reading use case exists); the specific internal-DB availability failure is not described in the assigned sections, and the refund-records wording conflicts with the logistics context.

### GEN-46C69DAB74：幂等性：Read or update Category records

推荐评分：0.4000；支持度：0.2500；缺失度：0.7500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-004-UC004：发布商品（401-425行） → UCG-004-UC004 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-004-UC004-API-M-IF4 发布商品（463-470行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-004-UC004-API-M-IF4 发布商品（1063-1109行） → UCG-004-UC004 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-004-UC004：发布商品（1194-1199行） → UCG-004-UC004 / 步骤 3

建议补充：执行「Read or update Category records」时：重复请求导致重复操作异常

候选关注幂等性于'Read or update Category records'。证据中API-M-IF4发布商品流程包含乐观锁语义（version一致校验，备选A4 VERSION_CONFLICT返回最新version），可视为一种重复/并发请求的防护，但这是版本冲突控制而非idempotencyKey式幂等；且'publish product'接口的请求参数为productId、version、publishAt，无idempotencyKey。category表仅在类目规则校验（第7步查询必填属性）中被读取，不做幂等写入。因此仅存在通用主题关联，无具体幂等支撑。缺失高：重复发布同一商品的结果（是否重复上架、是否触发重复索引刷新）未显式描述；A5仅覆盖目录同步失败的待同步重试，非幂等语义。

### GEN-4718D4278A：幂等性：Read or update Payment records

推荐评分：0.4000；支持度：0.2500；缺失度：0.7500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-002-UC003：查看订单详情（209-232行） → UCG-002-UC003 / 步骤 3
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-002-UC003-API-O-IF2 查看订单详情（399-406行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-002-UC003-API-O-IF2 查看订单详情（702-746行） → UCG-002-UC003 / 步骤 3；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-002-UC003：查看订单详情（1146-1151行） → UCG-002-UC003 / 步骤 3

建议补充：执行「Read or update Payment records」时：重复请求导致重复操作异常

候选关注幂等性于'Read or update Payment records'。证据中API-O-IF2为只读查询接口（GET /api/v1/orders/{orderId}），第7步仅'查询 payment 表，获取 payment_id、payment_method、provider_trade_no、payment_status、paid_at'，不进行任何写入；请求参数仅orderId，无idempotencyKey。备选流程覆盖INVALID_ORDER_ID、ORDER_ACCESS_DENIED、ORDER_NOT_FOUND、未发货、504超时，均非幂等语义。因此'重复请求导致重复操作'在只读接口上缺乏对象基础，仅有通用主题关联，支持0.25。缺失高：没有关于重复查询对payment数据一致性或副作用影响的描述。

### GEN-CAAE9F9578：并发一致性：Read or update SKU records

推荐评分：0.4000；支持度：0.2500；缺失度：0.7500；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「Read or update SKU records」时：并发更新冲突或后写覆盖前写

查看商品详情证据说明为只读查询（GET /api/v1/products/{productId}，查 product 表并过滤内部字段），未涉及 SKU 记录的读或并发更新；该用例的备选流程只覆盖格式错误、不存在、下架、超时、不可用与非关键字段缺失，无并发更新冲突/后写覆盖前写机制。

### GEN-9F1AB24665：显示正确性：调用 API-S-IF2：GET /api/v1/products/{productId}

推荐评分：0.3850；支持度：0.2500；缺失度：0.7000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-001-UC002：查看商品详情（111-133行） → UCG-001-UC002 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-001-UC002-API-S-IF2 查看商品详情（367-374行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-001-UC002-API-S-IF2 查看商品详情（516-556行） → UCG-001-UC002 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-001-UC002：查看商品详情（1122-1127行） → UCG-001-UC002 / 步骤 2

建议补充：执行「调用 API-S-IF2：GET /api/v1/products/{productId}」时：展示内容与业务结果不一致

Candidate concerns display correctness: rendered content inconsistent with the business result, at GET /api/v1/products/{productId}. The design detail describes filtering internal fields and converting to a front end structure, and A6 handling missing non-key display fields via defaults/hiding. These address presentation composition, but no source section defines a requirement that displayed content must match a business result, nor any failure path for a display/correctness discrepancy. Evidence is therefore topical (display/presentation handling) rather than an explicit constraint on the failure mechanism.

### GEN-C787E26252：查询性能：Read or update LogisticsEvent records

推荐评分：0.3850；支持度：0.2500；缺失度：0.7000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC002：更新物流信息（258-281行） → UCG-003-UC002 / 步骤 5
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（415-422行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC002-LOGI-EVT-01 更新物流信息（793-836行） → UCG-003-UC002 / 步骤 5；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC002：更新物流信息（1158-1163行） → UCG-003-UC002 / 步骤 5

建议补充：执行「Read or update LogisticsEvent records」时：大表联查超时

更新物流信息用例的证据只覆盖签名/单号/时间顺序/幂等事件（eventId 查询）等业务校验，未涉及大表联查（如 logistics_event 联查 shipment/order）的数据库查询性能约束；'大表联查超时' 属通用数据库性能话题，无接口级或约束级证据支持该失败机制。

### GEN-9ABCCE26E8：并发一致性：Read or update Refund records

推荐评分：0.2700；支持度：0.0000；缺失度：0.9000；等级：needs_confirmation

系统需求Delta_spec.md: 系统需求Delta_spec.md → 场景用例分析 → 用例详细说明 → UCG-003-UC003：查询物流信息（282-305行） → UCG-003-UC003 / 步骤 2
功能设计Delta_spec.md: 功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例 → UCG-003-UC003-API-L-IF2 查询物流信息（423-430行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → 设计用例详情 → UCG-003-UC003-API-L-IF2 查询物流信息（837-881行） → UCG-003-UC003 / 步骤 2；功能设计Delta_spec.md → Delta 功能设计文档 → SR设计：在线交易平台核心业务模块 → V5标准化设计用例调用链（抽取权威章节） → UCG-003-UC003：查询物流信息（1164-1169行） → UCG-003-UC003 / 步骤 2

建议补充：执行「Read or update Refund records」时：并发更新冲突或后写覆盖前写

Candidate scenario concerns concurrency consistency for 'Read or update Refund records' under use case 查询物流信息 (API-L-IF2, GET /api/v1/orders/{orderId}/logistics). The cited evidence describes only a read-only logistics query with cache-fallback (A3) and no refund records, no concurrency semantics, and no update path at all; the claimed failure mechanism has no supporting evidence in the assigned sections, so support is 0. The behavior is clearly not described and the expected response remains 待需求确认.
