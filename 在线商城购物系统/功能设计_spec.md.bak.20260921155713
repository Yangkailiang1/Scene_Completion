# Delta 功能设计文档

> 本文档为仿真数据，所有名称、编号、路径和业务数据均为虚构。

## SR设计：在线交易平台核心业务模块

### 基本信息

| SR编号 | SR名称 | SR描述 | 关联架构元素 | 关联资源对象 |
| --- | --- | --- | --- | --- |
| SR-DELTA-042 | 在线交易核心能力增强 | 支持商品浏览、购物车、订单、支付、物流、退款和商家商品管理，并完善异常响应。 | ProductBrowse、CartService、OrderService、PaymentAdapter、LogisticsService、RefundService、MerchantProductService、ProductCatalogService、CategoryService | Product、ProductCategory、Cart、Order、Payment、Shipment、Refund、SKU |

#### API接口变更点分析

| 序号 | 变更类型 | 接口名称 | 方法 | 资源路径 | 影响范围 |
| --- | --- | --- | --- | --- | --- |
| 1 | 修改 | 商品列表查询API | GET | /api/v1/products | ACT-001（顾客）、在线商城系统、ProductCatalogService |
| 2 | 新增 | 商品详情查询API | GET | /api/v1/products/{productId} | ACT-001（顾客）、在线商城系统、ProductCatalogService |
| 3 | 修改 | 加入购物车API | POST | /api/v1/cart/items | ACT-001（顾客）、在线商城系统、CartService、ProductCatalogService |
| 4 | 修改 | 创建订单API | POST | /api/v1/orders | ACT-001（顾客）、在线商城系统、OrderService、ProductCatalogService |
| 5 | 修改 | 订单支付接口 | POST | /payment/v1/payments | ACT-001（顾客）、在线商城系统、ACT-003（PaymentService） |
| 6 | 新增 | 订单详情查询API | GET | /api/v1/orders/{orderId} | ACT-001（顾客）、在线商城系统、OrderService |
| 7 | 新增 | 商家发货API | POST | /api/v1/orders/{orderId}/shipments | ACT-002（商家）、在线商城系统、ACT-004（LogisticsService） |
| 8 | 新增 | 物流事件接收接口 | POST | /api/v1/logistics/events | ACT-004（LogisticsService）、在线商城系统、OrderService |
| 9 | 修改 | 物流信息查询API | GET | /api/v1/orders/{orderId}/logistics | ACT-001（顾客）、在线商城系统、ACT-004（LogisticsService） |
| 10 | 修改 | 退款申请API | POST | /api/v1/refunds | ACT-001（顾客）、在线商城系统、ACT-003（PaymentService） |
| 11 | 新增 | 商品创建API | POST | /api/v1/merchant/products | ACT-002（商家）、在线商城系统、MerchantProductService |
| 12 | 新增 | 商品信息维护API | PUT | /api/v1/merchant/products/{productId} | ACT-002（商家）、在线商城系统、MerchantProductService、CategoryService |
| 13 | 修改 | 库存价格维护API | PUT | /api/v1/merchant/products/{productId}/skus | ACT-002（商家）、在线商城系统、MerchantProductService |
| 14 | 修改 | 商品发布API | POST | /api/v1/merchant/products/{productId}/publish | ACT-002（商家）、在线商城系统、MerchantProductService、ProductCatalogService |

#### 变更详情

##### 1. 商品列表查询API

- API编号：API-S-IF1
- 变更类型：修改
- 所属服务：ProductBrowse
- 方法：GET
- 资源路径：/api/v1/products
- 影响范围：ACT-001（顾客）、在线商城系统、ProductCatalogService

###### 变更前

- 接口版本：V0（API-S-IF1的变更前版本）
- 方法/路径：GET /api/v1/products
- 请求体：无
- 查询参数：keyword、page、pageSize
- 成功响应：productId、name、price
- 错误响应：INVALID_QUERY

###### 变更后

- 请求体：无
- 查询参数：
  - keyword：商品关键词，可选；若存在，应满足关键词格式约束。
  - categoryId：分类编号，可选；若存在，应为有效且未失效的分类。
  - minPrice、maxPrice：价格区间，可选，minPrice 大于等于 0，maxPrice 大于等于 minPrice。
  - sortBy：排序方式，可选值为 DEFAULT、PRICE_ASC、PRICE_DESC、SALES_DESC。
  - page：页码，从 1 开始。
  - pageSize：每页数量，取值为 1 至 100。
- 成功响应：

    {
      "code": "OK",
      "data": {
        "items": [
          {
            "productId": "P10001",
            "name": "仿真商品A",
            "coverImage": "https://example.invalid/images/P10001-cover.png",
            "price": 199.00,
            "originalPrice": 229.00,
            "stockStatus": "IN_STOCK",
            "salesCount": 120
          }
        ],
        "total": 1,
        "page": 1,
        "pageSize": 20
      }
    }

