---
name: scene-controller
description: 持续编排场景分析流水线，处理批次阻塞并完成工具验收及产物交付；用于Claude Code或其他宿主主控，不作为批量语义包。
---

# 默认主控：27页PPT独立任务流程

默认运行 `ppt-task-v1`。先读取 `docs/ppt-task-v1/protocol.md`，再只加载当前任务对应Skill。11个独立任务包含6项抽取、关注点匹配、异常生成、已有异常抽取、缺失比较、暂停的缺失推荐；测试操作投影与GT是隔离内部处理，不新增PPT任务。

执行 `.cac/tools/scene_completion.py scene-pipeline --rr-spec-document RR.md --sr-spec-document SR.md --test-spec-document TEST.md --output-dir NEW_RUN`。默认只准备任务包。显式external模式才调用配置模型；不得因准备包就启动评测。

保留现有DAG调度、共享限流/冷却、成功结果复用与最多两轮修复。新协议目录拒绝旧协议缓存。推荐暂停，不初始化embedding或历史检索，不生成Q。G不读取E/GT，GT不读取G/比较结果。只有完整语义对应计分。

恢复任务只重做失效依赖；保存拒绝结果及来源。报告不宣称真实模型稳定性已提高。需要复现历史版本时显式指定旧 `--protocol`，再读取 [旧主控](references/legacy-controller.md)。
