# external_llm.availability — 外部模型可用性

## 定义
模型服务不可用、连接失败或认证失败

## 判断提示
调用 LLM 时网络超时或服务不可用。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
