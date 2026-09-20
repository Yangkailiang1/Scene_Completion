# internal_database.persistence — 持久化能力

## 定义
写入失败或事务回滚

## 判断提示
插入记录报错但部分写入。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
