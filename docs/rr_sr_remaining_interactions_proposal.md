# 其余 SR 角色与调用关系确认提案

用户于2026-10-10确认：“同意文档列出的18项；其他新增项继续逐项确认”。本确认只授权下列具体角色和调用，不代表模型抽取完整性检查通过，也不授权新关注点。

这些关系来自 ecnu-max 对原始正常流程的独立提取；没有读取 C 或测试条件反推调用。93条交互已通过同层正常/普通可选来源结构检查，实际语义仍需复核。本提案未执行这些位置的异常生成。

模型版本：b87fedfe316bbe8260e72fc99a4522e9e970e628d5e9c58834d46db603c6e454

既有顾客、商家、外部调用方的 RR 边界分析，以及内外数据库资源服务化属于已明确授权的方法；原有 SR 接口编号作为入口别名不代表新增部署组件。此前具体确认的目录、购物车、支付和订单调用继续保留，不重复申请。

## 待确认项目

| 编号 | 原文用例/角色 | 图中位置 | 文档依据 | 影响 |
|---|---|---|---|---|
| 1 | SR角色 | POST /api/v1/logistics/events：internal_service / SR | 功能设计_spec.md:803-803；功能设计_spec.md:419-419 | 逻辑接收接口与既有 LOGI-EVT-01 对应；保留实际POST路径，不新增部署服务 |
| 2 | SR角色 | CategoryService：internal_service / SR | 功能设计_spec.md:450-450；功能设计_spec.md:988-988；功能设计_spec.md:1004-1004 | CategoryService补SR服务角色；接口路径未知则待确认 |
| 3 | UCG-003-UC001 | API-L-IF1 → OrderService：调用 OrderService 查询 order 表获取 order_id、merchant_id、status | 功能设计_spec.md:776-776 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 4 | UCG-003-UC001 | API-L-IF1 → OrderService：调用 OrderService 创建发货能力 | 功能设计_spec.md:777-777；功能设计_spec.md:782-782 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 5 | UCG-003-UC001 | OrderService → LogisticsService：向 LogisticsService 登记物流单号 | 功能设计_spec.md:781-781 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 6 | UCG-003-UC002 | POST /api/v1/logistics/events → LogisticsServiceAdapter：校验签名并处理物流事件 | 功能设计_spec.md:820-820；功能设计_spec.md:826-826 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 7 | UCG-003-UC003 | API-L-IF2 → OrderService：调用OrderService查询订单归属与状态 | 功能设计_spec.md:866-866 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 8 | UCG-003-UC003 | API-L-IF2 → LogisticsServiceAdapter：调用LogisticsServiceAdapter的物流查询能力 | 功能设计_spec.md:867-867；功能设计_spec.md:871-871 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 9 | UCG-003-UC003 | LogisticsServiceAdapter → LogisticsService：查询最新物流轨迹 | 功能设计_spec.md:870-870；系统需求_spec.md:295-295 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 10 | UCG-003-UC004 | API-R-IF1 → OrderService：查询订单和订单项并校验订单、计算可退款金额 | 功能设计_spec.md:912-912 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 11 | UCG-003-UC004 | API-R-IF1 → RefundService：调用退款申请能力 | 功能设计_spec.md:913-919 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 12 | UCG-003-UC004 | RefundService → PaymentService：提交退款请求 | 功能设计_spec.md:917-918 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 13 | UCG-004-UC001 | API-M-IF1 → MerchantProductService：调用MerchantProductService的创建商品能力 | 功能设计_spec.md:959-963 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 14 | UCG-004-UC002 | API-M-IF2 → MerchantProductService：调用商品信息维护能力 | 功能设计_spec.md:1002-1002 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 15 | UCG-004-UC002 | MerchantProductService → CategoryService：调用CategoryService校验 categoryId | 功能设计_spec.md:1004-1004 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 16 | UCG-004-UC003 | API-M-IF3 → MerchantProductService：调用库存与价格维护能力 | 功能设计_spec.md:1047-1052 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 17 | UCG-004-UC004 | API-M-IF4 → MerchantProductService：调用商品发布能力 | 功能设计_spec.md:1092-1092；功能设计_spec.md:1099-1099 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |
| 18 | UCG-004-UC004 | MerchantProductService → ProductCatalogService：刷新可售索引 | 功能设计_spec.md:1097-1098；系统需求_spec.md:417-417 | 纳入明确SR调用与依赖关注点；不新增部署组件或用例 |

