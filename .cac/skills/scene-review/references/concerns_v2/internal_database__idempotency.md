# internal_database.idempotency — 幂等性

## 定义
重复请求导致重复操作异常

## 判断提示
连续两次删除同一条数据产生不一致。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
