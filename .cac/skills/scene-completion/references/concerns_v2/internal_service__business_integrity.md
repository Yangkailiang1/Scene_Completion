# internal_service.business_integrity — 业务完整性

## 定义
配置缺失或引用对象不完整

## 判断提示
策略引用的资源不存在或配置不完整。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
