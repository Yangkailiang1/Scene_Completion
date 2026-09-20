# internal_service.compute.parameter_validity — 参数有效性

## 定义
计算参数缺失、非法或类型不匹配

## 判断提示
计算请求缺少必要输入。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