## 原文引句与校验标识

### 1. POST /api/v1/logistics/events：internal_service / SR
提案ID：PROPOSAL-NODE-04F948219E

| 方法/路径 | POST /api/v1/logistics/events |
- 方法/路径：POST /api/v1/logistics/events

### 2. CategoryService：internal_service / SR
提案ID：PROPOSAL-NODE-86D6B43A31

- 主要参与者：ACT-002（商家）、MerchantProductService、CategoryService
- 次要参与者：CategoryService
6. MerchantProductService调用CategoryService校验 categoryId，查询 category 表获取 category_id、status，确认分类有效且未停用。

### 3. API-L-IF1 → OrderService：调用 OrderService 查询 order 表获取 order_id、merchant_id、status
提案ID：PROPOSAL-EDGE-55A09CAD9C

4. 在线商城系统调用OrderService查询 order 表，获取 order_id、merchant_id、status，校验订单状态为 PAID 且属于当前商家。

### 4. API-L-IF1 → OrderService：调用 OrderService 创建发货能力
提案ID：PROPOSAL-EDGE-11A470FACE

5. 在线商城系统调用OrderService的创建发货能力，传入 orderId、carrierCode、trackingNumber、shippedItems[]。
10. OrderService向在线商城系统返回 HTTP 200，响应体包含 shipmentId、orderStatus（SHIPPED）、trackingNumber。

### 5. OrderService → LogisticsService：向 LogisticsService 登记物流单号
提案ID：PROPOSAL-EDGE-E6CF549558

9. OrderService向ACT-004（LogisticsService）登记物流单号，传入 trackingNumber、carrierCode、orderId。

### 6. POST /api/v1/logistics/events → LogisticsServiceAdapter：校验签名并处理物流事件
提案ID：PROPOSAL-EDGE-446A5B1A02

2. LogisticsServiceAdapter校验 signature 的合法性，确认请求来源为授权的LogisticsService。
8. LogisticsServiceAdapter向在线商城系统返回 HTTP 200，响应体包含 accepted=true、duplicate=false。

### 7. API-L-IF2 → OrderService：调用OrderService查询订单归属与状态
提案ID：PROPOSAL-EDGE-3D3E79AA7C

4. 在线商城系统调用OrderService查询 order 表，校验订单属于当前顾客且状态为 SHIPPED 或之后。

### 8. API-L-IF2 → LogisticsServiceAdapter：调用LogisticsServiceAdapter的物流查询能力
提案ID：PROPOSAL-EDGE-A56B9A4724

5. 在线商城系统调用LogisticsServiceAdapter的物流查询能力，传入 orderId。
9. LogisticsServiceAdapter向在线商城系统返回 HTTP 200，响应体包含 trackingNumber、status、events[]、lastUpdatedAt、dataSource。

### 9. LogisticsServiceAdapter → LogisticsService：查询最新物流轨迹
提案ID：PROPOSAL-EDGE-63D0B52584

8. LogisticsServiceAdapter判断本地数据是否过期（last_updated_at 距当前时间超过阈值）；若过期，调用ACT-004（LogisticsService）查询最新物流轨迹。
   ③ 当本地数据过期时，系统调用LogisticsService查询最新轨迹。

### 10. API-R-IF1 → OrderService：查询订单和订单项并校验订单、计算可退款金额
提案ID：PROPOSAL-EDGE-57451ABF7E

4. 在线商城系统调用OrderService查询 order 表和 order_item 表，校验订单属于当前顾客、状态满足退款条件、计算可退款金额。

### 11. API-R-IF1 → RefundService：调用退款申请能力
提案ID：PROPOSAL-EDGE-32418F8375

5. 在线商城系统调用RefundService的退款申请能力，传入 orderId、items[]、reasonCode、reasonDescription、requestedAmount、idempotencyKey。
6. RefundService按 idempotencyKey 执行幂等校验。
7. RefundService校验退款时限（是否在退款有效期内）和退款金额（requestedAmount <= 可退款金额）。
8. RefundService写入 refund 表（字段包括 refund_id、order_id、customer_id、items_snapshot、reason_code、reason_description、requested_amount、accepted_amount、status、created_at、updated_at）。
9. RefundService向ACT-003（PaymentService）提交退款请求，传入 refund_id、payment_id、accepted_amount。
10. PaymentService处理退款并向RefundService返回退款结果。
11. RefundService更新 refund 表中退款状态，并向在线商城系统返回 HTTP 200，响应体包含 refundId、refundStatus、acceptedAmount。

