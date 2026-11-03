# 开发约定

Python 3.12+；前端开发Node.js 22。执行`python -m pip install -r requirements-dev.txt`与`npm ci --prefix frontend`安装开发依赖。

| 命令 | 作用 |
|---|---|
| `make format` | Ruff与Prettier统一格式 |
| `make lint` | 后端Ruff、前端ESLint |
| `make test` | 全部离线Python及前端回归 |
| `make check` | 格式、静态检查、类型与测试 |
| `make frontend-build` | 生成由FastAPI服务的网页 |

生产模块按职责snake_case命名；外部入口补类型和可验证校验，注释说明业务隔离和约束依据。前端维持strict；旧API响应的显式any逐功能收敛，新增核心类型不得引入隐式any。Effect触发条件在结构重构中保持，不用自动修复改变执行时机。

`workflow/task_semantics.json`记录任务语义身份。只移动文件、重排导入、格式化或拆组件时不要改身份；改变Schema、来源或业务规则必须更新受影响项并验证下游失效。源码布局不再参与指纹。不得通过删校验、空产物或改状态制造成功。

更新后执行make check。无付费模型的离线验证不能声称客户网关或Windows原生验证成功。
