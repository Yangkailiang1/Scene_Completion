# Mini商城功能设计规格说明

本文件为合成设计，版本mini-mall-5-v1；明确声明的边界与返回用于验证输入、输出和业务规则。

## 架构与实现范围
- MiniMallPlatform是对外入口及SR调用方；ProductAdminService是内部服务及SR接口实现方。
- CatalogDatabaseService是外部数据库逻辑资源服务，负责product_record表的原子读写；不是HTTP接口，不补造其URL。
- AR-MINI-001实现说明：ProductAdminService部署为一个内部软件单元；以ProductRepository模块调用外部CatalogDatabaseService；表product_record持久化Product字段。
- AR-MINI-PLATFORM实现说明：MiniMallPlatform为对外入口软件单元，实现RR接口并委派SR内部接口；不直接调用数据库。
- 请求与返回是不同方向；所有本地校验和数据组装均为action，不构造自调用交互。
- RR对外/v1接口与SR内部/ms/v1接口是两次独立调用，分别声明约束，不因同名字段自动上移约束。

- AR-MINI-001实现接口：ProductAdminService.createProduct对应API-SR-01 POST /ms/v1/products，操作Product并调用CatalogDatabaseService.createProduct。
- AR-MINI-001实现接口：ProductAdminService.listProducts对应API-SR-02 GET /ms/v1/products，操作Product并调用CatalogDatabaseService.listProducts。
- AR-MINI-001实现接口：ProductAdminService.updateProduct对应API-SR-03 PUT /ms/v1/products/{productId}，操作Product并调用CatalogDatabaseService.compareAndUpdateProduct。
- AR-MINI-001实现接口：ProductAdminService.deleteProduct对应API-SR-04 DELETE /ms/v1/products/{productId}，操作Product并调用CatalogDatabaseService.compareAndDeleteProduct。
- AR-MINI-001实现接口：ProductAdminService.publishProduct对应API-SR-05 POST /ms/v1/products/{productId}/publish，操作Product并调用CatalogDatabaseService.compareAndPublishProduct。
## 通用SR约束
- 只允许x-service-id=mini-platform的已认证调用方；禁止使用其他service-id访问该服务数据。
- x-merchant-id只来自已认证上下文；所有数据库读写均按此merchantId隔离，跨商家访问返回403 RESOURCE_ACCESS_DENIED。
- U/D/发布接口的幂等键按商家、具体接口及键隔离；同键同内容重放首次成功结果，同键不同内容返回409 IDEMPOTENCY_CONFLICT。
- 查询是幂等读取：在数据、筛选及分页条件不变时重复查询应得到相同结果且不产生变更。
- 数据库不可达只归外部CatalogDatabaseService可用性；不把内部服务统一生成不可用检查。
- 未给出超时阈值，不额外生成具体超时要求。

## 业务实体属性及存储约束
- Product.productId（持久化实体属性，不是通用请求体定义）：类型 string；存储必有；格式 ^P[0-9]{4}$；唯一标识，由数据库服务生成；创建请求不传此字段
- Product.merchantId（持久化实体属性，不是通用请求体定义）：类型 string；存储必有；格式 ^M[0-9]{3}$；商品仅可由同一merchantId的商家访问
- Product.name（持久化实体属性，不是通用请求体定义）：类型 string；存储必有；长度 1-50；同一merchantId下name不可重名；不同商家可重名
- Product.productType（持久化实体属性，不是通用请求体定义）：类型 string；存储必有；枚举 {STANDARD|SERVICE}；创建后不可修改；更新时若提供相同值则允许，提供不同值则拒绝
- Product.price（持久化实体属性，不是通用请求体定义）：类型 number；存储必有；0 <= price <= 10000；productType为SERVICE时price必须大于等于1
- Product.status（持久化实体属性，不是通用请求体定义）：类型 string；存储必有；枚举 {DRAFT|PUBLISHED}；创建后为DRAFT；仅UC-005可由DRAFT改为PUBLISHED；仅DRAFT可更新或删除
- Product.version（持久化实体属性，不是通用请求体定义）：类型 integer；存储必有；version >= 1；创建后为1；有效更新或发布成功增加1；重复幂等请求不增加
- product_record字段与同名Product属性一一对应；存储类型与Product类型相同。
- Product.name按(merchantId,name)组合唯一；Product.productType创建后不可变。
- 错误响应统一为error对象，其中error.code、error.message都是必填string；错误响应字段不能混入成功响应。

