# V10 输出协议

完整输出默认由 `assemble` 生成：它从规范化模型构建 ER/CRUD 和依赖语义，再生成系统组成图、依赖图及其 JSON/SVG/PNG，并在 `diagram_manifest.json`、`run_manifest.json` 登记路径。单独预览和各 JSON 的来源说明见 [`diagrams_v2/system_composition.md`](diagrams_v2/system_composition.md)。

- `scene_model.json`: 标准化系统组成、用例、主成功场景、可选/异常分支和交互。
- `system_composition.json/.svg/.png`: 参与关系视图及语义。人类 Actor → 专属 UI/前端 → 实际参与用例；外部服务只连有证据的用例。
- `system_composition_dependencies.json/.svg/.png`: 依赖视图及语义。人类 Actor → 专属 UI/前端 → 用例区域边界；依赖用例根节点靠左、下游逐层向右，循环依赖保留并标记待审。
- 两张图均不显示 RR/SR/AR 标签、层级后缀或商城系统框；均保留其他系统分区。
- `test_scenarios.json`: 测试组消费格式，覆盖场景清单中的全部主成功、可选、需求异常和关注点异常；步骤转为带序号对象，来源、Spec 明确性和 SSD 追溯随场景导出。主成功/可选场景的 `prediction_id` 为 JSON `null`。
- `er_model.json`: 有来源证据的实体和实体关系。
- `use_case_entity_crud.json`: 每个用例对实体的 CRUD 操作与来源追溯。
- `use_case_entity_crud_<项目>.xlsx`: CRUD 矩阵、操作追溯和 ER 实体/关系审阅表。
- `interaction_catalog.json`: 交互清单。
- `concern_matrix.json`: 每条交互的全量关注点判断。
- `checkpoint_results.json`: 按动态关注点 key 分组的 applicable 异常结果。
- `exception_tree.json`: 用例 → 主流程步骤 → SSD 交换 → 异常。
- `diagram_manifest.json`: 两张系统组成图、独立依赖图及每个 RR 用例 SSD 产物的关联路径。
- `use_case_dependency_graph.json/.svg/.png`: 用例依赖关系语义和图形；边仅由有证据的实体创建/更新前置关系产生，单纯共享实体或 AR 微服务不生成边。
- `interface_service_mapping_<项目>.xlsx`: `SR接口映射` 与 `AR软件实现接口映射` 两张审计表。
- `diagrams/<use_case_id>/rr_main.*`、`sr_main.*`、`ar_main.*`、`fused_main.*`: 每个 RR 用例主成功流程的四套 SSD；融合 SSD 是关注点分析的交换输入。
- `diagrams/<use_case_id>/ssd_manifest.json`: 单个用例的四套 SSD 路径、SVG/PNG 状态和 AR 待确认项。
- `review_items.json`: unknown Service 分类、缺少 AR 映射的待确认项。
- `concern_coverage_report.json`: 按 Use Case、层级、交互对象、关注点族和状态统计审查覆盖率。
- `prediction_analysis_<项目>.xlsx`: 按 Use Case 和主流程步骤分组的异常预测，GT 列为空，并附追溯页；增加“关注点层级”“Spec中已明确”“场景生成来源”“Spec来源定位”。
- `scenario_catalog_<项目>.xlsx`: 每行一个主成功、可选、需求异常或关注点异常场景，并附关注点矩阵；场景清单区分“Spec中已明确”与“场景生成来源”。
- `run_manifest.json`: 统计信息、评估状态和所有输出路径。

Excel 场景清单是测试场景主数据源；`test_scenarios.json.scenarios` 与其场景行按稳定 `scenario_id` 一一对应。关注点矩阵是异常候选审核记录，不直接整体导出为测试场景；只有审核适用并生成 finding 的候选才补成异常场景，需求明确分支则独立保留。

参与关系图将人类 Actor 连到各自 UI/前端，再连接参与用例；不同人类 Actor 使用不同颜色的直线。为压低图高，参与关系图使用多列椭圆网格，允许参与线穿过用例椭圆。依赖关系图将 Actor 连到 UI/前端区域和用例区域，并按依赖分层；依赖箭头是直线，布局避开无关椭圆。外部系统只连有证据的参与关系。连接设备必须由 Spec 明示。图形标签隐藏层级缩写/后缀，且不绘制商城系统节点。SSD PlantUML 使用有方向消息箭头，ImplementationAPI 与 AR 微服务合并为一条生命线。默认纯 Python 生成 SVG，并通过本地可用转换器额外生成 PNG；无转换器时保留 SVG 并记录 `png_status=unavailable`。

V9 模型仍兼容旧输入；旧 `display`/`compute` Service 类型仅在输入边界兼容，规范化结果使用五类功能 Service 或 `unknown`。`pending_review` 不得进入最终 assemble。CRUD/依赖协议详见 `use_case_crud_dependencies.md`。

关注点矩阵每行对应一个 SSD 请求—响应交换和一个候选关注点。工作簿的“SSD交换ID”是请求及其返回的组标识，“SSD请求消息ID”是回溯锚点；用例 ID 直接从矩阵记录读取。请求交互消息必须从 SSD 请求复制到矩阵。超时影响维度只在“超时判断”页列出；JSON 未判定值为空，工作簿显示“待需求确认”。

异常来源和关注点分类是独立维度。需求异常分支的 `exception_origin=requirement_branch` 表示它由 Spec 中明示的分支产生，不代表它没有 concern key。可分类分支使用注册表 key 和标签；无法归类的使用“需求异常｜待分类”，不得把“非关注点”写成关注点名。关注点推导异常需矩阵审核为 `applicable` 并至少有一个 finding；与需求分支同用例、同锚点且触发/结果一致的 finding 合并到该分支，只保留一个预测和场景，合并其 concern evidence 与 SSD trace refs。其余 finding 单独生成预测和场景。主成功与可选场景不是异常，不产生预测 ID。

组装时可重复传入 `--spec-document` 指定系统需求和功能设计 Markdown。输出中的 `spec_explicitness` 为 `yes|no|unverified`，工作簿对应“是/否/待核实”；`scenario_source` 独立表示 `spec_exception_branch`、`spec_exception_branch+concern_mapping`、`concern_completion` 或 `spec_scenario`。`spec_sources` 为可核验的文件/行号列表。需求异常的 concern key 由已审核的匹配 finding 归类；匹配应优先使用显式场景 ID，其次同锚点及异常结果/触发条件，条件或处理结果不同则不得合并。

当等价的数据库可用性 finding 合并时，须同时满足用例、主流程锚点、目标数据库、异常结果和恢复方式相同。合并记录通过 `trace_refs` 保存全部 SSD 交换和消息；Excel 以多行单元格列出这些引用。需求来源异常的双方节点、层级和消息从锚定 SSD 请求补齐；找不到请求时必须输出待确认项，不得静默留空。
