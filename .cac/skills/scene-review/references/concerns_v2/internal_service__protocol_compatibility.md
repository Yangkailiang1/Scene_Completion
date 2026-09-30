# internal_service.protocol_compatibility — 协议兼容性

## 定义
协议、字段格式或版本不一致

## 判断提示
调用方使用 HTTP 而服务只接受 HTTPS。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
