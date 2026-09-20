# internal_service.display.output_completeness — 输出完整性

## 定义
展示结果缺少必要字段或内容

## 判断提示
列表缺少必要的展示字段。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
