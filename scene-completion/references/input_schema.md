# RR/SR/AR 分类输入协议

`scene_model.json` 至少包含：

```json
{
  "version": "6",
  "project": "demo",
  "system_name": "业务系统",
  "source": {"path": "requirements.md", "locations": []},
  "system_composition": {
    "nodes": [
      {"node_id": "user", "name": "用户", "kind": "human_actor"},
      {"node_id": "system", "name": "业务系统", "kind": "internal_service", "layer": "RR", "service_type": "unknown"},
      {"node_id": "sr-order", "name": "OrderService", "kind": "abstract_service", "layer": "SR", "use_case_id": "UC-1", "service_type": "resource_mutation", "classification_status": "confirmed", "classification_basis": "该 SR API 创建订单并触发订单状态变化", "source_location": "功能设计Delta_spec.md:API-ORDER-CREATE"},
      {"node_id": "abstract-uc-1", "name": "提交订单抽象服务", "kind": "abstract_service", "layer": "RR", "use_case_id": "UC-1"},
      {"node_id": "order-service", "name": "OrderMicroservice", "kind": "internal_service", "layer": "AR", "service_type": "unknown"},
      {"node_id": "impl-order", "name": "createOrder", "kind": "implementation_api", "layer": "AR"},
      {"node_id": "order-db", "name": "订单数据库", "kind": "internal_database", "layer": "AR"}
    ],
    "edges": [{"edge_id": "EDGE-1", "from_node": "user", "to_node": "abstract-uc-1", "relation": "participates_in", "use_case_id": "UC-1"}]
  },
  "use_cases": [{
    "use_case_id": "UC-1",
    "use_case_name": "提交订单",
    "actors": ["用户"],
    "main_flow": [{"step_index": 1, "text": "用户提交订单"}],
    "scenarios": [{"scenario_id": "UC-1-main", "scenario_type": "main", "anchor_step_index": 0, "steps": [{"step_index": 1, "text": "用户提交订单"}]}, {"scenario_id": "UC-1-1.a", "scenario_type": "requirement_exception", "anchor_step_index": 1, "anchor_label": "1.a", "steps": [{"step_index": 1, "text": "请求参数非法"}] }],
    "architecture": {
      "rr": {"service_id": "rr-service-UC-1", "service_name": "Order", "abstract_api_id": "RR-API-ORDER"},
      "sr": {"design_use_case_id": "SRUC-UC-1-API-ORDER", "service_id": "sr-order", "service_name": "OrderService", "abstract_api_id": "API-ORDER-CREATE", "service_type": "resource_mutation", "classification_status": "confirmed", "classification_basis": "该用例 API 创建订单并触发订单状态变化", "source_location": "功能设计Delta_spec.md:API-ORDER-CREATE"},
      "ar": [{"microservice_id": "order-service", "microservice_name": "OrderMicroservice", "implementation_api_id": "createOrder", "implementation_api_node_id": "impl-order", "software_interface": "POST /api/v1/orders", "service_type": "command_write", "classification_status": "inferred", "classification_basis": "实现接口执行订单写入", "source_location": "API.md:createOrder"}]
    }
  }],
  "interactions": [
    {"interaction_id": "INT-1", "use_case_id": "UC-1", "from_node": "user", "to_node": "system", "direction": "incoming", "message": "提交订单", "layer": "RR", "sequence": 1, "source_step_index": 1, "source_location": "page 2"}
  ]
}
```

`architecture.sr.service_type` 仅接受 `display_interaction|query_retrieval|resource_mutation|analysis_generation|release_activation|unknown`；`architecture.ar[].service_type` 仅接受 `query_read|command_write|orchestration|integration_event|publish_activation|unknown`。两层都需要 `classification_status`、`classification_basis` 和 `source_location`。工具允许归一化时补成 `unknown`，并生成 review item；未知分类不会路由专属关注点。不能把同名微服务或 AR 分类用作 SR 分类依据。旧 V3/V4 输出不直接作为 V6 输入。

`node_id`、`interaction_id`、`edge_id` 缺失时由 tools 稳定生成。节点类型和交互方向必须使用协议枚举。`unknown` 不阻塞流程，但会产生待确认项。每个 RR 用例会自动补齐一个 RR `abstract_service` 节点，除非 Agent 已显式提供同一 `use_case_id` 的节点。

接口条目可以包含 `validation_rules`。每条规则需结构化记录 `field`、`constraint`、`failure_type`、`error_code` 和 `source_location`。只记录需求或设计文档明确给出的约束，不推测最大长度、大小或速率限制。对 API 参数异常，finding 锚定系统执行校验的用例步骤；用户输入步骤可同时作为 `trigger` 与 `scenario_steps` 的成功前缀，但异常的 `source_step_index` 应指向实际校验/拒绝步骤。

## Diagram spec

Agent 生成的 `diagram_spec.json` 至少包含系统组成总览图；每个 RR 用例的 SSD 由 `generate-ssd` 单独生成。旧版交互关注点图字段仍可读取，但不再是 V2 主输出：

```json
{
  "version": "5",
  "project": "demo",
  "system_composition_diagram": {
    "node_ids": ["user", "order"],
    "puml": "@startuml\n...\n@enduml"
  },
  "ssd_artifacts": [{
    "use_case_id": "UC-1",
    "scenario_id": "main",
    "fused_puml": "@startuml\nactor user\nparticipant system\nuser -> system : submit\n@enduml"
  }]
}
```

系统组成图必须声明全部模型节点，并且只允许 `--` 无方向连线；SSD 使用有方向消息箭头。tools 会拒绝缺失节点、未知 SSD 用例、重复 SSD 场景或 PlantUML 起止标记缺失。

## SSD 消息

`generate-ssd` 输出 `rr_main.json`、`sr_main.json`、`ar_main.json` 和 `fused_main.json`，并默认生成同名 SVG。每条融合消息至少保留：

- `use_case_id`、`ssd_id`、`layer`、`interaction_id`
- `source_step_index`、`source_location`
- `abstract_api_id`、`implementation_api_id`、`service_id`
- `api_method`、`resource_path`
- `request_fields`、`response_fields`

AR 映射缺失时保留 SR 消息，设置 `ar_mapping_status=missing`，并写入 review item；不得为了填满图而虚构微服务。

## Concern matrix

关注点矩阵使用 `{"version":"5","items":[...]}`，每个融合 SSD 请求—响应交换对所有候选关注点保留一条记录。状态只能是 `applicable`、`not_applicable` 或 `needs_requirement`。只有 `applicable` 项允许产生 finding。

优先使用融合 SSD 作为 `plan-concerns --fused-ssd` 的输入。矩阵仍保留原始 `interaction_id`，并可附带 `ssd_id`、`ssd_message_id`、`layer`、`source_step_index`、`implementation_api_id` 和 `service_id`，以便从关注点回溯到融合消息。

超时项额外包含 `requirement_impact`、`subsequent_behavior_impact` 和 `environment_coordination_impact`。JSON 中未判断的影响值留空；工作簿显示“待需求确认”。

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
    "source_step_index": 1,
    "ssd_message_id": "MSG-...",
    "exchange_id": "EXCH-...",
    "source_location": "page 2"
  }]
}
```
