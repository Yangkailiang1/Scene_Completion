# V2 输入协议

`scene_model.json` 至少包含：

```json
{
  "version": "2",
  "project": "demo",
  "system_name": "业务系统",
  "source": {"path": "requirements.md", "locations": []},
  "system_composition": {
    "nodes": [
      {"node_id": "user", "name": "用户", "kind": "human_actor"},
      {"node_id": "order", "name": "订单展示 Service", "kind": "internal_service", "service_type": "display", "classification_status": "inferred"}
    ],
    "edges": [{"edge_id": "EDGE-1", "from_node": "user", "to_node": "order", "relation": "calls"}]
  },
  "use_cases": [],
  "interactions": [
    {"interaction_id": "INT-1", "use_case_id": "UC-1", "from_node": "user", "to_node": "order", "direction": "incoming", "message": "提交订单", "api": "POST /orders", "sequence": 1, "source_step_index": 3, "source_location": "page 2"}
  ]
}
```

`node_id`、`interaction_id`、`edge_id` 缺失时由 tools 稳定生成。节点类型、交互方向和 Service 类型必须使用协议枚举。`unknown` Service 不阻塞校验，但会产生待确认项。

## Diagram spec

Agent 生成的 `diagram_spec.json` 必须包含两张图，并完整声明关联 ID：

```json
{
  "version": "2",
  "project": "demo",
  "system_composition_diagram": {
    "node_ids": ["user", "order"],
    "puml": "@startuml\n...\n@enduml"
  },
  "interaction_concern_diagram": {
    "interaction_ids": ["INT-1"],
    "puml": "@startuml\n...\n@enduml"
  }
}
```

tools 会拒绝缺失节点、交互或 PlantUML 起止标记的图规格。

## Concern matrix

关注点矩阵使用 `{"version":"2","items":[...]}`，每条交互对所有候选关注点保留一条记录。状态只能是 `applicable`、`not_applicable` 或 `needs_requirement`。只有 `applicable` 项允许产生 finding。

超时项额外包含 `requirement_impact`、`subsequent_behavior_impact` 和 `environment_coordination_impact`，每个值为 `yes`、`no` 或 `unknown`。

## Semantic findings

```json
{
  "findings": [{
    "interaction_id": "INT-1",
    "concern_key": "api.data.completeness",
    "exception_desc": "请求缺少订单名称时系统拒绝创建并返回明确错误。",
    "trigger": "调用方提交缺少必填字段的请求。",
    "scenario_steps": ["调用方提交请求。", "系统校验必填字段。", "系统拒绝请求并返回错误。"],
    "recovery": "补充字段后重新提交。",
    "source_location": "page 2"
  }]
}
```
