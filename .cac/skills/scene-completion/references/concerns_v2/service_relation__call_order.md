# service_relation.call_order — 调用顺序

## 定义
前置操作未完成就执行后续操作

## 判断提示
资源尚未创建成功就执行发布配置。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
