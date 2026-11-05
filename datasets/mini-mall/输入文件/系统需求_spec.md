# Mini商城系统需求规格说明

本文件为人工构造的合成测试数据，版本mini-mall-5-v1；不是生产需求。

## 系统边界与参与者
- 商家是人类外部Actor。MiniMallPlatform是被测平台的统一系统边界与对外入口。
- RR只定义商家与MiniMallPlatform的实际请求/返回；内部调用在SR定义，不能合并为同一次调用。
- 业务实体为Product（商品）。用例恰好5个，编号UC-001至UC-005。

## 全局业务规则
- 必须先成功创建同一商品，才能更新、删除或发布它。
- 若创建后price=0，必须先完成UC-003将price调整为大于0，才能执行UC-005发布。
- 查询列表在不存在匹配商品时返回正常空列表，不是异常。
- 所有商品按merchantId隔离；不同商家可以使用相同商品名。

## UC-001 创建商品
- 目标：创建草稿商品；数据库事务实施同商家名称唯一性，生成productId，status=DRAFT、version=1。
- 参与者：商家、MiniMallPlatform。
- 接口：API-RR-01 POST /v1/products；source_layer=RR。
### 请求参数
- header.Authorization（必填；类型: string；Bearer凭证必须有效且未过期；调用商家必须有当前操作权限）
- body.name（必填；类型: string；长度 1-50）
- body.productType（必填；类型: string；枚举 {STANDARD|SERVICE}）
- body.price（必填；类型: number；0 <= price <= 10000）
### 主成功场景
R1. 商家向MiniMallPlatform发送POST /v1/products（API-RR-01），按字段表传递必填及实际提供的可选参数：header.Authorization、body.name、body.productType、body.price。
R2. MiniMallPlatform确认身份和操作权限，完成创建商品；创建草稿商品；数据库事务实施同商家名称唯一性，生成productId，status=DRAFT、version=1。
R3. MiniMallPlatform向商家返回 HTTP 201，包含productId、merchantId、name、productType、price、status、version。
### 成功响应
- response.productId（必填；类型: string；格式 ^P[0-9]{4}$；唯一标识，由数据库服务生成；创建请求不传此字段）
- response.merchantId（必填；类型: string；格式 ^M[0-9]{3}$；商品仅可由同一merchantId的商家访问）
- response.name（必填；类型: string；长度 1-50；同一merchantId下name不可重名；不同商家可重名）
- response.productType（必填；类型: string；枚举 {STANDARD|SERVICE}；创建后不可修改；更新时若提供相同值则允许，提供不同值则拒绝）
- response.price（必填；类型: number；0 <= price <= 10000；productType为SERVICE时price必须大于等于1）
- response.status（必填；类型: string；枚举 {DRAFT|PUBLISHED}；创建后为DRAFT；仅UC-005可由DRAFT改为PUBLISHED；仅DRAFT可更新或删除）
- response.version（必填；类型: integer；version >= 1；创建后为1；有效更新或发布成功增加1；重复幂等请求不增加）
### 已有异常分支
- Authorization未提供或无效返回401 AUTH_REQUIRED；无当前操作权限返回403 OPERATION_FORBIDDEN。
- body.name未提供；返回 HTTP 400，error.code=INVALID_REQUEST；不执行或不重复本次业务变更。
- 当前商家已有同名商品；返回 HTTP 409，error.code=NAME_CONFLICT；不执行或不重复本次业务变更。
### 成功备选
- 另一merchantId下已有同名商品，但当前merchantId下无同名商品；返回 HTTP 201，创建当前商家的新商品；两个商家数据保持隔离。

## UC-002 查询商品列表
- 目标：按当前merchantId过滤商品，再按productId升序、过滤条件及分页查询；不修改商品；无匹配项返回空列表。
- 参与者：商家、MiniMallPlatform。
- 接口：API-RR-02 GET /v1/products；source_layer=RR。
### 请求参数
- header.Authorization（必填；类型: string；Bearer凭证必须有效且未过期；调用商家必须有当前操作权限）
- query.page（可选；类型: integer；默认1；page >= 1）
- query.pageSize（可选；类型: integer；默认20；1 <= pageSize <= 100）
- query.keyword（可选；类型: string；长度 0-30）
- query.productType（可选；类型: string；枚举 {STANDARD|SERVICE}）
### 主成功场景
R1. 商家向MiniMallPlatform发送GET /v1/products（API-RR-02），按字段表传递必填及实际提供的可选参数：header.Authorization、query.page、query.pageSize、query.keyword、query.productType。
R2. MiniMallPlatform确认身份和操作权限，完成查询商品列表；按当前merchantId过滤商品，再按productId升序、过滤条件及分页查询；不修改商品；无匹配项返回空列表。
R3. MiniMallPlatform向商家返回 HTTP 200，包含items、total、page、pageSize。
### 成功响应
- response.items（必填；类型: array；每项为Product；仅包含当前merchantId商品；数量不超过pageSize）
- response.total（必填；类型: integer；total >= 0）
- response.page（必填；类型: integer；page >= 1）
- response.pageSize（必填；类型: integer；1 <= pageSize <= 100）
### 已有异常分支
- Authorization未提供或无效返回401 AUTH_REQUIRED；无当前操作权限返回403 OPERATION_FORBIDDEN。
- CatalogDatabaseService连接不可达；返回 HTTP 503，error.code=DATABASE_UNAVAILABLE；不执行或不重复本次业务变更。
- query.pageSize=101，超过100；返回 HTTP 400，error.code=INVALID_REQUEST；不执行或不重复本次业务变更。
### 成功备选
- 查询无匹配记录；返回 HTTP 200，items=[]、total=0，page和pageSize仍为有效值。

