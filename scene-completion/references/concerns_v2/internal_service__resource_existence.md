# internal_service.resource_existence — 资源存在性

## 定义
访问不存在资源

## 判断提示
修改不存在资源 ID 返回 404。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
