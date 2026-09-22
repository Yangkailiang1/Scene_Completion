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

- 在线商城系统正常运行，加入购物车接口可访问。
- CartService和ProductCatalogService服务可用。
- ACT-001已登录，请求携带合法 Authorization Token。
- 目标商品状态为 ON_SALE，目标SKU库存充足且有效。
- quantity满足约束（quantity>=1）和限购规则。

##### 基本流程

1. ACT-001发送 POST /api/v1/cart/items 请求到在线商城系统，请求体包含 productId、skuId、quantity、idempotencyKey。
2. 在线商城系统校验 Authorization Token，确认顾客身份。
3. 在线商城系统校验请求参数：productId和skuId格式合法、quantity>=1、idempotencyKey非空。
4. 在线商城系统调用ProductCatalogService的商品与SKU校验能力，传入 productId 和 skuId。
5. ProductCatalogService查询 product 表和 sku 表，获取 product_id、product_name、status、stock_quantity、sale_price、original_price、limit_per_order，并返回校验结果。
6. 在线商城系统确认商品状态为 ON_SALE，并校验库存（stock_quantity >= quantity）和限购规则（quantity <= limit_per_order）。
7. 在线商城系统调用CartService的加入购物车能力，传入顾客ID、productId、skuId、quantity、idempotencyKey。
8. CartService按 idempotencyKey 执行幂等校验；若同一SKU已存在于购物车，则累加数量并校验累加后不超限购上限。
9. CartService写入 cart_item 表（字段包括 cart_item_id、customer_id、product_id、sku_id、quantity、unit_price、created_at、updated_at），并计算购物车商品总数和金额汇总。
10. CartService向在线商城系统返回 HTTP 200，响应体包含 cartItemId、quantity、cartItemCount、amountSummary。
11. 在线商城系统向ACT-001返回 HTTP 200，响应体包含 cartItemId、quantity、cartItemCount、amountSummary。

##### 备选流程

- A1：quantity不合法（例如 quantity<1），在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_QUANTITY。
- A2：商品状态为 OFF_SALE，在线商城系统返回 HTTP 410 Gone，错误码 PRODUCT_OFF_SHELF。
- A3：SKU库存不足，在线商城系统返回 HTTP 409 Conflict，错误码 OUT_OF_STOCK，响应体包含当前可购买数量。
- A4：相同SKU已存在购物车中，CartService累加数量；若累加后超出限购上限，返回 HTTP 409 Conflict，错误码 PURCHASE_LIMIT_EXCEEDED。
- A5：idempotencyKey重复，CartService返回已有购物车条目，不重复写入。
- A6：ProductCatalogService不可用，在线商城系统返回 HTTP 503 Service Unavailable，错误码 PRODUCT_SERVICE_UNAVAILABLE。

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

- 在线商城系统正常运行，创建订单接口可访问。
- OrderService和ProductCatalogService服务可用。
- ACT-001已登录，购物车中存在已选中的有效商品条目。
- 收货地址有效且属于当前顾客。
- 商品价格与库存可校验，confirmedAmount与当前价格一致。
- idempotencyKey由客户端生成。

##### 基本流程

1. ACT-001发送 POST /api/v1/orders 请求到在线商城系统，请求体包含 cartItemIds、addressId、couponId、idempotencyKey、confirmedAmount。
2. 在线商城系统校验 Authorization Token，确认顾客身份。
3. 在线商城系统校验请求参数：cartItemIds非空、addressId格式合法、confirmedAmount>=0、idempotencyKey非空。
4. 在线商城系统调用CartService，读取 cart_item 表中 cartItemIds 对应的购物车条目，获取 product_id、sku_id、quantity、unit_price。
5. 在线商城系统调用ProductCatalogService的价格与库存校验能力，传入各商品的 productId、skuId、quantity。
6. ProductCatalogService查询 product 表和 sku 表，获取 sale_price、stock_quantity、status，并返回校验结果。
7. 在线商城系统校验：商品状态为 ON_SALE、库存充足、confirmedAmount与当前价格一致；若携带 couponId，校验优惠券有效性及适用范围。
8. 在线商城系统校验收货地址，查询 address 表获取 recipient_name、phone、province、city、district、detail_address。
9. 在线商城系统调用OrderService的创建订单能力，传入顾客ID、商品列表、地址信息、优惠券、confirmedAmount、idempotencyKey。
10. OrderService按 idempotencyKey 执行幂等校验，创建订单并锁定库存，写入 order 表（字段包括 order_id、customer_id、status、total_amount、payable_amount、coupon_id、address_snapshot、expire_at、created_at）和 order_item 表（字段包括 order_item_id、order_id、product_id、sku_id、quantity、unit_price、subtotal）。
11. OrderService向在线商城系统返回 HTTP 200，响应体包含 orderId、orderStatus（WAIT_PAY）、payableAmount、expireAt。
12. 在线商城系统向ACT-001返回 HTTP 200，响应体包含 orderId、orderStatus、payableAmount、expireAt。

