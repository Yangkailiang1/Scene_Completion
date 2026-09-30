# 终端云参考测试场景规格

本文依据《功能设计Delta_spec.md》的“设计用例详情”和“V5标准化设计用例调用链”整理。`AR-01` 至 `AR-07` 是本文件为场景分组生成的临时编号，不是原始规格中的 AR 需求编号；关联 AR 字段同时列出设计文档中的真实实现模块/API。仅整理文档明确的基本流程和备选流程，不补造未描述的业务分支。

类型约定：`正常`覆盖基本流程；产生有效业务结果的幂等重放、缓存降级、异步受理或明确成功替代结果归`可选`；校验失败、拒绝、不可用、超时或资源冲突归`异常`。来源定位均为 `功能设计Delta_spec.md` 的行号，行号用于当前版本，文档变更后应重新核验。

## AR-01：ProductBrowse 商品浏览模块

实现接口：`listProducts`、`getProductDetail`；SR：`SR-DELTA-042`；接口契约见功能设计文档 API-S-IF1/IF2。

| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |
|---|---|---|---|---|---|---|---|---|
| TEST-AR01-UC001-N01 | 默认浏览商品列表 | 正常 | 系统和 ProductCatalogService 可用，存在 ON_SALE 商品 | 顾客请求商品列表 | AR-01/listProducts；SR-DELTA-042/API-S-IF1；UCG-001-UC001 | 验证默认商品检索与前端字段转换 | HTTP 200，返回分页信息及 items 商品列表 | 功能设计Delta_spec.md:473-514，基本流程1-6 |
| TEST-AR01-UC001-A01 | 查询参数非法 | 异常 | 商品浏览接口可访问 | minPrice>maxPrice、page<1 或 sortBy 非法 | AR-01/listProducts；API-S-IF1；UCG-001-UC001 | 验证查询参数边界校验 | HTTP 400，错误码 INVALID_QUERY_PARAM | 功能设计Delta_spec.md:506-514，A1 |
| TEST-AR01-UC001-A02 | 商品分类无效 | 异常 | 商品浏览接口可访问 | categoryId 不存在或已失效 | AR-01/listProducts；API-S-IF1；UCG-001-UC001 | 验证分类引用校验 | HTTP 400，错误码 INVALID_CATEGORY | 功能设计Delta_spec.md:506-514，A2 |
| TEST-AR01-UC001-O01 | 无符合条件商品 | 可选 | 商品浏览接口和目录服务可用 | 查询条件不匹配任何商品 | AR-01/listProducts；API-S-IF1；UCG-001-UC001 | 验证空结果展示 | HTTP 200、total=0、products=[]，展示“暂无符合条件的商品” | 功能设计Delta_spec.md:506-514，A3 |
| TEST-AR01-UC001-A03 | 商品查询超时 | 异常 | 商品浏览接口可用 | ProductCatalogService 查询超时 | AR-01/listProducts；API-S-IF1；UCG-001-UC001 | 验证服务超时映射 | HTTP 504，错误码 PRODUCT_SERVICE_TIMEOUT | 功能设计Delta_spec.md:506-514，A4 |
| TEST-AR01-UC001-A04 | 商品目录服务不可用 | 异常 | 商品浏览接口可用 | ProductCatalogService 不可用 | AR-01/listProducts；API-S-IF1；UCG-001-UC001 | 验证依赖不可用处理 | HTTP 503，错误码 PRODUCT_SERVICE_UNAVAILABLE | 功能设计Delta_spec.md:506-514，A5 |
| TEST-AR01-UC001-O02 | 过滤已下架或无库存商品 | 可选 | 正在查询商品列表 | 查询期间商品转为 OFF_SALE 或库存变为0 | AR-01/listProducts；API-S-IF1；UCG-001-UC001 | 验证结果有效性过滤 | 返回前过滤失效商品，只展示当前有效商品 | 功能设计Delta_spec.md:506-514，A6 |
| TEST-AR01-UC001-O03 | 非关键商品字段缺失 | 可选 | 商品列表查询成功 | product_name、sale_price 或 cover_image_url 缺失 | AR-01/listProducts；API-S-IF1；UCG-001-UC001 | 验证缺失字段的容错展示 | 使用缺省值展示或过滤异常商品 | 功能设计Delta_spec.md:506-514，A7 |
| TEST-AR01-UC002-N01 | 查看商品详情 | 正常 | 系统可用，目标商品可查询 | 顾客请求指定 productId 的详情 | AR-01/getProductDetail；API-S-IF2；UCG-001-UC002 | 验证详情查询及字段转换 | HTTP 200，返回商品详情展示结构 | 功能设计Delta_spec.md:516-555，基本流程1-6 |
| TEST-AR01-UC002-A01 | 商品标识格式错误 | 异常 | 商品详情接口可访问 | 请求携带格式错误 productId | AR-01/getProductDetail；API-S-IF2；UCG-001-UC002 | 验证标识格式校验 | HTTP 400，错误码 INVALID_PRODUCT_ID | 功能设计Delta_spec.md:548-555，A1 |
| TEST-AR01-UC002-A02 | 商品资源不存在 | 异常 | 商品详情接口和目录服务可用 | 查询不存在的 productId | AR-01/getProductDetail；API-S-IF2；UCG-001-UC002 | 验证不存在资源处理 | HTTP 404，错误码 PRODUCT_NOT_FOUND | 功能设计Delta_spec.md:548-555，A2 |
| TEST-AR01-UC002-A03 | 商品已下架 | 异常 | 目标商品记录存在 | 查询状态为 OFF_SALE 的商品 | AR-01/getProductDetail；API-S-IF2；UCG-001-UC002 | 验证下架资源处理 | HTTP 410，错误码 PRODUCT_OFF_SHELF | 功能设计Delta_spec.md:548-555，A3 |
| TEST-AR01-UC002-A04 | 商品详情查询超时 | 异常 | 商品详情接口可访问 | ProductCatalogService 查询超时 | AR-01/getProductDetail；API-S-IF2；UCG-001-UC002 | 验证超时映射 | HTTP 504，错误码 PRODUCT_SERVICE_TIMEOUT | 功能设计Delta_spec.md:548-555，A4 |
| TEST-AR01-UC002-A05 | 商品目录服务不可用 | 异常 | 商品详情接口可访问 | ProductCatalogService 不可用 | AR-01/getProductDetail；API-S-IF2；UCG-001-UC002 | 验证依赖不可用处理 | HTTP 503，错误码 PRODUCT_SERVICE_UNAVAILABLE | 功能设计Delta_spec.md:548-555，A5 |
| TEST-AR01-UC002-O01 | 详情非关键字段缺失 | 可选 | 目标商品可查询 | description 或 image_urls 等非关键字段缺失 | AR-01/getProductDetail；API-S-IF2；UCG-001-UC002 | 验证部分详情容错 | 返回已有字段，缺失区域隐藏或使用缺省值 | 功能设计Delta_spec.md:548-555，A6 |

