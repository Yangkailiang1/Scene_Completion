# internal_service.compute.calculation_correctness — 计算正确性和精度

## 定义
计算结果错误或精度不满足要求

## 判断提示
金额计算出现舍入误差。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