##### 备选流程

- A1：商品价格与 confirmedAmount 不一致，在线商城系统返回 HTTP 409 Conflict，错误码 PRICE_CHANGED，响应体包含最新价格。
- A2：商品库存不足，在线商城系统返回 HTTP 409 Conflict，错误码 OUT_OF_STOCK，响应体包含不足商品及当前库存。
- A3：收货地址无效或不属于当前顾客，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_ADDRESS。
- A4：idempotencyKey重复，OrderService返回已有订单，不重复创建。
- A5：购物车商品为空，在线商城系统返回 HTTP 400 Bad Request，错误码 CART_EMPTY。
- A6：ProductCatalogService不可用，在线商城系统返回 HTTP 503 Service Unavailable，错误码 PRODUCT_SERVICE_UNAVAILABLE。

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

- 在线商城系统正常运行，订单支付接口可访问。
- PaymentAdapter服务可用，ACT-003（PaymentService）服务可用。
- 订单状态为 WAIT_PAY 且未超过支付有效期（expireAt）。
- ACT-001已登录，请求携带合法 Authorization Token。
- idempotencyKey由客户端生成。

##### 基本流程

1. ACT-001发送 POST /payment/v1/payments 请求到在线商城系统，请求体包含 orderId、amount、paymentMethod、notifyUrl、idempotencyKey。
2. 在线商城系统校验 Authorization Token，确认顾客身份。
3. 在线商城系统校验请求参数：orderId格式合法、amount>=0、paymentMethod合法、notifyUrl非空、idempotencyKey非空。
4. 在线商城系统调用OrderService查询 order 表，获取 order_id、customer_id、status、payable_amount、expire_at，校验订单状态为 WAIT_PAY、未过期、金额一致。
5. 在线商城系统调用PaymentAdapter的创建支付能力，传入 orderId、amount、paymentMethod、notifyUrl、idempotencyKey。
6. PaymentAdapter向ACT-003（PaymentService）发起支付请求，传入 orderId、amount、paymentMethod、notifyUrl。
7. PaymentService处理支付并向PaymentAdapter返回支付结果。
8. PaymentAdapter写入 payment 表（字段包括 payment_id、order_id、amount、payment_method、provider_trade_no、status、paid_at、created_at），并向在线商城系统返回 HTTP 200，响应体包含 paymentId、paymentStatus、paidAt、providerTradeNo。
9. 在线商城系统更新 order 表中订单状态为 PAID，记录支付流水。
10. 在线商城系统向ACT-001返回 HTTP 200，响应体包含 paymentId、paymentStatus、paidAt、providerTradeNo。

##### 备选流程

- A1：订单状态不是 WAIT_PAY，在线商城系统返回 HTTP 409 Conflict，错误码 ORDER_STATUS_INVALID。
- A2：支付金额与订单应付金额不一致，在线商城系统返回 HTTP 400 Bad Request，错误码 AMOUNT_MISMATCH。
- A3：PaymentService不可用或超时，在线商城系统返回 HTTP 503 Service Unavailable，错误码 PAYMENT_SERVICE_UNAVAILABLE，订单保持 WAIT_PAY 状态。
- A4：顾客取消支付，PaymentService返回取消状态，在线商城系统返回 HTTP 200，错误码 PAYMENT_CANCELLED，订单保持 WAIT_PAY。
- A5：idempotencyKey重复，PaymentAdapter返回已有支付结果，不重复处理。
- A6：支付回调通知到达时，在线商城系统按 paymentId 幂等处理，不重复更新订单状态。

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

- 在线商城系统正常运行，订单详情查询接口可访问。
- OrderService服务可用。
- ACT-001已登录，请求携带合法 Authorization Token。
- 目标订单存在且属于当前顾客。

##### 基本流程

1. ACT-001发送 GET /api/v1/orders/{orderId} 请求到在线商城系统。
2. 在线商城系统校验 Authorization Token，确认顾客身份。
3. 在线商城系统校验 orderId 格式合法。
4. 在线商城系统调用OrderService的订单详情查询能力，传入 orderId 和顾客ID。
5. OrderService查询 order 表，获取 order_id、customer_id、status、total_amount、payable_amount、coupon_id、address_snapshot、created_at、updated_at。
6. OrderService查询 order_item 表，获取各商品条目的 order_item_id、product_id、sku_id、quantity、unit_price、subtotal。
7. OrderService查询 payment 表，获取 payment_id、payment_method、provider_trade_no、payment_status、paid_at。
8. OrderService查询 shipment 表，获取 shipment_id、carrier_code、tracking_number、shipment_status、shipped_at（若已发货）。
9. OrderService组合商品、金额、支付和履约信息，向在线商城系统返回 HTTP 200，响应体包含 orderId、status、items[]、amountSummary、paymentSummary、shipmentSummary。
10. 在线商城系统向ACT-001返回 HTTP 200，响应体包含订单详情。

