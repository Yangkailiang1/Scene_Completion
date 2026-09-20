# service_relation.idempotency — 幂等性

## 定义
重复请求导致重复执行

## 判断提示
发布请求重试两次产生两次发布操作。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
