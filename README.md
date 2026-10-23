# Scene Completion

项目只保留 `scene-workflow-v1`：11个任务Skill和主控Skill。共享抽取系统组成/API两表，逐用例整理交互、匹配57项既定关注点、生成异常G、抽取已有异常E并交付缺失集合M。推荐未启用，不生成Q。

## 安装与离线验证

Python 3.9及以上（验收环境3.9）；Windows、macOS/Linux的运行锁均有实现。Graphviz可选，仅用于组成图SVG；JSON、Markdown、DOT与SSD SVG不依赖它。

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python .cac/tools/scene_completion.py --help
```

## 运行流水线

默认 `packets` 只构造任务包，**不调用模型**。退出码2表示仍有待执行任务，已成功任务及有效缺失报告仍保留。

```sh
python .cac/tools/scene_completion.py pipeline \
  --rr-spec-document 在线商城购物系统/系统需求_spec.md \
  --sr-spec-document 在线商城购物系统/功能设计_spec.md \
  --test-spec-document 在线商城购物系统/test_spec.md \
  --use-case-id UCG-001-UC001 --output-dir runs/mall-v1
```

省略 `--use-case-id` 时从文档发现 `UCG-nnn-UCnnn`、`SCnnn-UCnnn` 或 `UC-...`；其他编号须显式提供。用例标题应含编号，程序保留公共前言和本用例章节。非标准排版需先检查任务包中的分段是否正确，不以文件名推断场景。

需要真实执行时，先填写 `workflow.config.example.json` 对应的本地配置及环境变量，再在同一命令中明确添加：

```sh
--agent-mode external --config workflow.local.json --env-file .env
```

配置支持OpenAI兼容Chat接口、JSON Schema（仅在供应商支持时开启）、流式响应、输出/上下文限制与持久化token预算。本地CLI运行使用 `native.config.example.json`，记录实际配置模型和原生执行凭证。`.env`、`*.local.json`不会提交。模型选择来自配置，不重标记旧执行结果。模糊网络失败不自动当作语义失败重发；缺额度/配置停在对应状态。

## 其余三个公开入口

```sh
# 独立任务：输入必须符合该任务的具名输入契约
python .cac/tools/scene_completion.py task --task gap-recommend \
  --input-json examples/disabled-recommendation.json --output-dir runs/disabled

# 人工抽取GT计分：六类图表之一；决策不提供时只做精确已知属性匹配
python .cac/tools/scene_completion.py score-extraction --task components \
  --extracted EXTRACTED.json --truth TRUTH.json --output ACC.json

# 不联网检查当前运行的协议、任务状态与输出完整性
python .cac/tools/scene_completion.py check-run --run-dir runs/mall-v1
```

`--responses-dir`可导入人工/外部执行结果：文件名为任务包的batch_id，根对象为 `{protocol,task,batch_id,payload}`。任务包包含Skill文本、严格输出Schema、指定用例、输入及修复信息，不接受不匹配的响应。

流水线可选 `--extraction-truth GT.json` 与 `--adjudications DECISIONS.json`：共享任务键为 `components`、`api-map`、`api-parameters`，逐用例键为 `用例编号:rr-ssd`、`用例编号:sr-ssd`、`用例编号:object-operations`。未提供人工GT标“未评测”，明确空集合标“不适用”。语义决策须经人工确认；可复用的绑定格式及最小计分单元见[协议说明](docs/scene-workflow-v1/protocol.md)。测试异常GT与人工抽取GT是两个独立输入。

## 输出与恢复

- `run_manifest.json`：整体完成、每个用例分析完成及独立评测状态。GT失败不阻塞缺失报告。
- `missing_report.json` / `.md`：各成功用例的交互、双方及数据关注点、异常步骤、已有覆盖、缺失原因、来源和待确认。
- `artifacts/shared/`：共享图表；`artifacts/<用例ID哈希>/`：逐用例图表、富化交互及指标。任务JSON和metadata分开，物理数据库/逻辑服务映射保留。
- `packets/`、`attempts/`、`task_outputs/`、`workflow_tasks.json`：请求、被拒结果、验证通过的输出及依赖状态。

同一目录重跑会验证缓存；只有输入、契约、规则或执行身份变化的任务及其受影响结果才重新执行。上游重做但payload相同，下游成功结果复用。模型与额度限流共享，每任务最多两轮定向修复，修复记录不会靠再次运行清零。不要删除运行目录来规避预算。旧协议运行目录拒绝直接复用。

本轮仅离线与模拟响应验收，没有付费全量评测，也未据此宣称真实模型效果或稳定性提升。可运行 `python examples/memory_demo.py --output-dir /tmp/memory-demo` 查看明确标记mock的完整演示；其中抽取与语义对应是固定测试夹具，不代表真实模型结果。

完整[流程对照表](docs/scene-workflow-v1/workflow-map.md)、[迁移说明](docs/scene-workflow-v1/migration.md)与[测试记录](docs/scene-workflow-v1/validation.md)。