### 12. RefundService → PaymentService：提交退款请求
提案ID：PROPOSAL-EDGE-124842818A

9. RefundService向ACT-003（PaymentService）提交退款请求，传入 refund_id、payment_id、accepted_amount。
10. PaymentService处理退款并向RefundService返回退款结果。

### 13. API-M-IF1 → MerchantProductService：调用MerchantProductService的创建商品能力
提案ID：PROPOSAL-EDGE-58CCA42F50

4. 在线商城系统调用MerchantProductService的创建商品能力，传入 merchantId、idempotencyKey。
5. MerchantProductService校验商家经营资质（查询 merchant 表，获取 merchant_id、qualification_status、product_permission），确认资质有效且有商品管理权限。
6. MerchantProductService按 idempotencyKey 执行幂等校验。
7. MerchantProductService生成 productId 和初始 version，写入 product 表（字段包括 product_id、merchant_id、name、description、category_id、status（DRAFT）、version、created_at、updated_at）。
8. MerchantProductService向在线商城系统返回 HTTP 200，响应体包含 productId、status（DRAFT）、version。

### 14. API-M-IF2 → MerchantProductService：调用商品信息维护能力
提案ID：PROPOSAL-EDGE-21ECAC4740

4. 在线商城系统调用MerchantProductService的商品信息维护能力，传入 productId、name、description、categoryId、imageUrls[]、version。

### 15. MerchantProductService → CategoryService：调用CategoryService校验 categoryId
提案ID：PROPOSAL-EDGE-166B07248E

6. MerchantProductService调用CategoryService校验 categoryId，查询 category 表获取 category_id、status，确认分类有效且未停用。

### 16. API-M-IF3 → MerchantProductService：调用库存与价格维护能力
提案ID：PROPOSAL-EDGE-D05C8E5FD1

4. 在线商城系统调用MerchantProductService的库存与价格维护能力，传入 productId、skus[]、version。
5. MerchantProductService查询 product 表，获取 product_id、merchant_id、status、version，校验商品属于当前商家、状态为 DRAFT、version 一致（乐观锁）。
6. MerchantProductService校验 SKU 数据：stock 不为负数、salePrice 合法、originalPrice 合法、skuId 无重复。
7. MerchantProductService写入/更新 sku 表（字段包括 sku_id、product_id、attributes、stock_quantity、sale_price、original_price、updated_at）。
8. MerchantProductService更新 product 表中 version（+1）和 updated_at。
9. MerchantProductService向在线商城系统返回 HTTP 200，响应体包含 productId、skus[]、version（新版本号）。

### 17. API-M-IF4 → MerchantProductService：调用商品发布能力
提案ID：PROPOSAL-EDGE-FCD02B64FE

4. 在线商城系统调用MerchantProductService的商品发布能力，传入 productId、version、publishAt。
11. MerchantProductService向在线商城系统返回 HTTP 200，响应体包含 productId、status（ON_SALE）、publishedAt、catalogSyncStatus。

### 18. MerchantProductService → ProductCatalogService：刷新可售索引
提案ID：PROPOSAL-EDGE-2658FDD729

9. MerchantProductService调用ProductCatalogService刷新可售索引，传入 productId 和最新商品数据。
10. ProductCatalogService更新商品检索索引，向MerchantProductService返回同步结果。
   ⑤ 系统通知商品目录服务刷新可售商品索引。

## 不申请增加的错误调用

最初抽取出的 LogisticsServiceAdapter→OrderService 仅引用次要参与者及RR摘要步骤，缺少SR实际调用依据；已由来源工具阻断，并用原始正常包重抽移除。异常查询后的返回也不属于独立请求，已在重抽中消除。不会把这两条错误关系作为新增架构建议。

本轮不提出新增关注点。必须先完成原文/C审查与完整比较，才能判断57项既有体系是否存在无法表达的异常。