## AR-02：CartService 购物车服务

实现接口：`addCartItem`；SR：`SR-DELTA-042`；API：API-C-IF1。

| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |
|---|---|---|---|---|---|---|---|---|
| TEST-AR02-UC003-N01 | 加入有效商品到购物车 | 正常 | 顾客已登录；商品在售且库存、限购条件满足 | 顾客提交 productId、skuId、quantity 和幂等键 | AR-02/addCartItem；API-C-IF1；UCG-001-UC003 | 验证身份、商品校验和购物车写入 | HTTP 200，返回条目、数量及金额汇总 | 功能设计Delta_spec.md:557-603，基本流程1-11 |
| TEST-AR02-UC003-A01 | 购买数量非法 | 异常 | 顾客已登录 | quantity<1 | AR-02/addCartItem；API-C-IF1；UCG-001-UC003 | 验证数量约束 | HTTP 400，INVALID_QUANTITY | 功能设计Delta_spec.md:596-603，A1 |
| TEST-AR02-UC003-A02 | 商品已下架 | 异常 | 顾客已登录，商品记录存在 | 商品状态为 OFF_SALE | AR-02/addCartItem；API-C-IF1；UCG-001-UC003 | 验证不可购买状态处理 | HTTP 410，PRODUCT_OFF_SHELF | 功能设计Delta_spec.md:596-603，A2 |
| TEST-AR02-UC003-A03 | SKU库存不足 | 异常 | 顾客已登录，SKU 有效 | 请求数量超过库存 | AR-02/addCartItem；API-C-IF1；UCG-001-UC003 | 验证库存约束 | HTTP 409，OUT_OF_STOCK，并返回可购买数量 | 功能设计Delta_spec.md:596-603，A3 |
| TEST-AR02-UC003-A04 | 累加后超过限购 | 异常 | 同一 SKU 已在购物车 | 再次添加后数量超过限购上限 | AR-02/addCartItem；API-C-IF1；UCG-001-UC003 | 验证购物车累计限购 | HTTP 409，PURCHASE_LIMIT_EXCEEDED | 功能设计Delta_spec.md:596-603，A4 |
| TEST-AR02-UC003-O01 | 幂等键重复提交 | 可选 | 同一请求已成功处理 | 使用相同 idempotencyKey 重试 | AR-02/addCartItem；API-C-IF1；UCG-001-UC003 | 验证幂等重放 | 返回已有购物车条目，不重复写入 | 功能设计Delta_spec.md:596-603，A5 |
| TEST-AR02-UC003-A05 | 商品目录服务不可用 | 异常 | 顾客已登录 | ProductCatalogService 不可用 | AR-02/addCartItem；API-C-IF1；UCG-001-UC003 | 验证依赖失败处理 | HTTP 503，PRODUCT_SERVICE_UNAVAILABLE | 功能设计Delta_spec.md:596-603，A6 |

