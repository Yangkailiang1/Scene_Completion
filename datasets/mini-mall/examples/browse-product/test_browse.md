# 浏览商品测试逆向原始证据

访问 GET /api/v1/products，pageSize=1 与 pageSize=100 均成功。
访问 GET /api/v1/products，pageSize=0，拒绝查询并返回 PAGE_SIZE_OUT_OF_RANGE。
访问 GET /api/v1/products，pageSize=101，拒绝查询并返回 PAGE_SIZE_OUT_OF_RANGE。
访问 GET /api/v1/products，keyword 超过 32 个字符时被校验拒绝并返回 KEYWORD_TOO_LONG。
