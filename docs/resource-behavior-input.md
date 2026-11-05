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
| `main_success.json`的SR flow | 只提供主成功时序／引用；允许没有interactions/actions或只有不完整重复声明。引用向同用例、同操作的complete_behavior解析，不要求本文件重复包含完整定义 |
| `complete_behavior.json` | SR内部交互／本地动作的定义来源。既解析main_success引用，也依据sr_scenario的场景类型及source_steps补入未被时序引用的明确主成功内容；异常和备选分流，完整choice的异常guard和失败返回不进入G |
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

SR定义与时序分别追溯：sender／receiver／message等来自complete_behavior，flow来自main_success；main_success中重复或不完整的定义不覆盖完整文件。缺少完整文件、引用悬空或步骤归属不明确时，在导入详情显示待补齐原因，原建模流程保留。缺少main_success时，仍可采用sr_scenario明确归属的主成功定义，不按数组顺序虚构时序。

旧适配版本重新导入同一文件即可升级，原文件、旧投影和报告保留；新版需重新确认采用，避免将旧版“主成功文件必须自带全部定义”的结果当成新协议结果。

仅上传无用例身份的单份SSD或行为文件，需要同时选择相邻场景文件或通过导入确认接口指定`case_id`。支持`sequence`、`choice`、`optional`、`interaction`、`action`和`empty`；悬空引用及不支持的结构显示为格式待修正，不启动自由格式转换模型，也不阻断原始输入流程。

原文件逐字节保存。可读投影有独立来源ID和JSON属性位置，追溯回该输入文件；文件中列出的未提供spec、原始行号及`evidence`不被伪装成本系统已验证证据。采用不自动执行模型，也不改写业务实体、API约束、关注点定义或GT。

## SysOperation与有序行为格式

```text
行为模型/<资源分组>/<用例>/
  SysOperation.json
  SSD.json
  behaviour/IR/main_success.json
  behaviour/IR/<分支>.json
  behaviour/SR/main_success.json
  behaviour/SR/<分支>.json
```

`SysOperation.operations`保存操作段定义，段内的`participant`只在该操作作用域解析缩写。先加入`system_event`，再严格解析`Order`的`kind/ref`，最后加入未出现的`system_response`。同种类、同ID只展开一次，不同操作段或不同真实执行不合并。多段主成功须由相邻SSD的`system_operations`明确排序；没有排序时不按JSON字典顺序推断。

`interaction`与`action`分别按原类型处理。显式action以executor作为发送方和接收方，保存`step_kind=action`，保留操作、数据及对象关注点；同一对象的sender/receiver绑定归一为receiver，避免重复计分。普通interaction双方相同属于输入数据疑点，不自动改成action。没有类型依据的本地校验仍由原建模流程整理，不能虚构网络自调用。

`scenario_kind=main`进入正向材料；`exception`进入已有异常E；`alternative`保留查看；未知类型待确认。可省略scenario_kind：明确的main_success标识可识别主成功，其余不凭分支名称猜异常。行为分支不是测试GT，独立测试仍从recovered_usecases等测试文件进入。

完整SysOperation在参与方均能对应系统组成、Order和返回有效且通过同一融合SSD契约时，由工具采用到`<用例>:fused-ssd`；RR/SR投影仍由该正式结果产生。缺定义、归属歧义或校验失败时仅作为输入依据，保留原模型抽取路径，不把空结果标为完成。相同用例存在多个启用版本时须先解决冲突。

来源保存到原上传文件及实际JSON Pointer。输入内的document、quote及行号仅保留为文件自带的元数据；除非原文件也已提供并验证，不将它们冒充本系统已校验的spec引文。

接口字段的位置与路径分别保存：例如`location=body, name=name`。生成结果若重复写成`location=body, name=body.name`，工具只移除与本字段位置一致的一层前缀，并用既有要求并集规则合并同一字段；嵌套路径`items[].name`保留。不同位置和请求／返回字段不会因此合并，业务实体路径也不作无依据的截短。
