# 核心输入与补充文件

以独立目录保存一个项目，分别保留外部材料、转换版本、运行和交付件。

```text
<项目>/
├── source/
├── core/<revision>/
│   ├── architecture.json
│   ├── 功能树.json
│   ├── recovered_usecases.json       # 有测试来源时
│   ├── source-documents.json         # 有自定义文档角色时
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
`extension-mapping.json` 用 `source_uc_id` 和 `extension_id` 保留测试来源身份，
每条扩展都可追查。已确认的绑定派生 `test-exceptions.json` 中的 GT。
缺测试的用例仍保留分件，并显示未评估。
`source-map.json` 对应输入目录中的相对路径和源 JSON Pointer。原始 Markdown 和 XLSX 随
转换版本保存供工作台和离线报告核验。若文件名无明显角色，在来源根目录提供
`source-documents.json`，例如
`{"documents":[{"path":"spec-a.md","role":"RR","aliases":["rrSpec"]},{"path":"design-b.md","role":"SR","aliases":["srSpec"]},{"path":"testcase.xlsx","role":"test"}]}`。
功能树中，接口字段和实体属性的每条 `constraints[]` 用自身的 `source.doc`、`line` 和 `quote` 定位。
字符串标签和类型沿用所在字段的 `source`。若标签以 `{"name":"必填","source":{...}}` 提供，优先用标签自身的出处。
`line` 为原件的全文件行号。引文与声明位置不符时，只在同一文件内凭唯一引文重定位，否则保留声明位置并标记待核对。

`core-input convert` 默认输出 `analysis_profile=command-interaction-v3`。
用例按三份材料的名称对齐。命令在同一用例内按 apiId 合并 RR 方法和 SR 字段，再按证据或模型结果绑定主成功步骤。模型无法唯一定位时挂到首步并保留回退理由。同用例同一实际命令只设一个主挂载，重复调用保留出处。实体约束和接口字段约束同时挂载，只有带明确映射及等价作用域的规则合并计分。接口字段在接口首次调用处展开。实体约束挂在第一个使用该实体的接口，缺少对应接口时挂在首次出现处。原始校验、响应和失败位置保留。
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

修改用例内文件时另填 `case_id`，`id` 对应步骤、E 或测试扩展的稳定 ID。证据也可用 `{ "file": "...", "json_pointer": "/..." }`。修改测试映射后，工具重建对应 GT；提交的绑定需给出失败条件和预期。对实体属性使用 `entity_id`、`attribute`，对已定位接口字段使用 `parameter.name`、`location`、`direction`。普通条件缺少具体数值时保留一般失败条件或待确认。

合成单用例及其三份来源格式见 [浏览商品样例](../../../../datasets/mini-mall/examples/browse-product/README.md)。