##### 备选流程

- A1：orderId 格式错误，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_ORDER_ID。
- A2：订单不属于当前顾客，在线商城系统返回 HTTP 403 Forbidden，错误码 ORDER_ACCESS_DENIED。
- A3：订单不存在，在线商城系统返回 HTTP 404 Not Found，错误码 ORDER_NOT_FOUND。
- A4：订单未发货，shipmentSummary 中物流字段为空，不展示物流轨迹。
- A5：OrderService查询超时，在线商城系统返回 HTTP 504 Gateway Timeout，错误码 ORDER_SERVICE_TIMEOUT。

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

- 在线商城系统正常运行，商家发货接口可访问。
- OrderService服务可用，ACT-004（LogisticsService）服务可用。
- 商家已登录，具有订单处理权限，请求携带合法 Authorization Token。
- 订单状态为 PAID，且商品已完成出库准备。

##### 基本流程

1. ACT-002（商家）发送 POST /api/v1/orders/{orderId}/shipments 请求到在线商城系统，请求体包含 orderId、carrierCode、trackingNumber、shippedItems[]。
2. 在线商城系统校验 Authorization Token，确认商家身份和订单处理权限。
3. 在线商城系统校验请求参数：orderId格式合法、carrierCode合法、trackingNumber非空、shippedItems[]非空。
4. 在线商城系统调用OrderService查询 order 表，获取 order_id、merchant_id、status，校验订单状态为 PAID 且属于当前商家。
5. 在线商城系统调用OrderService的创建发货能力，传入 orderId、carrierCode、trackingNumber、shippedItems[]。
6. OrderService校验 trackingNumber 格式（如长度、字符集、承运商编码规则）。
7. OrderService写入 shipment 表（字段包括 shipment_id、order_id、carrier_code、tracking_number、shipped_items、status、shipped_at、created_at、updated_at）。
8. OrderService更新 order 表中订单状态为 SHIPPED。
9. OrderService向ACT-004（LogisticsService）登记物流单号，传入 trackingNumber、carrierCode、orderId。
10. OrderService向在线商城系统返回 HTTP 200，响应体包含 shipmentId、orderStatus（SHIPPED）、trackingNumber。
11. 在线商城系统向ACT-002返回 HTTP 200，响应体包含 shipmentId、orderStatus、trackingNumber。

##### 备选流程

- A1：订单状态不是 PAID，在线商城系统返回 HTTP 409 Conflict，错误码 ORDER_STATUS_INVALID。
- A2：trackingNumber 格式不合法，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_TRACKING_NUMBER。
- A3：ACT-004（LogisticsService）不可用，OrderService保存待同步任务，订单状态仍更新为 SHIPPED，物流单号登记异步重试。
- A4：shippedItems[] 中的商品不属于该订单，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_SHIPPED_ITEMS。
- A5：商家无订单处理权限，在线商城系统返回 HTTP 403 Forbidden，错误码 PERMISSION_DENIED。

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

- 在线商城系统正常运行，物流事件接收接口可访问。
- LogisticsServiceAdapter服务可用。
- 商城已登记有效物流单号（shipment 表中存在对应记录）。
- ACT-004（LogisticsService）持有合法调用凭证（signature）。

##### 基本流程

1. ACT-004（LogisticsService）发送 POST /api/v1/logistics/events 请求到在线商城系统，请求体包含 eventId、trackingNumber、eventCode、eventTime、location、signature。
2. LogisticsServiceAdapter校验 signature 的合法性，确认请求来源为授权的LogisticsService。
3. LogisticsServiceAdapter校验 trackingNumber 是否在 shipment 表中存在，查询 shipment 表获取 shipment_id、order_id、carrier_code。
4. LogisticsServiceAdapter校验 eventTime 的合理性（不早于发货时间、不晚于当前时间）。
5. LogisticsServiceAdapter按 eventId 执行幂等校验，查询 logistics_event 表是否已存在相同 eventId。
6. LogisticsServiceAdapter写入 logistics_event 表（字段包括 event_id、tracking_number、event_code、event_time、location、shipment_id、order_id、created_at）。
7. LogisticsServiceAdapter更新 shipment 表中的物流状态摘要（last_event_code、last_event_time、last_location、last_updated_at）。
8. LogisticsServiceAdapter向在线商城系统返回 HTTP 200，响应体包含 accepted=true、duplicate=false。
9. 在线商城系统向ACT-004返回 HTTP 200，响应体包含 accepted、duplicate。

##### 备选流程

