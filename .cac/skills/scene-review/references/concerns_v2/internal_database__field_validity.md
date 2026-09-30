# internal_database.field_validity — 字段合法性

## 定义
类型错误、非法字符或超长

## 判断提示
age 传字符串或 name 超长。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