- 错误响应：
  - HTTP 400，错误码 INVALID_QUERY_PARAM：查询参数不合法。
  - HTTP 400，错误码 INVALID_CATEGORY：分类不存在或已停用。
  - HTTP 504，错误码 PRODUCT_SERVICE_TIMEOUT：商品目录服务查询超时。
  - HTTP 503，错误码 PRODUCT_SERVICE_UNAVAILABLE：商品目录服务不可用。

##### 2. 商品详情查询API

- API编号：API-S-IF2
- 变更类型：新增
- 所属服务：ProductBrowse
- 方法：GET
- 资源路径：/api/v1/products/{productId}
- 影响范围：ACT-001（顾客）、在线商城系统、ProductCatalogService

###### 变更前

无。

###### 变更后

- 请求体：无
- 路径参数：
  - productId：商品唯一编号，必填。
- 成功响应：

    {
      "code": "OK",
      "data": {
        "productId": "P10001",
        "name": "仿真商品A",
        "description": "仿真商品描述",
        "price": 199.00,
        "stockStatus": "IN_STOCK",
        "images": ["https://example.invalid/images/P10001-1.png"]
      }
    }

- 错误响应：
  - HTTP 400，错误码 INVALID_PRODUCT_ID：商品编号格式错误。
  - HTTP 404，错误码 PRODUCT_NOT_FOUND：商品不存在。
  - HTTP 410，错误码 PRODUCT_OFF_SHELF：商品已下架。

##### 3. 加入购物车API

- API编号：API-C-IF1
- 变更类型：修改
- 所属服务：CartService
- 方法：POST
- 资源路径：/api/v1/cart/items

###### 变更前

- 请求体：skuId、quantity。
- 成功响应：cartItemId、quantity。
- 错误响应：OUT_OF_STOCK。

###### 变更后

- 请求体：productId、skuId、quantity、idempotencyKey。
- 成功响应：cartItemId、quantity、cartItemCount、amountSummary。
- 错误响应：INVALID_QUANTITY、OUT_OF_STOCK、PRODUCT_OFF_SHELF、PURCHASE_LIMIT_EXCEEDED。

##### 4. 创建订单API

- API编号：API-O-IF1
- 变更类型：修改
- 所属服务：OrderService
- 方法：POST
- 资源路径：/api/v1/orders

###### 变更前

- 请求体：cartItemIds、addressId。
- 成功响应：orderId。
- 错误响应：ORDER_CREATE_FAILED。

###### 变更后

- 请求体：cartItemIds、addressId、couponId、idempotencyKey、confirmedAmount。
- 成功响应：orderId、orderStatus、payableAmount、expireAt。
- 错误响应：PRICE_CHANGED、OUT_OF_STOCK、INVALID_ADDRESS、DUPLICATE_SUBMISSION。

##### 5. 订单支付接口

- API编号：PAYMENT-PAY-01
- 变更类型：修改
- 所属服务：PaymentAdapter
- 方法：POST
- 资源路径：/payment/v1/payments

###### 变更前

- 请求体：orderId、amount。
- 成功响应：paymentId、status。
- 错误响应：PAYMENT_FAILED。

###### 变更后

- 请求体：orderId、amount、paymentMethod、notifyUrl、idempotencyKey。
- 成功响应：paymentId、paymentStatus、paidAt、providerTradeNo。
- 错误响应：ORDER_STATUS_INVALID、AMOUNT_MISMATCH、PAYMENT_SERVICE_UNAVAILABLE、PAYMENT_CANCELLED。

##### 6. 订单详情查询API

- API编号：API-O-IF2
- 变更类型：新增
- 所属服务：OrderService
- 方法：GET
- 资源路径：/api/v1/orders/{orderId}

###### 变更前

无。

###### 变更后

- 请求体：无；路径参数为orderId。
- 成功响应：orderId、status、items[]、amountSummary、paymentSummary、shipmentSummary。
- 错误响应：ORDER_NOT_FOUND、ORDER_ACCESS_DENIED。

##### 7. 商家发货API

- API编号：API-L-IF1
- 变更类型：新增
- 所属服务：OrderService
- 方法：POST
- 资源路径：/api/v1/orders/{orderId}/shipments

###### 变更前

无。

###### 变更后

- 请求体：carrierCode、trackingNumber、shippedItems[]。
- 成功响应：shipmentId、orderStatus、trackingNumber。
- 错误响应：ORDER_STATUS_INVALID、INVALID_TRACKING_NUMBER、LOGISTICS_SERVICE_UNAVAILABLE。

