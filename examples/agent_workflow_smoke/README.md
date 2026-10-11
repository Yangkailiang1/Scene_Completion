# Agent流程快照重建

`snapshot.json`用于验证离线结果重建。它包含原始来源索引、正常模型、SSD、关注点挂载、场景、完整比较决定及质量诊断，不包含密钥、私人配置或模型执行缓存。

在项目根目录安装依赖后运行：

```bash
python .cac/tools/scene_completion.py rebuild-interaction-snapshot --snapshot-file examples/agent_workflow_smoke/snapshot.json --output-dir examples/results/agent_workflow_smoke
```

程序重新核实SSD、挂载、全部配对决定和一一分配，重建指标及结果哈希，并输出JSON、Markdown、图和 `scene_assessment.xlsx`。结果按快照中的业务和交互范围标记；离线重建不调用模型，不产生新的执行验收。

如需从其他完整运行导出快照：

```bash
python .cac/tools/scene_completion.py export-interaction-snapshot --output-dir <run-dir> --snapshot-file <snapshot.json>
```

实际运行和执行证明检查见[项目README](../../README.md)及[tools接口](../../docs/rr_sr_tools_checks.md)。