## UC-001-API-SR-01 创建商品
- 对应RR用例：UC-001；业务实体Product；CRUD=C。
- SR接口：API-SR-01 POST /ms/v1/products；source_layer=SR；所属ProductAdminService。
- RR入口：API-RR-01 POST /v1/products；所属MiniMallPlatform；它与SR接口是展开关系，不能合并。
### 请求参数
- header.x-service-id（必填；类型: string；枚举 {mini-platform}；只允许MiniMallPlatform身份调用；不得以其他service-id访问本服务的数据）
- header.x-merchant-id（必填；类型: string；格式 ^M[0-9]{3}$；来自已认证商家上下文，不可由请求正文覆盖）
- body.name（必填；类型: string；长度 1-50）
- body.productType（必填；类型: string；枚举 {STANDARD|SERVICE}）
- body.price（必填；类型: number；0 <= price <= 10000）
### 主成功场景
S1. MiniMallPlatform向ProductAdminService发送POST /ms/v1/products（API-SR-01），按字段表传递必填及实际提供的可选参数：header.x-service-id、header.x-merchant-id、body.name、body.productType、body.price。
S2. ProductAdminService在本地校验调用身份、数据类型及明示约束；涉及幂等键时先检查成功记录，相同内容重放成功结果，不重复请求数据库。
S3. ProductAdminService调用外部CatalogDatabaseService的createProduct操作，传入当前merchantId及本次业务所需字段。
S4. CatalogDatabaseService执行原子操作：创建草稿商品；数据库事务实施同商家名称唯一性，并检查productType为SERVICE时price必须大于等于1，生成productId，status=DRAFT、version=1，并向ProductAdminService返回结果。
S5. ProductAdminService本地构造接口规定的成功响应。
S6. ProductAdminService向MiniMallPlatform返回 HTTP 201，数据为response.productId、response.merchantId、response.name、response.productType、response.price、response.status、response.version。
S7. MiniMallPlatform本地校验该成功响应的字段、类型和约束后，向商家返回RR成功结果；本地校验不构造额外SR网络交互。
### 成功响应
- 成功状态码：HTTP 201。
- response.productId（必填；类型: string；格式 ^P[0-9]{4}$；唯一标识，由数据库服务生成；创建请求不传此字段）
- response.merchantId（必填；类型: string；格式 ^M[0-9]{3}$；商品仅可由同一merchantId的商家访问）
- response.name（必填；类型: string；长度 1-50；同一merchantId下name不可重名；不同商家可重名）
- response.productType（必填；类型: string；枚举 {STANDARD|SERVICE}；创建后不可修改；更新时若提供相同值则允许，提供不同值则拒绝）
- response.price（必填；类型: number；0 <= price <= 10000；productType为SERVICE时price必须大于等于1）
- response.status（必填；类型: string；枚举 {DRAFT|PUBLISHED}；创建后为DRAFT；仅UC-005可由DRAFT改为PUBLISHED；仅DRAFT可更新或删除）
- response.version（必填；类型: integer；version >= 1；创建后为1；有效更新或发布成功增加1；重复幂等请求不增加）
- 创建成功时status=DRAFT、version=1。
### 正常业务约束与校验责任
- S2仅执行本地输入、调用身份及幂等键校验；S4由数据库原子执行本例业务状态、存在性、归属、唯一性和版本约束；S7由平台验证成功返回契约。
- 输入、输出、数据库约束分别归属各自的实际交互，不将下游数据约束上移到RR对外接口。
### 已有异常场景
- E-NAME_MISSING：在S2，body.name未提供；返回 HTTP 400，error.code=INVALID_REQUEST；不执行或不重复本次业务变更。
- E-DUPLICATE_NAME：在S4，当前商家已有同名商品；返回 HTTP 409，error.code=NAME_CONFLICT；不执行或不重复本次业务变更。
### 成功备选
- 另一merchantId下已有同名商品，但当前merchantId下无同名商品；返回 HTTP 201，创建当前商家的新商品；两个商家数据保持隔离。

