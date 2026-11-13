# 开发约定

Python 3.12+；前端开发Node.js 22。执行`python -m pip install -r requirements-dev.txt`与`npm ci --prefix frontend`安装开发依赖。

| 命令 | 作用 |
|---|---|
| `make format` | Ruff与Prettier统一格式 |
| `make lint` | 后端Ruff、前端ESLint |
| `make test` | 全部离线Python及前端回归 |
| `make test-portable` | 可交付环境的便携测试集合 |
| `make check` | 格式、静态检查、类型与测试 |
| `make frontend-build` | 生成由FastAPI服务的网页 |

生产模块按职责snake_case命名；外部入口补类型和可验证校验，注释说明业务隔离和约束依据。前端维持strict；旧API响应的显式any逐功能收敛，新增核心类型不得引入隐式any。Effect触发条件在结构重构中保持，不用自动修复改变执行时机。

`workflow/task_semantics.json`记录任务语义身份。只移动文件、重排导入、格式化或拆组件时不要改身份；改变Schema、来源或业务规则必须更新受影响项并验证下游失效。源码布局不再参与指纹。不得通过删校验、空产物或改状态制造成功。

更新后执行make check。无付费模型的离线验证不能声称客户网关或Windows原生验证成功。

## 验证与发布边界

Python测试分为`tests/unit`、`integration`、`contracts`、`acceptance`和`portable`，共享构造器在`tests/support`，数据在`tests/fixtures`；前端测试随功能组件放置。不要由一个测试模块导入另一个测试模块充当工具。

`web/`由前端构建成套生成，index、哈希资源、懒加载组件及许可证一起发布；只替换部分文件会使已打开页面的动态资源失效。`deployment/windows/`提供程序包模板，`deployment/experiments/`不进入正常发布路径。打包使用显式清单；历史文档、实验与本机运行数据不应因目录递归复制混入程序包。

发布和原生Windows验证见[Windows说明](../current/windows-portable.md)。目录整理不自动移动`.workbench`、`runs`、`dist`的既有产物，也不修改报告、账户、额度和审核历史。

完整开发测试通过 `tests/conftest.py` 自动切换到临时工作目录；仓库 fixture 只从 `tests/support/paths.py` 定位，默认运行日志不写入用户 `runs/`。缺少 Node/jsdom 时 HTML 回归明确失败。Windows 交付包只执行 `tests/portable`，不包含依赖开发数据集的完整回归。兼容样例分别保留提交 bundle、准备后的快照和细化 E 后的快照；文件名不表达协议版本。
