# service_relation.cross_service_consistency — 跨服务数据一致性

## 定义
一侧成功、一侧失败或版本不一致

## 判断提示
修改成功但下游配置仍为旧版本。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