## UC-002-API-SR-02 查询商品列表
- 对应RR用例：UC-002；业务实体Product；CRUD=R。
- SR接口：API-SR-02 GET /ms/v1/products；source_layer=SR；所属ProductAdminService。
- RR入口：API-RR-02 GET /v1/products；所属MiniMallPlatform；它与SR接口是展开关系，不能合并。
### 请求参数
- header.x-service-id（必填；类型: string；枚举 {mini-platform}；只允许MiniMallPlatform身份调用；不得以其他service-id访问本服务的数据）
- header.x-merchant-id（必填；类型: string；格式 ^M[0-9]{3}$；来自已认证商家上下文，不可由请求正文覆盖）
- query.page（可选；类型: integer；默认1；page >= 1）
- query.pageSize（可选；类型: integer；默认20；1 <= pageSize <= 100）
- query.keyword（可选；类型: string；长度 0-30）
- query.productType（可选；类型: string；枚举 {STANDARD|SERVICE}）
### 主成功场景
S1. MiniMallPlatform向ProductAdminService发送GET /ms/v1/products（API-SR-02），按字段表传递必填及实际提供的可选参数：header.x-service-id、header.x-merchant-id、query.page、query.pageSize、query.keyword、query.productType。
S2. ProductAdminService在本地校验调用身份、数据类型及明示约束；涉及幂等键时先检查成功记录，相同内容重放成功结果，不重复请求数据库。
S3. ProductAdminService调用外部CatalogDatabaseService的listProducts操作，传入当前merchantId及本次业务所需字段。
S4. CatalogDatabaseService执行原子操作：按当前merchantId过滤商品，再按productId升序、过滤条件及分页查询；不修改商品；无匹配项返回空列表，并向ProductAdminService返回结果。
S5. ProductAdminService本地构造接口规定的成功响应。
S6. ProductAdminService向MiniMallPlatform返回 HTTP 200，数据为response.items、response.total、response.page、response.pageSize。
S7. MiniMallPlatform本地校验该成功响应的字段、类型和约束后，向商家返回RR成功结果；本地校验不构造额外SR网络交互。
### 成功响应
- 成功状态码：HTTP 200。
- response.items（必填；类型: array；每项为Product；仅包含当前merchantId商品；数量不超过pageSize）
- response.total（必填；类型: integer；total >= 0）
- response.page（必填；类型: integer；page >= 1）
- response.pageSize（必填；类型: integer；1 <= pageSize <= 100）
### 正常业务约束与校验责任
- S2仅执行本地输入、调用身份及幂等键校验；S4由数据库原子执行本例业务状态、存在性、归属、唯一性和版本约束；S7由平台验证成功返回契约。
- 输入、输出、数据库约束分别归属各自的实际交互，不将下游数据约束上移到RR对外接口。
### 已有异常场景
- E-DB_UNAVAILABLE：在S3，CatalogDatabaseService连接不可达；返回 HTTP 503，error.code=DATABASE_UNAVAILABLE；不执行或不重复本次业务变更。
- E-SIZE_HIGH：在S2，query.pageSize=101，超过100；返回 HTTP 400，error.code=INVALID_REQUEST；不执行或不重复本次业务变更。
### 成功备选
- 查询无匹配记录；返回 HTTP 200，items=[]、total=0，page和pageSize仍为有效值。