## AR-03：OrderService 订单服务

实现接口：`createOrder`、`getOrderDetail`、`createShipment`；SR：`SR-DELTA-042`；API：API-O-IF1、API-O-IF2、API-L-IF1。

| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |
|---|---|---|---|---|---|---|---|---|
| TEST-AR03-UC001-N01 | 创建订单 | 正常 | 顾客已登录，购物车非空，地址有效，商品有库存 | 顾客提交订单请求 | AR-03/createOrder；API-O-IF1；UCG-002-UC001 | 验证订单校验、创建及返回 | 创建订单并返回 orderId、状态和金额 | 功能设计Delta_spec.md:605-645，基本流程 |
| TEST-AR03-UC001-A01 | 商品价格已变化 | 异常 | 订单请求包含确认金额 | 商品价格与 confirmedAmount 不一致 | AR-03/createOrder；API-O-IF1；UCG-002-UC001 | 验证价格一致性检查 | HTTP 409，PRICE_CHANGED，返回最新价格 | 功能设计Delta_spec.md:646-653，A1 |
| TEST-AR03-UC001-A02 | 商品库存不足 | 异常 | 购物车含待购商品 | 下单时库存不足 | AR-03/createOrder；API-O-IF1；UCG-002-UC001 | 验证下单库存校验 | HTTP 409，OUT_OF_STOCK，返回商品及当前库存 | 功能设计Delta_spec.md:646-653，A2 |
| TEST-AR03-UC001-A03 | 收货地址无效 | 异常 | 顾客已登录 | 地址无效或不属于当前顾客 | AR-03/createOrder；API-O-IF1；UCG-002-UC001 | 验证地址归属和有效性 | HTTP 400，INVALID_ADDRESS | 功能设计Delta_spec.md:646-653，A3 |
| TEST-AR03-UC001-O01 | 创建订单幂等重放 | 可选 | 相同幂等键已创建订单 | 使用相同 idempotencyKey 重试 | AR-03/createOrder；API-O-IF1；UCG-002-UC001 | 验证订单幂等 | 返回已有订单，不重复创建 | 功能设计Delta_spec.md:646-653，A4 |
| TEST-AR03-UC001-A04 | 购物车为空 | 异常 | 顾客已登录 | 提交空购物车订单 | AR-03/createOrder；API-O-IF1；UCG-002-UC001 | 验证空订单拒绝 | HTTP 400，CART_EMPTY | 功能设计Delta_spec.md:646-653，A5 |
| TEST-AR03-UC001-A05 | 商品目录服务不可用 | 异常 | 创建订单请求有效 | ProductCatalogService 不可用 | AR-03/createOrder；API-O-IF1；UCG-002-UC001 | 验证下游失败处理 | HTTP 503，PRODUCT_SERVICE_UNAVAILABLE | 功能设计Delta_spec.md:646-653，A6 |
| TEST-AR03-UC003-N01 | 查看订单详情 | 正常 | 顾客已登录且订单存在 | 顾客查询自己的订单 | AR-03/getOrderDetail；API-O-IF2；UCG-002-UC003 | 验证订单读取和权限范围 | 返回订单、商品、支付及物流状态 | 功能设计Delta_spec.md:704-738，基本流程 |
| TEST-AR03-UC003-A01 | 订单标识格式错误 | 异常 | 顾客已登录 | 使用格式错误 orderId 查询订单详情 | AR-03/getOrderDetail；API-O-IF2；UCG-002-UC003 | 验证订单标识校验 | HTTP 400，INVALID_ORDER_ID | 功能设计Delta_spec.md:739-745，A1 |
| TEST-AR03-UC003-A02 | 查询他人订单 | 异常 | 顾客已登录，目标订单属于其他顾客 | 顾客查询他人订单 | AR-03/getOrderDetail；API-O-IF2；UCG-002-UC003 | 验证订单数据访问控制 | HTTP 403，ORDER_ACCESS_DENIED | 功能设计Delta_spec.md:739-745，A2 |
| TEST-AR03-UC003-A03 | 订单不存在 | 异常 | 顾客已登录 | 查询不存在的 orderId | AR-03/getOrderDetail；API-O-IF2；UCG-002-UC003 | 验证订单资源存在性 | HTTP 404，ORDER_NOT_FOUND | 功能设计Delta_spec.md:739-745，A3 |
| TEST-AR03-UC003-O01 | 订单未发货时隐藏物流轨迹 | 可选 | 订单存在但尚未发货 | 顾客查询订单详情 | AR-03/getOrderDetail；API-O-IF2；UCG-002-UC003 | 验证物流字段的部分响应 | shipmentSummary 物流字段为空，不展示物流轨迹 | 功能设计Delta_spec.md:739-745，A4 |
| TEST-AR03-UC003-A04 | 订单查询超时 | 异常 | 订单详情接口可访问 | OrderService 查询超时 | AR-03/getOrderDetail；API-O-IF2；UCG-002-UC003 | 验证订单服务超时处理 | HTTP 504，ORDER_SERVICE_TIMEOUT | 功能设计Delta_spec.md:739-745，A5 |
| TEST-AR03-SHIP-N01 | 商家发货 | 正常 | 商家已登录有权限，订单 PAID 且完成出库准备 | 商家提交承运商、物流单号和发货商品 | AR-03/createShipment；API-L-IF1；UCG-003-UC001 | 验证订单检查、发货记录和物流登记 | 订单转为 SHIPPED，返回 shipmentId、orderStatus、trackingNumber | 功能设计Delta_spec.md:749-784，基本流程 |
| TEST-AR03-SHIP-A01 | 订单状态不允许发货 | 异常 | 订单存在 | 订单状态不是 PAID | AR-03/createShipment；API-L-IF1；UCG-003-UC001 | 验证发货状态前置条件 | HTTP 409，ORDER_STATUS_INVALID | 功能设计Delta_spec.md:787-791，A1 |
| TEST-AR03-SHIP-A02 | 物流单号格式非法 | 异常 | 订单状态允许发货 | trackingNumber 格式不合法 | AR-03/createShipment；API-L-IF1；UCG-003-UC001 | 验证物流单号格式 | HTTP 400，INVALID_TRACKING_NUMBER | 功能设计Delta_spec.md:787-791，A2 |
| TEST-AR03-SHIP-O01 | 外部物流不可用时登记重试 | 可选 | 订单具备发货条件 | LogisticsService 不可用 | AR-03/createShipment；API-L-IF1；UCG-003-UC001 | 验证降级发货和异步补偿 | 订单状态更新为 SHIPPED，保存待同步任务并登记物流单号异步重试 | 功能设计Delta_spec.md:787-791，A3 |
| TEST-AR03-SHIP-A03 | 发货商品不属于订单 | 异常 | 订单存在且商家已认证 | shippedItems 含其他订单商品 | AR-03/createShipment；API-L-IF1；UCG-003-UC001 | 验证发货商品归属 | HTTP 400，INVALID_SHIPPED_ITEMS | 功能设计Delta_spec.md:787-791，A4 |
| TEST-AR03-SHIP-A04 | 商家无订单处理权限 | 异常 | 商家已登录 | 商家处理无权限订单 | AR-03/createShipment；API-L-IF1；UCG-003-UC001 | 验证操作授权 | HTTP 403，PERMISSION_DENIED | 功能设计Delta_spec.md:787-791，A5 |

