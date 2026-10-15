# 创建商品测试 spec 示例

与 test_spec.example.xlsx 的记录相同。步骤依据现有测试描述整理，保留原测试编号、需求关联和类型。

### TEST-AR07-UC001-N01：创建商品草稿
- 前提条件：商家登录且具备商品管理资格
- 测试步骤：1. 以具备商品管理资格的商家登录。<br>2. 提交商品名称、类目、描述和图片。
- 预期结果：返回 productId 和草稿状态
- 对应需求：AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001
- 场景类型：正常
- 原始来源：在线商城购物系统/test_spec.md；功能设计Delta_spec.md:932-965，基本流程

### TEST-AR07-UC001-A01：商家资质失效
- 前提条件：商家已登录
- 测试步骤：1. 使用已登录但经营资质已失效的商家。<br>2. 提交商品创建请求。
- 预期结果：HTTP 403，MERCHANT_NOT_QUALIFIED
- 对应需求：AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001
- 场景类型：异常
- 原始来源：在线商城购物系统/test_spec.md；功能设计Delta_spec.md:966-971，A1

### TEST-AR07-UC001-A02：商家无商品管理权限
- 前提条件：商家已登录
- 测试步骤：1. 使用已登录但无商品管理权限的商家。<br>2. 提交商品创建请求。
- 预期结果：HTTP 403，PERMISSION_DENIED
- 对应需求：AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001
- 场景类型：异常
- 原始来源：在线商城购物系统/test_spec.md；功能设计Delta_spec.md:966-971，A2

### TEST-AR07-UC001-O01：商品创建幂等重放
- 前提条件：同一幂等键已创建草稿
- 测试步骤：1. 使用已创建草稿的同一幂等键。<br>2. 重复提交商品创建请求。
- 预期结果：返回已有商品草稿，不重复创建
- 对应需求：AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001
- 场景类型：异常
- 原始来源：在线商城购物系统/test_spec.md；功能设计Delta_spec.md:966-971，A3

### TEST-AR07-UC001-A03：商家商品服务不可用
- 前提条件：商品创建请求合法
- 测试步骤：1. 保持商品创建请求合法。<br>2. 在 MerchantProductService 不可用时提交创建请求。
- 预期结果：HTTP 503，MERCHANT_SERVICE_UNAVAILABLE
- 对应需求：AR-07/createMerchantProduct；API-M-IF1；UCG-004-UC001
- 场景类型：异常
- 原始来源：在线商城购物系统/test_spec.md；功能设计Delta_spec.md:966-971，A4
