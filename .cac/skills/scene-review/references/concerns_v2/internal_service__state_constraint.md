# internal_service.state_constraint — 状态约束

## 定义
当前状态不允许执行操作

## 判断提示
已发布实例不能直接删除。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
