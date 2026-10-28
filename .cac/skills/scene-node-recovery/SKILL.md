---
name: scene-node-recovery
description: Recover a failed node using its own packet, rejected candidate and validator feedback.
---
# 节点失败恢复
仅处理当前任务包和本节点候选。先解释失败位置，保留合法事实，只修正具体结构/引用/缺项。原任务的Skill、Schema、材料通道和业务约束始终有效。
禁止读取其他通道的G/E/GT或比较答案；禁止修改程序、Schema、原文、Key、账本、其他节点或标记空成功。
未知业务事实使用原任务允许的pending/提问结构；提出业务问题后继续提交有依据的部分。
结果须经原校验及后处理，成功才进入下游。重试次数、模型与请求参数由守护工具控制，不自行突破预算。
