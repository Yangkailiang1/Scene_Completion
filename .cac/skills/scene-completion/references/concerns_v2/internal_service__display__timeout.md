# internal_service.display.timeout — 超时关注点

## 定义
展示等待超过要求，影响后续流程或交互

## 判断提示
等待结果导致用户下一步无法继续。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
