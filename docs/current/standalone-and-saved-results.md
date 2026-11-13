# 独立分析与保存结果

新分析使用[单用例Skill](../../.cac/skills/scene-case-analysis/SKILL.md)的共同SSD流程。脚本负责结构、规则和明确定位，Code Agent或工作台处理未决语义；只运行脚本不能声称所有语义比较已完成。

```sh
python .cac/skills/scene-case-analysis/scripts/case_analysis.py build \
  --input INPUT_DIRECTORY --case CASE_ID --output OUTPUT_DIRECTORY
python scene.py import-case-result --project PROJECT_ID \
  --file OUTPUT_DIRECTORY/case-analysis.json --dry-run
python scene.py import-case-result --project PROJECT_ID \
  --file OUTPUT_DIRECTORY/case-analysis.json
```

单用例build输出`case-analysis.json`，多个用例使用各自文件名，命令输出列出实际位置。格式为`ssd-case-v1`，导入后在新三方结果页查看、编辑和追溯，不经过风险推荐步骤。

原`scene-case-analysis-v1`工件继续由`compat/standalone`校验和导入。`schema`、`prepare`、`finalize`子命令服务于这类既有工件；它们与build命令的输出结构不同。导入保留原G/E/GT、场景ID、来源和匹配，不用新的脚本G覆盖旧提交。

`compat/saved`及前端`results/saved`保留原报告、独立导入版本、图表、接口范围和指标浏览。存在共同SSD结果时，结果入口优先展示SSD页；没有共同结果时仍可浏览保存报告。原“结果来源”下的导入版本选择属于保存结果界面，不应作为所有新SSD导入的使用说明。

`compat/detailed`则是既有细粒度执行流程和历史mock契约，与独立导入和保存结果展示分别维护。它们不意味着支持v2/v3/v4协议重跑。版本对应关系见[版本说明](../reference/versions.md)。
