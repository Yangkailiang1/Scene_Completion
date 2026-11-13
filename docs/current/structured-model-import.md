# RR／SR结构模型接入

结构模型是已经抽取的需求材料，不是测试GT。支持JSON根对象包含：

```json
{
  "schema_version": "3",
  "scope": {"model_level": "RR"},
  "entities": [
    {"entity_id": "case-1", "entity_type": "use_case", "use_case_id": "UC-1", "canonical_name": "查询列表"},
    {"entity_id": "scene-1", "entity_type": "scenario", "scenario_kind": "main_success", "steps": ["开发者向平台请求列表"], "expected_result": "返回列表"},
    {"entity_id": "scene-2", "entity_type": "scenario", "scenario_kind": "exception", "steps": ["必填参数未提供"], "expected_result": "拒绝请求"}
  ],
  "relations": [
    {"relation_type": "associated_with_usecase", "source_entity_id": "scene-1", "target_entity_id": "case-1"},
    {"relation_type": "associated_with_usecase", "source_entity_id": "scene-2", "target_entity_id": "case-1"}
  ]
}
```

SR文件使用 `scope.model_level=SR`。不根据文件名、用例编号或URL前缀判断层级。支持带缩进及单行JSON；重复实体ID、重复用例ID、未绑定场景和多重场景归属会明确报错，不静默丢失数据。

## 使用方式

在项目“输入与导入”上传两份JSON。详情显示所属层、用例数、主成功路径数、原标注异常分支数和其他分支数。唯一结构版本默认启用，仅在下一次显式执行时接入；上传、启停都不会自动发起模型请求或替换在途任务。存在多个同层版本时，先停用非当前版本。

新项目也可以将结构模型JSON直接作为RR／SR来源上传；上传位置必须与文件声明层级一致。原Markdown输入继续兼容。CLI原有 `create --rr/--sr` 及 `input-scan`、`imports` 同样可使用这些文件，无需另一套执行器。

## 转换及能跳过的节点

| 同事JSON内容 | 正式产物 | 执行方式 |
| --- | --- | --- |
| `use_case`实体及关联主成功路径 | `rr-use-cases`、`sr-use-cases`中的`cases` | 工具直接转换、校验，跳过该层目录模型抽取 |
| `scenario_kind=exception`，经关系表绑定用例 | 每用例`existing-branches`中的`branches` | 工具直接转换、校验，跳过分支发现模型抽取 |
| `main_success` | 该用例正向材料 | SSD模型仍需据此建立最小双方交互 |
| `alternative`及其他非异常分支 | 原文件及导入详情的保留记录 | 不自动转成异常E或GT |

目录保留全部原用例。例如RR14例、SR20例时，保留两层目录的实际数量，不裁剪成14对；用例对应任务独立确认对应或待定。没有明确参与者时保留空列表，不补造Actor。

完整SSD、RR／SR展开对应、已有异常的实际交互绑定、关注点识别和细化仍需执行。这两份文件不能单独跳过完整API参数、实体约束或关注点结果的生成。API表、功能树和测试逆向JSON仍各自使用独立导入／分析通道。

已有异常分支进入后续流程时，继续执行统一场景类型筛选。原标注异常数量不等于最终计分数量；普通取消、允许的正常空列表等已有排除规则仍保留。

## 来源和隔离

工具生成带JSON属性位置的可读投影，引用其中的真实行。查看来源时可打开原JSON文件并查看`/entities/N/...`位置。投影行号明确属于可读投影，不冒充原始spec或JSON物理行号；原始字节保存在项目中，不改写上传文件。

`source_inputs`、`evidence.quote`、`trace_anchors`及旧基线`review_items`仅保存在原文件，不注入正向模型，不要求访问未提供的RR/SR原文件。原分支仅进入已有异常通道；测试仍走独立用例对齐与GT通道。

与原Markdown并存时，共享API、实体等任务保留其允许的正向材料；目录与逐用例流程采用所选结构版本，避免反复全文解析。不会因结构导入而将测试答案或已有异常复制进G。

成功复用记录保存在任务执行元数据及导入采用记录中，执行图标注“已有文件输入”。新来源改变时按真实任务输入使受影响节点失效；旧报告和运行数据不删除。
