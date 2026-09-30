# external_service.identity — 调用方身份

## 定义
调用方身份不明或身份过期

## 判断提示
外部服务携带过期身份调用本系统。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
