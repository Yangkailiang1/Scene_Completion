# Use Case—实体 CRUD 与依赖提取契约

在需要生成系统级用例依赖图时读取本参考。Agent 负责从 Spec 提取数据语义；工具只校验并绘图，不通过名称相似度或 AR 组件复用猜业务依赖。

## 模型结构

实体放入 `entities` 和 `er_model.entities`。ER 关系放入 `er_model.relationships`，每条关系至少提供：

```json
{
  "from_entity": "Order",
  "to_entity": "OrderItem",
  "relation": "has_many",
  "evidence": "订单包含订单商品明细",
  "source_location": "功能设计Delta_spec.md:line 640",
  "mapping_status": "confirmed"
}
```

每条已识别 CRUD 操作放入 `use_case_entity_operations`：

```json
{
  "operation_id": "CRUD-ORDER-CREATE-ORDER-C",
  "use_case_id": "UCG-002-UC001",
  "entity": "Order",
  "operation": "C",
  "source_step_index": 4,
  "evidence": "创建订单记录并返回订单编号",
  "source_location": "功能设计Delta_spec.md:line 642",
  "mapping_status": "confirmed"
}
```

CRUD 操作值只允许 `C`、`R`、`U`、`D`。无法确定实体或操作时不要填造 CRUD 值；添加待确认项，并在可确定实体时用 `mapping_status=needs_confirmation` 标记记录。所有定位应指向可复核的文档位置和对应主流程步骤。

## 依赖声明

仅当证据说明消费用例必须依赖一个前置创建/更新操作时，消费方 CRUD 记录才引用 `depends_on_operations`：

```json
{
  "depends_on_operations": ["CRUD-PRODUCT-DRAFT-CREATE"],
  "dependency_relation": "consumes_created_resource",
  "dependency_evidence": "编辑接口的前置条件要求商品草稿已存在",
  "dependency_source_location": "功能设计Delta_spec.md:line 994"
}
```

同实体读写但没有上述引用和证据时，工具不会生成边。仅凭“先创建、后更新”的文档排列顺序、共享表、同一 AR 微服务，均不能证明依赖。状态变更依赖必须引用确切状态/数据消费者证据；删除依赖必须有明确的生命周期、级联或资源失效证据。无法确定就留在 `review_items`。

## 输出与验证

`use_case_dependency_graph.json` 汇总实体 CRUD 矩阵、每条依赖的前置/消费 CRUD 操作 ID、证据和来源定位。CRUD Excel 含矩阵、逐操作追溯和 ER 实体/关系页。系统总览图嵌入同一图语义，线条只用于有证据的边。