- A1：signature 校验失败，LogisticsServiceAdapter返回 HTTP 401 Unauthorized，错误码 INVALID_SIGNATURE，并记录安全告警日志。
- A2：trackingNumber 在 shipment 表中不存在，LogisticsServiceAdapter返回 HTTP 404 Not Found，错误码 TRACKING_NUMBER_NOT_FOUND。
- A3：eventTime 不合理（早于发货时间或晚于当前时间），LogisticsServiceAdapter返回 HTTP 400 Bad Request，错误码 INVALID_EVENT_TIME。
- A4：eventId 已存在，LogisticsServiceAdapter返回 HTTP 200，响应体包含 accepted=true、duplicate=true，不重复写入。
- A5：signature 校验通过但 eventCode 非法（不在允许的事件编码范围内），LogisticsServiceAdapter返回 HTTP 400 Bad Request，错误码 INVALID_EVENT_CODE。

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

- 在线商城系统正常运行，物流信息查询接口可访问。
- LogisticsServiceAdapter服务可用。
- ACT-001已登录，请求携带合法 Authorization Token。
- 订单属于当前顾客且已发货（订单状态为 SHIPPED 或更后状态）。

##### 基本流程

1. ACT-001发送 GET /api/v1/orders/{orderId}/logistics 请求到在线商城系统。
2. 在线商城系统校验 Authorization Token，确认顾客身份。
3. 在线商城系统校验 orderId 格式合法。
4. 在线商城系统调用OrderService查询 order 表，校验订单属于当前顾客且状态为 SHIPPED 或之后。
5. 在线商城系统调用LogisticsServiceAdapter的物流查询能力，传入 orderId。
6. LogisticsServiceAdapter查询 shipment 表，获取 shipment_id、carrier_code、tracking_number、status、shipped_at。
7. LogisticsServiceAdapter查询 logistics_event 表，获取该物流单的所有事件节点（event_code、event_time、location），按 event_time 排序。
8. LogisticsServiceAdapter判断本地数据是否过期（last_updated_at 距当前时间超过阈值）；若过期，调用ACT-004（LogisticsService）查询最新物流轨迹。
9. LogisticsServiceAdapter向在线商城系统返回 HTTP 200，响应体包含 trackingNumber、status、events[]、lastUpdatedAt、dataSource。
10. 在线商城系统向ACT-001返回 HTTP 200，响应体包含 trackingNumber、status、events[]、lastUpdatedAt、dataSource。

##### 备选流程

- A1：订单未发货（状态为 WAIT_PAY 或 PAID），在线商城系统返回 HTTP 409 Conflict，错误码 ORDER_NOT_SHIPPED。
- A2：本地物流数据不存在，在线商城系统返回 HTTP 404 Not Found，错误码 LOGISTICS_NOT_FOUND。
- A3：ACT-004（LogisticsService）查询失败或超时，LogisticsServiceAdapter返回本地最近一次同步数据，dataSource 标记为 CACHE，并包含 lastUpdatedAt。
- A4：物流已签收，events[] 中包含签收节点，status 为 DELIVERED，响应包含签收时间。
- A5：LogisticsServiceAdapter服务不可用，在线商城系统返回 HTTP 503 Service Unavailable，错误码 LOGISTICS_SERVICE_UNAVAILABLE。

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

- 在线商城系统正常运行，退款申请接口可访问。
- RefundService服务可用，ACT-003（PaymentService）服务可用。
- ACT-001已登录，订单属于当前顾客且已支付（订单状态为 PAID 或 SHIPPED）。
- 订单满足退款时限（在退款有效期内）和状态规则。
- idempotencyKey由客户端生成。

##### 基本流程

1. ACT-001发送 POST /api/v1/refunds 请求到在线商城系统，请求体包含 orderId、items[]、reasonCode、reasonDescription、requestedAmount、idempotencyKey。
2. 在线商城系统校验 Authorization Token，确认顾客身份。
3. 在线商城系统校验请求参数：orderId格式合法、items[]非空、reasonCode合法、requestedAmount>=0、idempotencyKey非空。
4. 在线商城系统调用OrderService查询 order 表和 order_item 表，校验订单属于当前顾客、状态满足退款条件、计算可退款金额。
5. 在线商城系统调用RefundService的退款申请能力，传入 orderId、items[]、reasonCode、reasonDescription、requestedAmount、idempotencyKey。
6. RefundService按 idempotencyKey 执行幂等校验。
7. RefundService校验退款时限（是否在退款有效期内）和退款金额（requestedAmount <= 可退款金额）。
8. RefundService写入 refund 表（字段包括 refund_id、order_id、customer_id、items_snapshot、reason_code、reason_description、requested_amount、accepted_amount、status、created_at、updated_at）。
9. RefundService向ACT-003（PaymentService）提交退款请求，传入 refund_id、payment_id、accepted_amount。
10. PaymentService处理退款并向RefundService返回退款结果。
11. RefundService更新 refund 表中退款状态，并向在线商城系统返回 HTTP 200，响应体包含 refundId、refundStatus、acceptedAmount。
12. 在线商城系统向ACT-001返回 HTTP 200，响应体包含 refundId、refundStatus、acceptedAmount。

