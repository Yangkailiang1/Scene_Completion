# api.data.legality — 数据合法性

## 定义
包含非法字符、不允许字段或非法取值

## 判断提示
传入未定义类型或控制字符。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
