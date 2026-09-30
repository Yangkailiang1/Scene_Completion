# external_llm.access_permission — 访问权限

## 定义
外部模型调用本系统时无权限

## 判断提示
外部 LLM 调用受保护接口但没有授权。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