##### 8. 物流事件接收接口

- API编号：LOGI-EVT-01
- 变更类型：新增
- 所属服务：LogisticsServiceAdapter
- 方法：POST
- 资源路径：/api/v1/logistics/events

###### 变更前

无。

###### 变更后

- 请求体：eventId、trackingNumber、eventCode、eventTime、location、signature。
- 成功响应：accepted、duplicate。
- 错误响应：INVALID_SIGNATURE、TRACKING_NUMBER_NOT_FOUND、INVALID_EVENT_TIME。

##### 9. 物流信息查询API

- API编号：API-L-IF2
- 变更类型：修改
- 所属服务：LogisticsServiceAdapter
- 方法：GET
- 资源路径：/api/v1/orders/{orderId}/logistics

###### 变更前

- 请求体：无；路径参数为orderId。
- 成功响应：trackingNumber、status。
- 错误响应：LOGISTICS_NOT_FOUND。

###### 变更后

- 请求体：无；路径参数为orderId。
- 成功响应：trackingNumber、status、events[]、lastUpdatedAt、dataSource。
- 错误响应：ORDER_NOT_SHIPPED、LOGISTICS_NOT_FOUND、LOGISTICS_SERVICE_UNAVAILABLE。

##### 10. 退款申请API

- API编号：API-R-IF1
- 变更类型：修改
- 所属服务：RefundService
- 方法：POST
- 资源路径：/api/v1/refunds

###### 变更前

- 请求体：orderId、reason。
- 成功响应：refundId、status。
- 错误响应：REFUND_FAILED。

###### 变更后

- 请求体：orderId、items[]、reasonCode、reasonDescription、requestedAmount。
- 成功响应：refundId、refundStatus、acceptedAmount。
- 错误响应：REFUND_WINDOW_EXPIRED、REFUND_AMOUNT_EXCEEDED、ORDER_STATUS_INVALID、PAYMENT_SERVICE_UNAVAILABLE。

##### 11. 商品创建API

- API编号：API-M-IF1
- 变更类型：新增
- 所属服务：MerchantProductService
- 方法：POST
- 资源路径：/api/v1/merchant/products

###### 变更前

无。

###### 变更后

- 请求体：merchantId、idempotencyKey。
- 成功响应：productId、status、version。
- 错误响应：MERCHANT_NOT_QUALIFIED、PERMISSION_DENIED、DUPLICATE_SUBMISSION。

##### 12. 商品信息维护API

- API编号：API-M-IF2
- 变更类型：新增
- 所属服务：MerchantProductService
- 方法：PUT
- 资源路径：/api/v1/merchant/products/{productId}

###### 变更前

无。

###### 变更后

- 请求体：name、description、categoryId、imageUrls[]、version。
- 成功响应：productId、status、version、updatedAt。
- 错误响应：PRODUCT_NOT_FOUND、INVALID_CATEGORY、INVALID_IMAGE、VERSION_CONFLICT。

##### 13. 库存价格维护API

- API编号：API-M-IF3
- 变更类型：修改
- 所属服务：MerchantProductService
- 方法：PUT
- 资源路径：/api/v1/merchant/products/{productId}/skus

###### 变更前

- 请求体：skuId、stock、price。
- 成功响应：skuId、version。
- 错误响应：INVALID_SKU_DATA。

###### 变更后

- 请求体：skus[]；每项包含skuId、attributes、stock、salePrice、originalPrice，以及商品version。
- 成功响应：productId、skus[]、version。
- 错误响应：NEGATIVE_STOCK、INVALID_PRICE、DUPLICATE_SKU、VERSION_CONFLICT。

##### 14. 商品发布API

- API编号：API-M-IF4
- 变更类型：修改
- 所属服务：MerchantProductService
- 方法：POST
- 资源路径：/api/v1/merchant/products/{productId}/publish

###### 变更前

- 请求体：无。
- 成功响应：productId、status。
- 错误响应：PUBLISH_FAILED。

###### 变更后

- 请求体：version、publishAt。
- 成功响应：productId、status、publishedAt、catalogSyncStatus。
- 错误响应：PRODUCT_INCOMPLETE、CATEGORY_RULE_VIOLATION、INVALID_PRODUCT_STATUS、VERSION_CONFLICT。

### 设计用例

#### UCG-001-UC001-API-S-IF1 浏览商品

- 关联API：API-S-IF1
- 主要参与者：ACT-001（顾客）、ProductCatalogService
- 方法/路径：GET /api/v1/products
- 关键请求参数：keyword、categoryId、minPrice、maxPrice、sortBy、page、pageSize
- 关键响应：items[]、total、page、pageSize