## AR-04：PaymentAdapter 支付适配服务

实现接口：`createPayment`；SR：`SR-DELTA-042`；支付 API：`PAYMENT-PAY-01`。

| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |
|---|---|---|---|---|---|---|---|---|
| TEST-AR04-UC002-N01 | 支付待支付订单 | 正常 | 顾客已登录，订单状态 WAIT_PAY | 顾客确认支付方式并提交支付 | AR-04/createPayment；PAYMENT-PAY-01；UCG-002-UC002 | 验证支付请求和状态更新 | 返回支付标识及支付状态，成功结果逐层反馈 | 功能设计Delta_spec.md:657-692，基本流程 |
| TEST-AR04-UC002-A01 | 订单状态不允许支付 | 异常 | 订单存在 | 订单状态不是 WAIT_PAY | AR-04/createPayment；PAYMENT-PAY-01；UCG-002-UC002 | 验证支付状态前置条件 | HTTP 409，ORDER_STATUS_INVALID | 功能设计Delta_spec.md:693-700，A1 |
| TEST-AR04-UC002-A02 | 支付金额不匹配 | 异常 | 订单存在且有应付金额 | 请求金额与订单应付金额不同 | AR-04/createPayment；PAYMENT-PAY-01；UCG-002-UC002 | 验证金额一致性 | HTTP 400，AMOUNT_MISMATCH | 功能设计Delta_spec.md:693-700，A2 |
| TEST-AR04-UC002-A03 | 支付服务不可用或超时 | 异常 | 订单状态 WAIT_PAY | PaymentService 不可用或超时 | AR-04/createPayment；PAYMENT-PAY-01；UCG-002-UC002 | 验证支付失败时订单保护 | HTTP 503，PAYMENT_SERVICE_UNAVAILABLE，订单保持 WAIT_PAY | 功能设计Delta_spec.md:693-700，A3 |
| TEST-AR04-UC002-O01 | 顾客取消支付 | 可选 | 订单状态 WAIT_PAY | 顾客在支付过程中取消 | AR-04/createPayment；PAYMENT-PAY-01；UCG-002-UC002 | 验证取消结果处理 | HTTP 200，PAYMENT_CANCELLED，订单保持 WAIT_PAY | 功能设计Delta_spec.md:693-700，A4 |
| TEST-AR04-UC002-O02 | 支付请求幂等重放 | 可选 | 相同幂等键已处理 | 顾客重复提交支付请求 | AR-04/createPayment；PAYMENT-PAY-01；UCG-002-UC002 | 验证支付幂等 | 返回已有支付结果，不重复处理 | 功能设计Delta_spec.md:693-700，A5 |
| TEST-AR04-UC002-O03 | 重复支付回调 | 可选 | paymentId 对应回调已处理 | 相同支付回调再次到达 | AR-04/createPayment；PAYMENT-PAY-01；UCG-002-UC002 | 验证回调幂等 | 不重复更新订单状态 | 功能设计Delta_spec.md:693-700，A6 |