## UC-003-API-SR-03 更新商品
- 对应RR用例：UC-003；业务实体Product；CRUD=U。
- SR接口：API-SR-03 PUT /ms/v1/products/{productId}；source_layer=SR；所属ProductAdminService。
- RR入口：API-RR-03 PUT /v1/products/{productId}；所属MiniMallPlatform；它与SR接口是展开关系，不能合并。
### 请求参数
- header.x-service-id（必填；类型: string；枚举 {mini-platform}；只允许MiniMallPlatform身份调用；不得以其他service-id访问本服务的数据）
- header.x-merchant-id（必填；类型: string；格式 ^M[0-9]{3}$；来自已认证商家上下文，不可由请求正文覆盖）
- header.Idempotency-Key（必填；类型: string；长度 8-36；格式 ^[A-Za-z0-9_-]{8,36}$；同一商家、接口、幂等键和相同请求内容重复提交时复用首次成功结果，不重复写入；同键不同内容拒绝）
- path.productId（必填；类型: string；格式 ^P[0-9]{4}$）
- body.version（必填；类型: integer；version >= 1）
- body.name（必填；类型: string；长度 1-50）
- body.price（必填；类型: number；0 <= price <= 10000）
- body.productType（可选；类型: string；枚举 {STANDARD|SERVICE}；若提供必须等于原productType，不得改变）
### 主成功场景
S1. MiniMallPlatform向ProductAdminService发送PUT /ms/v1/products/{productId}（API-SR-03），按字段表传递必填及实际提供的可选参数：header.x-service-id、header.x-merchant-id、header.Idempotency-Key、path.productId、body.version、body.name、body.price、body.productType。
S2. ProductAdminService在本地校验调用身份、数据类型及明示约束；涉及幂等键时先检查成功记录，相同内容重放成功结果，不重复请求数据库。
S3. ProductAdminService调用外部CatalogDatabaseService的compareAndUpdateProduct操作，传入当前merchantId及本次业务所需字段。
S4. CatalogDatabaseService执行原子操作：数据库原子核对商品归属、存在性、DRAFT状态、version、名称唯一性和不可变属性，成功更新name/price并增加version，并向ProductAdminService返回结果。
S5. ProductAdminService本地构造接口规定的成功响应。
S6. ProductAdminService向MiniMallPlatform返回 HTTP 200，数据为response.productId、response.merchantId、response.name、response.productType、response.price、response.status、response.version。
S7. MiniMallPlatform本地校验该成功响应的字段、类型和约束后，向商家返回RR成功结果；本地校验不构造额外SR网络交互。
### 成功响应
- 成功状态码：HTTP 200。
- response.productId（必填；类型: string；格式 ^P[0-9]{4}$；唯一标识，由数据库服务生成；创建请求不传此字段）
- response.merchantId（必填；类型: string；格式 ^M[0-9]{3}$；商品仅可由同一merchantId的商家访问）
- response.name（必填；类型: string；长度 1-50；同一merchantId下name不可重名；不同商家可重名）
- response.productType（必填；类型: string；枚举 {STANDARD|SERVICE}；创建后不可修改；更新时若提供相同值则允许，提供不同值则拒绝）
- response.price（必填；类型: number；0 <= price <= 10000；productType为SERVICE时price必须大于等于1）
- response.status（必填；类型: string；枚举 {DRAFT|PUBLISHED}；创建后为DRAFT；仅UC-005可由DRAFT改为PUBLISHED；仅DRAFT可更新或删除）
- response.version（必填；类型: integer；version >= 1；创建后为1；有效更新或发布成功增加1；重复幂等请求不增加）
### 正常业务约束与校验责任
- S2仅执行本地输入、调用身份及幂等键校验；S4由数据库原子执行本例业务状态、存在性、归属、唯一性和版本约束；S7由平台验证成功返回契约。
- 输入、输出、数据库约束分别归属各自的实际交互，不将下游数据约束上移到RR对外接口。
### 已有异常场景
- E-VERSION_CONFLICT：在S4，请求version与商品当前version不一致；返回 HTTP 409，error.code=VERSION_CONFLICT；不执行或不重复本次业务变更。
- E-IMMUTABLE_TYPE：在S4，请求productType与原商品productType不同；返回 HTTP 409，error.code=IMMUTABLE_ATTRIBUTE；不执行或不重复本次业务变更。
### 成功备选
- 同一商家和接口的相同幂等键、相同请求内容已有成功记录；返回首次成功的HTTP 200和结果；不再次写入或增加version。

