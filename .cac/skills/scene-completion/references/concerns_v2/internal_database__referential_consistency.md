# internal_database.referential_consistency — 关联一致性

## 定义
级联删除失效或子对象残留

## 判断提示
删除父对象后子对象没有同步删除。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