#### UCG-001-UC002-API-S-IF2 查看商品详情

- 关联API：API-S-IF2
- 主要参与者：ACT-001（顾客）、ProductCatalogService
- 方法/路径：GET /api/v1/products/{productId}
- 关键请求参数：productId
- 关键响应：productId、name、description、price、stockStatus、images[]

#### UCG-001-UC003-API-C-IF1 加入购物车

- 关联API：API-C-IF1
- 主要参与者：ACT-001（顾客）、CartService、ProductCatalogService
- 方法/路径：POST /api/v1/cart/items
- 关键请求参数：productId、skuId、quantity、idempotencyKey
- 关键响应：cartItemId、quantity、cartItemCount、amountSummary

#### UCG-002-UC001-API-O-IF1 创建订单

- 关联API：API-O-IF1
- 主要参与者：ACT-001（顾客）、OrderService、ProductCatalogService
- 方法/路径：POST /api/v1/orders
- 关键请求参数：cartItemIds、addressId、couponId、idempotencyKey、confirmedAmount
- 关键响应：orderId、orderStatus、payableAmount、expireAt

#### UCG-002-UC002-PAYMENT-PAY-01 支付订单

- 关联API：PAYMENT-PAY-01
- 主要参与者：ACT-001（顾客）、ACT-003（PaymentService）、PaymentAdapter
- 方法/路径：POST /payment/v1/payments
- 关键请求参数：orderId、amount、paymentMethod、idempotencyKey
- 关键响应：paymentId、paymentStatus、paidAt、providerTradeNo

#### UCG-002-UC003-API-O-IF2 查看订单详情

- 关联API：API-O-IF2
- 主要参与者：ACT-001（顾客）、OrderService
- 方法/路径：GET /api/v1/orders/{orderId}
- 关键请求参数：orderId
- 关键响应：orderId、status、items[]、amountSummary、paymentSummary、shipmentSummary

#### UCG-003-UC001-API-L-IF1 商家发货

- 关联API：API-L-IF1
- 主要参与者：ACT-002（商家）、ACT-004（LogisticsService）、OrderService
- 方法/路径：POST /api/v1/orders/{orderId}/shipments
- 关键请求参数：orderId、carrierCode、trackingNumber、shippedItems[]
- 关键响应：shipmentId、orderStatus、trackingNumber

#### UCG-003-UC002-LOGI-EVT-01 更新物流信息

- 关联API：LOGI-EVT-01
- 主要参与者：ACT-004（LogisticsService）、LogisticsServiceAdapter
- 方法/路径：POST /api/v1/logistics/events
- 关键请求参数：eventId、trackingNumber、eventCode、eventTime、location、signature
- 关键响应：accepted、duplicate

#### UCG-003-UC003-API-L-IF2 查询物流信息

- 关联API：API-L-IF2
- 主要参与者：ACT-001（顾客）、ACT-004（LogisticsService）、LogisticsServiceAdapter
- 方法/路径：GET /api/v1/orders/{orderId}/logistics
- 关键请求参数：orderId
- 关键响应：trackingNumber、status、events[]、lastUpdatedAt、dataSource

#### UCG-003-UC004-API-R-IF1 申请退款

- 关联API：API-R-IF1
- 主要参与者：ACT-001（顾客）、ACT-003（PaymentService）、RefundService
- 方法/路径：POST /api/v1/refunds
- 关键请求参数：orderId、items[]、reasonCode、reasonDescription、requestedAmount
- 关键响应：refundId、refundStatus、acceptedAmount

#### UCG-004-UC001-API-M-IF1 创建商品

- 关联API：API-M-IF1
- 主要参与者：ACT-002（商家）、MerchantProductService
- 方法/路径：POST /api/v1/merchant/products
- 关键请求参数：merchantId、idempotencyKey
- 关键响应：productId、status、version

#### UCG-004-UC002-API-M-IF2 填写商品信息

- 关联API：API-M-IF2
- 主要参与者：ACT-002（商家）、MerchantProductService、CategoryService
- 方法/路径：PUT /api/v1/merchant/products/{productId}
- 关键请求参数：productId、name、description、categoryId、imageUrls[]、version
- 关键响应：productId、status、version、updatedAt

#### UCG-004-UC003-API-M-IF3 设置库存与价格

- 关联API：API-M-IF3
- 主要参与者：ACT-002（商家）、MerchantProductService
- 方法/路径：PUT /api/v1/merchant/products/{productId}/skus
- 关键请求参数：productId、skus[]、version
- 关键响应：productId、skus[]、version

#### UCG-004-UC004-API-M-IF4 发布商品