##### 备选流程

- A1：超过退款有效期，在线商城系统返回 HTTP 409 Conflict，错误码 REFUND_WINDOW_EXPIRED。
- A2：退款金额超过可退款金额，在线商城系统返回 HTTP 409 Conflict，错误码 REFUND_AMOUNT_EXCEEDED，响应体包含可退款金额。
- A3：订单状态不满足退款条件（例如已退款或已取消），在线商城系统返回 HTTP 409 Conflict，错误码 ORDER_STATUS_INVALID。
- A4：ACT-003（PaymentService）不可用，RefundService保留退款单为 PENDING 状态，异步重试提交退款请求，响应体 refundStatus 为 PROCESSING。
- A5：idempotencyKey重复，RefundService返回已有退款单，不重复创建。

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

- 在线商城系统正常运行，商品创建接口可访问。
- MerchantProductService服务可用。
- ACT-002（商家）已登录，经营资质有效，拥有商品管理权限，请求携带合法 Authorization Token。
- idempotencyKey由客户端生成。

##### 基本流程

1. ACT-002（商家）发送 POST /api/v1/merchant/products 请求到在线商城系统，请求体包含 merchantId、idempotencyKey。
2. 在线商城系统校验 Authorization Token，确认商家身份。
3. 在线商城系统校验请求参数：merchantId格式合法、idempotencyKey非空。
4. 在线商城系统调用MerchantProductService的创建商品能力，传入 merchantId、idempotencyKey。
5. MerchantProductService校验商家经营资质（查询 merchant 表，获取 merchant_id、qualification_status、product_permission），确认资质有效且有商品管理权限。
6. MerchantProductService按 idempotencyKey 执行幂等校验。
7. MerchantProductService生成 productId 和初始 version，写入 product 表（字段包括 product_id、merchant_id、name、description、category_id、status（DRAFT）、version、created_at、updated_at）。
8. MerchantProductService向在线商城系统返回 HTTP 200，响应体包含 productId、status（DRAFT）、version。
9. 在线商城系统向ACT-002返回 HTTP 200，响应体包含 productId、status、version。

##### 备选流程

- A1：商家经营资质已失效，在线商城系统返回 HTTP 403 Forbidden，错误码 MERCHANT_NOT_QUALIFIED。
- A2：商家无商品管理权限，在线商城系统返回 HTTP 403 Forbidden，错误码 PERMISSION_DENIED。
- A3：idempotencyKey重复，MerchantProductService返回已有商品草稿，不重复创建。
- A4：MerchantProductService不可用，在线商城系统返回 HTTP 503 Service Unavailable，错误码 MERCHANT_SERVICE_UNAVAILABLE。

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

- 在线商城系统正常运行，商品信息维护接口可访问。
- MerchantProductService和CategoryService服务可用。
- 商品草稿存在且属于当前商家（product 表中 status 为 DRAFT）。
- 商家拥有编辑权限，请求携带合法 Authorization Token。

##### 基本流程

1. ACT-002（商家）发送 PUT /api/v1/merchant/products/{productId} 请求到在线商城系统，请求体包含 name、description、categoryId、imageUrls[]、version。
2. 在线商城系统校验 Authorization Token，确认商家身份。
3. 在线商城系统校验请求参数：name非空且长度合法、description长度合法、categoryId格式合法、imageUrls[]格式合法、version非空。
4. 在线商城系统调用MerchantProductService的商品信息维护能力，传入 productId、name、description、categoryId、imageUrls[]、version。
5. MerchantProductService查询 product 表，获取 product_id、merchant_id、status、version，校验商品属于当前商家、状态为 DRAFT、version 一致（乐观锁）。
6. MerchantProductService调用CategoryService校验 categoryId，查询 category 表获取 category_id、status，确认分类有效且未停用。
7. MerchantProductService校验图片格式和数量约束（imageUrls[] 中每项URL格式合法、数量在允许范围内）。
8. MerchantProductService更新 product 表（字段包括 name、description、category_id、image_urls、version（+1）、updated_at）。
9. MerchantProductService向在线商城系统返回 HTTP 200，响应体包含 productId、status（DRAFT）、version（新版本号）、updatedAt。
10. 在线商城系统向ACT-002返回 HTTP 200，响应体包含 productId、status、version、updatedAt。

##### 备选流程

