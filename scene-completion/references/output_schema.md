# V6 输出协议

- `scene_model.json`: 标准化系统组成、用例、主成功场景、可选/异常分支和交互。
- `system_composition.json`: 节点和边。
- `interaction_catalog.json`: 交互清单。
- `concern_matrix.json`: 每条交互的全量关注点判断。
- `checkpoint_results.json`: 按动态关注点 key 分组的 applicable 异常结果。
- `exception_tree.json`: 用例 → 主流程步骤 → SSD 交换 → 异常。
- `diagram_manifest.json`: 系统组成总览图及每个 RR 用例 SSD 产物的关联路径。
- `use_case_dependency_graph.json/.svg`: RR 用例依赖关系的语义和图形产物；边表示显式依赖或共享 AR 服务候选，不代表时序。
- `interface_service_mapping_<项目>.xlsx`: `SR接口映射` 与 `AR软件实现接口映射` 两张审计表。
- `diagrams/<use_case_id>/rr_main.*`、`sr_main.*`、`ar_main.*`、`fused_main.*`: 每个 RR 用例主成功流程的四套 SSD；融合 SSD 是关注点分析的交换输入。
- `diagrams/<use_case_id>/ssd_manifest.json`: 单个用例的四套 SSD 路径、SVG/PNG 状态和 AR 待确认项。
- `review_items.json`: unknown Service 分类、缺少 AR 映射的待确认项。
- `concern_coverage_report.json`: 按 Use Case、层级、交互对象、关注点族和状态统计审查覆盖率。
- `prediction_analysis_<项目>.xlsx`: 按 Use Case 和主流程步骤分组的七列异常预测，GT 列为空，并附追溯页。
- `scenario_catalog_<项目>.xlsx`: 每行一个主成功、可选、需求异常或关注点异常场景，并附关注点矩阵。
- `run_manifest.json`: 统计信息、评估状态和所有输出路径。

系统组成图只展示 RR 抽象服务/用例，RR 用例使用椭圆且不绘制用例间连线；PlantUML 只使用无方向 `--` 连线。SSD PlantUML 使用有方向消息箭头，ImplementationAPI 与 AR 微服务合并为一条生命线。默认纯 Python 生成 SVG，并通过本地可用转换器额外生成 PNG；无转换器时保留 SVG 并记录 `png_status=unavailable`。

V6/V7 模型版本为 `6`。旧 `display`/`compute` Service 类型仅在输入边界兼容，规范化结果使用五类功能 Service 或 `unknown`。`pending_review` 不得进入最终 assemble。

关注点矩阵每行对应一个 SSD 请求—响应交换和一个候选关注点。工作簿的“SSD交换ID”是请求及其返回的组标识，“SSD请求消息ID”是回溯锚点；用例 ID 直接从矩阵记录读取。请求交互消息必须从 SSD 请求复制到矩阵。超时影响维度只在“超时判断”页列出；JSON 未判定值为空，工作簿显示“待需求确认”。

需求明确异常是来源类别而非注册表关注点，使用 `exception_origin=requirement_branch` 标识，不占用 concern key。关注点推导异常需矩阵审核为 `applicable` 并至少有一个 finding；每个未与需求分支合并的 finding 生成一个异常预测和场景。需求明确异常独立保留为异常预测。主成功与可选场景不是异常，不产生预测 ID。

当等价的数据库可用性 finding 合并时，须同时满足用例、主流程锚点、目标数据库、异常结果和恢复方式相同。合并记录通过 `trace_refs` 保存全部 SSD 交换和消息；Excel 以多行单元格列出这些引用。需求来源异常的双方节点、层级和消息从锚定 SSD 请求补齐；找不到请求时必须输出待确认项，不得静默留空。
