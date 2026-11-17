# 在线商城输入样例（mall-input）

本目录是一次真实运行留下的**输入样例**，不是程序产物，也不会被打包进 Windows 离线包。

## 内容

| 文件 | 作用 |
|---|---|
| `系统需求_spec.md` | RR 原始需求文本 |
| `功能设计_spec.md` | SR 原始设计文本 |
| `test_spec.md` | 测试原始文本 |
| `scene_completion_output/` | 当时运行留下的历史产物（图表、清单），只作参考 |

## 用途

用于对照 [五类输入](../docs/current/five-input-bundle.md) 与
[结构化输入工作流](../docs/current/structured-input-workflow.md) 的实际材料形态。
需要完整的结构化行为目录时，请参考同级的 [mini-mall](../mini-mall/README.md)。

## 注意

- 本目录**不**是新的结构化输入格式示范。结构化输入要求目录下存在
  `行为模型/<资源>/<用例>/SysOperation.json`，本目录没有该结构，直接用它建项目
  会走文档抽取分支。
- `scene_completion_output/` 中的历史产物按当时的规则生成，不能用于当前口径的
  成绩对比，也不要原地改写。