## UC-003 更新商品
- 目标：数据库原子核对商品归属、存在性、DRAFT状态、version、名称唯一性和不可变属性，成功更新name/price并增加version。
- 参与者：商家、MiniMallPlatform。
- 接口：API-RR-03 PUT /v1/products/{productId}；source_layer=RR。
### 请求参数
- header.Authorization（必填；类型: string；Bearer凭证必须有效且未过期；调用商家必须有当前操作权限）
- header.Idempotency-Key（必填；类型: string；长度 8-36；格式 ^[A-Za-z0-9_-]{8,36}$；同一商家、接口、幂等键和相同请求内容重复提交时复用首次成功结果，不重复写入；同键不同内容拒绝）
- path.productId（必填；类型: string；格式 ^P[0-9]{4}$）
- body.version（必填；类型: integer；version >= 1）
- body.name（必填；类型: string；长度 1-50）
- body.price（必填；类型: number；0 <= price <= 10000）
- body.productType（可选；类型: string；枚举 {STANDARD|SERVICE}；若提供必须等于原productType，不得改变）
### 主成功场景
R1. 商家向MiniMallPlatform发送PUT /v1/products/{productId}（API-RR-03），按字段表传递必填及实际提供的可选参数：header.Authorization、header.Idempotency-Key、path.productId、body.version、body.name、body.price、body.productType。
R2. MiniMallPlatform确认身份和操作权限，完成更新商品；数据库原子核对商品归属、存在性、DRAFT状态、version、名称唯一性和不可变属性，成功更新name/price并增加version。
R3. MiniMallPlatform向商家返回 HTTP 200，包含productId、merchantId、name、productType、price、status、version。
### 成功响应
- response.productId（必填；类型: string；格式 ^P[0-9]{4}$；唯一标识，由数据库服务生成；创建请求不传此字段）
- response.merchantId（必填；类型: string；格式 ^M[0-9]{3}$；商品仅可由同一merchantId的商家访问）
- response.name（必填；类型: string；长度 1-50；同一merchantId下name不可重名；不同商家可重名）
- response.productType（必填；类型: string；枚举 {STANDARD|SERVICE}；创建后不可修改；更新时若提供相同值则允许，提供不同值则拒绝）
- response.price（必填；类型: number；0 <= price <= 10000；productType为SERVICE时price必须大于等于1）
- response.status（必填；类型: string；枚举 {DRAFT|PUBLISHED}；创建后为DRAFT；仅UC-005可由DRAFT改为PUBLISHED；仅DRAFT可更新或删除）
- response.version（必填；类型: integer；version >= 1；创建后为1；有效更新或发布成功增加1；重复幂等请求不增加）
### 已有异常分支
- Authorization未提供或无效返回401 AUTH_REQUIRED；无当前操作权限返回403 OPERATION_FORBIDDEN。
- 请求version与商品当前version不一致；返回 HTTP 409，error.code=VERSION_CONFLICT；不执行或不重复本次业务变更。
- 请求productType与原商品productType不同；返回 HTTP 409，error.code=IMMUTABLE_ATTRIBUTE；不执行或不重复本次业务变更。
### 成功备选
- 同一商家和接口的相同幂等键、相同请求内容已有成功记录；返回首次成功的HTTP 200和结果；不再次写入或增加version。

