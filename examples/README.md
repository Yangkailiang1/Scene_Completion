# 终端云三角色实验

terminal_cloud_model.json 是终端云规范模型快照。原始输入为“终端云例子”目录内的系统需求Delta_spec.md、功能设计Delta_spec.md。生成器使用现有模型、SSD 和关注点路由，得到 472 个 G：14 主成功、5 可选、37 明确异常、416 未经过适用性审查的候选。

检查器独立读取两份原始用例，得到 97 个 C；不读取 G、旧审核结果或 test_spec。为公平比较，各实验冻结同一个检查集合，并保留首次抽取的场景 ID。新抽取的稳定 ID 已加入前置条件和步骤；历史 ID 在快照中作为不透明标识使用。

Agent 批次由最多三个实际子 Agent 调度 ecnu-max；embedding 为 ecnu-embedding-small，rerank 为 ecnu-rerank。审查使用 gpt-6-luna / max，发现的问题已通过语义复核、分支条件修正和评分量表复核处理，再重新运行。Luna 对最终 60 条已接受关系全量复核：3 条完整、45 条部分、12 条未匹配；脚本校验并应用全部决定，再重新计算以下指标。

## 实际结果

|实验|完整/部分链接|漏报率|当前已有完整率|待推荐数|
|---|---:|---:|---:|---:|
|Agent（默认，Luna 全量复核）|3 / 45|54/97 = 55.67%|47/472 = 9.96%|425|
|Embedding 默认 0.85 / 0.70|629 / 2640|0/97 = 0%|472/472 = 100%|0|
|Embedding 敏感性 0.95 / 0.85|6 / 623|18/97 = 18.56%|347/472 = 73.52%|125|
|同敏感性阈值 + rerank|6 / 623|18/97 = 18.56%|347/472 = 73.52%|125|

完整/部分链接是关系条数，指标按两端场景 ID 分别去重。主成功、可选、未分类、每个具体关注点和大类均有分子、分母和场景清单。

默认 embedding 阈值在此样例上过宽：主题相关的候选也可能超过 0.70，不能把“100%”当作文档真的完整。敏感性实验用于展示阈值影响，未改动默认值。两种后端均需用人工标注集评估/校准，Agent 的结果也不等于客观真值。

生成器本地词汇仅标注了 3/37 个明确异常；检查器独立标注了 72/76 个异常。未分类项目保留在总计及未分类桶，分类指标受标签覆盖限制。详细 ID、标签差异及章节见 metrics_summary.json 与工作簿。

## Rerank 对照

同一 125 个候选中，124 项名次变化，83 项首选证据章节变化，110 项首选证据片段变化；匹配关系、总指标、分类指标和候选集合完全一致。

首次证据运行记录约为基础 67.84 秒、增强 477.27 秒；最终缓存重放为基础 3.05 秒、增强 2.68 秒。首次已经复用文本向量，重放也复用 rerank 缓存，网络与缓存状态不同，不能据此得出稳定性能倍数。首次记录保留在 first_pass_manifest.json，候选及证据仍是同一 125 项。

Rerank 用于从相关文档中找更相关的证据，不能证明异常合理，更不能作为覆盖概率。基础/增强评分分开标记。接口说明见[华师文本重排序文档](https://developer.ecnu.edu.cn/vitepress/llm/api/rerank.html)。

## 文件与离线复验

[summary.json](three_agent_demo/summary.json) 汇总四次实验和增强前后对照。common 保存相同 G、C 和原始章节索引；每个实验包含匹配 JSON、指标摘要、全量推荐、Markdown 与 Excel：

- [Agent 报告](three_agent_demo/agent/report.md)、[工作簿](three_agent_demo/agent/scene_assessment.xlsx)。
- [Embedding 默认报告](three_agent_demo/embedding_default/report.md)。
- [敏感性基础报告](three_agent_demo/embedding_sensitivity/report.md)。
- [Rerank 增强报告](three_agent_demo/embedding_sensitivity_rerank/report.md)。

指标摘要省略重复场景对象，通过 ID 查 common；完整指标可离线重建。基础推荐保留评分、引用和依据，原文在 common 的索引中；增强推荐额外保留全部精排片段及原始分数。Agent 保存逐对复核、四项语义判断和高支持度证据复核记录；native_review_packet.json、native_review_results.json 和 native_review.json 分别保存全量原生子 Agent 复核输入、决定及应用记录。

~~~bash
python examples/verify_demo.py
python examples/verify_demo.py --output-dir examples/results/replayed
~~~

第一条重新计算全部指标并校验候选集合、公式、排序和 rerank 不变性，无需联网或密钥；第二条重新导出完整 JSON、Markdown 和 Excel。快照中的 SSD 路径保留首次运行位置用于追溯，重新生成图形应运行 scene-pipeline。

## 重新调用模型

Agent 的完整生成/分包/续跑方法见仓库 README。比较 embedding 时，可复用冻结检查器：

~~~bash
python .cac/tools/scene_completion.py scene-pipeline \
  --model examples/terminal_cloud_model.json \
  --spec-document 终端云例子/系统需求Delta_spec.md \
  --spec-document 终端云例子/功能设计Delta_spec.md \
  --checker-input examples/three_agent_demo/common/existing_scenarios.json \
  --match-backend embedding --recommend-backend embedding \
  --full-threshold 0.95 --partial-threshold 0.85 \
  --output-dir examples/results/embedding
~~~

增加 --rerank 运行增强对照。默认阈值实验省略两个阈值参数。examples/results 与 .scene_cache 均忽略提交；.env 和密钥始终只保留在本地。推荐缺失描述表示建议补充文档，不直接断言产品未实现。