- A1：商品不存在，在线商城系统返回 HTTP 404 Not Found，错误码 PRODUCT_NOT_FOUND。
- A2：categoryId 不存在或已停用，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_CATEGORY。
- A3：图片URL格式不合法或数量超限，在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_IMAGE。
- A4：version 不一致（商品已被其他操作修改），在线商城系统返回 HTTP 409 Conflict，错误码 VERSION_CONFLICT，响应体包含最新version，要求商家重新加载。
- A5：商品状态不是 DRAFT（已发布），在线商城系统返回 HTTP 409 Conflict，错误码 INVALID_PRODUCT_STATUS。

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

- 在线商城系统正常运行，库存价格维护接口可访问。
- MerchantProductService服务可用。
- 商品草稿存在且至少定义一个SKU，属于当前商家。
- 商家拥有编辑权限，请求携带合法 Authorization Token。

##### 基本流程

1. ACT-002（商家）发送 PUT /api/v1/merchant/products/{productId}/skus 请求到在线商城系统，请求体包含 skus[]（每项含 skuId、attributes、stock、salePrice、originalPrice）和商品 version。
2. 在线商城系统校验 Authorization Token，确认商家身份。
3. 在线商城系统校验请求参数：skus[]非空、每项 skuId 格式合法、stock>=0、salePrice>=0、originalPrice>=0、version非空。
4. 在线商城系统调用MerchantProductService的库存与价格维护能力，传入 productId、skus[]、version。
5. MerchantProductService查询 product 表，获取 product_id、merchant_id、status、version，校验商品属于当前商家、状态为 DRAFT、version 一致（乐观锁）。
6. MerchantProductService校验 SKU 数据：stock 不为负数、salePrice 合法、originalPrice 合法、skuId 无重复。
7. MerchantProductService写入/更新 sku 表（字段包括 sku_id、product_id、attributes、stock_quantity、sale_price、original_price、updated_at）。
8. MerchantProductService更新 product 表中 version（+1）和 updated_at。
9. MerchantProductService向在线商城系统返回 HTTP 200，响应体包含 productId、skus[]、version（新版本号）。
10. 在线商城系统向ACT-002返回 HTTP 200，响应体包含 productId、skus[]、version。

##### 备选流程

- A1：stock 为负数，在线商城系统返回 HTTP 400 Bad Request，错误码 NEGATIVE_STOCK。
- A2：salePrice 或 originalPrice 不合法（例如为负数或格式错误），在线商城系统返回 HTTP 400 Bad Request，错误码 INVALID_PRICE。
- A3：skus[] 中存在重复的 skuId，在线商城系统返回 HTTP 409 Conflict，错误码 DUPLICATE_SKU。
- A4：version 不一致，在线商城系统返回 HTTP 409 Conflict，错误码 VERSION_CONFLICT，响应体包含最新version。
- A5：商品不存在，在线商城系统返回 HTTP 404 Not Found，错误码 PRODUCT_NOT_FOUND。

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

- 在线商城系统正常运行，商品发布接口可访问。
- MerchantProductService和ProductCatalogService服务可用。
- 商品处于 DRAFT 状态，且资料（名称、描述、分类、图片）、SKU、库存和价格完整。
- 商家经营资质有效，请求携带合法 Authorization Token。

##### 基本流程

1. ACT-002（商家）发送 POST /api/v1/merchant/products/{productId}/publish 请求到在线商城系统，请求体包含 version、publishAt。
2. 在线商城系统校验 Authorization Token，确认商家身份。
3. 在线商城系统校验请求参数：version非空、publishAt格式合法。
4. 在线商城系统调用MerchantProductService的商品发布能力，传入 productId、version、publishAt。
5. MerchantProductService查询 product 表，获取 product_id、merchant_id、status、version，校验商品属于当前商家、状态为 DRAFT、version 一致（乐观锁）。
6. MerchantProductService校验商品资料完整性：name、description、category_id、image_urls 非空，sku 表中存在至少一个有效SKU且 stock_quantity>0、sale_price>0。
7. MerchantProductService校验类目规则：查询 category 表获取分类的必填属性和发布规则，确认商品满足类目要求。
8. MerchantProductService更新 product 表中 status 为 ON_SALE、published_at、version（+1）、updated_at。
9. MerchantProductService调用ProductCatalogService刷新可售索引，传入 productId 和最新商品数据。
10. ProductCatalogService更新商品检索索引，向MerchantProductService返回同步结果。
11. MerchantProductService向在线商城系统返回 HTTP 200，响应体包含 productId、status（ON_SALE）、publishedAt、catalogSyncStatus。
12. 在线商城系统向ACT-002返回 HTTP 200，响应体包含 productId、status、publishedAt、catalogSyncStatus。

##### 备选流程