## AR-05：LogisticsServiceAdapter 物流适配服务

实现接口：`receiveLogisticsEvent`、`getOrderLogistics`；SR：`SR-DELTA-042`；API：LOGI-EVT-01、API-L-IF2。

| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |
|---|---|---|---|---|---|---|---|---|
| TEST-AR05-UC002-N01 | 接收物流事件 | 正常 | 物流回调可达，签名有效，物流单存在 | 物流服务推送事件 | AR-05/receiveLogisticsEvent；LOGI-EVT-01；UCG-003-UC002 | 验证事件校验、落库与确认 | 返回 accepted=true 和 eventId，订单物流信息更新 | 功能设计Delta_spec.md:795-828，基本流程 |
| TEST-AR05-UC002-A01 | 物流事件签名无效 | 异常 | 回调接口可达 | signature 校验失败 | AR-05/receiveLogisticsEvent；LOGI-EVT-01；UCG-003-UC002 | 验证回调身份认证 | HTTP 401，INVALID_SIGNATURE，并记录安全告警 | 功能设计Delta_spec.md:829-835，A1 |
| TEST-AR05-UC002-A02 | 物流单号不存在 | 异常 | 回调签名有效 | trackingNumber 不在 shipment 表中 | AR-05/receiveLogisticsEvent；LOGI-EVT-01；UCG-003-UC002 | 验证物流资源存在性 | HTTP 404，TRACKING_NUMBER_NOT_FOUND | 功能设计Delta_spec.md:829-835，A2 |
| TEST-AR05-UC002-A03 | 物流事件时间非法 | 异常 | 物流单存在 | eventTime 早于发货时间或晚于当前时间 | AR-05/receiveLogisticsEvent；LOGI-EVT-01；UCG-003-UC002 | 验证事件时间约束 | HTTP 400，INVALID_EVENT_TIME | 功能设计Delta_spec.md:829-835，A3 |
| TEST-AR05-UC002-O01 | 重复物流事件 | 可选 | eventId 已处理 | 同一 eventId 再次到达 | AR-05/receiveLogisticsEvent；LOGI-EVT-01；UCG-003-UC002 | 验证事件幂等 | HTTP 200，accepted=true、duplicate=true，不重复写入 | 功能设计Delta_spec.md:829-835，A4 |
| TEST-AR05-UC002-A04 | 物流事件编码非法 | 异常 | signature 校验通过 | eventCode 不在允许范围 | AR-05/receiveLogisticsEvent；LOGI-EVT-01；UCG-003-UC002 | 验证事件契约约束 | HTTP 400，INVALID_EVENT_CODE | 功能设计Delta_spec.md:829-835，A5 |
| TEST-AR05-UC003-N01 | 查询订单物流 | 正常 | 订单存在，物流信息可查询 | 顾客查询订单物流 | AR-05/getOrderLogistics；API-L-IF2；UCG-003-UC003 | 验证物流状态和轨迹查询 | 返回 shipmentStatus 与 trackingEvents | 功能设计Delta_spec.md:839-873，基本流程 |
| TEST-AR05-UC003-A01 | 订单尚未发货 | 异常 | 订单状态 WAIT_PAY 或 PAID | 顾客请求物流信息 | AR-05/getOrderLogistics；API-L-IF2；UCG-003-UC003 | 验证未发货状态处理 | HTTP 409，ORDER_NOT_SHIPPED | 功能设计Delta_spec.md:874-880，A1 |
| TEST-AR05-UC003-A02 | 本地物流数据不存在 | 异常 | 订单已创建 | 查询不到本地物流记录 | AR-05/getOrderLogistics；API-L-IF2；UCG-003-UC003 | 验证本地物流资源缺失 | HTTP 404，LOGISTICS_NOT_FOUND | 功能设计Delta_spec.md:874-880，A2 |
| TEST-AR05-UC003-O01 | 外部物流查询失败使用缓存 | 可选 | 本地存在最近一次同步物流数据 | 外部 LogisticsService 查询失败或超时 | AR-05/getOrderLogistics；API-L-IF2；UCG-003-UC003 | 验证缓存降级 | 返回本地最近数据，dataSource=CACHE 且包含 lastUpdatedAt | 功能设计Delta_spec.md:874-880，A3 |
| TEST-AR05-UC003-O02 | 物流已签收 | 可选 | 物流轨迹包含签收事件 | 查询已签收订单物流 | AR-05/getOrderLogistics；API-L-IF2；UCG-003-UC003 | 验证终态轨迹展示 | status=DELIVERED，响应包含签收时间 | 功能设计Delta_spec.md:874-880，A4 |
| TEST-AR05-UC003-A03 | 物流适配服务不可用 | 异常 | 物流查询接口可访问 | LogisticsServiceAdapter 不可用 | AR-05/getOrderLogistics；API-L-IF2；UCG-003-UC003 | 验证适配服务不可用映射 | HTTP 503，LOGISTICS_SERVICE_UNAVAILABLE | 功能设计Delta_spec.md:874-880，A5 |