- 关联API：API-M-IF4
- 主要参与者：ACT-002（商家）、MerchantProductService、ProductCatalogService
- 方法/路径：POST /api/v1/merchant/products/{productId}/publish
- 关键请求参数：productId、version、publishAt
- 关键响应：productId、status、publishedAt、catalogSyncStatus

### 设计用例详情

#### UCG-001-UC001-API-S-IF1 浏览商品

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-001-UC001-API-S-IF1 |
| 用例名称 | 浏览商品 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-S-IF1 |
| 方法/路径 | GET /api/v1/products |

##### 参与者

- 主要参与者：ACT-001（顾客）、ProductCatalogService
- 次要参与者：无

##### 前置条件

- 在线商城系统正常运行，商品浏览接口可访问。
- ProductCatalogService服务可用，商品目录中存在状态为 ON_SALE 的商品。
- ACT-001可匿名访问；若已登录，则请求可携带合法 Authorization Token。
- 查询参数 keyword、categoryId、minPrice、maxPrice、sortBy、page、pageSize 若存在，应满足接口约束。

##### 基本流程

1. ACT-001发送 GET /api/v1/products 请求到在线商城系统，可携带查询参数 keyword、categoryId、minPrice、maxPrice、sortBy、page、pageSize。
2. 在线商城系统校验查询参数，其中 page>=1、1<=pageSize<=100、minPrice>=0、maxPrice>=minPrice，并校验 categoryId 是否有效。
3. 在线商城系统调用ProductCatalogService的商品检索能力，传入查询条件并补充status=ON_SALE。
4. ProductCatalogService根据请求条件查询 product 表，涉及字段包括 product_id、product_name、category_id、cover_image_url、sale_price、original_price、stock_quantity、sales_count、status、merchant_id、updated_at。
5. ProductCatalogService向在线商城系统返回 HTTP 200，响应体包含 page、pageSize、total、products[]；每个商品包含 productId、productName、categoryId、coverImageUrl、salePrice、originalPrice、stockQuantity、salesCount、status。
6. 在线商城系统过滤内部字段，将结果转换为前端展示结构，并向ACT-001返回 HTTP 200，响应体包含 page、pageSize、total、items[]；每个商品包含 productId、name、coverImage、price、originalPrice、stockStatus、salesCount。

##### 备选流程

- A1：查询参数非法，例如 minPrice>maxPrice、page<1 或 sortBy 不在允许范围内，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_QUERY_PARAM。
- A2：categoryId 不存在或已失效，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_CATEGORY。
- A3：ProductCatalogService未查询到符合条件的商品，返回 HTTP 200，其中 total=0、products=[]，在线商城系统向ACT-001展示“暂无符合条件的商品”。
- A4：ProductCatalogService查询超时，在线商城系统返回 HTTP 504 Gateway Timeout，错误码 PRODUCT_SERVICE_TIMEOUT。
- A5：ProductCatalogService不可用，在线商城系统返回 HTTP 503 Service Unavailable，错误码 PRODUCT_SERVICE_UNAVAILABLE。
- A6：查询期间商品状态被商家修改为 OFF_SALE 或库存变为 0，在线商城系统在返回结果前过滤失效商品，仅返回当前有效商品。
- A7：商品必要字段缺失，例如 product_name、sale_price 或 cover_image_url 为空，在线商城系统采用缺省值展示或过滤异常商品。

#### UCG-001-UC002-API-S-IF2 查看商品详情

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-001-UC002-API-S-IF2 |
| 用例名称 | 查看商品详情 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-S-IF2 |
| 方法/路径 | GET /api/v1/products/{productId} |

##### 参与者

- 主要参与者：ACT-001（顾客）、ProductCatalogService
- 次要参与者：无

##### 前置条件

- 在线商城系统正常运行，商品详情接口可访问。
- ProductCatalogService服务可用，商品目录中存在可查询商品。
- ACT-001可匿名访问；若已登录，则请求可携带合法 Authorization Token。

##### 基本流程

1. ACT-001发送 GET /api/v1/products/{productId} 请求到在线商城系统。
2. 在线商城系统校验 productId 的格式，并保留合法 Authorization Token 和请求上下文。
3. 在线商城系统调用ProductCatalogService的商品详情读取能力，并传入productId。
4. ProductCatalogService根据 productId 查询 product 表，获取 product_id、product_name、description、image_urls、sale_price、original_price、stock_quantity、sales_count、status、merchant_id、updated_at。
5. ProductCatalogService向在线商城系统返回 HTTP 200 和商品详情数据。
6. 在线商城系统过滤内部字段并转换为前端结构，向ACT-001返回 HTTP 200；响应包含 productId、name、description、images[]、price、originalPrice、stockStatus、salesCount。

##### 备选流程

