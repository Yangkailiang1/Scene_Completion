# 系统组成图：参与关系与用例依赖

V10 将拥挤的总览拆成两张图；二者共用系统分区、节点语义和样式，但回答的问题不同。可视标签不显示 RR/SR/AR 缩写、分层后缀或商城系统边界节点，用例使用椭圆。

- `system_composition.*` 是**参与关系图**：Actor → 专属 UI/前端 → 实际参与的用例；有依据的外部 Service → 用例。用例以多列网格紧凑排列，参与关系使用直线连接到椭圆左右端点；不同人类 Actor 使用不同颜色，并显示图例。参与线可穿过椭圆，这是为缩短图高而接受的视觉取舍。
- `system_composition_dependencies.*` 是**依赖关系图**：Actor 只连专属 UI/前端，前端只连用例区域外框；外部 Service 的有证据参与关系连接到用例区域边界，并按目标用例所在行对齐。用例依赖区域同时展示两种有明确标签的边：蓝色实线是 CRUD 生命周期依赖（执行 R/U/D 的用例 → 创建同实体的 C 用例）；橙色虚线是单独声明且有证据的状态/前置依赖（前置/生产用例 → 消费/依赖用例）。两种边保留各自方向，不能合并解释；布局按两类边共同分层。
- 依赖环保留语义边并标红虚线，同时写入 `review_items`；图上的层级不表示环内先后。单纯共享实体不构成依赖。

## Actor、前端与设备

- 每个 `human_actor` 使用独立 `frontend_ui`。没有明确映射时，兼容归一化器按 Actor 生成稳定前端 ID，标为 `inferred`；顾客和商家不得共用一个自动生成前端。
- 人类 Actor 连到自己的前端。参与关系图中前端再连到真实参与的 Use Case；依赖关系图中前端只接用例区域边界，不重复扇出到每个用例。外部系统 Actor 直接连到参与的 Use Case。
- `connection_device` 仅在 Spec 明确支持并含来源定位时进入图。网页端/移动端 UI 节点不是手机、平板或折叠屏支持证据。
- 未能确认的映射放入 `review_items`，不画猜测的关系。

## ER、CRUD 与依赖

- Agent 从需求/设计文档提取实体、关系及每个 Use Case 的实体 CRUD 操作；每条 CRUD 记录必须包含 `use_case_id`、`entity`、`operation`（C/R/U/D）、`source_step_index`、`source_location`、`evidence` 和 `mapping_status`。
- Tools 校验实体引用、CRUD 值、步骤和定位，不从共享 AR 微服务或仅仅共享实体自动推导业务依赖。
- 有证据的状态/前置依赖只在消费方 CRUD 记录明确引用同实体的前置 C/U 操作，且带有具体依赖依据和来源定位时生成；证据不足只进入 `review_items`。
- CRUD 生命周期图按独立 dependency-graph Skill 的确定规则推导：同实体上每个 R/U/D 用例指向 C 用例，方向表示源用例依赖创建用例。它不使用显式状态依赖声明，也不改变 SSD 调用依赖。
- `er_model.json` 和 `use_case_entity_crud.json` 是结构化语义源；Excel CRUD 矩阵、独立 CRUD JSON/DOT/Markdown/SVG 及系统组成依赖图都可追溯至它们。当前只输出 ER JSON 和 CRUD Excel，不单独绘制 ER 图片。

## 产物

- `system_composition.json/.svg/.png`：参与关系语义与图形。
- `system_composition_dependencies.json/.svg/.png`：用例依赖视图语义与图形，内嵌证据型依赖图和 CRUD 生命周期依赖图两个独立字段。
- `test_scenarios.json`：测试组消费的全量场景记录，覆盖场景清单所有主成功、可选及异常场景；非异常场景的 `prediction_id` 为 JSON `null`。
- `use_case_dependency_graph.json/.svg/.png`：独立的用例依赖图及逐边证据。
- `crud_dependency_graph.json/.dot/.svg`：独立 CRUD 生命周期图，边标注 `R→C`、`U→C`、`D→C` 和实体来源。
- `er_model.json`、`use_case_entity_crud.json`、`use_case_entity_crud_<项目>.xlsx`：实体关系、CRUD 映射、步骤和来源追溯。

