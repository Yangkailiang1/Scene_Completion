# internal_service.display.output_consistency — 输出一致性

## 定义
展示结果与当前内部状态不一致

## 判断提示
缓存中的展示状态已过期。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