## AR-06：RefundService 退款服务

实现接口：`createRefund`；SR：`SR-DELTA-042`；API：API-R-IF1。

| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |
|---|---|---|---|---|---|---|---|---|
| TEST-AR06-UC004-N01 | 申请订单退款 | 正常 | 顾客已登录，订单符合退款条件且处于有效期 | 顾客提交退款原因和金额 | AR-06/createRefund；API-R-IF1；UCG-003-UC004 | 验证退款受理及状态返回 | 创建退款单并返回 refundId、refundStatus | 功能设计Delta_spec.md:884-921，基本流程 |
| TEST-AR06-UC004-A01 | 退款超过有效期 | 异常 | 订单可查询 | 超过退款有效期后申请退款 | AR-06/createRefund；API-R-IF1；UCG-003-UC004 | 验证退款时间窗 | HTTP 409，REFUND_WINDOW_EXPIRED | 功能设计Delta_spec.md:922-928，A1 |
| TEST-AR06-UC004-A02 | 退款金额超过可退金额 | 异常 | 订单存在可退金额 | 申请金额大于可退金额 | AR-06/createRefund；API-R-IF1；UCG-003-UC004 | 验证退款金额上限 | HTTP 409，REFUND_AMOUNT_EXCEEDED，并返回可退款金额 | 功能设计Delta_spec.md:922-928，A2 |
| TEST-AR06-UC004-A03 | 订单状态不支持退款 | 异常 | 订单存在 | 订单已退款或已取消等不满足条件 | AR-06/createRefund；API-R-IF1；UCG-003-UC004 | 验证退款状态约束 | HTTP 409，ORDER_STATUS_INVALID | 功能设计Delta_spec.md:922-928，A3 |
| TEST-AR06-UC004-O01 | 支付服务不可用时异步重试 | 可选 | 退款请求合法 | PaymentService 不可用 | AR-06/createRefund；API-R-IF1；UCG-003-UC004 | 验证异步补偿受理 | 退款单为 PENDING，异步重试，响应 refundStatus=PROCESSING | 功能设计Delta_spec.md:922-928，A4 |
| TEST-AR06-UC004-O02 | 退款请求幂等重放 | 可选 | 相同幂等键已创建退款单 | 重复提交退款申请 | AR-06/createRefund；API-R-IF1；UCG-003-UC004 | 验证退款幂等 | 返回已有退款单，不重复创建 | 功能设计Delta_spec.md:922-928，A5 |

