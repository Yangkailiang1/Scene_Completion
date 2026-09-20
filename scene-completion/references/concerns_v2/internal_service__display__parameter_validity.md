# internal_service.display.parameter_validity — 参数有效性

## 定义
展示服务参数不满足接口约束

## 判断提示
筛选条件缺失或类型错误。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