SVG 使用 Python 标准库生成；PNG 通过本机可用转换器生成，完整验收可使用 `--require-png`。

## 生成流程与语义 JSON

完整场景流程中无需单独调用图形工具：最终 `assemble` 会基于规范化 `scene_model.json` 自动生成两张系统组成图、用例依赖图、SR Service 依赖图及 JSON/SVG/PNG，并把路径写入 `diagram_manifest.json` 和最终 `run_manifest.json`。建议按主 Skill 的顺序先生成全部 SSD、完成关注点审核，再运行 `assemble --require-png`。

先规范化模型并生成每个用例的 SSD（SSD 根清单是后续关注点规划与 `assemble` 的输入）：

```bash
python .cac/tools/scene_completion.py validate-model \
  --input scene_model.json --output normalized_scene_model.json
python .cac/tools/scene_completion.py generate-ssd \
  --model normalized_scene_model.json --output-dir run/diagrams --render
```

完成关注点审核后，`assemble` 会在 `--output-dir` 中一次性导出图形和语义 JSON；把 SSD 根清单传给 `--ssd-manifest`，以便场景与消息来源可追溯：

```bash
python .cac/tools/scene_completion.py assemble \
  --model normalized_scene_model.json \
  --concern-matrix reviewed_concern_matrix.json \
  --semantic-findings findings.json \
  --ssd-manifest run/diagrams/diagram_manifest.json \
  --spec-document system_spec.md --spec-document design_spec.md \
  --output-dir run/assembled --require-png
```

若只需预览/重绘图形，而不重新组装场景，可运行 `render-diagrams`。系统组成图的 PlantUML 源为可选项；最小输入如下，模型中的所有节点和交互默认纳入校验。请把预览放到独立目录，避免覆盖包含 SSD 用例清单的同名 `diagram_manifest.json`：

```json
{"version":"5","system_composition_diagram":{}}
```

```bash
python .cac/tools/scene_completion.py render-diagrams \
  --model normalized_scene_model.json --input diagram_spec.json \
  --output-dir run/diagram_preview --require-png
```

JSON 的来源与职责如下：

- `system_composition.json`：参与关系图语义；记录 Actor—前端—用例、外部参与关系、节点和布局。
- `system_composition_dependencies.json`：依赖视图语义；保留前端到用例区域的关系，并分别嵌入证据型依赖图和 CRUD 生命周期依赖图及布局。
- `use_case_dependency_graph.json`：证据型依赖关系语义；包含依赖边、操作 ID、来源定位、循环和待确认项。它由显式有证据的依赖声明确定性构建。
- `crud_dependency_graph.json`：CRUD 生命周期依赖权威语义；确定性遵循 R/U/D → C 算法，含操作来源、标签、实体和四元组。
- `er_model.json`、`use_case_entity_crud.json`：分别导出实体/关系和逐用例 CRUD 操作，支持审阅依赖推导输入。
- `diagram_manifest.json`：记录各语义 JSON、SVG、PNG 的路径和状态；最终组装时一并登记 SSD、系统组成图和依赖图产物。
- `test_scenarios.json`：由最终场景目录导出，不是图布局输入；包含主成功、可选、需求异常和关注点异常场景。

单独运行 `render-dependency-graph` 只生成 `use_case_dependency_graph.json/.svg/.png`，不会生成两张系统组成图；完整交付优先用 `assemble`。SVG 为标准库实现，PNG 转换器不可用时 `--require-png` 会失败并提示缺失，不会自动安装依赖。

在 CRUD 生命周期依赖图中，创建实体的根用例排在左侧，读取、更新或删除该实体的子用例排在右侧；箭头仍从子用例指向创建用例，表示其数据依赖方向。系统组成依赖图中的 CRUD 子图遵循相同布局和箭头规则。
