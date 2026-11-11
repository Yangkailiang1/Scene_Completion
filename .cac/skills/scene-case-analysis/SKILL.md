---
name: scene-case-analysis
description: 复用行为模型、功能树、SR 已有异常及逆向测试，对一个用例独立完成 SSD 四元组、关注点、异常对照和推荐，生成可导入工作台的 JSON 与 Markdown。
---

# 单用例异常分析

接收输入目录、目标用例名称或 ID、输出目录。直接用本地 Code Agent 完成语义分析。辅助脚本使用仓库的文件解析、字段回挂、计分和推荐函数，运行时只需要项目 Python 环境。以下命令中的 `SCRIPT` 指本 Skill 的 `scripts/case_analysis.py`，`python` 使用已安装项目依赖的解释器。

## 建模器

1. 执行 `python SCRIPT prepare --input INPUT --case CASE --phase model --out OUTPUT/model.json`。这份材料只包含当前用例的正向证据。核对已采用文件、RR/SR 用例身份、实际交互、参与者、时序及接口绑定。脚本优先采用通过校验的 `SysOperation.json`，多段成功路径由相邻 `SSD.json` 排序，SR 契约及业务属性取自 `功能树.json`。SSD 缺失或无效时，交付待补原因，等待有效文件。
2. 使用 `model.json` 中已补全的四元组与当前注册表。在具体发送方、接收方、操作或数据字段上识别可确认的关注点，生成独立失败条件 G。约束明示时使用真实值和边界；保留完整字段路径、条件和来源。对未知规则记录待确认。保存独立的 G 材料，之后再读取检查器输入。

## 检查器

1. 执行 `python SCRIPT prepare --input INPUT --case CASE --phase existing --out OUTPUT/existing.json`。只用该文件与正向四元组识别 E。通过步骤 ID 或明确来源锚点定位 `behaviour/SR` 的已有异常，保留实际发生交互、原分支 ID 和证据。已完成定位的分支可逐条采用，剩余分支保持待确认。
2. 执行 `python SCRIPT prepare --input INPUT --case CASE --phase test --out OUTPUT/test.json`。只用该文件与正向四元组独立整理 GT。仅接受明确异常的测试分支，记录未绑定、正常、备选和待确认原因。分别保存 E 与 GT。
3. 关注点按用例、实际交互、方向和四元组定位匹配。场景还须核对同一关注点及同一独立失败条件。保存 G→E、GT→G、GT→E 的判定和依据。同一次请求的 RR/SR 重复视图使用同一实际交互身份。完整对应可计分，部分对应保留以便复核。

## 推荐器与交付

1. 阅读 [结果契约](references/result.md)。执行 `python SCRIPT schema` 获取实际 JSON Schema。把模型阶段的证据、原始 SSD 和 API 契约与 G、E、GT、匹配判定组成 `OUTPUT/draft.json`。用 `python SCRIPT finalize --draft OUTPUT/draft.json --output OUTPUT` 生成 `case-analysis.json` 和 `case-analysis.md`。
2. 辅助脚本从 G 与 E 计算缺失集合 M，再按冻结的模式、风险和已审核历史计算 Q。GT 用于评测，推荐排名只使用 M、模式与历史。默认评测范围是 SR；指标同时给出分子、分母、空分母及待补材料状态。
3. 如需在工作台展示，使用 `scene.cmd import-case-result --project PROJECT_ID --file OUTPUT/case-analysis.json --dry-run` 预检，随后去掉 `--dry-run` 导入。打开结果页，在「结果来源」选中该 Code Agent 版本。