- A1：商品资料不完整（如缺少名称、描述、图片或SKU），在线商城系统返回 HTTP 409 Conflict，错误码 PRODUCT_INCOMPLETE，响应体包含缺失字段列表。
- A2：商品不满足类目发布规则（如必填属性缺失），在线商城系统返回 HTTP 409 Conflict，错误码 CATEGORY_RULE_VIOLATION，商品进入审核队列。
- A3：商品状态不是 DRAFT（如已发布或已删除），在线商城系统返回 HTTP 409 Conflict，错误码 INVALID_PRODUCT_STATUS。
- A4：version 不一致，在线商城系统返回 HTTP 409 Conflict，错误码 VERSION_CONFLICT，响应体包含最新version。
- A5：ProductCatalogService同步失败，MerchantProductService记录待同步任务并自动重试，catalogSyncStatus 为 SYNC_PENDING，商品状态仍更新为 ON_SALE。

### V5标准化设计用例调用链（抽取权威章节）

本节将每个 RR 用例对应的 SR 设计用例、Abstract API、AR 软件实现接口和微服务调用关系显式化。前文版本化内容保留作为原始设计证据；本节用于 V5 语义抽取和 SSD 生成。

统一调用链：系统接收 RR 业务动作 → SR Service/Abstract API → ImplementationAPI/AR 微服务 → 内部数据库或外部服务 → 逐层返回 SR → 系统向 Actor 返回业务结果。顾客/商家到系统的消息不携带 HTTP 细节。

#### UCG-001-UC001：浏览商品

- 关联 SR 用例/API：`UCG-001-UC001-API-S-IF1` / `API-S-IF1` / `ProductDisplayService`
- SR 接口：`GET /api/v1/products`；请求：`keyword, categoryId, minPrice, maxPrice, sortBy, page, pageSize`；返回：`page, pageSize, total, items[]`；错误：`INVALID_QUERY_PARAM, INVALID_CATEGORY, PRODUCT_SERVICE_TIMEOUT, PRODUCT_SERVICE_UNAVAILABLE`
- AR 调用：`listProducts` → `ProductCatalogService` → 查询 `product` 表（已由 API.md 确认）；结果逐层返回并转换为商品列表。

#### UCG-001-UC002：查看商品详情

- 关联 SR 用例/API：`UCG-001-UC002-API-S-IF2` / `API-S-IF2` / `ProductDisplayService`
- SR 接口：`GET /api/v1/products/{productId}`；请求：`productId, Authorization`；返回：`productId, name, description, images[], price, stockStatus`；错误：`INVALID_PRODUCT_ID, PRODUCT_NOT_FOUND, PRODUCT_OFF_SHELF`
- AR 调用：`getProductDetail` → `ProductCatalogService` → 查询 `product` 表；映射为 inferred，逐层返回。

#### UCG-001-UC003：加入购物车

- 关联 SR 用例/API：`UCG-001-UC003-API-C-IF1` / `API-C-IF1` / `CartService`
- SR 接口：`POST /api/v1/cart/items`；请求：`productId, skuId, quantity`；返回：`cartId, items[], totalAmount`；错误：`PRODUCT_NOT_FOUND, STOCK_NOT_ENOUGH, CART_ITEM_DUPLICATE`
- AR 调用：`addCartItem` → `CartService`，并调用 `getProductDetail` → `ProductCatalogService` 校验商品和库存；映射为 inferred。

#### UCG-002-UC001：创建订单

- 关联 SR 用例/API：`UCG-002-UC001-API-O-IF1` / `API-O-IF1` / `OrderService`
- SR 接口：`POST /api/v1/orders`；请求：`cartId, addressId, items[], paymentMethod`；返回：`orderId, status, totalAmount`；错误：`CART_EMPTY, STOCK_NOT_ENOUGH, PRICE_CHANGED`
- AR 调用：`createOrder` → `OrderService`，调用 `validatePriceStock` → `ProductCatalogService`，写入订单数据；映射为 inferred。

#### UCG-002-UC002：支付订单

- 关联 SR 用例/API：`UCG-002-UC002-PAYMENT-PAY-01` / `PAYMENT-PAY-01` / `PaymentAdapter`
- SR 接口：`POST /payment/v1/payments`；请求：`orderId, amount, paymentMethod, callbackUrl`；返回：`paymentId, paymentStatus`；错误：`PAYMENT_INVALID, PAYMENT_TIMEOUT, PAYMENT_FAILED`
- AR 调用：`createPayment` → `PaymentAdapter` → 外部 `PaymentService`，接收支付结果回调；映射为 inferred。

#### UCG-002-UC003：查看订单详情

- 关联 SR 用例/API：`UCG-002-UC003-API-O-IF2` / `API-O-IF2` / `OrderService`
- SR 接口：`GET /api/v1/orders/{orderId}`；请求：`orderId, Authorization`；返回：`orderId, items[], paymentStatus, shipmentStatus`；错误：`ORDER_NOT_FOUND, FORBIDDEN`
- AR 调用：`getOrderDetail` → `OrderService` → 查询订单数据；映射为 inferred。

