# 商城五用例 mini 数据集

用于验证已有文件输入、RR/SR融合交互、两层关注点／场景分析和独立测试计分。它是人工设计的测试材料，不代表客户需求或真实评测结论。

包含创建商品、查询商品列表、更新商品、删除商品、发布商品5个用例。RR边界是商家→MiniMallPlatform，SR内部接口是MiniMallPlatform→ProductAdminService，数据库调用是ProductAdminService→外部CatalogDatabaseService；各自身份和请求／返回独立保存。

## 输入文件

| 文件 | 用途 |
| --- | --- |
| `输入文件/系统需求_spec.md` | RR需求，Markdown保留原格式 |
| `输入文件/功能设计_spec.md` | SR设计及接口契约，Markdown保留原格式 |
| `输入文件/structure_model_fusion/RR/structure_model.json` | RR用例目录、主成功描述、已有异常 |
| `输入文件/structure_model_fusion/SR/structure_model.json` | SR结构化需求及已有异常 |
| `输入文件/structure_model_fusion/AR/structure_model.json` | 可选AR结构模型；不默认为本轮权威建模材料 |
| `输入文件/structure_model_fusion.json` | 合并结构视图，保留查看，不冒充额外需求 |
| `输入文件/功能树.json` | 业务实体、属性及接口对应 |
| `输入文件/api_extraction.json` | 10个RR/SR独立接口的已声明参数 |
| `输入文件/recovered_usecases.json` | 独立测试；明确异常进入GT，成功／待定不计入异常集合 |
| `输入文件/行为模型/Product/<用例>/SysOperation.json` | 融合操作段的交互与action定义 |
| `输入文件/行为模型/Product/<用例>/SSD.json` | RR场景及系统操作段对应 |
| `输入文件/行为模型/Product/<用例>/behaviour/IR/*.json` | RR主成功、已有异常和备选 |
| `输入文件/行为模型/Product/<用例>/behaviour/SR/*.json` | SR主成功、已有异常和备选 |

保留5类核心JSON的原文件名；行为文件采用新格式的SysOperation、SSD及behaviour目录。每例4个融合操作段，IR有6个场景、SR有4个场景，共60个行为JSON。5例主成功合计45条有序四元组（含显式本地action）。

## 使用与检查

在网页创建项目或“输入与导入”中选择整个`输入文件`目录，先查看5类核心文件与行为文件的识别结果，再采用所需内容。行为分支提供E材料，不成为GT。完整、有据且通过校验的融合定义可跳过融合SSD模型调用；其他缺项仍由原流程处理。

在本目录运行：

```sh
python validate_dataset.py
```

脚本仅依赖Python标准库，检查用例与接口映射、参与者别名、Order的类型与引用、入口／返回、来源引文及分支关系。此检查证明文件内部一致性，不代替完整流水线及模型质量验收。

数据集随GitHub／Gitee源码发布，位于`datasets/`，不复制进Windows离线程序包。运行数据、模型响应、密钥和用量账本不在此目录。

## 本轮实测

5个用例及全局链路已完成，488个有效节点通过。结果质量待核查项、SR指标和历史累计用量见[验收记录](验收记录.md)及[结构化报告](acceptance_report.json)。
