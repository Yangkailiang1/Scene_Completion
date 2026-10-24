# scene-workflow-v2 数据协议

输入原件为Markdown。读取后转换为DOCUMENT：source_id、文件名、通道normal/existing/test、原始行号及文本。正向通道去除已有异常分支，保留原文定位；已有异常和测试异常各自使用独立通道。

所有实际任务请求包包含protocol、task、batch_id、case_ids、input、Skill文本及严格output_schema。输出根对象必须符合专属Schema；来源引文须来自本任务允许的材料。校验通过后才进入缓存和审核版本。

## 用例与SSD

- use-case-extract输入documents和RR/SR层级；输出cases，含id、name、goal、actors、layer、source_ranges及source_refs。ID不要求固定正则。范围记录原始文件位置，不能跨邻近用例。
- use-case-align输入两层目录；输出groups，含组ID、rr_ids、sr_ids、confirmed/pending、原因及依据。允许编号不同和一对多，所有目录项必须对应或明确待确认。
- fused-ssd同时输入对应RR/SR正向描述、组成及case-group；输出interactions、rr_sr_links、pending。
- 每条交互保留id、case_id、layer、sequence、发送方、操作、数据、接收方、direction、parent_id、api_id和来源。发送/接收方记录名称及组成位置，操作记录名称/本次类型/操作序列/可选操作；数据字段记录名称、位置、类型、必填性、默认值及独立约束。
- RR保留系统边界，SR只展开有原文依据的实际调用；层内sequence递增。返回parent_id引用本层先前请求并反转双方。rr_sr_links关联两层消息，无法确认时pending；无AR材料不新增AR。

## 图表与富化交互

| 产物 | 展示字段 |
|---|---|
| 系统组成 | 名称、系统组成；JSON另存节点ID、父级、来源状态、参与关系 |
| 对象操作 | 名称、支持的操作列表 |
| API映射 | 服务名称、对应接口列表；接口保留ID/名称/方法/地址 |
| API参数 | API名称、接口地址；参数位置、数据类型、可选/必填、默认值、约束条件 |
| 关注点匹配 | 交互、对象/字段、关注点、适用状态、具体正常规则、依据和继承路径 |

富化交互补全组成身份、接收方能力、实际API及关注点；classification独立保存actor_system/service_service/undetermined，以及原调用方/提供方和内外位置。返回不改变原调用身份。能力表不能创造本次操作。

组成绘图从当前JSON确定性生成，采用历史分区参与关系布局，导出原生SVG和layout.json；API表不创造新的调用。所有明示约束必须有来源，未知类型/必填性/地址用null，未知具体约束pending。

## 异常与隔离

G只消费正向模型及本次适用关注点；E独立从原文已有分支抽取。测试操作投影只含对象与支持操作；测试GT独立从测试描述、正常约束和框架整理，明示与推导分别记录。建模器的Deep Agent虚拟文件系统中没有E、GT或宿主文件访问。

异常单元包含用例、交互、层级、对象、实际操作、具体原因、全部必要条件、关注点、字段/规则、来源状态及依据。steps保留正常交互上下文、触发步骤、原文明示后续行为；未知响应不编造。

缺失比较仅消费G/E，输出全部候选对决策及missing=M。只有full语义一一对应计覆盖；partial仅诊断。同名关注点不能替代具体原因，无匹配记录不能覆盖指定实例不存在。推荐enabled=false，不生成Q。

## 审核与恢复

review_mode=manual在需确认产物上暂停；auto保存结果后继续。审核项包含task、key、input_hash、payload、版本revision及状态。编辑必须携带当前revision和input_hash；通过前重新校验字段与来源。每次版本不可变保存到reviews/versions，待确认图表在reviews/previews可见。

人工通过或修改使相应任务版本改变；下游依赖按payload摘要决定是否重算。成功缓存被篡改时拒绝，模型失败最多两轮修复；网络/配置/额度失败不伪装成语义成功。重新生成是显式审核操作，不自动篡改G或复制E。

## 评测

六类抽取仍使用Acc（抽取准确率）=H（命中真值单元数）/N（真值单元总数）×100%，GT表示人工真值。同场景同层级语义一一对应，重复不加分，未知GT属性不入分母，空分母不适用；未提供GT未评测。

最小单元：组成“名称—类型”；SSD整条“发送方、操作、数据、接收方”（含GT要求的序列与属性）；对象操作“名称—单项操作”；API映射“服务—单项接口”；API参数“接口—参数—属性—属性值”。保留输入绑定的人工语义核验结果。

异常漏报率=(1-|M∩(GT-E)|/|GT-E|)×100%；生成有效率=|G∩GT|/|G|×100%。推荐相关指标显示未启用。没有真实模型或GT时不得填写效果数值。
