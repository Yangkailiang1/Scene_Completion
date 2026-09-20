# human.input_data — 输入数据

## 定义
人类输入重复、超长、过大或重复点击

## 判断提示
用户连续点击提交，或上传超过限制的文件。

只在需求证据支持时标记 `applicable`；证据不足标记 `needs_requirement`；不适用时标记 `not_applicable`。异常描述必须绑定交互 ID 和来源定位。
