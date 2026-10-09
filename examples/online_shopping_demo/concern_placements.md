# 在线商城购物系统：架构与关注点检查挂载

数据表为逻辑资源；框架抽象服务为分析视图，不表示新增部署。缺少 SSD 对应交换时保留业务检查位置并明确待确认。

- 抽取关联 47 条：原文明示 40 条；待确认 7 条。
- 来源约束 139 条；118 条尚无精确 SSD 交换，保留责任方和待确认检查位置。

## 有证据的组件补充

- CategoryService（NODE-F332011A86）：功能设计_spec.md:1004-1004

## 调用与回调关联

|用例/步骤|调用方 → 被调用方|操作|来源|证据状态与依据|
|---|---|---|---|---|
|UCG-001-UC001/4|ProductCatalogService → product 表|根据请求条件查询 product 表，涉及字段 product_id、product_name、category_id、cover_image_url、sale_price、original_price、stock_quantity、sales_count、status、merchant_id、updated_at|功能设计_spec.md:502-502；功能设计_spec.md:1120-1120|confirmed：UCG-001-UC001：功能设计_spec.md:502 明确写 ProductCatalogService 按请求条件查询 product 表；1120 又给出 listProducts → ProductCatalogService → product 表的调用链。可确认这是逻辑数据资源关系。|
|UCG-001-UC002/3|ProductCatalogService → product 表|根据 productId 查询 product 表，获取 product_id、product_name、description、image_urls、sale_price、original_price、stock_quantity、sales_count、status、merchant_id、updated_at|功能设计_spec.md:544-544；功能设计_spec.md:1126-1126|confirmed：UCG-001-UC002：功能设计_spec.md:544 明确写 ProductCatalogService 根据 productId 查询 product 表；1126 给出 getProductDetail → ProductCatalogService → product 表。可确认逻辑资源关系。|
|UCG-001-UC003/2|CartService → ProductCatalogService|商品与SKU校验能力，传入 productId 和 skuId|功能设计_spec.md:587-588；功能设计_spec.md:1132-1132|confirmed：UCG-001-UC003：功能设计_spec.md:587-588 明确调用 ProductCatalogService 的商品与 SKU 校验能力并查询两表；1132 将 addCartItem → CartService 调用 getProductDetail → ProductCatalogService 校验连在一起，支持该服务间关系。|
|UCG-001-UC003/2|ProductCatalogService → product 表和 sku 表|查询 product 表和 sku 表|功能设计_spec.md:588-588|confirmed：UCG-001-UC003：功能设计_spec.md:588 明确 ProductCatalogService 查询 product 表和 sku 表并返回校验结果；目标是逻辑表资源。|
|UCG-001-UC003/3|CartService → cart_item 表|写入 cart_item 表|功能设计_spec.md:592-592|confirmed：UCG-001-UC003：功能设计_spec.md:592 明确 CartService 写入 cart_item 表及字段，支持该逻辑数据资源关系。|
|UCG-002-UC001/4|OrderService → CartService|读取 cart_item 表中 cartItemIds 对应的购物车条目，获取 product_id、sku_id、quantity、unit_price|功能设计_spec.md:636-636|needs_confirmation：UCG-002-UC001：功能设计_spec.md:636 明确在线商城系统调用 CartService 读取 cart_item；但该条边把调用方记为 OrderService，来源没有说 OrderService 调用 CartService。1138 仅把 createOrder 映射到 OrderService，未补足这条跨服务调用。CartService 读取表有依据，OrderService → CartService 的调用方归属仍待确认。|
|UCG-002-UC001/5|OrderService → ProductCatalogService|价格与库存校验能力，传入各商品的 productId、skuId、quantity|功能设计_spec.md:637-638；功能设计_spec.md:1138-1138|confirmed：UCG-002-UC001：功能设计_spec.md:637-638 明确调用 ProductCatalogService 做价格/库存校验；1138 明确 createOrder → OrderService 调用 validatePriceStock → ProductCatalogService，支持该边。|
|UCG-002-UC001/6|ProductCatalogService → product 表和 sku 表|查询 product 表和 sku 表获取 sale_price、stock_quantity、status|功能设计_spec.md:638-638|confirmed：UCG-002-UC001：功能设计_spec.md:638 明确 ProductCatalogService 查询 product 与 sku 表并读取 sale_price、stock_quantity、status；目标为逻辑表资源。|
|UCG-002-UC001/8|OrderService → address 表|校验收货地址，查询 address 表获取 recipient_name、phone、province、city、district、detail_address|功能设计_spec.md:640-640|needs_confirmation：UCG-002-UC001：功能设计_spec.md:640 明确在线商城系统查询 address 表并读取地址字段，表访问有原文依据；但来源未将该查询明确分配给图中的 OrderService 调用方，故 OrderService → address 表的精确归属仍需确认。|
|UCG-002-UC001/10|OrderService → order 表和 order_item 表|创建订单并锁定库存，写入 order 表（order_id、customer_id、status、total_amount、payable_amount、coupon_id、address_snapshot、expire_at、created_at）和 order_item 表（order_item_id、order_id、product_id、sku_id、quantity、unit_price、subtotal）|功能设计_spec.md:642-642；功能设计_spec.md:1138-1138|confirmed：UCG-002-UC001：功能设计_spec.md:642 明确 OrderService 按 idempotencyKey 校验、创建订单并写入 order 与 order_item 表；1138 同时映射 createOrder → OrderService。|
|UCG-002-UC002/2|PaymentAdapter → OrderService|查询 order 表，获取 order_id、customer_id、status、payable_amount、expire_at|功能设计_spec.md:685-685|needs_confirmation：UCG-002-UC002：功能设计_spec.md:685 明确在线商城系统调用 OrderService 查询 order 表；但该边的调用方是 PaymentAdapter，685 未说 PaymentAdapter 调用 OrderService。1144 只说明 PaymentAdapter 对外调用 PaymentService 和接收回调，不能证明这条 PaymentAdapter → OrderService 边。|
|UCG-002-UC002/3|PaymentAdapter → PaymentService|发起支付请求，传入 orderId、amount、paymentMethod、notifyUrl|功能设计_spec.md:687-688；功能设计_spec.md:1144-1144|confirmed：UCG-002-UC002：功能设计_spec.md:687-688 明确 PaymentAdapter 向 ACT-003 PaymentService 发起支付请求并接收支付结果；1144 也列出 createPayment → PaymentAdapter → 外部 PaymentService。|
|UCG-002-UC002/4|PaymentAdapter → payment 表|写入 payment 表（payment_id、order_id、amount、payment_method、provider_trade_no、status、paid_at、created_at）|功能设计_spec.md:689-689|confirmed：UCG-002-UC002：功能设计_spec.md:689 明确 PaymentAdapter 写入 payment 表并返回支付信息，支持逻辑表资源关系。|
|UCG-002-UC002/5|PaymentAdapter → order 表|更新 order 表中订单状态为 PAID，记录支付流水|功能设计_spec.md:690-690；系统需求_spec.md:191-191|needs_confirmation：UCG-002-UC002：功能设计_spec.md:690 与系统需求_spec.md:191 明确在线商城系统把订单状态更新为 PAID 并记录支付流水；但没有把此 order 表更新明确归给 PaymentAdapter。操作存在，PaymentAdapter → order 表的调用方归属仍需确认。|
|UCG-002-UC002/5|PaymentService → PaymentAdapter|支付结果回调通知（按 paymentId 幂等处理）|功能设计_spec.md:700-700；系统需求_spec.md:206-207|confirmed：UCG-002-UC002：功能设计_spec.md:687-688 明确 PaymentService 返回支付结果给 PaymentAdapter；700 说明支付回调通知到达时按 paymentId 幂等处理，系统需求_spec.md:206-207 也明确重复通知处理，支持外部回调方向。|
|UCG-002-UC003/3|OrderService → order 表|查询 order 表，获取 order_id、customer_id、status、total_amount、payable_amount、coupon_id、address_snapshot、created_at、updated_at|功能设计_spec.md:732-732|confirmed：UCG-002-UC003：功能设计_spec.md:732 明确 OrderService 查询 order 表并读取订单字段；这是逻辑数据资源关系。|
|UCG-002-UC003/3|OrderService → order_item 表|查询 order_item 表，获取各商品条目的 order_item_id、product_id、sku_id、quantity、unit_price、subtotal|功能设计_spec.md:733-733|confirmed：UCG-002-UC003：功能设计_spec.md:733 明确 OrderService 查询 order_item 表并读取商品条目字段；这是逻辑数据资源关系。|
|UCG-002-UC003/3|OrderService → payment 表|查询 payment 表，获取 payment_id、payment_method、provider_trade_no、payment_status、paid_at|功能设计_spec.md:734-734|confirmed：UCG-002-UC003：功能设计_spec.md:734 明确 OrderService 查询 payment 表并读取支付字段；这是逻辑数据资源关系。|
|UCG-002-UC003/3|OrderService → shipment 表|查询 shipment 表，获取 shipment_id、carrier_code、tracking_number、shipment_status、shipped_at（若已发货）|功能设计_spec.md:735-735|confirmed：UCG-002-UC003：功能设计_spec.md:735 明确 OrderService 查询 shipment 表并读取物流字段；这是逻辑数据资源关系。|
|UCG-003-UC001/7|OrderService → shipment 表|写入 shipment 记录（shipment_id、order_id、carrier_code、tracking_number、shipped_items、status、shipped_at、created_at、updated_at）|功能设计_spec.md:779-779|confirmed：UCG-003-UC001：功能设计_spec.md:779 明确 OrderService 写入 shipment 记录及字段，支持逻辑表资源关系。|
|UCG-003-UC001/8|OrderService → order 表|更新订单状态为 SHIPPED|功能设计_spec.md:780-780|confirmed：UCG-003-UC001：功能设计_spec.md:780 明确 OrderService 更新 order 表状态为 SHIPPED，支持逻辑表资源关系。|
|UCG-003-UC001/9|OrderService → LogisticsService|登记物流单号（传入 trackingNumber、carrierCode、orderId）|功能设计_spec.md:781-781；功能设计_spec.md:1156-1156|confirmed：UCG-003-UC001：功能设计_spec.md:781 明确 OrderService 向 ACT-004 LogisticsService 登记物流单号及参数；1156 也列出 createShipment → OrderService → 外部 LogisticsService。|
|UCG-003-UC002/4|LogisticsServiceAdapter → logistics_event 表|按 eventId 幂等校验，查询是否已存在相同 eventId。|功能设计_spec.md:823-823|confirmed：UCG-003-UC002：功能设计_spec.md:823 明确 LogisticsServiceAdapter 按 eventId 幂等校验并查询 logistics_event 表。|
|UCG-003-UC002/4|LogisticsServiceAdapter → logistics_event 表|写入 logistics_event 表（event_id、tracking_number、event_code、event_time、location、shipment_id、order_id、created_at）。|功能设计_spec.md:824-824|confirmed：UCG-003-UC002：功能设计_spec.md:824 明确 LogisticsServiceAdapter 写入 logistics_event 表及字段，支持逻辑资源关系。|
|UCG-003-UC002/2|LogisticsServiceAdapter → shipment 表|校验 trackingNumber 是否存在，查询 shipment 表获取 shipment_id、order_id、carrier_code。|功能设计_spec.md:821-821|confirmed：UCG-003-UC002：功能设计_spec.md:821 明确 LogisticsServiceAdapter 检查 trackingNumber 并查询 shipment 表。|
|UCG-003-UC002/5|LogisticsServiceAdapter → shipment 表|更新 shipment 表中的物流状态摘要（last_event_code、last_event_time、last_location、last_updated_at）。|功能设计_spec.md:825-825|confirmed：UCG-003-UC002：功能设计_spec.md:825 明确 LogisticsServiceAdapter 更新 shipment 表中的物流状态摘要。|
|UCG-003-UC002/1|LogisticsService → LogisticsServiceAdapter|发送 POST /api/v1/logistics/events 请求到在线商城系统，请求体包含 eventId、trackingNumber、eventCode、eventTime、location、signature。|系统需求_spec.md:268-269；功能设计_spec.md:819-819；功能设计_spec.md:827-827；功能设计_spec.md:1161-1161|confirmed：UCG-003-UC002：功能设计_spec.md:819 明确 ACT-004 LogisticsService 向在线商城系统发送 POST /api/v1/logistics/events；同一处理流程821-825明确由 LogisticsServiceAdapter 校验、写入和更新，支持将系统入口映射到该接收适配器。系统需求_spec.md:268-269 也描述物流服务推送轨迹。|
|UCG-003-UC002/5|LogisticsServiceAdapter → LogisticsService|向ACT-004返回 HTTP 200，响应体包含 accepted、duplicate。|功能设计_spec.md:827-827|confirmed：UCG-003-UC002：功能设计_spec.md:827 明确在线商城系统向 ACT-004 返回 HTTP 200 及 accepted、duplicate；同一事件接收用例由 LogisticsServiceAdapter 处理（821-825），故该响应属于该入口处理链。|
|UCG-003-UC003/3|LogisticsServiceAdapter → OrderService|查询 order 表，校验订单属于当前顾客且状态为 SHIPPED 或之后|功能设计_spec.md:866-866|needs_confirmation：UCG-003-UC003：功能设计_spec.md:866 明确在线商城系统调用 OrderService 查询订单归属和状态；该条边却把调用方记为 LogisticsServiceAdapter。来源没有说物流适配器调用 OrderService，需确认准确调用方或改为系统级关系。|
|UCG-003-UC003/3|LogisticsServiceAdapter → shipment 表|查询 shipment 表，获取 shipment_id、carrier_code、tracking_number、status、shipped_at|功能设计_spec.md:868-868|confirmed：UCG-003-UC003：功能设计_spec.md:868 明确 LogisticsServiceAdapter 查询 shipment 表并读取物流字段，支持逻辑资源关系。|
|UCG-003-UC003/3|LogisticsServiceAdapter → logistics_event 表|查询 logistics_event 表，获取该物流单的所有事件节点，按 event_time 排序|功能设计_spec.md:869-869|confirmed：UCG-003-UC003：功能设计_spec.md:869 明确 LogisticsServiceAdapter 查询 logistics_event 表并按 event_time 排序，支持逻辑资源关系。|
|UCG-003-UC003/3|LogisticsServiceAdapter → LogisticsService|查询最新物流轨迹|功能设计_spec.md:870-870；系统需求_spec.md:295-295|confirmed：UCG-003-UC003：功能设计_spec.md:870 明确本地数据过期时 LogisticsServiceAdapter 调用 ACT-004 LogisticsService 查询最新轨迹；系统需求_spec.md:295 也明确过期时调用物流服务。|
|UCG-003-UC004/2|RefundService → OrderService|查询 order 表和 order_item 表，校验订单归属、状态与可退款金额|功能设计_spec.md:912-912|needs_confirmation：UCG-003-UC004：功能设计_spec.md:912 明确在线商城系统调用 OrderService 查询 order 与 order_item 并校验退款条件；但该边的调用方标为 RefundService，来源未说明 RefundService 调用 OrderService。916-918 明确的是 RefundService 写退款记录并调用 PaymentService，不能据此补出 RefundService → OrderService。|
|UCG-003-UC004/3|RefundService → refund 表|写入 refund 表并更新退款状态|功能设计_spec.md:916-916；功能设计_spec.md:919-919|confirmed：UCG-003-UC004：功能设计_spec.md:916 明确 RefundService 写入 refund 表；919 明确更新退款状态，支持逻辑表资源关系。|
|UCG-003-UC004/4|RefundService → PaymentService|提交退款请求|系统需求_spec.md:321-321；功能设计_spec.md:917-917；功能设计_spec.md:1174-1174|confirmed：UCG-003-UC004：功能设计_spec.md:917 明确 RefundService 向 ACT-003 PaymentService 提交退款请求及参数；系统需求_spec.md:321 和 V5 行1174相符。|
|UCG-003-UC004/4|PaymentService → RefundService|向 RefundService 返回退款结果|系统需求_spec.md:321-321；功能设计_spec.md:918-918|confirmed：UCG-003-UC004：功能设计_spec.md:918 明确 PaymentService 处理退款并向 RefundService 返回退款结果，支持响应方向。|
|UCG-004-UC001/10|MerchantProductService → merchant 表|查询商家经营资质（获取 merchant_id、qualification_status、product_permission）|功能设计_spec.md:960-960|confirmed：UCG-004-UC001：功能设计_spec.md:960 明确 MerchantProductService 查询 merchant 表并读取资质和权限字段，支持逻辑表资源关系。|
|UCG-004-UC001/12|MerchantProductService → product 表|写入商品记录（product_id、merchant_id、name、description、category_id、status（DRAFT）、version、created_at、updated_at）|功能设计_spec.md:962-962|confirmed：UCG-004-UC001：功能设计_spec.md:962 明确 MerchantProductService 写入 product 表及字段，支持逻辑表资源关系。|
|UCG-004-UC001/1|MerchantProductService → Category records|Read or update Category records|功能设计_spec.md:1179-1179|needs_confirmation：UCG-004-UC001：功能设计_spec.md:1179 仅列 POST 请求字段 name/categoryId/description/imageUrls[]、返回字段和 CATEGORY_NOT_FOUND 等错误码，没有 CategoryService 调用或读取/更新 Category records 的步骤。962 明确的是写 product 表，不能证明 MerchantProductService → Category records。该关联应待确认。|
|UCG-004-UC002/4|MerchantProductService → product 表|查询 product 表获取 product_id、merchant_id、status、version，并更新 name、description、category_id、image_urls、version（+1）、updated_at|功能设计_spec.md:1003-1003；功能设计_spec.md:1006-1006|confirmed：UCG-004-UC002：功能设计_spec.md:1003 与1006明确 MerchantProductService 查询并更新 product 表字段，支持逻辑资源关系。|
|UCG-004-UC002/4|MerchantProductService → CategoryService|validateCategory → 查询 category 表获取 category_id、status 校验分类有效且未停用|功能设计_spec.md:1004-1004；功能设计_spec.md:1186-1186|confirmed：UCG-004-UC002：功能设计_spec.md:1004 明确 MerchantProductService 调用 CategoryService 校验 categoryId；1186 也列出 updateMerchantProduct → MerchantProductService → validateCategory → CategoryService。|
|UCG-004-UC002/4|MerchantProductService → category 表|查询 category 表获取 category_id、status，确认分类有效且未停用|功能设计_spec.md:1004-1004|confirmed：UCG-004-UC002：功能设计_spec.md:1004 明确 category 表查询及 category_id/status 字段，支持逻辑资源关系。|
|UCG-004-UC003/5|MerchantProductService → product 表|查询 product 表获取 product_id、merchant_id、status、version；更新 version（+1）和 updated_at|功能设计_spec.md:1048-1048；功能设计_spec.md:1051-1051|confirmed：UCG-004-UC003：功能设计_spec.md:1048 明确查询 product 表并校验归属、状态、version；1051 明确更新 version 与 updated_at，支持逻辑资源关系。|
|UCG-004-UC003/7|MerchantProductService → sku 表|写入/更新 sku 表（sku_id、product_id、attributes、stock_quantity、sale_price、original_price、updated_at）|功能设计_spec.md:1050-1050；功能设计_spec.md:1191-1192|confirmed：UCG-004-UC003：功能设计_spec.md:1050 明确 MerchantProductService 写入/更新 sku 表及字段；1191-1192列出 SKU 接口和更新操作，支持逻辑资源关系。|
|UCG-004-UC004/3|MerchantProductService → product/category/sku 表|查询 product 表（product_id、merchant_id、status、version）及 category 表（必填属性与发布规则）、sku 表（有效SKU、stock_quantity、sale_price）；更新 product 表 status、published_at、version、updated_at|功能设计_spec.md:1093-1096；系统需求_spec.md:414-414|confirmed：UCG-004-UC004：功能设计_spec.md:1093-1096 明确 MerchantProductService 查询 product/category/sku 表并更新 product 状态；系统需求_spec.md:414 同样要求校验资料、类目、库存和价格。目标是逻辑数据资源集合。|
|UCG-004-UC004/5|MerchantProductService → ProductCatalogService|调用 refreshCatalog 刷新可售索引，传入 productId 和最新商品数据|系统需求_spec.md:417-417；功能设计_spec.md:1097-1098；功能设计_spec.md:1198-1198|confirmed：UCG-004-UC004：功能设计_spec.md:1097-1098 明确 MerchantProductService 调用 ProductCatalogService 刷新可售索引并传入 productId/数据，后者更新索引并返回同步结果；系统需求_spec.md:417也要求通知目录服务刷新索引。|
|UCG-004-UC004/5|MerchantProductService → ProductCatalogService|向 MerchantProductService 返回索引同步结果|功能设计_spec.md:1098-1098|confirmed：UCG-004-UC004：功能设计_spec.md:1098 明确 ProductCatalogService 更新商品检索索引后向 MerchantProductService 返回同步结果，支持该响应方向。|

