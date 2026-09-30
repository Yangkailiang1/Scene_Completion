# human.authentication — 身份认证

## 定义
无凭证、Token 无效或过期

## 判断提示
请求未携带 Token、Token 失效或会话过期。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