## AR-07：MerchantProductService 商家商品服务

实现接口：`createMerchantProduct`、`updateMerchantProduct`、`updateSkuInventoryAndPrice`、`publishMerchantProduct`；SR：`SR-DELTA-042`；API：API-M-IF1 至 API-M-IF4。

| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |
|---|---|---|---|---|---|---|---|---|
| TEST-AR07-UC001-N01 | 创建商品草稿 | 正常 | 商家登录且具备商品管理资格 | 商家提交商品名称、类目、描述和图片 | AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001 | 验证商品草稿创建 | 返回 productId 和草稿状态 | 功能设计Delta_spec.md:932-965，基本流程 |
| TEST-AR07-UC001-A01 | 商家资质失效 | 异常 | 商家已登录 | 商家提交商品创建请求但资质失效 | AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001 | 验证经营资质门禁 | HTTP 403，MERCHANT_NOT_QUALIFIED | 功能设计Delta_spec.md:966-971，A1 |
| TEST-AR07-UC001-A02 | 商家无商品管理权限 | 异常 | 商家已登录 | 无权限商家请求创建商品 | AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001 | 验证权限控制 | HTTP 403，PERMISSION_DENIED | 功能设计Delta_spec.md:966-971，A2 |
| TEST-AR07-UC001-O01 | 商品创建幂等重放 | 可选 | 同一幂等键已创建草稿 | 重复提交商品创建 | AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001 | 验证商品创建幂等 | 返回已有商品草稿，不重复创建 | 功能设计Delta_spec.md:966-971，A3 |
| TEST-AR07-UC001-A03 | 商家商品服务不可用 | 异常 | 商品创建请求合法 | MerchantProductService 不可用 | AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001 | 验证服务不可用处理 | HTTP 503，MERCHANT_SERVICE_UNAVAILABLE | 功能设计Delta_spec.md:966-971，A4 |
| TEST-AR07-UC002-N01 | 更新商品信息 | 正常 | 商品草稿存在，商家有权限 | 商家提交商品字段和版本号 | AR-07/updateMerchantProduct；API-M-IF2；UCG-004-UC002 | 验证商品资料更新和版本控制 | 更新成功并返回最新状态及版本 | 功能设计Delta_spec.md:975-1009，基本流程 |
| TEST-AR07-UC002-A01 | 商品不存在 | 异常 | 商家已认证 | 更新不存在的 productId | AR-07/updateMerchantProduct；API-M-IF2；UCG-004-UC002 | 验证商品资源存在性 | HTTP 404，PRODUCT_NOT_FOUND | 功能设计Delta_spec.md:1010-1016，A1 |
| TEST-AR07-UC002-A02 | 商品类目无效 | 异常 | 商品草稿存在 | categoryId 不存在或已停用 | AR-07/updateMerchantProduct；API-M-IF2；UCG-004-UC002 | 验证类目有效性 | HTTP 400，INVALID_CATEGORY | 功能设计Delta_spec.md:1010-1016，A2 |
| TEST-AR07-UC002-A03 | 商品图片不合法 | 异常 | 商品草稿存在 | 图片 URL 格式错误或图片数量超限 | AR-07/updateMerchantProduct；API-M-IF2；UCG-004-UC002 | 验证图片字段契约 | HTTP 400，INVALID_IMAGE | 功能设计Delta_spec.md:1010-1016，A3 |
| TEST-AR07-UC002-A04 | 商品版本冲突 | 异常 | 商品已被其他操作修改 | 使用过期 version 更新 | AR-07/updateMerchantProduct；API-M-IF2；UCG-004-UC002 | 验证并发版本控制 | HTTP 409，VERSION_CONFLICT，返回最新 version 并要求重新加载 | 功能设计Delta_spec.md:1010-1016，A4 |
| TEST-AR07-UC002-A05 | 非草稿商品不可编辑 | 异常 | 商品已发布 | 提交商品资料更新 | AR-07/updateMerchantProduct；API-M-IF2；UCG-004-UC002 | 验证商品状态约束 | HTTP 409，INVALID_PRODUCT_STATUS | 功能设计Delta_spec.md:1010-1016，A5 |
| TEST-AR07-UC003-N01 | 设置 SKU 库存与价格 | 正常 | 商品草稿存在，商家有权限 | 商家提交 SKU、库存、价格及版本 | AR-07/updateSkuInventoryAndPrice；API-M-IF3；UCG-004-UC003 | 验证 SKU 库存价格更新 | 返回更新后的 SKU 数据及版本 | 功能设计Delta_spec.md:1020-1054，基本流程 |
| TEST-AR07-UC003-A01 | 库存为负数 | 异常 | 商品存在 | 提交 stock<0 | AR-07/updateSkuInventoryAndPrice；API-M-IF3；UCG-004-UC003 | 验证库存范围 | HTTP 400，NEGATIVE_STOCK | 功能设计Delta_spec.md:1055-1061，A1 |
| TEST-AR07-UC003-A02 | 商品价格非法 | 异常 | 商品存在 | salePrice/originalPrice 为负数或格式错误 | AR-07/updateSkuInventoryAndPrice；API-M-IF3；UCG-004-UC003 | 验证价格合法性 | HTTP 400，INVALID_PRICE | 功能设计Delta_spec.md:1055-1061，A2 |
| TEST-AR07-UC003-A03 | SKU 标识重复 | 异常 | 商品存在 | skus[] 含重复 skuId | AR-07/updateSkuInventoryAndPrice；API-M-IF3；UCG-004-UC003 | 验证 SKU 唯一性 | HTTP 409，DUPLICATE_SKU | 功能设计Delta_spec.md:1055-1061，A3 |
| TEST-AR07-UC003-A04 | SKU 更新版本冲突 | 异常 | 商品已被其他操作修改 | 使用过期 version 更新 SKU | AR-07/updateSkuInventoryAndPrice；API-M-IF3；UCG-004-UC003 | 验证版本并发控制 | HTTP 409，VERSION_CONFLICT，返回最新 version | 功能设计Delta_spec.md:1055-1061，A4 |
| TEST-AR07-UC003-A05 | 待更新商品不存在 | 异常 | 商家已认证 | 设置库存价格时 productId 不存在 | AR-07/updateSkuInventoryAndPrice；API-M-IF3；UCG-004-UC003 | 验证商品存在性 | HTTP 404，PRODUCT_NOT_FOUND | 功能设计Delta_spec.md:1055-1061，A5 |
| TEST-AR07-UC004-N01 | 发布商品 | 正常 | 商品资料完整，状态为 DRAFT | 商家提交发布请求 | AR-07/publishMerchantProduct；API-M-IF4；UCG-004-UC004 | 验证发布门禁、激活和目录同步 | 商品发布并返回状态、时间和目录同步结果 | 功能设计Delta_spec.md:1063-1101，基本流程 |
| TEST-AR07-UC004-A01 | 商品资料不完整 | 异常 | 商品为草稿 | 缺名称、描述、图片或 SKU 时申请发布 | AR-07/publishMerchantProduct；API-M-IF4；UCG-004-UC004 | 验证发布前置条件 | HTTP 409，PRODUCT_INCOMPLETE，并返回缺失字段 | 功能设计Delta_spec.md:1102-1108，A1 |
| TEST-AR07-UC004-O01 | 类目规则不满足进入审核 | 可选 | 商品为草稿，类目规则配置有效 | 缺少类目必填属性后申请发布 | AR-07/publishMerchantProduct；API-M-IF4；UCG-004-UC004 | 验证规则分流 | HTTP 409，CATEGORY_RULE_VIOLATION，商品进入审核队列 | 功能设计Delta_spec.md:1102-1108，A2 |
| TEST-AR07-UC004-A02 | 商品状态不允许发布 | 异常 | 商品已发布或已删除 | 再次申请发布 | AR-07/publishMerchantProduct；API-M-IF4；UCG-004-UC004 | 验证发布状态约束 | HTTP 409，INVALID_PRODUCT_STATUS | 功能设计Delta_spec.md:1102-1108，A3 |
| TEST-AR07-UC004-A03 | 发布版本冲突 | 异常 | 商品已被其他操作修改 | 使用过期 version 发布 | AR-07/publishMerchantProduct；API-M-IF4；UCG-004-UC004 | 验证版本控制 | HTTP 409，VERSION_CONFLICT，并返回最新 version | 功能设计Delta_spec.md:1102-1108，A4 |
| TEST-AR07-UC004-O02 | 目录同步失败后待重试 | 可选 | 商品满足发布条件 | ProductCatalogService 同步失败 | AR-07/publishMerchantProduct；API-M-IF4；UCG-004-UC004 | 验证发布后的异步恢复 | 商品状态更新为 ON_SALE，catalogSyncStatus=SYNC_PENDING，记录待同步任务并重试 | 功能设计Delta_spec.md:1102-1108，A5 |
