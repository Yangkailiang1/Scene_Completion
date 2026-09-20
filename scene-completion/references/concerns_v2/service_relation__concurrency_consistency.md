# service_relation.concurrency_consistency — 并发一致性

## 定义
并发修改或删除产生冲突

## 判断提示
两个请求同时修改同一资源。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