#### UCG-003-UC001：商家发货

- 关联 SR 用例/API：`UCG-003-UC001-API-L-IF1` / `API-L-IF1` / `LogisticsServiceAdapter`
- SR 接口：`POST /api/v1/orders/{orderId}/shipments`；请求：`orderId, carrier, trackingNo`；返回：`shipmentId, shipmentStatus`；错误：`ORDER_STATE_INVALID, LOGISTICS_SERVICE_UNAVAILABLE`
- AR 调用：`createShipment` → `OrderService`，再调用外部 `LogisticsService`；映射为 inferred。

#### UCG-003-UC002：更新物流信息

- 关联 SR 用例/API：`UCG-003-UC002-LOGI-EVT-01` / `LOGI-EVT-01` / `LogisticsServiceAdapter`
- SR 接口：`POST /api/v1/logistics/events`；请求：`trackingNo, status, eventTime`；返回：`accepted, eventId`；错误：`INVALID_EVENT, DUPLICATE_EVENT`
- AR 调用：`receiveLogisticsEvent` → `LogisticsServiceAdapter` → 更新订单/物流数据；映射为 inferred。

#### UCG-003-UC003：查询物流信息

- 关联 SR 用例/API：`UCG-003-UC003-API-L-IF2` / `API-L-IF2` / `LogisticsServiceAdapter`
- SR 接口：`GET /api/v1/orders/{orderId}/logistics`；请求：`orderId`；返回：`shipmentStatus, trackingEvents[]`；错误：`ORDER_NOT_FOUND, LOGISTICS_SERVICE_TIMEOUT`
- AR 调用：`getOrderLogistics` → `LogisticsServiceAdapter` → 外部 `LogisticsService`；映射为 inferred。

#### UCG-003-UC004：申请退款

- 关联 SR 用例/API：`UCG-003-UC004-API-R-IF1` / `API-R-IF1` / `RefundService`
- SR 接口：`POST /api/v1/orders/{orderId}/refunds`；请求：`orderId, reason, amount`；返回：`refundId, refundStatus`；错误：`REFUND_NOT_ALLOWED, PAYMENT_SERVICE_UNAVAILABLE`
- AR 调用：`createRefund` → `RefundService` → 外部 `PaymentService`；映射为 inferred。

#### UCG-004-UC001：创建商品

- 关联 SR 用例/API：`UCG-004-UC001-API-M-IF1` / `API-M-IF1` / `MerchantProductService`
- SR 接口：`POST /api/v1/merchant/products`；请求：`name, categoryId, description, imageUrls[]`；返回：`productId, status`；错误：`INVALID_PRODUCT, CATEGORY_NOT_FOUND`
- AR 调用：`createMerchantProduct` → `MerchantProductService` → 写入商品数据；映射为 inferred。

#### UCG-004-UC002：填写商品信息

- 关联 SR 用例/API：`UCG-004-UC002-API-M-IF2` / `API-M-IF2` / `MerchantProductService`
- SR 接口：`PUT /api/v1/merchant/products/{productId}`；请求：`productId, name, description, categoryId, imageUrls[], version`；返回：`productId, status, version`；错误：`PRODUCT_NOT_FOUND, CATEGORY_NOT_FOUND, VERSION_CONFLICT`
- AR 调用：`updateMerchantProduct` → `MerchantProductService`，调用 `validateCategory` → `CategoryService`；映射为 inferred。

#### UCG-004-UC003：设置库存与价格

- 关联 SR 用例/API：`UCG-004-UC003-API-M-IF3` / `API-M-IF3` / `MerchantProductService`
- SR 接口：`PUT /api/v1/merchant/products/{productId}/skus`；请求：`productId, skus[], version`；返回：`productId, skus[], version`；错误：`SKU_INVALID, PRICE_INVALID, VERSION_CONFLICT`
- AR 调用：`updateSkuInventoryAndPrice` → `MerchantProductService` → 写入 SKU/库存/价格数据；映射为 inferred。

#### UCG-004-UC004：发布商品

- 关联 SR 用例/API：`UCG-004-UC004-API-M-IF4` / `API-M-IF4` / `MerchantProductService`
- SR 接口：`POST /api/v1/merchant/products/{productId}/publish`；请求：`productId, version, publishAt`；返回：`productId, status, publishedAt, catalogSyncStatus`；错误：`PRODUCT_INCOMPLETE, CATEGORY_RULE_VIOLATION, CATALOG_SYNC_FAILED`
- AR 调用：`publishMerchantProduct` → `MerchantProductService`，调用 `refreshCatalog` → `ProductCatalogService`；映射为 inferred。

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