- A1：productId 格式错误，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_PRODUCT_ID。
- A2：ProductCatalogService未查询到目标商品，在线商城系统返回 HTTP 404 Not Found，错误码 PRODUCT_NOT_FOUND。
- A3：目标商品状态为 OFF_SALE，在线商城系统返回 HTTP 410 Gone，错误码 PRODUCT_OFF_SHELF。
- A4：ProductCatalogService查询超时，在线商城系统返回 HTTP 504 Gateway Timeout，错误码 PRODUCT_SERVICE_TIMEOUT。
- A5：ProductCatalogService不可用，在线商城系统返回 HTTP 503 Service Unavailable，错误码 PRODUCT_SERVICE_UNAVAILABLE。
- A6：description、image_urls 等非关键展示字段缺失，在线商城系统返回已有字段并隐藏或采用缺省值处理缺失区域。

#### UCG-001-UC003-API-C-IF1 加入购物车

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-001-UC003-API-C-IF1 |
| 用例名称 | 加入购物车 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-C-IF1 |
| 方法/路径 | POST /api/v1/cart/items |

##### 参与者

- 主要参与者：ACT-001（顾客）、CartService
- 次要参与者：ProductCatalogService

##### 前置条件

- 顾客已登录，目标商品与SKU处于可售状态。
- quantity满足库存和限购规则。

##### 基本流程

1. 顾客选择SKU和购买数量。
2. 系统校验商品状态、库存和限购规则。
3. 系统调用API-C-IF1写入购物车。
4. CartService返回购物车条目及金额摘要。
5. 系统提示“已加入购物车”。

##### 备选流程

- A1：库存不足，返回OUT_OF_STOCK及当前可购买数量。
- A2：商品已下架，返回PRODUCT_OFF_SHELF。
- A3：相同SKU已存在时累加数量，但不得超过上限。

#### UCG-002-UC001-API-O-IF1 创建订单

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-002-UC001-API-O-IF1 |
| 用例名称 | 创建订单 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-O-IF1 |
| 方法/路径 | POST /api/v1/orders |

##### 参与者

- 主要参与者：ACT-001（顾客）、OrderService
- 次要参与者：ProductCatalogService

##### 前置条件

- 顾客已登录并选中有效购物车商品。
- 收货地址有效，商品价格与库存可校验。

##### 基本流程

1. 系统读取选中的购物车商品。
2. 系统校验价格、库存、促销和收货地址。
3. 顾客确认订单金额。
4. 系统调用API-O-IF1创建订单并锁定库存。
5. 系统返回orderId、WAIT_PAY状态和待支付金额。

##### 备选流程

- A1：价格变化时返回PRICE_CHANGED并要求重新确认。
- A2：库存不足时返回OUT_OF_STOCK并阻止创建。
- A3：重复提交时按idempotencyKey返回已有订单。

#### UCG-002-UC002-PAYMENT-PAY-01 支付订单

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-002-UC002-PAYMENT-PAY-01 |
| 用例名称 | 支付订单 |
| 关联SR | SR-DELTA-042 |
| 关联API | PAYMENT-PAY-01 |
| 方法/路径 | POST /payment/v1/payments |

##### 参与者

- 主要参与者：ACT-001（顾客）、ACT-003（PaymentService）
- 次要参与者：PaymentAdapter、OrderService

##### 前置条件

- 订单状态为WAIT_PAY且未超过支付有效期。
- PaymentService可用。

##### 基本流程

1. 顾客选择支付方式并确认支付。
2. 系统校验订单状态和应付金额。
3. PaymentAdapter通过PAYMENT-PAY-01创建支付请求。
4. PaymentService返回支付成功结果。
5. 系统记录支付流水并将订单更新为PAID。
6. 系统展示支付成功页面。

##### 备选流程

- A1：PaymentService不可用时保留WAIT_PAY并提示重试。
- A2：顾客取消支付时订单保持WAIT_PAY。
- A3：重复支付通知按paymentId幂等处理。

#### UCG-002-UC003-API-O-IF2 查看订单详情

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-002-UC003-API-O-IF2 |
| 用例名称 | 查看订单详情 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-O-IF2 |
| 方法/路径 | GET /api/v1/orders/{orderId} |

##### 参与者

- 主要参与者：ACT-001（顾客）、OrderService
- 次要参与者：无

##### 前置条件

- 顾客已登录，订单属于当前顾客。

##### 基本流程

1. 顾客提交orderId。
2. 系统校验订单归属关系。
3. 系统调用API-O-IF2查询订单。
4. OrderService组合商品、金额、支付和履约信息。
5. 系统展示订单详情。

##### 备选流程

