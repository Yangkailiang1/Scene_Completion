# internal_service.compute.state_constraint — 状态约束

## 定义
当前业务状态不允许计算

## 判断提示
未完成初始化就执行结算。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
