# human.authorization — 权限控制

## 定义
水平越权或垂直越权

## 判断提示
用户 A 尝试修改用户 B 的资源，或普通用户调用管理员接口。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