## UC-004-API-SR-04 删除商品
- 对应RR用例：UC-004；业务实体Product；CRUD=D。
- SR接口：API-SR-04 DELETE /ms/v1/products/{productId}；source_layer=SR；所属ProductAdminService。
- RR入口：API-RR-04 DELETE /v1/products/{productId}；所属MiniMallPlatform；它与SR接口是展开关系，不能合并。
### 请求参数
- header.x-service-id（必填；类型: string；枚举 {mini-platform}；只允许MiniMallPlatform身份调用；不得以其他service-id访问本服务的数据）
- header.x-merchant-id（必填；类型: string；格式 ^M[0-9]{3}$；来自已认证商家上下文，不可由请求正文覆盖）
- header.Idempotency-Key（必填；类型: string；长度 8-36；格式 ^[A-Za-z0-9_-]{8,36}$；同一商家、接口、幂等键和相同请求内容重复提交时复用首次成功结果，不重复写入；同键不同内容拒绝）
- path.productId（必填；类型: string；格式 ^P[0-9]{4}$）
- body.version（必填；类型: integer；version >= 1）
### 主成功场景
S1. MiniMallPlatform向ProductAdminService发送DELETE /ms/v1/products/{productId}（API-SR-04），按字段表传递必填及实际提供的可选参数：header.x-service-id、header.x-merchant-id、header.Idempotency-Key、path.productId、body.version。
S2. ProductAdminService在本地校验调用身份、数据类型及明示约束；涉及幂等键时先检查成功记录，相同内容重放成功结果，不重复请求数据库。
S3. ProductAdminService调用外部CatalogDatabaseService的compareAndDeleteProduct操作，传入当前merchantId及本次业务所需字段。
S4. CatalogDatabaseService执行原子操作：数据库原子核对商品归属、存在性、DRAFT状态和version后删除商品；PUBLISHED商品不允许删除，并向ProductAdminService返回结果。
S5. ProductAdminService本地构造接口规定的成功响应。
S6. ProductAdminService向MiniMallPlatform返回 HTTP 200，数据为response.productId、response.deleted。
S7. MiniMallPlatform本地校验该成功响应的字段、类型和约束后，向商家返回RR成功结果；本地校验不构造额外SR网络交互。
### 成功响应
- 成功状态码：HTTP 200。
- response.productId（必填；类型: string；格式 ^P[0-9]{4}$）
- response.deleted（必填；类型: boolean；成功删除时deleted=true）
### 正常业务约束与校验责任
- S2仅执行本地输入、调用身份及幂等键校验；S4由数据库原子执行本例业务状态、存在性、归属、唯一性和版本约束；S7由平台验证成功返回契约。
- 输入、输出、数据库约束分别归属各自的实际交互，不将下游数据约束上移到RR对外接口。
### 已有异常场景
- E-NOT_FOUND：在S4，指定productId的商品不存在；返回 HTTP 404，error.code=PRODUCT_NOT_FOUND；不执行或不重复本次业务变更。
- E-STATE：在S4，商品status=PUBLISHED，不允许本次更新或删除；返回 HTTP 409，error.code=STATE_CONFLICT；不执行或不重复本次业务变更。
### 成功备选
- 同一商家和接口的相同幂等键、相同请求内容已有成功记录；返回首次成功的HTTP 200和结果；不再次写入或增加version。

