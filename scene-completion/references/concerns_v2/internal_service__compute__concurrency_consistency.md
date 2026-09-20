# internal_service.compute.concurrency_consistency — 并发一致性

## 定义
并发计算或更新产生冲突

## 判断提示
两个请求基于不同版本同时计算。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