- A1：订单不属于当前顾客时返回ORDER_ACCESS_DENIED。
- A2：订单不存在时返回ORDER_NOT_FOUND。
- A3：订单未发货时不展示物流轨迹。

#### UCG-003-UC001-API-L-IF1 商家发货

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-003-UC001-API-L-IF1 |
| 用例名称 | 商家发货 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-L-IF1 |
| 方法/路径 | POST /api/v1/orders/{orderId}/shipments |

##### 参与者

- 主要参与者：ACT-002（商家）、ACT-004（LogisticsService）
- 次要参与者：OrderService

##### 前置条件

- 商家具有订单处理权限，订单状态为PAID。
- 商品已完成出库准备。

##### 基本流程

1. 商家填写承运商和物流单号。
2. 系统校验商家权限和订单状态。
3. 系统调用API-L-IF1创建发货记录。
4. 系统向LogisticsService登记物流单。
5. 系统保存物流单号并将订单更新为SHIPPED。

##### 备选流程

- A1：订单状态不是PAID时返回ORDER_STATUS_INVALID。
- A2：物流单号非法时返回INVALID_TRACKING_NUMBER。
- A3：物流服务不可用时保存待同步任务并重试。

#### UCG-003-UC002-LOGI-EVT-01 更新物流信息

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-003-UC002-LOGI-EVT-01 |
| 用例名称 | 更新物流信息 |
| 关联SR | SR-DELTA-042 |
| 关联API | LOGI-EVT-01 |
| 方法/路径 | POST /api/v1/logistics/events |

##### 参与者

- 主要参与者：ACT-004（LogisticsService）、LogisticsServiceAdapter
- 次要参与者：OrderService

##### 前置条件

- 商城已登记有效物流单号。
- LogisticsService持有合法调用凭证。

##### 基本流程

1. LogisticsService通过LOGI-EVT-01推送物流事件。
2. 系统校验签名、物流单号和事件时间。
3. 系统按eventId执行幂等校验。
4. 系统保存物流节点并更新订单物流摘要。
5. 系统返回接收结果。

##### 备选流程

- A1：签名失败时返回INVALID_SIGNATURE并记录告警。
- A2：重复事件返回duplicate=true，不重复写入。
- A3：事件时间倒序时返回INVALID_EVENT_TIME并进入审核队列。

#### UCG-003-UC003-API-L-IF2 查询物流信息

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-003-UC003-API-L-IF2 |
| 用例名称 | 查询物流信息 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-L-IF2 |
| 方法/路径 | GET /api/v1/orders/{orderId}/logistics |

##### 参与者

- 主要参与者：ACT-001（顾客）、ACT-004（LogisticsService）
- 次要参与者：LogisticsServiceAdapter

##### 前置条件

- 顾客已登录，订单属于当前顾客且已发货。

##### 基本流程

1. 顾客提交物流查询请求。
2. 系统调用API-L-IF2读取本地物流轨迹。
3. 本地数据过期时，系统查询LogisticsService。
4. 系统按时间顺序整理物流节点。
5. 系统展示最新物流状态和轨迹。

##### 备选流程

- A1：订单未发货时返回ORDER_NOT_SHIPPED。
- A2：外部查询失败时展示最近一次同步数据及更新时间。
- A3：物流已签收时展示签收时间和状态。

#### UCG-003-UC004-API-R-IF1 申请退款

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-003-UC004-API-R-IF1 |
| 用例名称 | 申请退款 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-R-IF1 |
| 方法/路径 | POST /api/v1/refunds |

##### 参与者

- 主要参与者：ACT-001（顾客）、ACT-003（PaymentService）
- 次要参与者：RefundService

##### 前置条件

- 订单属于当前顾客且已支付。
- 订单满足退款时限和状态规则。

##### 基本流程

1. 顾客选择退款商品、数量和原因。
2. 系统校验订单和可退款金额。
3. 系统调用API-R-IF1创建退款单。
4. RefundService向PaymentService提交退款请求。
5. 系统保存退款流水并展示处理状态。

##### 备选流程

- A1：超过退款期限时返回REFUND_WINDOW_EXPIRED。
- A2：金额超限时返回REFUND_AMOUNT_EXCEEDED。
- A3：支付服务不可用时保留待处理退款单并异步重试。

#### UCG-004-UC001-API-M-IF1 创建商品

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-004-UC001-API-M-IF1 |
| 用例名称 | 创建商品 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-M-IF1 |
| 方法/路径 | POST /api/v1/merchant/products |

##### 参与者

- 主要参与者：ACT-002（商家）、MerchantProductService
- 次要参与者：无

##### 前置条件

- 商家已登录、经营资质有效且拥有商品管理权限。

##### 基本流程