## UC-005-API-SR-05 发布商品
- 对应RR用例：UC-005；业务实体Product；CRUD=U,PUBLISH。
- SR接口：API-SR-05 POST /ms/v1/products/{productId}/publish；source_layer=SR；所属ProductAdminService。
- RR入口：API-RR-05 POST /v1/products/{productId}/publish；所属MiniMallPlatform；它与SR接口是展开关系，不能合并。
### 请求参数
- header.x-service-id（必填；类型: string；枚举 {mini-platform}；只允许MiniMallPlatform身份调用；不得以其他service-id访问本服务的数据）
- header.x-merchant-id（必填；类型: string；格式 ^M[0-9]{3}$；来自已认证商家上下文，不可由请求正文覆盖）
- header.Idempotency-Key（必填；类型: string；长度 8-36；格式 ^[A-Za-z0-9_-]{8,36}$；同一商家、接口、幂等键和相同请求内容重复提交时复用首次成功结果，不重复写入；同键不同内容拒绝）
- path.productId（必填；类型: string；格式 ^P[0-9]{4}$）
- body.version（必填；类型: integer；version >= 1）
### 主成功场景
S1. MiniMallPlatform向ProductAdminService发送POST /ms/v1/products/{productId}/publish（API-SR-05），按字段表传递必填及实际提供的可选参数：header.x-service-id、header.x-merchant-id、header.Idempotency-Key、path.productId、body.version。
S2. ProductAdminService在本地校验调用身份、数据类型及明示约束；涉及幂等键时先检查成功记录，相同内容重放成功结果，不重复请求数据库。
S3. ProductAdminService调用外部CatalogDatabaseService的compareAndPublishProduct操作，传入当前merchantId及本次业务所需字段。
S4. CatalogDatabaseService执行原子操作：数据库原子核对商品归属、存在性、DRAFT状态、version、name非空且price>0，成功将status设为PUBLISHED并增加version，并向ProductAdminService返回结果。
S5. ProductAdminService本地构造接口规定的成功响应。
S6. ProductAdminService向MiniMallPlatform返回 HTTP 200，数据为response.productId、response.merchantId、response.name、response.productType、response.price、response.status、response.version。
S7. MiniMallPlatform本地校验该成功响应的字段、类型和约束后，向商家返回RR成功结果；本地校验不构造额外SR网络交互。
### 成功响应
- 成功状态码：HTTP 200。
- response.productId（必填；类型: string；格式 ^P[0-9]{4}$；唯一标识，由数据库服务生成；创建请求不传此字段）
- response.merchantId（必填；类型: string；格式 ^M[0-9]{3}$；商品仅可由同一merchantId的商家访问）
- response.name（必填；类型: string；长度 1-50；同一merchantId下name不可重名；不同商家可重名）
- response.productType（必填；类型: string；枚举 {STANDARD|SERVICE}；创建后不可修改；更新时若提供相同值则允许，提供不同值则拒绝）
- response.price（必填；类型: number；0 <= price <= 10000；productType为SERVICE时price必须大于等于1）
- response.status（必填；类型: string；枚举 {DRAFT|PUBLISHED}；创建后为DRAFT；仅UC-005可由DRAFT改为PUBLISHED；仅DRAFT可更新或删除）
- response.version（必填；类型: integer；version >= 1；创建后为1；有效更新或发布成功增加1；重复幂等请求不增加）
- 发布成功时status=PUBLISHED、version比调用前增加1。
### 正常业务约束与校验责任
- S2仅执行本地输入、调用身份及幂等键校验；S4由数据库原子执行本例业务状态、存在性、归属、唯一性和版本约束；S7由平台验证成功返回契约。
- 输入、输出、数据库约束分别归属各自的实际交互，不将下游数据约束上移到RR对外接口。
### 已有异常场景
- E-VERSION_CONFLICT：在S4，请求version与商品当前version不一致；返回 HTTP 409，error.code=VERSION_CONFLICT；不执行或不重复本次业务变更。
- E-PRICE_ZERO：在S4，待发布商品price=0，不满足发布前置条件price>0；返回 HTTP 409，error.code=PUBLISH_PREREQUISITE_FAILED；不执行或不重复本次业务变更。
### 成功备选
- 同一商家和接口的相同幂等键、相同请求内容已有成功记录；返回首次成功的HTTP 200和结果；不再次写入或增加version。

