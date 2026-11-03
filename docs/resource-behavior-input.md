# 已有文件输入：资源／用例行为目录

支持在原五类JSON输入旁附带以下目录；也可向现有项目上传这些文件。原五类输入、Markdown建模及原有正式产物导入保持兼容。

```text
行为建模_资源用例/outputs/<分组>/<用例>/
  ssd.json
  ir_scenario.json
  sr_scenario.json
  operations/<operation_id>/
    main_success.json
    complete_behavior.json
```

按JSON结构识别用途，不要求文件必须使用这些名称。目录只用于寻找同用例的相邻文件，不把“支付”“退款”或其他分组名称当作业务实体。用例ID和名称来自场景文件；没有身份或存在歧义时保持待确认，不跨用例猜测。IR在本资源行为格式中对应RR材料，不改变其他输入格式的层级含义。

## 映射与采用范围

| 文件内容 | 节点及处理 |
| --- | --- |
| `ssd.json`的`system_boundary`、`interactions`和`scenario_flows` | 补充本用例`ssd-context`／`fused-ssd`的RR事实；只取唯一相邻IR主成功场景明确覆盖且不属于异常／备选的步骤，保留发送方和接收方 |
| `main_success.json`的SR flow、interactions、actions | 补充本用例SR主成功事实；保留顺序和显式选择，不将分支摊平；本地action不制造新Service或调用 |
| `complete_behavior.json` | 完整原文件可预览；只将同操作主成功视图明确引用的交互／本地动作定义提供给正向建模，完整choice的异常guard和失败返回不进入G |
| `ir_scenario.json`、`sr_scenario.json`的`kind=main` | 本用例的RR／SR正向描述，参与上下文、融合SSD及正常规则整理 |
| 上述场景文件的`kind=exception` | 进入`existing-branches`的E通道，再执行实际交互绑定、关注点逆向识别及场景细化；不成为GT |
| `alternative`或未知kind | 保留原文件及预览；不自动当成异常E或测试GT |

这些文件不是完整项目的用例目录，因此不会替换`rr-use-cases`、`sr-use-cases`或跳过`use-case-align`。目录及原已有分支抽取仍可复用同时输入的`structure_model_fusion`。

本适配器不声称这些行为视图已经是当前正式`fused-ssd`契约。仍需统一系统组成身份、最小双方交互、请求／返回和RR／SR展开关系，所以不直接把融合节点标为成功。`rr-ssd`／`sr-ssd`由经校验的融合结果工具投影。已经提供原生正式契约的文件仍走原完整产物导入机制。

例如文件标SR但实际写“顾客→系统”，不会改写成“系统→AdminService”。缺少调用双方的“调用API”动作只作为文字依据，由原建模流程结合允许的原文补齐，不按API名字伪造调用。

## 操作方式

1. 创建项目或“输入与导入”中预览整个输入目录，识别五类JSON及当前行为文件；行为生成工程的`inputs`及`history`／`backup`／`archive`等目录不与当前`outputs`混用。
2. 勾选采用部分已提供内容后，行为文件按用例作为补充输入；也可逐文件“采用此行为版本／停用此行为版本”。未采用时原流程不变。
3. 导入依赖图显示每份文件涉及的真实节点。“提供依据”与“跳过抽取”分开表示，不把候选或部分事实冒充完成。
4. 下一次显式执行时使用冻结的输入版本，不覆盖在途结果。相同用例、层级、操作和视图存在多个版本时，先停用非当前版本。

仅上传无用例身份的单份SSD或行为文件，需要同时选择相邻场景文件或通过导入确认接口指定`case_id`。支持`sequence`、`choice`、`optional`、`interaction`、`action`和`empty`；悬空引用及不支持的结构显示为格式待修正，不启动自由格式转换模型，也不阻断原始输入流程。

原文件逐字节保存。可读投影有独立来源ID和JSON属性位置，追溯回该输入文件；文件中列出的未提供spec、原始行号及`evidence`不被伪装成本系统已验证证据。采用不自动执行模型，也不改写业务实体、API约束、关注点定义或GT。
