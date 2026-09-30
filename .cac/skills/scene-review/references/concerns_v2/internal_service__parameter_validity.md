# internal_service.parameter_validity — 参数有效性

## 定义
参数缺失、非法字符、超长或类型不匹配

## 判断提示
创建资源时 name 缺失返回 400。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
