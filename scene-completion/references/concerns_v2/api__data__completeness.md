# api.data.completeness — 数据完整性

## 定义
必填数据缺失或请求体为空

## 判断提示
创建资源时缺少名称或外部调用没有传必填字段。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