## 检查位置与关注点

|用例/步骤|检查对象|关注点|SSD 交换/定位状态|已有实现组件/待确认挂载|来源|
|---|---|---|---|---|---|
|UCG-001-UC001/2|ProductDisplayService|数据完整性 (api.data.completeness)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|数据格式 (api.data.format)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|在线商城购物系统|数据格式 (api.data.format)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|数据合法性 (api.data.legality)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|数据长度 (api.data.length)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|在线商城购物系统|数据长度 (api.data.length)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|数据范围 (api.data.range)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|在线商城购物系统|数据范围 (api.data.range)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|数据大小 (api.data.size)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|在线商城购物系统|数据大小 (api.data.size)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|数据类型 (api.data.type)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|在线商城购物系统|数据类型 (api.data.type)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|超时关注点 (common.timeout)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|顾客|身份认证 (human.authentication)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|顾客|权限控制 (human.authorization)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|显示正确性 (service.display_interaction.display_correctness)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC001/2|ProductDisplayService|渲染性能 (service.display_interaction.render_performance)|EXCH-ED4C0A89A0||系统需求_spec.md:85-110；功能设计_spec.md:359-366；功能设计_spec.md:473-515；功能设计_spec.md:1116-1121|
|UCG-001-UC002/2|ProductDisplayService|数据完整性 (api.data.completeness)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|数据格式 (api.data.format)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|在线商城购物系统|数据格式 (api.data.format)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|数据合法性 (api.data.legality)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|数据长度 (api.data.length)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|在线商城购物系统|数据长度 (api.data.length)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|数据范围 (api.data.range)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|在线商城购物系统|数据范围 (api.data.range)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|数据大小 (api.data.size)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|在线商城购物系统|数据大小 (api.data.size)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|数据类型 (api.data.type)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|在线商城购物系统|数据类型 (api.data.type)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|超时关注点 (common.timeout)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|顾客|身份认证 (human.authentication)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|顾客|权限控制 (human.authorization)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|显示正确性 (service.display_interaction.display_correctness)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-001-UC002/2|ProductDisplayService|渲染性能 (service.display_interaction.render_performance)|EXCH-72B79A0231||系统需求_spec.md:111-133；功能设计_spec.md:367-374；功能设计_spec.md:516-556；功能设计_spec.md:1122-1127|
|UCG-003-UC003/2|LogisticsServiceAdapter|数据完整性 (api.data.completeness)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|数据格式 (api.data.format)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|在线商城购物系统|数据格式 (api.data.format)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|数据合法性 (api.data.legality)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|数据长度 (api.data.length)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|在线商城购物系统|数据长度 (api.data.length)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|数据范围 (api.data.range)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|在线商城购物系统|数据范围 (api.data.range)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|数据大小 (api.data.size)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|在线商城购物系统|数据大小 (api.data.size)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|数据类型 (api.data.type)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|在线商城购物系统|数据类型 (api.data.type)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|超时关注点 (common.timeout)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|顾客|身份认证 (human.authentication)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|顾客|权限控制 (human.authorization)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|数据可见性 (service.query_retrieval.data_visibility)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|资源存在性 (service.query_retrieval.resource_existence)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC003/2|LogisticsServiceAdapter|结果正确性 (service.query_retrieval.result_correctness)|EXCH-8C4AEC9C3E||系统需求_spec.md:282-305；功能设计_spec.md:423-430；功能设计_spec.md:837-881；功能设计_spec.md:1164-1169|
|UCG-003-UC004/2|RefundService|数据完整性 (api.data.completeness)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|数据格式 (api.data.format)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|在线商城购物系统|数据格式 (api.data.format)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|数据合法性 (api.data.legality)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|数据长度 (api.data.length)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|在线商城购物系统|数据长度 (api.data.length)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|数据范围 (api.data.range)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|在线商城购物系统|数据范围 (api.data.range)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|数据大小 (api.data.size)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|在线商城购物系统|数据大小 (api.data.size)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|数据类型 (api.data.type)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|在线商城购物系统|数据类型 (api.data.type)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|超时关注点 (common.timeout)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|顾客|身份认证 (human.authentication)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|顾客|权限控制 (human.authorization)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|业务约束 (service.resource_mutation.business_constraint)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-003-UC004/2|RefundService|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-ED50F5ACE8||系统需求_spec.md:306-330；功能设计_spec.md:431-438；功能设计_spec.md:882-929；功能设计_spec.md:1170-1175|
|UCG-001-UC003/3|CartService|数据完整性 (api.data.completeness)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|数据格式 (api.data.format)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|在线商城购物系统|数据格式 (api.data.format)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|数据合法性 (api.data.legality)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|数据长度 (api.data.length)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|在线商城购物系统|数据长度 (api.data.length)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|数据范围 (api.data.range)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|在线商城购物系统|数据范围 (api.data.range)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|数据大小 (api.data.size)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|在线商城购物系统|数据大小 (api.data.size)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|数据类型 (api.data.type)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|在线商城购物系统|数据类型 (api.data.type)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|超时关注点 (common.timeout)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|顾客|身份认证 (human.authentication)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|顾客|权限控制 (human.authorization)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|业务约束 (service.resource_mutation.business_constraint)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-001-UC003/3|CartService|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-8E4113B27A||系统需求_spec.md:134-157；功能设计_spec.md:375-382；功能设计_spec.md:557-604；功能设计_spec.md:1128-1133|
|UCG-002-UC002/3|PaymentAdapter|数据完整性 (api.data.completeness)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|数据格式 (api.data.format)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|在线商城购物系统|数据格式 (api.data.format)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|数据合法性 (api.data.legality)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|数据长度 (api.data.length)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|在线商城购物系统|数据长度 (api.data.length)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|数据范围 (api.data.range)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|在线商城购物系统|数据范围 (api.data.range)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|数据大小 (api.data.size)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|在线商城购物系统|数据大小 (api.data.size)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|数据类型 (api.data.type)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|在线商城购物系统|数据类型 (api.data.type)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|超时关注点 (common.timeout)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|顾客|身份认证 (human.authentication)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|顾客|权限控制 (human.authorization)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|业务约束 (service.resource_mutation.business_constraint)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC002/3|PaymentAdapter|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-14D35159A9||系统需求_spec.md:183-208；功能设计_spec.md:391-398；功能设计_spec.md:655-701；功能设计_spec.md:1140-1145|
|UCG-002-UC003/3|OrderService|数据完整性 (api.data.completeness)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|数据格式 (api.data.format)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|在线商城购物系统|数据格式 (api.data.format)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|数据合法性 (api.data.legality)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|数据长度 (api.data.length)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|在线商城购物系统|数据长度 (api.data.length)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|数据范围 (api.data.range)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|在线商城购物系统|数据范围 (api.data.range)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|数据大小 (api.data.size)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|在线商城购物系统|数据大小 (api.data.size)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|数据类型 (api.data.type)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|在线商城购物系统|数据类型 (api.data.type)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|超时关注点 (common.timeout)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|顾客|身份认证 (human.authentication)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|顾客|权限控制 (human.authorization)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|数据可见性 (service.query_retrieval.data_visibility)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|资源存在性 (service.query_retrieval.resource_existence)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-002-UC003/3|OrderService|结果正确性 (service.query_retrieval.result_correctness)|EXCH-DB62DBDDB7||系统需求_spec.md:209-232；功能设计_spec.md:399-406；功能设计_spec.md:702-746；功能设计_spec.md:1146-1151|
|UCG-003-UC001/3|LogisticsServiceAdapter|数据完整性 (api.data.completeness)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|数据格式 (api.data.format)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|在线商城购物系统|数据格式 (api.data.format)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|数据合法性 (api.data.legality)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|数据长度 (api.data.length)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|在线商城购物系统|数据长度 (api.data.length)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|数据范围 (api.data.range)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|在线商城购物系统|数据范围 (api.data.range)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|数据大小 (api.data.size)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|在线商城购物系统|数据大小 (api.data.size)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|数据类型 (api.data.type)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|在线商城购物系统|数据类型 (api.data.type)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|超时关注点 (common.timeout)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|商家|身份认证 (human.authentication)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|商家|权限控制 (human.authorization)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|业务约束 (service.resource_mutation.business_constraint)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-003-UC001/3|LogisticsServiceAdapter|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-293276D860||系统需求_spec.md:233-257；功能设计_spec.md:407-414；功能设计_spec.md:747-792；功能设计_spec.md:1152-1157|
|UCG-004-UC001/3|MerchantProductService|数据完整性 (api.data.completeness)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|数据格式 (api.data.format)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|在线商城购物系统|数据格式 (api.data.format)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|数据合法性 (api.data.legality)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|数据长度 (api.data.length)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|在线商城购物系统|数据长度 (api.data.length)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|数据范围 (api.data.range)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|在线商城购物系统|数据范围 (api.data.range)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|数据大小 (api.data.size)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|在线商城购物系统|数据大小 (api.data.size)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|数据类型 (api.data.type)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|在线商城购物系统|数据类型 (api.data.type)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|超时关注点 (common.timeout)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|商家|身份认证 (human.authentication)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|商家|权限控制 (human.authorization)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|业务约束 (service.resource_mutation.business_constraint)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC001/3|MerchantProductService|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-32118567D1||系统需求_spec.md:331-352；功能设计_spec.md:439-446；功能设计_spec.md:930-972；功能设计_spec.md:1176-1181|
|UCG-004-UC004/3|MerchantProductService|数据完整性 (api.data.completeness)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|数据格式 (api.data.format)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|在线商城购物系统|数据格式 (api.data.format)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|数据合法性 (api.data.legality)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|数据长度 (api.data.length)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|在线商城购物系统|数据长度 (api.data.length)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|数据范围 (api.data.range)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|在线商城购物系统|数据范围 (api.data.range)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|数据大小 (api.data.size)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|在线商城购物系统|数据大小 (api.data.size)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|数据类型 (api.data.type)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|在线商城购物系统|数据类型 (api.data.type)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|超时关注点 (common.timeout)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|商家|身份认证 (human.authentication)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|商家|权限控制 (human.authorization)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|失败恢复 (service.release_activation.failure_recovery)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|发布前置条件 (service.release_activation.prerequisite)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-004-UC004/3|MerchantProductService|发布结果一致性 (service.release_activation.result_consistency)|EXCH-E279D1A3F3||系统需求_spec.md:401-425；功能设计_spec.md:463-470；功能设计_spec.md:1063-1109；功能设计_spec.md:1194-1199|
|UCG-001-UC001/4|product 表资源服务|数据库可用性 (internal_database.availability)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|幂等性 (internal_database.idempotency)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|持久化能力 (internal_database.persistence)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|查询性能 (internal_database.query_performance)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC001/4|product 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-24B52AD0A7||功能设计_spec.md:502-502|
|UCG-001-UC002/3|product 表资源服务|数据库可用性 (internal_database.availability)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|幂等性 (internal_database.idempotency)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|持久化能力 (internal_database.persistence)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|查询性能 (internal_database.query_performance)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-001-UC002/3|product 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-D7B76388B2||功能设计_spec.md:544-544|
|UCG-002-UC001/4|OrderService|数据完整性 (api.data.completeness)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|数据格式 (api.data.format)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|在线商城购物系统|数据格式 (api.data.format)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|数据合法性 (api.data.legality)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|数据长度 (api.data.length)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|在线商城购物系统|数据长度 (api.data.length)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|数据范围 (api.data.range)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|在线商城购物系统|数据范围 (api.data.range)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|数据大小 (api.data.size)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|在线商城购物系统|数据大小 (api.data.size)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|数据类型 (api.data.type)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|在线商城购物系统|数据类型 (api.data.type)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|超时关注点 (common.timeout)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|顾客|身份认证 (human.authentication)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|顾客|权限控制 (human.authorization)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|业务约束 (service.resource_mutation.business_constraint)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-002-UC001/4|OrderService|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-B72440858E||系统需求_spec.md:158-182；功能设计_spec.md:383-390；功能设计_spec.md:605-654；功能设计_spec.md:1134-1139|
|UCG-003-UC003/3|OrderService|内部依赖可用性 (service.dependency.availability)|EXCH-303AA6307A||功能设计_spec.md:866-866|
|UCG-003-UC003/3|对象未定位|调用顺序 (service_relation.call_order)|EXCH-303AA6307A||功能设计_spec.md:866-866|
|UCG-003-UC003/3|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-303AA6307A||功能设计_spec.md:866-866|
|UCG-003-UC003/3|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-303AA6307A||功能设计_spec.md:866-866|
|UCG-003-UC003/3|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-303AA6307A||功能设计_spec.md:866-866|
|UCG-003-UC003/3|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-303AA6307A||功能设计_spec.md:866-866|
|UCG-003-UC003/3|对象未定位|幂等性 (service_relation.idempotency)|EXCH-303AA6307A||功能设计_spec.md:866-866|
|UCG-003-UC004/2|OrderService|内部依赖可用性 (service.dependency.availability)|EXCH-7101B3C0D5||功能设计_spec.md:912-912|
|UCG-003-UC004/2|对象未定位|调用顺序 (service_relation.call_order)|EXCH-7101B3C0D5||功能设计_spec.md:912-912|
|UCG-003-UC004/2|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-7101B3C0D5||功能设计_spec.md:912-912|
|UCG-003-UC004/2|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-7101B3C0D5||功能设计_spec.md:912-912|
|UCG-003-UC004/2|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-7101B3C0D5||功能设计_spec.md:912-912|
|UCG-003-UC004/2|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-7101B3C0D5||功能设计_spec.md:912-912|
|UCG-003-UC004/2|对象未定位|幂等性 (service_relation.idempotency)|EXCH-7101B3C0D5||功能设计_spec.md:912-912|
|UCG-001-UC003/2|ProductCatalogService|内部依赖可用性 (service.dependency.availability)|EXCH-08716862FC||功能设计_spec.md:587-588|
|UCG-001-UC003/2|对象未定位|调用顺序 (service_relation.call_order)|EXCH-08716862FC||功能设计_spec.md:587-588|
|UCG-001-UC003/2|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-08716862FC||功能设计_spec.md:587-588|
|UCG-001-UC003/2|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-08716862FC||功能设计_spec.md:587-588|
|UCG-001-UC003/2|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-08716862FC||功能设计_spec.md:587-588|
|UCG-001-UC003/2|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-08716862FC||功能设计_spec.md:587-588|
|UCG-001-UC003/2|对象未定位|幂等性 (service_relation.idempotency)|EXCH-08716862FC||功能设计_spec.md:587-588|
|UCG-002-UC002/2|OrderService|内部依赖可用性 (service.dependency.availability)|EXCH-8F28263B7F||功能设计_spec.md:685-685|
|UCG-002-UC002/2|对象未定位|调用顺序 (service_relation.call_order)|EXCH-8F28263B7F||功能设计_spec.md:685-685|
|UCG-002-UC002/2|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-8F28263B7F||功能设计_spec.md:685-685|
|UCG-002-UC002/2|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-8F28263B7F||功能设计_spec.md:685-685|
|UCG-002-UC002/2|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-8F28263B7F||功能设计_spec.md:685-685|
|UCG-002-UC002/2|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-8F28263B7F||功能设计_spec.md:685-685|
|UCG-002-UC002/2|对象未定位|幂等性 (service_relation.idempotency)|EXCH-8F28263B7F||功能设计_spec.md:685-685|
|UCG-002-UC003/3|order 表资源服务|数据库可用性 (internal_database.availability)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|幂等性 (internal_database.idempotency)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|持久化能力 (internal_database.persistence)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|查询性能 (internal_database.query_performance)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-002-UC003/3|order 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-42F3CF5CA8||功能设计_spec.md:732-732|
|UCG-003-UC001/7|shipment 表资源服务|数据库可用性 (internal_database.availability)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|幂等性 (internal_database.idempotency)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|持久化能力 (internal_database.persistence)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|查询性能 (internal_database.query_performance)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC001/7|shipment 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-08C8B2B507||功能设计_spec.md:779-779|
|UCG-003-UC002/5|LogisticsServiceAdapter|数据完整性 (api.data.completeness)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|数据格式 (api.data.format)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|在线商城购物系统|数据格式 (api.data.format)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|数据合法性 (api.data.legality)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|数据长度 (api.data.length)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|在线商城购物系统|数据长度 (api.data.length)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|数据范围 (api.data.range)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|在线商城购物系统|数据范围 (api.data.range)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|数据大小 (api.data.size)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|在线商城购物系统|数据大小 (api.data.size)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|数据类型 (api.data.type)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|在线商城购物系统|数据类型 (api.data.type)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|超时关注点 (common.timeout)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|业务约束 (service.resource_mutation.business_constraint)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC002/5|LogisticsServiceAdapter|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-5044511CE9||系统需求_spec.md:258-281；功能设计_spec.md:415-422；功能设计_spec.md:793-836；功能设计_spec.md:1158-1163|
|UCG-003-UC003/3|shipment 表资源服务|数据库可用性 (internal_database.availability)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|幂等性 (internal_database.idempotency)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|持久化能力 (internal_database.persistence)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|查询性能 (internal_database.query_performance)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC003/3|shipment 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-91312FD4F0||功能设计_spec.md:868-868|
|UCG-003-UC004/3|refund 表资源服务|数据库可用性 (internal_database.availability)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|幂等性 (internal_database.idempotency)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|持久化能力 (internal_database.persistence)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|查询性能 (internal_database.query_performance)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-003-UC004/3|refund 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-0A8530E0CE||功能设计_spec.md:916-916|
|UCG-004-UC001/10|merchant 表资源服务|数据库可用性 (internal_database.availability)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|幂等性 (internal_database.idempotency)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|持久化能力 (internal_database.persistence)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|查询性能 (internal_database.query_performance)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC001/10|merchant 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-3FE192905B||功能设计_spec.md:960-960|
|UCG-004-UC002/4|MerchantProductService|数据完整性 (api.data.completeness)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|数据格式 (api.data.format)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|在线商城购物系统|数据格式 (api.data.format)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|数据合法性 (api.data.legality)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|数据长度 (api.data.length)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|在线商城购物系统|数据长度 (api.data.length)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|数据范围 (api.data.range)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|在线商城购物系统|数据范围 (api.data.range)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|数据大小 (api.data.size)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|在线商城购物系统|数据大小 (api.data.size)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|数据类型 (api.data.type)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|在线商城购物系统|数据类型 (api.data.type)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|超时关注点 (common.timeout)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|商家|身份认证 (human.authentication)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|商家|权限控制 (human.authorization)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|业务约束 (service.resource_mutation.business_constraint)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC002/4|MerchantProductService|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-178D36A0D3||系统需求_spec.md:353-376；功能设计_spec.md:447-454；功能设计_spec.md:973-1017；功能设计_spec.md:1182-1187|
|UCG-004-UC003/4|MerchantProductService|数据完整性 (api.data.completeness)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|数据格式 (api.data.format)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|在线商城购物系统|数据格式 (api.data.format)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|数据合法性 (api.data.legality)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|数据长度 (api.data.length)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|在线商城购物系统|数据长度 (api.data.length)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|数据范围 (api.data.range)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|在线商城购物系统|数据范围 (api.data.range)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|数据大小 (api.data.size)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|在线商城购物系统|数据大小 (api.data.size)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|数据类型 (api.data.type)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|在线商城购物系统|数据类型 (api.data.type)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|超时关注点 (common.timeout)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|商家|身份认证 (human.authentication)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|商家|权限控制 (human.authorization)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|业务约束 (service.resource_mutation.business_constraint)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC003/4|MerchantProductService|持久化一致性 (service.resource_mutation.persistence_consistency)|EXCH-E4B0C80650||系统需求_spec.md:377-400；功能设计_spec.md:455-462；功能设计_spec.md:1018-1062；功能设计_spec.md:1188-1193|
|UCG-004-UC004/3|product/category/sku 表资源服务|数据库可用性 (internal_database.availability)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|幂等性 (internal_database.idempotency)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|持久化能力 (internal_database.persistence)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|查询性能 (internal_database.query_performance)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-004-UC004/3|product/category/sku 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-92D14E7140||功能设计_spec.md:1093-1096|
|UCG-001-UC003/2|product 表和 sku 表资源服务|数据库可用性 (internal_database.availability)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|幂等性 (internal_database.idempotency)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|持久化能力 (internal_database.persistence)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|查询性能 (internal_database.query_performance)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-001-UC003/2|product 表和 sku 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-3E250653B7||功能设计_spec.md:588-588|
|UCG-002-UC001/4|CartService|内部依赖可用性 (service.dependency.availability)|EXCH-58280F8C64||功能设计_spec.md:636-636|
|UCG-002-UC001/4|对象未定位|调用顺序 (service_relation.call_order)|EXCH-58280F8C64||功能设计_spec.md:636-636|
|UCG-002-UC001/4|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-58280F8C64||功能设计_spec.md:636-636|
|UCG-002-UC001/4|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-58280F8C64||功能设计_spec.md:636-636|
|UCG-002-UC001/4|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-58280F8C64||功能设计_spec.md:636-636|
|UCG-002-UC001/4|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-58280F8C64||功能设计_spec.md:636-636|
|UCG-002-UC001/4|对象未定位|幂等性 (service_relation.idempotency)|EXCH-58280F8C64||功能设计_spec.md:636-636|
|UCG-002-UC002/3|PaymentService|超时关注点 (common.timeout)|EXCH-A8717CA97C||功能设计_spec.md:687-688|
|UCG-002-UC002/3|PaymentService|外部服务可用性 (external_service.availability)|EXCH-A8717CA97C||功能设计_spec.md:687-688|
|UCG-002-UC002/3|PaymentService|外部接口契约 (external_service.contract)|EXCH-A8717CA97C||功能设计_spec.md:687-688|
|UCG-002-UC002/3|顾客|身份认证 (human.authentication)|EXCH-A8717CA97C||功能设计_spec.md:687-688|
|UCG-002-UC002/3|顾客|权限控制 (human.authorization)|EXCH-A8717CA97C||功能设计_spec.md:687-688|
|UCG-002-UC003/3|order_item 表资源服务|数据库可用性 (internal_database.availability)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|幂等性 (internal_database.idempotency)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|持久化能力 (internal_database.persistence)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|查询性能 (internal_database.query_performance)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-002-UC003/3|order_item 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-FAE2E41843||功能设计_spec.md:733-733|
|UCG-003-UC001/8|order 表资源服务|数据库可用性 (internal_database.availability)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|幂等性 (internal_database.idempotency)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|持久化能力 (internal_database.persistence)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|查询性能 (internal_database.query_performance)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC001/8|order 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-46F44B3EE2||功能设计_spec.md:780-780|
|UCG-003-UC003/3|logistics_event 表资源服务|数据库可用性 (internal_database.availability)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|幂等性 (internal_database.idempotency)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|持久化能力 (internal_database.persistence)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|查询性能 (internal_database.query_performance)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC003/3|logistics_event 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-AA6EC44696||功能设计_spec.md:869-869|
|UCG-003-UC004/4|PaymentService|超时关注点 (common.timeout)|EXCH-EA756A3143||系统需求_spec.md:321-321|
|UCG-003-UC004/4|PaymentService|外部服务可用性 (external_service.availability)|EXCH-EA756A3143||系统需求_spec.md:321-321|
|UCG-003-UC004/4|PaymentService|外部接口契约 (external_service.contract)|EXCH-EA756A3143||系统需求_spec.md:321-321|
|UCG-003-UC004/4|顾客|身份认证 (human.authentication)|EXCH-EA756A3143||系统需求_spec.md:321-321|
|UCG-003-UC004/4|顾客|权限控制 (human.authorization)|EXCH-EA756A3143||系统需求_spec.md:321-321|
|UCG-004-UC001/12|product 表资源服务|数据库可用性 (internal_database.availability)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|幂等性 (internal_database.idempotency)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|持久化能力 (internal_database.persistence)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|查询性能 (internal_database.query_performance)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC001/12|product 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-385BA4C46A||功能设计_spec.md:962-962|
|UCG-004-UC004/5|ProductCatalogService|内部依赖可用性 (service.dependency.availability)|EXCH-0420DC832F||系统需求_spec.md:417-417|
|UCG-004-UC004/5|对象未定位|调用顺序 (service_relation.call_order)|EXCH-0420DC832F||系统需求_spec.md:417-417|
|UCG-004-UC004/5|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-0420DC832F||系统需求_spec.md:417-417|
|UCG-004-UC004/5|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-0420DC832F||系统需求_spec.md:417-417|
|UCG-004-UC004/5|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-0420DC832F||系统需求_spec.md:417-417|
|UCG-004-UC004/5|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-0420DC832F||系统需求_spec.md:417-417|
|UCG-004-UC004/5|对象未定位|幂等性 (service_relation.idempotency)|EXCH-0420DC832F||系统需求_spec.md:417-417|
|UCG-001-UC003/3|cart_item 表资源服务|数据库可用性 (internal_database.availability)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|幂等性 (internal_database.idempotency)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|持久化能力 (internal_database.persistence)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|查询性能 (internal_database.query_performance)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-001-UC003/3|cart_item 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-81406F6C9C||功能设计_spec.md:592-592|
|UCG-002-UC001/5|ProductCatalogService|内部依赖可用性 (service.dependency.availability)|EXCH-7B23A2F46F||功能设计_spec.md:637-638|
|UCG-002-UC001/5|对象未定位|调用顺序 (service_relation.call_order)|EXCH-7B23A2F46F||功能设计_spec.md:637-638|
|UCG-002-UC001/5|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-7B23A2F46F||功能设计_spec.md:637-638|
|UCG-002-UC001/5|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-7B23A2F46F||功能设计_spec.md:637-638|
|UCG-002-UC001/5|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-7B23A2F46F||功能设计_spec.md:637-638|
|UCG-002-UC001/5|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-7B23A2F46F||功能设计_spec.md:637-638|
|UCG-002-UC001/5|对象未定位|幂等性 (service_relation.idempotency)|EXCH-7B23A2F46F||功能设计_spec.md:637-638|
|UCG-002-UC002/4|payment 表资源服务|数据库可用性 (internal_database.availability)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|幂等性 (internal_database.idempotency)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|持久化能力 (internal_database.persistence)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|查询性能 (internal_database.query_performance)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC002/4|payment 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-E120105835||功能设计_spec.md:689-689|
|UCG-002-UC003/3|payment 表资源服务|数据库可用性 (internal_database.availability)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|幂等性 (internal_database.idempotency)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|持久化能力 (internal_database.persistence)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|查询性能 (internal_database.query_performance)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-002-UC003/3|payment 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-B05DD6FA01||功能设计_spec.md:734-734|
|UCG-003-UC001/9|LogisticsService|超时关注点 (common.timeout)|EXCH-88CF5485F4||功能设计_spec.md:781-781|
|UCG-003-UC001/9|LogisticsService|外部服务可用性 (external_service.availability)|EXCH-88CF5485F4||功能设计_spec.md:781-781|
|UCG-003-UC001/9|LogisticsService|外部接口契约 (external_service.contract)|EXCH-88CF5485F4||功能设计_spec.md:781-781|
|UCG-003-UC001/9|商家|身份认证 (human.authentication)|EXCH-88CF5485F4||功能设计_spec.md:781-781|
|UCG-003-UC001/9|商家|权限控制 (human.authorization)|EXCH-88CF5485F4||功能设计_spec.md:781-781|
|UCG-003-UC002/4|logistics_event 表资源服务|数据库可用性 (internal_database.availability)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|幂等性 (internal_database.idempotency)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|持久化能力 (internal_database.persistence)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|查询性能 (internal_database.query_performance)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC002/4|logistics_event 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-2984C11A41||功能设计_spec.md:823-823|
|UCG-003-UC003/3|LogisticsService|超时关注点 (common.timeout)|EXCH-878D273380||功能设计_spec.md:870-870|
|UCG-003-UC003/3|LogisticsService|外部服务可用性 (external_service.availability)|EXCH-878D273380||功能设计_spec.md:870-870|
|UCG-003-UC003/3|LogisticsService|外部接口契约 (external_service.contract)|EXCH-878D273380||功能设计_spec.md:870-870|
|UCG-003-UC003/3|顾客|身份认证 (human.authentication)|EXCH-878D273380||功能设计_spec.md:870-870|
|UCG-003-UC003/3|顾客|权限控制 (human.authorization)|EXCH-878D273380||功能设计_spec.md:870-870|
|UCG-003-UC004/4|createRefund|超时关注点 (common.timeout)|EXCH-956C02D07F||系统需求_spec.md:321-321|
|UCG-003-UC004/4|PaymentService|调用方身份 (external_service.identity)|EXCH-956C02D07F||系统需求_spec.md:321-321|
|UCG-003-UC004/4|PaymentService|调用权限 (external_service.permission)|EXCH-956C02D07F||系统需求_spec.md:321-321|
|UCG-003-UC004/4|顾客|身份认证 (human.authentication)|EXCH-956C02D07F||系统需求_spec.md:321-321|
|UCG-003-UC004/4|顾客|权限控制 (human.authorization)|EXCH-956C02D07F||系统需求_spec.md:321-321|
|UCG-004-UC001/1|Category records资源服务|数据库可用性 (internal_database.availability)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|字段合法性 (internal_database.field_validity)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|幂等性 (internal_database.idempotency)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|持久化能力 (internal_database.persistence)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|查询性能 (internal_database.query_performance)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|资源存在性 (internal_database.resource_existence)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC001/1|Category records资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-9D5DFECE8D||功能设计_spec.md:1179-1179|
|UCG-004-UC002/4|product 表资源服务|数据库可用性 (internal_database.availability)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|幂等性 (internal_database.idempotency)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|持久化能力 (internal_database.persistence)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|查询性能 (internal_database.query_performance)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|product 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-BC3912F9BD||功能设计_spec.md:1003-1003|
|UCG-004-UC003/5|product 表资源服务|数据库可用性 (internal_database.availability)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|幂等性 (internal_database.idempotency)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|持久化能力 (internal_database.persistence)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|查询性能 (internal_database.query_performance)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|product 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-34AEC69F81||功能设计_spec.md:1048-1048|
|UCG-004-UC004/5|ProductCatalogService|内部依赖可用性 (service.dependency.availability)|EXCH-E7DC5B90A9||功能设计_spec.md:1098-1098|
|UCG-004-UC004/5|对象未定位|调用顺序 (service_relation.call_order)|EXCH-E7DC5B90A9||功能设计_spec.md:1098-1098|
|UCG-004-UC004/5|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-E7DC5B90A9||功能设计_spec.md:1098-1098|
|UCG-004-UC004/5|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-E7DC5B90A9||功能设计_spec.md:1098-1098|
|UCG-004-UC004/5|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-E7DC5B90A9||功能设计_spec.md:1098-1098|
|UCG-004-UC004/5|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-E7DC5B90A9||功能设计_spec.md:1098-1098|
|UCG-004-UC004/5|对象未定位|幂等性 (service_relation.idempotency)|EXCH-E7DC5B90A9||功能设计_spec.md:1098-1098|
|UCG-002-UC001/6|product 表和 sku 表资源服务|数据库可用性 (internal_database.availability)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|幂等性 (internal_database.idempotency)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|持久化能力 (internal_database.persistence)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|查询性能 (internal_database.query_performance)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC001/6|product 表和 sku 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-800DB0F90A||功能设计_spec.md:638-638|
|UCG-002-UC002/5|order 表资源服务|数据库可用性 (internal_database.availability)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|幂等性 (internal_database.idempotency)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|持久化能力 (internal_database.persistence)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|查询性能 (internal_database.query_performance)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC002/5|order 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-2D2C8A748A||功能设计_spec.md:690-690|
|UCG-002-UC003/3|shipment 表资源服务|数据库可用性 (internal_database.availability)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|幂等性 (internal_database.idempotency)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|持久化能力 (internal_database.persistence)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|查询性能 (internal_database.query_performance)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-002-UC003/3|shipment 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-DDC866B397||功能设计_spec.md:735-735|
|UCG-003-UC002/4|logistics_event 表资源服务|数据库可用性 (internal_database.availability)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|幂等性 (internal_database.idempotency)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|持久化能力 (internal_database.persistence)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|查询性能 (internal_database.query_performance)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-003-UC002/4|logistics_event 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-D5EFCE9B3B||功能设计_spec.md:824-824|
|UCG-004-UC002/4|CategoryService|内部依赖可用性 (service.dependency.availability)|EXCH-29F2412D5B||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|对象未定位|调用顺序 (service_relation.call_order)|EXCH-29F2412D5B||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|对象未定位|级联操作 (service_relation.cascade_operation)|EXCH-29F2412D5B||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|对象未定位|并发一致性 (service_relation.concurrency_consistency)|EXCH-29F2412D5B||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|对象未定位|跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-29F2412D5B||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|对象未定位|依赖一致性 (service_relation.dependency_consistency)|EXCH-29F2412D5B||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|对象未定位|幂等性 (service_relation.idempotency)|EXCH-29F2412D5B||功能设计_spec.md:1004-1004|
|UCG-004-UC003/7|sku 表资源服务|数据库可用性 (internal_database.availability)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|幂等性 (internal_database.idempotency)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|持久化能力 (internal_database.persistence)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|查询性能 (internal_database.query_performance)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-004-UC003/7|sku 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-A81D00F6B2||功能设计_spec.md:1050-1050|
|UCG-002-UC001/8|address 表资源服务|数据库可用性 (internal_database.availability)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|幂等性 (internal_database.idempotency)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|持久化能力 (internal_database.persistence)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|查询性能 (internal_database.query_performance)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC001/8|address 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-F73883C85F||功能设计_spec.md:640-640|
|UCG-002-UC002/5|createPayment|超时关注点 (common.timeout)|EXCH-C186161A51||功能设计_spec.md:700-700|
|UCG-002-UC002/5|PaymentService|调用方身份 (external_service.identity)|EXCH-C186161A51||功能设计_spec.md:700-700|
|UCG-002-UC002/5|PaymentService|调用权限 (external_service.permission)|EXCH-C186161A51||功能设计_spec.md:700-700|
|UCG-002-UC002/5|顾客|身份认证 (human.authentication)|EXCH-C186161A51||功能设计_spec.md:700-700|
|UCG-002-UC002/5|顾客|权限控制 (human.authorization)|EXCH-C186161A51||功能设计_spec.md:700-700|
|UCG-003-UC002/2|shipment 表资源服务|数据库可用性 (internal_database.availability)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|幂等性 (internal_database.idempotency)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|持久化能力 (internal_database.persistence)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|查询性能 (internal_database.query_performance)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-003-UC002/2|shipment 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-6B993AD539||功能设计_spec.md:821-821|
|UCG-004-UC002/4|category 表资源服务|数据库可用性 (internal_database.availability)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|幂等性 (internal_database.idempotency)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|持久化能力 (internal_database.persistence)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|查询性能 (internal_database.query_performance)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|category 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-B1738387F7||功能设计_spec.md:1004-1004|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|数据库可用性 (internal_database.availability)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|幂等性 (internal_database.idempotency)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|持久化能力 (internal_database.persistence)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|查询性能 (internal_database.query_performance)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-002-UC001/10|order 表和 order_item 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-0A855CEC60||功能设计_spec.md:642-642|
|UCG-003-UC002/5|shipment 表资源服务|数据库可用性 (internal_database.availability)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|并发一致性 (internal_database.concurrency_consistency)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|字段合法性 (internal_database.field_validity)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|幂等性 (internal_database.idempotency)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|持久化能力 (internal_database.persistence)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|查询性能 (internal_database.query_performance)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|关联一致性 (internal_database.referential_consistency)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|必填字段完整性 (internal_database.required_field_completeness)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|资源存在性 (internal_database.resource_existence)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/5|shipment 表资源服务|唯一性约束 (internal_database.uniqueness)|EXCH-2725A7F411||功能设计_spec.md:825-825|
|UCG-003-UC002/1|receiveLogisticsEvent|超时关注点 (common.timeout)|EXCH-528835C51B||系统需求_spec.md:268-269|
|UCG-003-UC002/1|LogisticsService|调用方身份 (external_service.identity)|EXCH-528835C51B||系统需求_spec.md:268-269|
|UCG-003-UC002/1|LogisticsService|调用权限 (external_service.permission)|EXCH-528835C51B||系统需求_spec.md:268-269|
|UCG-003-UC002/5|LogisticsService|超时关注点 (common.timeout)|EXCH-9BAD333B1F||功能设计_spec.md:827-827|
|UCG-003-UC002/5|LogisticsService|外部服务可用性 (external_service.availability)|EXCH-9BAD333B1F||功能设计_spec.md:827-827|
|UCG-003-UC002/5|LogisticsService|外部接口契约 (external_service.contract)|EXCH-9BAD333B1F||功能设计_spec.md:827-827|
|UCG-001-UC001/2|在线商城购物系统|数据范围 (api.data.range)|EXCH-ED4C0A89A0|ProductCatalogService|功能设计_spec.md:500-500；功能设计_spec.md:508-508|
|UCG-001-UC001/2|在线商城购物系统|数据范围 (api.data.range)|EXCH-ED4C0A89A0|ProductCatalogService|功能设计_spec.md:500-500；功能设计_spec.md:508-508|
|UCG-001-UC001/2|在线商城购物系统|数据范围 (api.data.range)|EXCH-ED4C0A89A0|ProductCatalogService|功能设计_spec.md:500-500；功能设计_spec.md:508-508|
|UCG-001-UC001/2|在线商城购物系统|数据范围 (api.data.range)|EXCH-ED4C0A89A0|ProductCatalogService|功能设计_spec.md:500-500；功能设计_spec.md:508-508|
|UCG-001-UC001/2|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-ED4C0A89A0|ProductCatalogService|功能设计_spec.md:508-508|
|UCG-001-UC001/2|在线商城购物系统|资源存在性 (service.query_retrieval.resource_existence)|EXCH-ED4C0A89A0|ProductCatalogService|功能设计_spec.md:500-500；功能设计_spec.md:509-509|
|UCG-001-UC001/4|ProductCatalogService|结果正确性 (service.query_retrieval.result_correctness)|needs_confirmation|ProductCatalogService（检查步骤待确认）|系统需求_spec.md:99-99；功能设计_spec.md:501-501；功能设计_spec.md:513-513|
|UCG-001-UC001/5|在线商城购物系统|必填字段完整性 (internal_database.required_field_completeness)|needs_confirmation|ProductCatalogService（检查步骤待确认）|功能设计_spec.md:514-514|
|UCG-001-UC001/3|ProductCatalogService|内部依赖可用性 (service.dependency.availability)|needs_confirmation|ProductCatalogService（检查步骤待确认）|功能设计_spec.md:512-512|
|UCG-001-UC001/3|ProductCatalogService|超时关注点 (common.timeout)；内部依赖可用性 (service.dependency.availability)|needs_confirmation|ProductCatalogService（检查步骤待确认）|功能设计_spec.md:511-511|
|UCG-001-UC001/1|在线商城购物系统|身份认证 (human.authentication)|needs_confirmation|ProductCatalogService（检查步骤待确认）|功能设计_spec.md:494-494|
|UCG-001-UC002/2|在线商城购物系统|数据格式 (api.data.format)|EXCH-72B79A0231|ProductCatalogService|功能设计_spec.md:542-542；功能设计_spec.md:550-550|
|UCG-001-UC002/3|ProductCatalogService 商品目录|资源存在性 (service.query_retrieval.resource_existence)|needs_confirmation|ProductCatalogService（检查步骤待确认）|系统需求_spec.md:127-128；功能设计_spec.md:544-544；功能设计_spec.md:551-551|
|UCG-001-UC002/3|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|ProductCatalogService（检查步骤待确认）|系统需求_spec.md:129-130；功能设计_spec.md:552-552|
|UCG-001-UC002/3|ProductCatalogService|超时关注点 (common.timeout)；内部依赖可用性 (service.dependency.availability)|needs_confirmation|ProductCatalogService（检查步骤待确认）|功能设计_spec.md:543-544；功能设计_spec.md:553-553|
|UCG-001-UC002/3|ProductCatalogService|内部依赖可用性 (service.dependency.availability)|needs_confirmation|ProductCatalogService（检查步骤待确认）|功能设计_spec.md:543-543；功能设计_spec.md:554-554|
|UCG-001-UC002/4|在线商城系统 响应转换|显示正确性 (service.display_interaction.display_correctness)|needs_confirmation|ProductCatalogService（检查步骤待确认）|系统需求_spec.md:131-132；功能设计_spec.md:555-555|
|UCG-001-UC002/4|在线商城购物系统|显示正确性 (service.display_interaction.display_correctness)|needs_confirmation|ProductCatalogService（检查步骤待确认）|功能设计_spec.md:544-546|
|UCG-001-UC002/2|在线商城购物系统|身份认证 (human.authentication)|EXCH-72B79A0231|ProductCatalogService|功能设计_spec.md:537-537；功能设计_spec.md:542-542|
|UCG-001-UC002/2|在线商城系统 与 ProductCatalogService|幂等性 (service_relation.idempotency)|needs_confirmation|ProductCatalogService（检查步骤待确认）|功能设计_spec.md:541-546|
|UCG-001-UC003/2|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|CartService（检查步骤待确认）|系统需求_spec.md:146-146|
|UCG-001-UC003/2|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|CartService（检查步骤待确认）|系统需求_spec.md:146-146|
|UCG-001-UC003/2|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|CartService（检查步骤待确认）|系统需求_spec.md:146-146|
|UCG-001-UC003/3|系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|CartService（检查步骤待确认）|系统需求_spec.md:155-156|
|UCG-001-UC003/2|ProductCatalogService|资源存在性 (service.query_retrieval.resource_existence)；依赖一致性 (service_relation.dependency_consistency)|needs_confirmation|CartService（检查步骤待确认）|功能设计_spec.md:587-588|
|UCG-001-UC003/2|在线商城购物系统|数据范围 (api.data.range)|needs_confirmation|CartService（检查步骤待确认）|功能设计_spec.md:586-598|
|UCG-001-UC003/2|在线商城购物系统|数据完整性 (api.data.completeness)|needs_confirmation|CartService（检查步骤待确认）|功能设计_spec.md:586-586|
|UCG-001-UC003/3|CartService|幂等性 (internal_database.idempotency)；并发与幂等性 (service.resource_mutation.concurrency_idempotency)|needs_confirmation|CartService（检查步骤待确认）|功能设计_spec.md:602-602|
|UCG-002-UC001/3|在线商城购物系统|数据完整性 (api.data.completeness)；数据格式 (api.data.format)；数据范围 (api.data.range)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:635-635|
|UCG-002-UC001/2|在线商城购物系统|身份认证 (human.authentication)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:634-634|
|UCG-002-UC001/4|CartService|资源存在性 (internal_database.resource_existence)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:636-636|
|UCG-002-UC001/11|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:638-639|
|UCG-002-UC001/11|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:638-639|
|UCG-002-UC001/11|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:638-639|
|UCG-002-UC001/11|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:639-639|
|UCG-002-UC001/12|在线商城购物系统|数据可见性 (service.query_retrieval.data_visibility)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:640-640|
|UCG-002-UC001/14|OrderService|幂等性 (internal_database.idempotency)；幂等性 (service_relation.idempotency)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:642-642；功能设计_spec.md:651-651|
|UCG-002-UC001/14|OrderService|持久化能力 (internal_database.persistence)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:642-642|
|UCG-002-UC002/2|在线商城系统（OrderService/order表）|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|PaymentAdapter（检查步骤待确认）|系统需求_spec.md:186-187；功能设计_spec.md:685-685；功能设计_spec.md:695-695|
|UCG-002-UC002/2|在线商城系统（order表 payable_amount）|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|PaymentAdapter（检查步骤待确认）|系统需求_spec.md:196-196；功能设计_spec.md:685-685；功能设计_spec.md:696-696|
|UCG-002-UC002/2|在线商城系统（order表 expire_at）|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|PaymentAdapter（检查步骤待确认）|系统需求_spec.md:188-188；功能设计_spec.md:676-676；功能设计_spec.md:685-685|
|UCG-002-UC002/1|在线商城系统（支付接口参数校验）|数据完整性 (api.data.completeness)；数据格式 (api.data.format)；数据合法性 (api.data.legality)；数据范围 (api.data.range)|needs_confirmation|PaymentAdapter（检查步骤待确认）|功能设计_spec.md:684-684|
|UCG-002-UC002/1|在线商城系统（支付接口参数校验）|数据范围 (api.data.range)|needs_confirmation|PaymentAdapter（检查步骤待确认）|功能设计_spec.md:684-684|
|UCG-002-UC002/1|在线商城系统（支付接口参数校验）|数据完整性 (api.data.completeness)|needs_confirmation|PaymentAdapter（检查步骤待确认）|功能设计_spec.md:684-684|
|UCG-002-UC002/1|在线商城系统（认证校验）|身份认证 (human.authentication)|needs_confirmation|PaymentAdapter（检查步骤待确认）|功能设计_spec.md:677-677；功能设计_spec.md:683-683|
|UCG-002-UC002/3|PaymentService / PaymentAdapter|超时关注点 (common.timeout)；外部服务可用性 (external_service.availability)|needs_confirmation|PaymentAdapter（检查步骤待确认）|系统需求_spec.md:202-203；功能设计_spec.md:675-675；功能设计_spec.md:697-697|
|UCG-002-UC002/3|PaymentAdapter（payment表）|幂等性 (service_relation.idempotency)|needs_confirmation|PaymentAdapter（检查步骤待确认）|功能设计_spec.md:678-678；功能设计_spec.md:699-699|
|UCG-002-UC002/4|在线商城系统（order表状态更新）|幂等性 (service_relation.idempotency)|needs_confirmation|PaymentAdapter（检查步骤待确认）|系统需求_spec.md:206-207；功能设计_spec.md:700-700|
|UCG-002-UC002/4|PaymentService / PaymentAdapter|外部接口契约 (external_service.contract)|needs_confirmation|PaymentAdapter（检查步骤待确认）|功能设计_spec.md:397-397；功能设计_spec.md:689-689；功能设计_spec.md:1143-1143|
|UCG-002-UC002/5|在线商城系统（order表、payment表）|持久化能力 (internal_database.persistence)|needs_confirmation|PaymentAdapter（检查步骤待确认）|系统需求_spec.md:199-199；功能设计_spec.md:690-690|
|UCG-002-UC002/5|在线商城系统（回调处理）|幂等性 (service_relation.idempotency)|needs_confirmation|PaymentAdapter（检查步骤待确认）|功能设计_spec.md:700-700|
|UCG-002-UC003/2|在线商城购物系统|权限控制 (human.authorization)|needs_confirmation|OrderService（检查步骤待确认）|系统需求_spec.md:226-227；功能设计_spec.md:742-742|
|UCG-002-UC003/3|在线商城系统 / OrderService|资源存在性 (service.query_retrieval.resource_existence)|needs_confirmation|OrderService（检查步骤待确认）|系统需求_spec.md:228-229；功能设计_spec.md:743-743|
|UCG-002-UC003/4|OrderService|显示正确性 (service.display_interaction.display_correctness)|needs_confirmation|OrderService（检查步骤待确认）|系统需求_spec.md:230-231；功能设计_spec.md:744-744|
|UCG-002-UC003/1|在线商城购物系统|身份认证 (human.authentication)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:723-723；功能设计_spec.md:729-729|
|UCG-002-UC003/1|在线商城购物系统|数据格式 (api.data.format)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:730-730；功能设计_spec.md:741-741|
|UCG-002-UC003/3|OrderService|超时关注点 (common.timeout)；内部依赖可用性 (service.dependency.availability)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:731-731；功能设计_spec.md:745-745|
|UCG-003-UC001/2|在线商城系统 / OrderService|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|OrderService（检查步骤待确认）|系统需求_spec.md:251-252；功能设计_spec.md:787-787|
|UCG-003-UC001/3|OrderService|数据格式 (api.data.format)|needs_confirmation|OrderService（检查步骤待确认）|系统需求_spec.md:253-254；功能设计_spec.md:778-778；功能设计_spec.md:788-788|
|UCG-003-UC001/4|LogisticsService（外部服务）|外部服务可用性 (external_service.availability)|needs_confirmation|OrderService（检查步骤待确认）|系统需求_spec.md:255-256；功能设计_spec.md:789-789|
|UCG-003-UC001/2|在线商城购物系统|身份认证 (human.authentication)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:774-774|
|UCG-003-UC001/2|在线商城购物系统|权限控制 (human.authorization)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:791-791|
|UCG-003-UC001/3|在线商城购物系统|数据格式 (api.data.format)|EXCH-293276D860|OrderService|功能设计_spec.md:775-775|
|UCG-003-UC001/3|在线商城购物系统|数据合法性 (api.data.legality)|EXCH-293276D860|OrderService|功能设计_spec.md:775-775|
|UCG-003-UC001/3|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-293276D860|OrderService|功能设计_spec.md:775-775|
|UCG-003-UC001/3|在线商城购物系统|数据完整性 (api.data.completeness)|EXCH-293276D860|OrderService|功能设计_spec.md:775-775|
|UCG-003-UC001/4|OrderService|权限控制 (human.authorization)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:776-776|
|UCG-003-UC001/3|在线商城系统 / OrderService|依赖一致性 (service_relation.dependency_consistency)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:790-790|
|UCG-003-UC001/7|OrderService / shipment 表|持久化能力 (internal_database.persistence)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:779-779|
|UCG-003-UC001/8|OrderService / order 表|持久化能力 (internal_database.persistence)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:780-780|
|UCG-003-UC001/5|OrderService|并发与幂等性 (service.resource_mutation.concurrency_idempotency)|needs_confirmation|OrderService（检查步骤待确认）|功能设计_spec.md:777-777|
|UCG-003-UC002/2|LogisticsServiceAdapter|调用方身份 (external_service.identity)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:270-270；系统需求_spec.md:275-276；功能设计_spec.md:820-820；功能设计_spec.md:831-831；功能设计_spec.md:815-815|
|UCG-003-UC002/2|LogisticsServiceAdapter|资源存在性 (internal_database.resource_existence)；资源存在性 (service.query_retrieval.resource_existence)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:270-270；功能设计_spec.md:821-821；功能设计_spec.md:832-832；功能设计_spec.md:814-814|
|UCG-003-UC002/3|LogisticsServiceAdapter|数据范围 (api.data.range)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:271-271；功能设计_spec.md:822-822；功能设计_spec.md:833-833|
|UCG-003-UC002/3|系统/LogisticsServiceAdapter|业务约束 (service.resource_mutation.business_constraint)；调用顺序 (service_relation.call_order)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:271-271；系统需求_spec.md:279-280|
|UCG-003-UC002/4|LogisticsServiceAdapter|并发与幂等性 (service.resource_mutation.concurrency_idempotency)；幂等性 (service_relation.idempotency)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:277-278；功能设计_spec.md:823-823；功能设计_spec.md:834-834|
|UCG-003-UC002/2|LogisticsServiceAdapter|数据合法性 (api.data.legality)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|功能设计_spec.md:835-835|
|UCG-003-UC002/4|LogisticsServiceAdapter|持久化能力 (internal_database.persistence)；持久化一致性 (service.resource_mutation.persistence_consistency)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:272-272；功能设计_spec.md:824-824|
|UCG-003-UC002/5|LogisticsServiceAdapter|持久化能力 (internal_database.persistence)；持久化一致性 (service.resource_mutation.persistence_consistency)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:273-273；功能设计_spec.md:825-825|
|UCG-003-UC003/3|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:299-300；功能设计_spec.md:876-876|
|UCG-003-UC003/3|在线商城购物系统|权限控制 (human.authorization)；数据可见性 (service.query_retrieval.data_visibility)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:287-287；功能设计_spec.md:866-866|
|UCG-003-UC003/3|LogisticsServiceAdapter|超时关注点 (common.timeout)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|系统需求_spec.md:295-295；功能设计_spec.md:870-870|
|UCG-003-UC003/3|LogisticsService|超时关注点 (common.timeout)；外部服务可用性 (external_service.availability)|EXCH-878D273380|LogisticsServiceAdapter|系统需求_spec.md:301-302；功能设计_spec.md:878-878|
|UCG-003-UC003/2|LogisticsServiceAdapter|内部依赖可用性 (service.dependency.availability)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|功能设计_spec.md:880-880|
|UCG-003-UC003/2|LogisticsServiceAdapter|资源存在性 (internal_database.resource_existence)；资源存在性 (service.query_retrieval.resource_existence)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|功能设计_spec.md:877-877|
|UCG-003-UC003/1|在线商城购物系统|身份认证 (human.authentication)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|功能设计_spec.md:864-864|
|UCG-003-UC003/1|在线商城购物系统|数据格式 (api.data.format)|needs_confirmation|LogisticsServiceAdapter（检查步骤待确认）|功能设计_spec.md:865-865|
|UCG-003-UC004/2|RefundService|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|RefundService（检查步骤待确认）|系统需求_spec.md:312-312；系统需求_spec.md:324-325；功能设计_spec.md:915-915；功能设计_spec.md:924-924|
|UCG-003-UC004/2|RefundService|数据范围 (api.data.range)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|RefundService（检查步骤待确认）|系统需求_spec.md:326-327；功能设计_spec.md:915-915；功能设计_spec.md:925-925|
|UCG-003-UC004/2|在线商城系统（OrderService 查询）|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|RefundService（检查步骤待确认）|系统需求_spec.md:311-311；功能设计_spec.md:912-912；功能设计_spec.md:926-926|
|UCG-003-UC004/2|在线商城系统（OrderService 查询）|权限控制 (human.authorization)|needs_confirmation|RefundService（检查步骤待确认）|系统需求_spec.md:311-311；功能设计_spec.md:910-912|
|UCG-003-UC004/2|在线商城购物系统|身份认证 (human.authentication)|EXCH-ED50F5ACE8|RefundService|系统需求_spec.md:310-310；功能设计_spec.md:910-910|
|UCG-003-UC004/2|在线商城购物系统|数据完整性 (api.data.completeness)；数据格式 (api.data.format)；数据合法性 (api.data.legality)；数据范围 (api.data.range)|EXCH-ED50F5ACE8|RefundService|功能设计_spec.md:911-911；功能设计_spec.md:905-905|
|UCG-003-UC004/3|RefundService|并发与幂等性 (service.resource_mutation.concurrency_idempotency)；幂等性 (service_relation.idempotency)|needs_confirmation|RefundService（检查步骤待确认）|功能设计_spec.md:914-914；功能设计_spec.md:928-928|
|UCG-003-UC004/3|RefundService|持久化能力 (internal_database.persistence)|needs_confirmation|RefundService（检查步骤待确认）|功能设计_spec.md:916-916；功能设计_spec.md:919-919|
|UCG-003-UC004/4|RefundService（调用 PaymentService）|外部服务可用性 (external_service.availability)|needs_confirmation|RefundService（检查步骤待确认）|系统需求_spec.md:328-329；功能设计_spec.md:927-927|
|UCG-004-UC001/10|MerchantProductService|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:960-960；功能设计_spec.md:968-968|
|UCG-004-UC001/10|MerchantProductService|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:960-960；功能设计_spec.md:969-969|
|UCG-004-UC001/11|MerchantProductService|幂等性 (internal_database.idempotency)；并发与幂等性 (service.resource_mutation.concurrency_idempotency)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:961-961；功能设计_spec.md:970-970；系统需求_spec.md:350-351|
|UCG-004-UC001/8|在线商城购物系统|数据格式 (api.data.format)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:958-958|
|UCG-004-UC001/8|在线商城购物系统|数据完整性 (api.data.completeness)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:958-958|
|UCG-004-UC001/7|在线商城购物系统|身份认证 (human.authentication)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:957-957|
|UCG-004-UC001/12|MerchantProductService|持久化能力 (internal_database.persistence)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:962-962|
|UCG-004-UC001/12|MerchantProductService|必填字段完整性 (internal_database.required_field_completeness)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:962-962|
|UCG-004-UC001/9|在线商城购物系统|内部依赖可用性 (service.dependency.availability)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:959-959；功能设计_spec.md:971-971|
|UCG-004-UC001/12|MerchantProductService|数据完整性 (api.data.completeness)；数据合法性 (api.data.legality)；资源存在性 (internal_database.resource_existence)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1179-1179|
|UCG-004-UC002/2|CategoryService|业务约束 (service.resource_mutation.business_constraint)；依赖一致性 (service_relation.dependency_consistency)|needs_confirmation|MerchantProductService（检查步骤待确认）|系统需求_spec.md:370-371；功能设计_spec.md:1004-1004|
|UCG-004-UC002/4|在线商城购物系统|业务约束 (service.resource_mutation.business_constraint)；依赖一致性 (service_relation.dependency_consistency)|EXCH-178D36A0D3|MerchantProductService|功能设计_spec.md:1013-1013|
|UCG-004-UC002/3|MerchantProductService|数据格式 (api.data.format)；数据范围 (api.data.range)|needs_confirmation|MerchantProductService（检查步骤待确认）|系统需求_spec.md:372-373；功能设计_spec.md:1005-1005|
|UCG-004-UC002/4|在线商城购物系统|数据格式 (api.data.format)；数据范围 (api.data.range)|EXCH-178D36A0D3|MerchantProductService|功能设计_spec.md:1014-1014|
|UCG-004-UC002/4|MerchantProductService|权限控制 (human.authorization)；数据可见性 (service.query_retrieval.data_visibility)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1003-1003|
|UCG-004-UC002/4|MerchantProductService|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1003-1003；功能设计_spec.md:1016-1016|
|UCG-004-UC002/4|MerchantProductService|并发一致性 (internal_database.concurrency_consistency)；并发与幂等性 (service.resource_mutation.concurrency_idempotency)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1003-1003；功能设计_spec.md:1015-1015|
|UCG-004-UC002/4|MerchantProductService|资源存在性 (internal_database.resource_existence)；资源存在性 (service.query_retrieval.resource_existence)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1012-1012|
|UCG-004-UC002/4|在线商城购物系统|身份认证 (human.authentication)|EXCH-178D36A0D3|MerchantProductService|功能设计_spec.md:1000-1000|
|UCG-004-UC002/3|在线商城购物系统|数据完整性 (api.data.completeness)；数据格式 (api.data.format)；数据长度 (api.data.length)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1001-1001；系统需求_spec.md:366-366|
|UCG-004-UC002/4|MerchantProductService|内部依赖可用性 (service.dependency.availability)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:993-993|
|UCG-004-UC003/3|在线商城系统 / MerchantProductService|数据范围 (api.data.range)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|系统需求_spec.md:394-395；功能设计_spec.md:1046-1046；功能设计_spec.md:1057-1057|
|UCG-004-UC003/3|在线商城购物系统|数据合法性 (api.data.legality)；数据范围 (api.data.range)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1046-1046；功能设计_spec.md:1058-1058|
|UCG-004-UC003/1|在线商城购物系统|数据完整性 (api.data.completeness)；数据格式 (api.data.format)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1044-1046|
|UCG-004-UC003/1|在线商城购物系统|身份认证 (human.authentication)；权限控制 (human.authorization)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1039-1040；功能设计_spec.md:1045-1045|
|UCG-004-UC003/5|MerchantProductService|权限控制 (human.authorization)；数据可见性 (service.query_retrieval.data_visibility)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|MerchantProductService|业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1048-1048|
|UCG-004-UC003/5|MerchantProductService|并发一致性 (internal_database.concurrency_consistency)；并发与幂等性 (service.resource_mutation.concurrency_idempotency)；并发一致性 (service_relation.concurrency_consistency)|needs_confirmation|MerchantProductService（检查步骤待确认）|系统需求_spec.md:398-399；功能设计_spec.md:1048-1048；功能设计_spec.md:1060-1060|
|UCG-004-UC003/6|MerchantProductService|唯一性约束 (internal_database.uniqueness)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1049-1049；功能设计_spec.md:1059-1059|
|UCG-004-UC003/7|MerchantProductService|持久化能力 (internal_database.persistence)；持久化一致性 (service.resource_mutation.persistence_consistency)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1050-1051|
|UCG-004-UC003/8|MerchantProductService|幂等性 (internal_database.idempotency)；并发与幂等性 (service.resource_mutation.concurrency_idempotency)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1047-1052|
|UCG-004-UC003/5|MerchantProductService|数据库可用性 (internal_database.availability)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1048-1048|
|UCG-004-UC003/4|在线商城购物系统|内部依赖可用性 (service.dependency.availability)|EXCH-E4B0C80650|MerchantProductService|功能设计_spec.md:1037-1038；功能设计_spec.md:1047-1047|
|UCG-004-UC004/1|在线商城购物系统|数据完整性 (api.data.completeness)；数据格式 (api.data.format)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1089-1091|
|UCG-004-UC004/1|在线商城购物系统|身份认证 (human.authentication)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1085-1090|
|UCG-004-UC004/3|MerchantProductService|权限控制 (human.authorization)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1092-1093|
|UCG-004-UC004/2|MerchantProductService|数据完整性 (api.data.completeness)；必填字段完整性 (internal_database.required_field_completeness)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1094-1094|
|UCG-004-UC004/2|MerchantProductService|数据范围 (api.data.range)；资源存在性 (internal_database.resource_existence)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1094-1094|
|UCG-004-UC004/2|MerchantProductService|发布前置条件 (service.release_activation.prerequisite)；业务约束 (service.resource_mutation.business_constraint)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1095-1095|
|UCG-004-UC004/4|MerchantProductService|并发一致性 (internal_database.concurrency_consistency)；持久化能力 (internal_database.persistence)|needs_confirmation|MerchantProductService（检查步骤待确认）|功能设计_spec.md:1096-1096|
|UCG-004-UC004/5|ProductCatalogService|内部依赖可用性 (service.dependency.availability)；跨服务数据一致性 (service_relation.cross_service_consistency)|EXCH-E7DC5B90A9|MerchantProductService|功能设计_spec.md:1097-1108；功能设计_spec.md:1197-1198|
|UCG-004-UC004/5|ProductCatalogService|外部接口契约 (external_service.contract)；依赖一致性 (service_relation.dependency_consistency)|EXCH-E7DC5B90A9|MerchantProductService|功能设计_spec.md:1098-1098|
|UCG-004-UC004/3|MerchantProductService|幂等性 (internal_database.idempotency)；并发与幂等性 (service.resource_mutation.concurrency_idempotency)|needs_confirmation|MerchantProductService（检查步骤待确认）|系统需求_spec.md:412-418；功能设计_spec.md:1093-1096|
