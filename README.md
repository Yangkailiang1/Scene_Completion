# Scene Completion 场景完整性审核

以用例为单位融合RR/SR，建立系统组成与完整SSD，逐交互匹配关注点，生成异常G、独立抽取已有异常E并输出缺失M。支持业务手动确认中间产物，以及自动运行后集中审核。推荐器保留但未启用。

## Windows x64离线使用

下载Release中的 `scene-completion-windows-x64.zip`，完整解压后双击 `start.cmd`，访问 `http://127.0.0.1:8765`。包内包含CPython 3.12.10、全部Windows依赖、后端、前端和测试，不需要客户联网下载Python或环境包。模型通过内网API提供，不携带模型权重。

在界面新建项目，导入RR、SR及可选测试Markdown；填写OpenAI兼容Base URL、实际模型标识、凭证和并发。客户提供的Qwen/DeepSeek部署须支持tool_calls；名称以其API实际公布的标识为准。模型配置只保存在本地，项目导出不包含密钥。

`check.cmd`检查离线依赖并运行测试。构建包时已经验证Windows wheel匹配及包内文件摘要；原生Windows启动验证应以GitHub Actions记录或客户机器结果为准，不能以macOS测试代替。

## 开发与本地运行

需要Python 3.12。依赖精确锁定在requirements-windows.lock，Windows离线包使用相同版本的Windows wheels。

```sh
python -m pip install -r requirements.txt
python serve.py
python -m pytest -q
```

前端源码使用React / TypeScript / Vite，执行图使用React Flow，基础组件适配shadcn/ui。仓库已提交构建好的web静态文件，由FastAPI本地提供。客户运行无需Node、CDN或联网下载资源；只有开发时需要Node 22：

