# external_service.contract — 外部接口契约

## 定义
返回字段缺失、格式改变或版本不兼容

## 判断提示
外部服务响应字段结构变化导致解析失败。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
