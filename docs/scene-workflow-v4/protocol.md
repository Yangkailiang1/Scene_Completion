# scene-workflow-v4：关注点与具体场景两层协议

当前运行使用two-level-concern-scenario-v1；旧项目继续可查看，启动时创建升级副本，保留previous_project_id。只从positive_reuse.json重用输入、Schema、Skill一致且重新验证通过的正向结果，不导入旧异常配对、关注点自动继承或指标缓存。

## 建模与独立检查

融合SSD及正常规则→LLM关注点识别G_c→已识别关注点的模式适用性→G_s。基础可用性和字段约束也须实际识别；工具候选不是G_c。模型空结果保留为空，不能自动继承整张注册表。

E通道：独立原文异常分支→交互绑定→existing-concerns识别E_c→existing-extract细化E_s。
GT通道：严格筛选异常类型→test-concerns识别GT_c→test-ground-truth细化GT_s。正常/可选/待确认不计分。补充测试在独立结构化测试构造时记录关注点，先保存test-additional-concerns再形成场景，不能从G/E回填。

模型负责识别与证据；工具负责合法对象、分类和证据校验、稳定ID、集合比较、模式构造及导出。手动审核包含三个关注点识别节点，自动模式记录版本。

## 标识与集合

每个绑定：case_id、canonical interaction_id、direction、target(sender/operation/data/receiver)、element_id、concern_key。发送方/接收方是该次实际对象；操作既可定位整次调用，也可用operation_index定位内部序列项；数据保留位置和完整字段路径，HTTP头名称忽略大小写。内部/外部调用认证与授权归具体操作项并保存caller/callee。

MATCH增加binding_id、element_id及上述定位；模型无需输出派生ID。SCENARIO增加concern_binding_ids、element_anchors和matching_version；同一独立失败可关联多个绑定但只计一次。

concern-compare产物：G_c、E_c、M_c和按规则对齐的rows。concern-evaluation另含GT_c、metrics、excluded及original_evaluation。已识别关注点即使场景生成失败仍留在G_c。父分类不计数，重复绑定按ID去重；歧义保留待确认及原因。宽泛参数分支只能在其独立识别范围内覆盖本交互输入，不覆盖输出。分类冲突先由各自证据规范化，不能借另一通道改答案。

## 场景与指标

pageSize范围对应一个关注点；小于下界、大于上界是两条场景；-1/-2是同一场景的测试值。G_s、E_s、GT_s独立构造；按共同绑定筛选候选，再按失败条件规则或语义匹配。没有共同绑定不能成为完整匹配。E_c覆盖不阻止M_s仍有缺失。

- 关注点漏报率：(1−|M_c∩(GT_c−E_c)|/|GT_c−E_c|)×100%。
- 关注点生成有效率：|G_c∩GT_c|/|G_c|×100%。
- 场景推荐采纳率：|Q_s∩GT_s|/|Q_s|×100%。
- 场景推荐误报率：|Q_s−(Q_s∩GT_s)|/|GT_s|×100%，可超过100%。

空分母为不适用，原始/扩展测试分别保存；汇总合并分子分母。exception-evaluation.metrics使用新单位，metric_units显式说明；旧场景前两项仅留legacy_scenario_metrics，不成为新版主指标。

## 网页与导出

既有results/{case}接口增加matching_version、concern_rows、concern_excluded、concern_metrics、metric_units及场景推荐信息；results/metrics增加unit/matching_version及每例两层计数。视图只读已经保存的对齐，不在前端重新判断。关注点表可下钻场景；场景显示四要素对象→关注点→具体失败及Q_s状态。JSON/Markdown导出保留两层集合和来源。

## 验收

运行`.venv/bin/python -m pytest`及`npm test --prefix frontend`、`npm run build --prefix frontend`。工具`tools/audit_two_level_migration.py PROJECT --output FILE`只审计历史场景是否能定位到新标识，不调用模型、不伪造G_c或新指标。真实定向验收使用原账号额度账本，不重置用量。本轮不重建Windows包。

## 数据要求并集与方向化大小场景（v2-union-size）

派生交互读取本交互SSD数据序列与接收方API参数的有据并集；原始SSD/API产物保持不变。按字段位置和完整路径合并；不同位置、请求和返回分别处理。任一来源明确必填则保留必填；未知属性不覆盖已知属性。不同已知类型保留为分别有来源的类型要求，相同约束合并并保留全部引用。默认值差异只在来源明细展示，不据此生成需求一致性异常。

派生交互可含`parameter_requirement_sources`，逐字段记录SSD/API的类型、必填性、默认值、约束和证据。网页数据属性表可展开这些来源；此字段不改变原始抽取契约。

`data_requirements.py`只接收正向交互、接口约束和正常规则，供G及独立测试构造分别使用，不读取G/E/GT和比较结果。文件大小、数组数量、数据类型与数据格式不得相互替代。

已实际识别的大小关注点，有大小校验依据但未说明方向时，构造`size.minimum`与`size.maximum`两个独立条件。明示单边只保留该方向。未知阈值为null，保留conditional、executable=false及待确认说明，不能与已知数值阈值声称完全命中。关注点层仍为一个绑定，场景层按两个独立失败条件计数。模式示例不是本用例的新需求或测试答案；注册表候选不能成为识别结果。

同一两层匹配协议内的工具规则升级，在执行前归档旧报告、指标快照及任务状态，再按输入和实现版本定向失效。经校验的模型原始响应仍可重放并重新规范化；澄清记录和用量审计不丢弃。跨协议仍新建项目，旧场景不能冒充LLM识别的关注点。

## 独立测试用例与推荐前后对照

测试先经test-inventory独立整理，再经test-case-align与RR/SR用例组对应，之后按实际交互识别GT_c与细化GT_s。未知格式和编号不同不直接丢弃；未确认对应保留待确认，不参与确定GT。详见[输入、隔离与指标说明](../test-markdown-alignment.md)。推荐前以全部M为候选，推荐后以Q为候选，同一冻结GT下分别保存采纳率及GT分母误报率。