## UC-004 删除商品
- 目标：数据库原子核对商品归属、存在性、DRAFT状态和version后删除商品；PUBLISHED商品不允许删除。
- 参与者：商家、MiniMallPlatform。
- 接口：API-RR-04 DELETE /v1/products/{productId}；source_layer=RR。
### 请求参数
- header.Authorization（必填；类型: string；Bearer凭证必须有效且未过期；调用商家必须有当前操作权限）
- header.Idempotency-Key（必填；类型: string；长度 8-36；格式 ^[A-Za-z0-9_-]{8,36}$；同一商家、接口、幂等键和相同请求内容重复提交时复用首次成功结果，不重复写入；同键不同内容拒绝）
- path.productId（必填；类型: string；格式 ^P[0-9]{4}$）
- body.version（必填；类型: integer；version >= 1）
### 主成功场景
R1. 商家向MiniMallPlatform发送DELETE /v1/products/{productId}（API-RR-04），按字段表传递必填及实际提供的可选参数：header.Authorization、header.Idempotency-Key、path.productId、body.version。
R2. MiniMallPlatform确认身份和操作权限，完成删除商品；数据库原子核对商品归属、存在性、DRAFT状态和version后删除商品；PUBLISHED商品不允许删除。
R3. MiniMallPlatform向商家返回 HTTP 200，包含productId、deleted。
### 成功响应
- response.productId（必填；类型: string；格式 ^P[0-9]{4}$）
- response.deleted（必填；类型: boolean；成功删除时deleted=true）
### 已有异常分支
- Authorization未提供或无效返回401 AUTH_REQUIRED；无当前操作权限返回403 OPERATION_FORBIDDEN。
- 指定productId的商品不存在；返回 HTTP 404，error.code=PRODUCT_NOT_FOUND；不执行或不重复本次业务变更。
- 商品status=PUBLISHED，不允许本次更新或删除；返回 HTTP 409，error.code=STATE_CONFLICT；不执行或不重复本次业务变更。
### 成功备选
- 同一商家和接口的相同幂等键、相同请求内容已有成功记录；返回首次成功的HTTP 200和结果；不再次写入或增加version。

## UC-005 发布商品
- 目标：数据库原子核对商品归属、存在性、DRAFT状态、version、name非空且price>0，成功将status设为PUBLISHED并增加version。
- 参与者：商家、MiniMallPlatform。
- 接口：API-RR-05 POST /v1/products/{productId}/publish；source_layer=RR。
### 请求参数
- header.Authorization（必填；类型: string；Bearer凭证必须有效且未过期；调用商家必须有当前操作权限）
- header.Idempotency-Key（必填；类型: string；长度 8-36；格式 ^[A-Za-z0-9_-]{8,36}$；同一商家、接口、幂等键和相同请求内容重复提交时复用首次成功结果，不重复写入；同键不同内容拒绝）
- path.productId（必填；类型: string；格式 ^P[0-9]{4}$）
- body.version（必填；类型: integer；version >= 1）
### 主成功场景
R1. 商家向MiniMallPlatform发送POST /v1/products/{productId}/publish（API-RR-05），按字段表传递必填及实际提供的可选参数：header.Authorization、header.Idempotency-Key、path.productId、body.version。
R2. MiniMallPlatform确认身份和操作权限，完成发布商品；数据库原子核对商品归属、存在性、DRAFT状态、version、name非空且price>0，成功将status设为PUBLISHED并增加version。
R3. MiniMallPlatform向商家返回 HTTP 200，包含productId、merchantId、name、productType、price、status、version。
### 成功响应
- response.productId（必填；类型: string；格式 ^P[0-9]{4}$；唯一标识，由数据库服务生成；创建请求不传此字段）
- response.merchantId（必填；类型: string；格式 ^M[0-9]{3}$；商品仅可由同一merchantId的商家访问）
- response.name（必填；类型: string；长度 1-50；同一merchantId下name不可重名；不同商家可重名）
- response.productType（必填；类型: string；枚举 {STANDARD|SERVICE}；创建后不可修改；更新时若提供相同值则允许，提供不同值则拒绝）
- response.price（必填；类型: number；0 <= price <= 10000；productType为SERVICE时price必须大于等于1）
- response.status（必填；类型: string；枚举 {DRAFT|PUBLISHED}；创建后为DRAFT；仅UC-005可由DRAFT改为PUBLISHED；仅DRAFT可更新或删除）
- response.version（必填；类型: integer；version >= 1；创建后为1；有效更新或发布成功增加1；重复幂等请求不增加）
### 已有异常分支
- Authorization未提供或无效返回401 AUTH_REQUIRED；无当前操作权限返回403 OPERATION_FORBIDDEN。
- 请求version与商品当前version不一致；返回 HTTP 409，error.code=VERSION_CONFLICT；不执行或不重复本次业务变更。
- 待发布商品price=0，不满足发布前置条件price>0；返回 HTTP 409，error.code=PUBLISH_PREREQUISITE_FAILED；不执行或不重复本次业务变更。
### 成功备选
- 同一商家和接口的相同幂等键、相同请求内容已有成功记录；返回首次成功的HTTP 200和结果；不再次写入或增加version。

