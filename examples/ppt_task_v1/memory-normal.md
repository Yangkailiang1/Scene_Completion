# SC002-UC002 查询记忆库列表：固定正向示例
开发者是人类外部Actor，通过开发者UI/前端向WiseCloudMemoryPlatformService查询记忆库列表。
接口API-M-IF2：/ms/v1/memory-instances/{memoryInstanceID}/mem-repos，HTTP方法待确认。
请求头x-wisecloud-service-id必填；已提供值的其他约束待确认。
路径参数memoryInstanceID必填；已提供值的其他约束待确认。
查询参数memoryType可选；枚举PROFILE/SEMANTIC。
查询参数page可选，整数，默认1，page≥1。
查询参数pageSize可选，整数，默认20，范围1—100。
Gaussdb4MySQL是外部依赖，保留物理资源与逻辑SR资源服务映射，不等同API-M-IF2。
调用者身份必须通过认证。
只允许有权限的开发者查询。
指定记忆实例必须存在。
返回符合查询条件的正确列表。
只返回调用者可见的记忆库。
