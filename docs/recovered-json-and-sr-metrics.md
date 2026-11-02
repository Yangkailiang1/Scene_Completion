# 恢复用例JSON与SR指标范围

测试输入支持Markdown、XLSX及用例恢复JSON。RR/SR/AR仍使用Markdown。网页新建项目、测试场景版本更新、输入与导入、CLI均使用同一解析与类型筛选。

## JSON结构与原文件追溯

支持根用例数组、`usecases`／`use_cases`／`cases`包装或单用例对象。例如：

```json
[{"id":"REC-001","name":"查询资源列表","preconditions":["资源服务已配置"],"main_success":["读取列表并返回"],"extensions":[
  {"id":"EXT-01","scene_id":"SC@range","condition":"pageSize超过明确上限","expected_result":"拒绝请求，返回错误","note":"分叉点未确定"},
  {"id":"EXT-02","condition":"未传可选参数","expected_result":"按默认值正常查询","note":"成功备选"}
]}]
```

用例必需`id`、`name`、`extensions`（兼容`Extensions`），分支必需`id`、`condition`、`expected_result`。同一用例不允许重复分支ID；不同用例可各自使用`EXT-01`。内部测试ID为“原用例ID::原扩展ID”；原`scene_id`保留，不能因编号相同就认为与需求用例一致。前置条件等未提供时保留空值，不补造。

- 明确的场景类型字段优先。明确标注“成功备选”为正常，仅保留查看。
- 没有类型字段时，根据明示失败预期建立异常索引；含义不明则待确认。“分叉点未确定”只代表交互待绑定，不能直接排除异常。
- 正常、可选及待确认不进入确定GT、匹配请求或指标分母。此索引不是已经完成的关注点或场景GT。
- 保存上传原文件、用例/分支/场景ID、JSON指针和真实物理行号。单行JSON的分支均在真实第1行，分支模型任务只携带当前分支字面片段。
- 文件内EV@等未上传资料标记仅作为原文数据，不虚构外部文档行号。主成功路径只用于测试用例对应背景，不作为正向SSD、G或推荐依据。

## 可以节省哪些调用

| 节点 | 接入结构化恢复JSON后的行为 |
|---|---|
| 测试目录 `test-inventory` | 工具直接解析，不调用LLM重复抄写用例与扩展分支 |
| 测试与需求用例对应 `test-case-align` | 明确且唯一的编号与目标可精确核验；否则仍由模型对应，不仅凭编号判断 |
| 测试关注点 `test-concerns` | 仍须按异常分支独立定位实际交互、接口/职责和四要素，识别关注点 |
| 具体测试场景 `test-ground-truth` | 仍须细化独立失败条件、规范化并保留原分支来源 |
| 关注点规则匹配、场景比较、评测 | 仍须执行；已验证的确定性匹配及缓存按现有规则复用 |
| 机器测试补全与扩展GT | 默认停用；不会因JSON导入自动启用 |
| 系统组成、API、融合SSD、正向规则、G | 不能用测试逆向结果替代；可复用与当前正向输入和契约一致的已有正式产物 |

## SR指标范围

网页结果默认选择SR；可切换RR或全部。CLI新建项目默认`--evaluation-scope SR`；旧项目及既有冻结报告不改写，旧REST创建接口未传参数时保留`all`兼容行为。结果接口可显式传`scope=SR|RR|all`。

SR范围由**实际关联接口的定义来源、调用双方和校验职责**判定，不识别`/v1`、`/mx`、`/ms`前缀。两次不同调用各自定位；RR/SR同一次调用的重复视图即使统一为SR交互ID，若实际接口仍属于RR，不纳入SR分母。内部Service实际调用没有接口声明时保留明确的SR内部交互；无法确定归属的列为待确认，不猜测。

请求及其返回使用同一接口归属，输入和成功输出数据关注点分别保留。测试异常按明确的实际检查职责绑定，不能将下游约束或异常上移到入口请求。

筛选同时限定G/E/GT及缺失M、推荐Q，复用已保存完整匹配重算分子/分母，不调用模型、不重新排序Q、不覆盖旧报告。推荐前全部M与推荐后Q同范围比较；尚无GT为未评测，空分母为不适用。其他范围交互仍可查看，并显示不参与当前计分。全局业务级无接口层标签，独立展示，不混入SR接口汇总。

```bat
scene.cmd create --name "SR异常验收" --rr RR.md --sr SR.md --test recovered_usecases.json --evaluation-scope SR
scene.cmd metrics --project PROJECT_ID --scope SR --test-set original
scene.cmd metrics --project PROJECT_ID --case G-001 --scope SR --test-set original
```

接口：`GET /api/projects/PROJECT_ID/results/metrics?scope=SR&test_set=original`；单用例及项目汇总分别使用`results/CASE_ID`、`results/project-metrics`，同样支持`scope`。

自动诊断使用项目保存的指标范围，新项目SR结果与诊断一致。历史报告保留原口径；切换界面范围仅改变查看范围。
