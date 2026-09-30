# internal_service.compute.idempotency — 幂等性

## 定义
重复计算或重复提交造成错误副作用

## 判断提示
重试导致重复扣款或重复发布。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
