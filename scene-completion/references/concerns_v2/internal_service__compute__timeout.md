# internal_service.compute.timeout — 超时关注点

## 定义
计算延时影响业务后续行为

## 判断提示
计算未完成导致审批无法继续。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
