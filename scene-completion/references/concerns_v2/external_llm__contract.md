# external_llm.contract — 外部接口契约

## 定义
LLM 输出字段、格式或版本不符合约定

## 判断提示
响应不符合约定 JSON 格式。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
