# 浏览商品设计

B1 顾客调用 GET /api/v1/products 浏览商品（BROWSE-GET）。
B2 商城校验 B1 的查询参数 page、pageSize、keyword、minPrice 及 Category.category_id 格式。
B3 商城调用 POST /catalog/v1/products/search 查询在售商品（CATALOG-SEARCH）。
B4 商品目录服务查询 Product 的 status 和 product_id。
B5 商品目录服务向商城返回商品列表。
B6 商城向顾客返回浏览结果。

page 为整数且不小于 1。pageSize 为整数且在 1 至 100 之间。
keyword 为可选字符串。minPrice 为可选数值且不小于 0。
categoryId 对应 Category.category_id，两处声明均指商城 B2 的同一次分类编号格式检查。
入口允许匿名访问。分页容量大于 100 时拒绝查询并返回 PAGE_SIZE_OUT_OF_RANGE。
目录请求的 status 必须等于 ON_SALE。Product.status 限定为 ON_SALE 或 OFF_SALE。
目录服务不可用时返回 CATALOG_UNAVAILABLE。
筛选无结果时展示空列表。
