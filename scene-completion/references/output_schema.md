# V2 输出协议

- `scene_model.json`: 标准化系统组成、用例和交互。
- `system_composition.json`: 节点和边。
- `interaction_catalog.json`: 交互清单。
- `concern_matrix.json`: 每条交互的全量关注点判断。
- `checkpoint_results.json`: 按动态关注点 key 分组的 applicable 异常结果。
- `exception_tree.json`: 用例 → 交互 → 异常。
- `diagram_manifest.json`: 两张图的 PlantUML/SVG/PNG 路径。
- `prediction_analysis_<项目>.xlsx`: V2 异常预测，GT 列为空。
- `scenario_catalog_<项目>.xlsx`: 场景清单和关注点矩阵。
- `run_manifest.json`: 统计信息、评估状态和所有输出路径。