1. 商家点击“创建商品”。
2. 系统校验商家身份、资质和权限。
3. 系统调用API-M-IF1创建商品草稿。
4. MerchantProductService生成productId和初始version。
5. 系统进入商品信息编辑页面。

##### 备选流程

- A1：资质失效时返回MERCHANT_NOT_QUALIFIED。
- A2：无权限时返回PERMISSION_DENIED。
- A3：重复提交时根据idempotencyKey返回已有草稿。

#### UCG-004-UC002-API-M-IF2 填写商品信息

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-004-UC002-API-M-IF2 |
| 用例名称 | 填写商品信息 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-M-IF2 |
| 方法/路径 | PUT /api/v1/merchant/products/{productId} |

##### 参与者

- 主要参与者：ACT-002（商家）、MerchantProductService
- 次要参与者：CategoryService

##### 前置条件

- 商品草稿存在且属于当前商家。
- 商家拥有编辑权限。

##### 基本流程

1. 商家填写名称、描述、分类和图片。
2. 系统校验必填字段、文本长度、分类和图片格式。
3. 系统调用API-M-IF2保存资料。
4. MerchantProductService更新商品版本。
5. 系统提示保存成功。

##### 备选流程

- A1：分类无效时返回INVALID_CATEGORY。
- A2：图片不合规时返回INVALID_IMAGE。
- A3：版本冲突时返回VERSION_CONFLICT并要求重新加载。

#### UCG-004-UC003-API-M-IF3 设置库存与价格

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-004-UC003-API-M-IF3 |
| 用例名称 | 设置库存与价格 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-M-IF3 |
| 方法/路径 | PUT /api/v1/merchant/products/{productId}/skus |

##### 参与者

- 主要参与者：ACT-002（商家）、MerchantProductService
- 次要参与者：无

##### 前置条件

- 商品草稿存在且至少定义一个SKU。

##### 基本流程

1. 商家为各SKU填写库存和价格。
2. 系统校验库存、价格和SKU唯一性。
3. 系统调用API-M-IF3保存SKU数据。
4. MerchantProductService更新版本并返回最新SKU列表。
5. 系统展示保存结果。

##### 备选流程

- A1：库存为负时返回NEGATIVE_STOCK。
- A2：价格非法时返回INVALID_PRICE。
- A3：版本冲突时返回VERSION_CONFLICT。

#### UCG-004-UC004-API-M-IF4 发布商品

##### 基本信息

| 项目 | 内容 |
| --- | --- |
| 用例编号 | UCG-004-UC004-API-M-IF4 |
| 用例名称 | 发布商品 |
| 关联SR | SR-DELTA-042 |
| 关联API | API-M-IF4 |
| 方法/路径 | POST /api/v1/merchant/products/{productId}/publish |

##### 参与者

- 主要参与者：ACT-002（商家）、MerchantProductService
- 次要参与者：ProductCatalogService

##### 前置条件

- 商品处于DRAFT状态且资料、SKU、库存和价格完整。
- 商家经营资质有效。

##### 基本流程

1. 商家提交商品发布。
2. 系统校验资料完整性、类目规则、库存和价格。
3. 系统调用API-M-IF4发布商品。
4. MerchantProductService将状态更新为ON_SALE。
5. 系统通知ProductCatalogService刷新可售索引。
6. 系统提示发布成功。

##### 备选流程

- A1：资料不完整时返回PRODUCT_INCOMPLETE。
- A2：违反类目规则时返回CATEGORY_RULE_VIOLATION并进入审核。
- A3：目录同步失败时记录待同步任务并自动重试。

### 关联实现接口OpenAPI文件

#### AR： ProductBrowse 商品浏览模块

软件实现接口1：listProducts 商品列表查询API

软件实现接口2：getProductDetail 商品详情查询API

#### AR： CartService 购物车服务

软件实现接口1：addCartItem 加入购物车API

#### AR： OrderService 订单服务

软件实现接口1：createOrder 创建订单API

软件实现接口2：getOrderDetail 订单详情查询API

软件实现接口3：createShipment 商家发货API

#### AR： PaymentAdapter 支付适配服务

软件实现接口1：createPayment 订单支付接口

#### AR： LogisticsServiceAdapter 物流适配服务

软件实现接口1：receiveLogisticsEvent 物流事件接收接口

软件实现接口2：getOrderLogistics 物流信息查询API

#### AR： RefundService 退款服务

软件实现接口1：createRefund 退款申请API

#### AR： MerchantProductService 商家商品服务

软件实现接口1：createMerchantProduct 商品创建API

软件实现接口2：updateMerchantProduct 商品信息维护API

软件实现接口3：updateSkuInventoryAndPrice 库存价格维护API

软件实现接口4：publishMerchantProduct 商品发布API
