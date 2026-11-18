# 核心输入与补充文件

输入根目录有 `architecture.json`、功能树、可选接口及测试逆向数据和原始文档。每个用例目录有以下核心文件。

| 文件 | 内容 |
| --- | --- |
| `main-success.json` | 稳定步骤 ID、顺序、发送方、操作、实体、接收方。响应可引用请求 `parent_id`。接口字段单独存为 `declared_fields`。 |
| `existing-exceptions.json` | E，含条件、预期、`step_id`、`target`、`concern_key` 和原文定位。实际检出位置可存为 `failure_step_id`。 |
| `extension-mapping.json` | 每个测试扩展一条记录，保留异常、正常、范围外和待确认的分类。已确认异常以 `bindings` 记录每条独立挂载。 |
| `test-exceptions.json` | 从已确认测试扩展挂载派生的 GT。 |
| `source-map.json` | 转换时的源文件、JSON Pointer 及原文引用。 |

同一用例的同一实体、属性和关注点可跨步骤匹配。接口字段按实际步骤和方向对应。用例级代码相同时仍应区分 RR／SR接口。比较前保留独立失败条件及出处。

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
