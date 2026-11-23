# Mini-mall 浏览商品单用例

这是独立的合成用例，编号 `UC-BROWSE-01`。工作台以行为模型中的 `operations`、`Order` 和参与者为主成功流。功能树的 `srLayer.commands` 定义两个接口，`srLayer.entities` 定义实际涉及的实体。测试逆向以 `extensions` 和 `evidence_locations` 保留来源，通过测试原文中的行号核对。

| 步骤 | 行为 | 命令 |
| --- | --- | --- |
| B1 | 顾客向商城发起浏览请求 | BROWSE-GET |
| B2 | 商城校验入口查询参数 | 校验 B1 |
| B3 | 商城向目录服务发起查询 | CATALOG-SEARCH |
| B4 | 目录读取商品数据 | 本地读取 |
| B5、B6 | 目录返回商城，商城返回顾客 | 返回 |

`pageSize` 的两个边界失败在 B1 分别进入三方表，实际校验保留 B2。商品实体约束在 B3 展开，B4 保留读取步骤。分类编号的接口和实体约束带显式等价证据，合并同一格式义务。测试中合法边界属于正常结果。测试独立的关键词长度边界用于验证 GT 独有场景。入口允许匿名访问。

从源码离线复现全部五个节点和新报告，执行 `python -m pytest -q tests/acceptance/test_browse_product_route.py`。它使用本地测试模型。[字段追踪、命令与排障](../../../../docs/architecture/ssd-walkthrough.md)

使用已授权项目模型时，在仓库根目录执行：

```sh
SOURCE=datasets/mini-mall/examples/browse-product
python scene.py core-input inspect --input "$SOURCE" --case UC-BROWSE-01
python scene.py core-input convert --input "$SOURCE" --output PATH/core/001 --case UC-BROWSE-01
python scene.py core-input validate --input PATH/core/001 --case UC-BROWSE-01
python scene.py --local --data-dir PATH/workbench create --name "Mini-mall 浏览商品" --input-dir PATH/core/001 --adopt-partial --case UC-BROWSE-01
python scene.py --local --data-dir PATH/workbench run --project PROJECT_ID --case UC-BROWSE-01 --wait
```

配置已获授权的模型后再执行最后一条命令。启动本地工作台后，在最终结果查看四元组、三方匹配及来源，在审核交接导出离线报告。
