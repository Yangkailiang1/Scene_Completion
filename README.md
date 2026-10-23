# Scene Completion

按27页PPT执行系统组成、RR/SR SSD、对象操作、API两表和异常识别。默认协议为 **`ppt-task-v1`**：11个独立Skill任务入口，推荐暂停。保留现有DAG、共享限流/冷却、成功结果复用和有界修复；本轮不迁移Deep Agents。

## 开始使用

安装Python 3.10+及依赖（测试环境同时验证了3.9兼容性）：

```sh
python -m pip install -r requirements.txt
python .cac/tools/scene_completion.py scene-pipeline \
  --rr-spec-document RR.md --sr-spec-document SR.md \
  --test-spec-document test_spec.md --output-dir output/ppt-v1
```

默认只准备有输入约束的任务包，返回码2表示尚有待执行任务，不调用付费模型。输出位于`packets/`，可以用同一命令恢复。模型执行必须显式加入`--agent-mode external --config CONFIG.json`；本次交付仅进行了离线模拟和测试。

每个任务均可单独执行：

```sh
python .cac/tools/scene_completion.py scene-task \
  --task api-parameters --input-json INPUT.json --output-dir output/api-parameters
```

完整输入格式、外部结果提交方式、数据契约与迁移约束见 [新协议说明](docs/ppt-task-v1/protocol.md)。可运行的离线记忆库演示见 [示例说明](examples/ppt_task_v1/README.md)。

## 方法边界

- 六项抽取各自读取指定材料；系统组成直接读取RR/SR。未添加32页版本的架构/依赖图任务。
- 测试只向对象能力表提供名称和支持操作；来源引文仅保留操作名称，不带异常答案。能力表不反向新增SSD交互或写入异常。
- 当前57项定义作为固定输入。按双方身份、实际操作、字段属性匹配；不强制每个关注点生成异常。未知约束待确认，不进入G，可选缺省正常。
- G、已有异常E和测试GT分通道。GT允许有依据的框架推导直接计分，明示/推导分别报告；不得读取G或比较结果。
- 只有完整语义对应计命中；部分对应只诊断。空列表不等同实例不存在。
- 推荐不生成Q、不初始化历史向量、不执行排序或随机回退；推荐指标为“未启用”。

制品包含严格JSON、中文字段Markdown表、可编辑DOT，以及安装Graphviz时的SVG。物理数据库、逻辑SR资源服务及映射单独保留。所有结构与来源校验通过后才进入成功缓存；拒绝结果保留在`attempts/`。

抽取指标仅为`Acc（抽取准确率）=H（命中的真值单元数）/N（真值单元总数）×100%`。未运行全量模型评测，不宣称真实输出稳定性已有提升。

## 离线验证

```sh
PYTHONPATH=.cac/tools python -m pytest -q
python examples/ppt_task_v1/offline_demo.py --output-dir output/ppt-memory-offline
```

新增验收覆盖8条记忆库字段异常、泛化字段/对象、未知约束、只读交互、数据库封装、输入隔离、部分匹配、去重、缓存恢复/局部失效及推荐停用。模拟结果会标记`mode=mock`，不能在原目录转成正式运行。

## 旧协议

[历史v2说明](README.legacy-v2.md)及旧Skill仅用于显式兼容：`--protocol rr-sr-concern-gap-v2`、`--protocol rr-sr-ssd-identification-v1`或`--protocol legacy`。旧模式仍需要`--model`。它们的“每关注点至少一条”、部分匹配计分、历史推荐规则均不适用于新协议；不得将旧结果搬入新运行目录。
