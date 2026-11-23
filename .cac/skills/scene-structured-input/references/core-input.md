# 核心输入与补充文件

源码入口、逐字段映射与可回放例子见[默认 SSD 代码路线](../../../../docs/architecture/ssd-walkthrough.md)。以独立目录保存一个项目，分别保留外部材料、转换版本、运行和交付件。

```text
<项目>/
├── source/
├── core/<revision>/
│   ├── architecture.json
│   ├── 功能树.json
│   ├── recovered_usecases.json       # 有测试来源时
│   ├── source-documents.json         # 来源已提供清单时
│   ├── <登记或引用的原始 Markdown／XLSX>
│   └── cases/<用例ID>-<用例名>-<短标识>/
│       ├── main-success.json
│       ├── existing-exceptions.json
│       ├── extension-mapping.json
│       ├── test-exceptions.json
│       └── source-map.json
├── workbench/
└── delivery/
```

用 `main-success.case.id` 引用用例。目录名称仅用于浏览。参与者由
`architecture.elements[].id` 引用，使用 `external_actor`、`external_service`、
`internal_service`，数据库另填 `technology=database`。步骤 ID 按原节点保持稳定。
`main-success.function_tree.uc_id` 指向功能树用例，`steps[].entities` 指向其中的实体。
`operation.crud` 为增、查、改、删的枚举数组，空数组有可能表示校验或返回。由模型
判断的操作会说明依据。功能树 SR 命令的 HTTP 方法和步骤原文用于判断操作语义。

`existing-exceptions.json` 记录 E 的原始异常分支和失败位置。
在 `extension-mapping.json`，根字段 `source_uc_id` 指向 recovered 来源用例，
`items[].extension_id` 指向该用例的扩展，并与 `test-exceptions.exceptions[].extension_id` 关联。
测试分件可有已确认绑定和待分类记录。每条扩展引用的证据在该用例的 `evidence_locations` 查证。
缺测试的用例仍保留分件，并显示未评估。
`source-map.json` 对应输入目录中的相对路径和源 JSON Pointer。原始 Markdown 和 XLSX 随
转换版本保存供工作台和离线报告核验。若文件名无明显角色，在来源根目录提供完整的原件清单
`source-documents.json`，例如
`{"documents":[{"path":"spec-a.md","role":"RR","aliases":["rrSpec"]},{"path":"design-b.md","role":"SR","aliases":["srSpec"]},{"path":"testcase.xlsx","role":"test"}]}`。
功能树中，接口字段和实体属性的每条 `constraints[]` 用自身的 `source.doc`、`line` 和 `quote` 定位。
字符串标签和类型沿用所在字段的 `source`。若标签以 `{"name":"必填","source":{...}}` 提供，优先用标签自身的出处。
`line` 为原件的全文件行号。声明位置无效或与引文不符时，使用 `quote` 在同一文件中全文定位。每个命中都有独立的实际行区间和查看入口。原件缺失或全文未找到引文时保留结构化出处和原因。

`core-input convert` 默认输出 `analysis_profile=command-interaction-v3` 和 `interface_field_policy=sr-input-by-name-v1`。功能树的 SR 命令属性按接口 ID 和字段名挂载到 SysOperation 声明的主调用步，字段直接作为发送数据处理。无需推断字段位置或方向，原文行号及 Excel 坐标仍用于追溯。
用例按三份材料的名称对齐。转换脚本按同用例的 SR apiId 建契约，合入可用 RR 方法与路径，用明确调用证据挂载。正式运行的 ssd-resolve 处理剩余的语义定位，仍无法唯一定位时挂到首步并保留回退理由。同用例同一实际命令只设一个主挂载，重复调用保留出处。实体约束和接口字段约束同时挂载，只有带明确映射及等价作用域的规则合并计分。接口字段在接口首次调用处展开。实体约束挂在第一个使用该实体的接口，缺少对应接口时挂在首次出现处。原始校验、响应和失败位置保留。
E 与 GT 分别识别，跨步骤对齐同一义务时保留实际失败步骤。
第三层和数据库存量数据有效性暂停生成。
`--profile entity` 读取仅实体模式，`--profile compat` 用于旧适配输入。


补充文件只对 `inspect` 列出的输入版本有效。示例将源角色 U 确认为人类 Actor：

```json
{
  "version": "core-input-overrides-v1",
  "input_hash": "<inspect 返回的哈希>",
  "patches": [
    {
      "file": "architecture.json",
      "id": "U",
      "set": { "kind": "external_actor" },
      "evidence": [
        {
          "file": "系统需求_spec.md",
          "start_line": 20,
          "end_line": 20,
          "quote": "<替换为原文>"
        }
      ]
    }
  ]
}
```

修改用例内文件时另填 `case_id`，`id` 对应步骤、E 或测试扩展的稳定 ID。证据也可用 `{ "file": "...", "json_pointer": "/..." }`。修改测试映射后，工具重建对应 GT；提交的绑定需给出失败条件和预期。对实体属性使用 `entity_id`、`attribute`，对已定位接口字段使用 `parameter.command_id` 和 `parameter.name`。普通条件缺少具体数值时保留一般失败条件或待确认。

合成单用例及其三份来源格式见 [浏览商品样例](../../../../datasets/mini-mall/examples/browse-product/README.md)。
