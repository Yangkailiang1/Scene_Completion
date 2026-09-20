# internal_service.availability — 服务可用性

## 定义
内部处理失败或超时

## 判断提示
处理超过规定时间返回超时错误。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
