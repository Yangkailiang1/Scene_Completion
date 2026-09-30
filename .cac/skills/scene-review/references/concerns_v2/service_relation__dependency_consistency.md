# service_relation.dependency_consistency — 依赖一致性

## 定义
被依赖资源不存在或失效

## 判断提示
策略仍引用已删除资源。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