```sh
npm ci --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

默认只监听127.0.0.1。服务端默认读取仓库根目录`.env`中的`ECNU_BASE_URL`、`ECNU_API_KEY`，请求模型默认`ecnu-plus`；可用`python serve.py --env-file /path/to/.env`指定。项目配置优先，未覆盖项继续读取服务端配置。密钥不返回浏览器、不进入项目或Windows导出包。请求模型与服务端实际返回模型分别保存。

## 实际工作流

1. RR/SR用例目录、系统组成、API映射、API参数并行抽取。用例识别由模型基于正文完成，不依赖固定编号格式。
2. 建立RR/SR用例对应：支持编号不同和一对多；未对应项明确pending，项目不能标为完成。
3. 对每个confirmed用例组，将两层正向描述一起交给建模器，生成完整SSD及RR步骤—SR展开关系。保留整体系统边界、层级、实际调用及逐层返回；没有AR材料不生成AR。
4. 从完整SSD投影RR/SR视图，整理名称—支持操作，再结合API表、组成身份补全交互。
5. 匹配双方及输入/输出数据的关注点，按本次实际操作组合五类功能与数据库/LLM扩展；生成有明确规则的异常G。
6. 检查器并行提取原文异常分支，再绑定融合SSD具体交互、逆向归类和细化E。参数非法可覆盖同交互多个请求细项（含缺失），不覆盖输出。G/E比较输出M及JSON/Markdown报告。测试GT独立绑定、细化后评测。
7. 可选测试GT及抽取Acc评测独立运行。测试操作仅投影对象和支持操作，不向G提供异常答案。推荐器未启用，不生成Q。

Deep Agents实际承担建模器和检查器的任务执行，加载各自Skill并通过工具提交结构化结果。任务依赖由持久化DAG约束；每个Agent只拿到本任务包和独立虚拟文件系统，无宿主文件/其他角色结果访问。共用原有传输、模型额度与并发控制，最多两轮任务修复。

## 三栏执行工作台

中间节点对话区默认占60%、执行图40%，支持调宽、恢复默认和最大化工作区。日志正文至少14px，工具参数默认折叠，输入框在底部。可对节点发指导、提问、回答模型阻断疑问；指导在下一次模型调用生效。旧项目继续运行会保留原记录并创建新版项目。

左侧项目栏可收起，偏好保存在浏览器；中间与右侧可拖动分隔线调整宽度。右侧只读执行图按建模器、检查器、推荐器分组，节点和连线读取调度器实际DAG，支持缩放、平移、用例筛选和定位当前节点。用例对应完成后展开真实用例节点；历史未保存依赖图的运行只展示原状态，不补造连线。

点击节点，在中间查看实时模型正文、工具参数与返回、校验反馈、文件保存、原文依据和审核版本。等待依赖的节点可点击上游定位。产物通过校验后即可预览与下载；未完成工具参数不会被当成产物。推荐器灰色显示“未启用”。阶段由后端提供，不计算虚假的完成百分比。

事件存储在各运行的`execution_events.sqlite3`，先提交后推送；SSE支持`Last-Event-ID`或`after`续接，节点详情按序读取历史。导出包含JSONL事件而不携带数据库锁文件。端点：

- `GET /api/projects/{id}/graph`：实际节点、依赖、文件、阻塞、阶段及耗时。
- `GET /api/projects/{id}/events`：SSE增量；`events/history?task_key=...&after=...`读取节点历史。
- `GET /api/projects/{id}/review-history?task_key=...`：审核版本。

Deep Agents有效提交后由中间件直接结束，避免追加模型轮次。单任务默认最多5次模型请求，最后一次强制提交；无效提交使用执行器原有最多两轮定向修复。失败保留部分输出及完整任务诊断，不提高递归上限、不返回空结果冒充成功。

## 业务审核与保存

手动模式在需要确认的产物停下，先查看图表、字段和原文依据，编辑后“保存并通过”，再“继续运行”。自动模式执行所有可运行任务，同样保留结果供之后审核。可切换两种模式。

审核决定绑定输入摘要和版本，修改结果重新校验Schema、来源及任务边界。旧版本保存在reviews/versions，成功任务缓存有摘要校验。重新执行时只重算受输入或审核修改影响的任务；同一上游payload不会使后续重复调用模型。用例失败不阻止其他用例，GT失败不阻止缺失报告。

界面支持下载JSON、Markdown、可编辑SVG和完整项目ZIP。项目导出包括源文、图表、任务记录和审核版本，排除模型密钥。

## CLI与独立绘图

默认packets只准备任务包，不调用模型。真实运行需显式external及模型配置。

```sh
python .cac/tools/scene_completion.py pipeline \
  --rr-spec-document 在线商城购物系统/系统需求_spec.md \
  --sr-spec-document 在线商城购物系统/功能设计_spec.md \
  --review-mode auto --output-dir runs/project

python .cac/tools/scene_completion.py pipeline \
  --rr-spec-document RR.md --sr-spec-document SR.md \
  --agent-mode external --config workflow.local.json --env-file .env \
  --review-mode manual --output-dir runs/customer

python .cac/tools/scene_completion.py render-composition \
  --input-json COMPONENTS.json --output-svg composition.svg

python .cac/tools/scene_completion.py check-run --run-dir runs/customer
python examples/memory_demo.py --output-dir runs/memory-demo
```

组成绘图恢复历史分区参与关系设计，适配当前JSON；用例为椭圆、人类Actor旁带小人。不会恢复旧CRUD推导或部署猜测。示例明确使用mock，不代表真实模型效果。

协议为 `scene-workflow-v3`，关注点版本为 `interaction-concerns-v3`。旧协议项目升级时创建新版本，原记录保留，旧缓存不直接复用。关注点依据用户2026-10-24新版分类图，当前40个定义（含输入/输出两个抽象族及共享七类数据），不再沿用旧45项。

详见[协议与字段](docs/scene-workflow-v3/protocol.md)、[任务依赖](docs/scene-workflow-v3/workflow-map.md)、[关注点体系](docs/scene-workflow-v2/concern-hierarchy.md)及[验证记录](docs/scene-workflow-v3/validation.md)。
