> 当前协议：**scene-workflow-v4**。关注点识别与具体场景生成分开保存和计分，说明见[两层协议](docs/scene-workflow-v4/protocol.md)。旧项目保留；继续运行会建立升级副本，旧场景结果不会直接作为新关注点识别。

# Scene Completion 场景完整性审核

以用例为单位融合RR/SR，建立系统组成与完整SSD，逐交互匹配关注点，生成异常G、独立抽取已有异常E并输出缺失M。支持业务手动确认中间产物，以及自动运行后集中审核。推荐器在新版规则下按缺失M执行风险保底排序。

## Windows x64离线使用

下载Release中的 `scene-completion-windows-x64.zip`，完整解压后双击 `start.cmd`；启动器就绪后会打开浏览器，访问 `http://127.0.0.1:8765`。包内包含CPython 3.12.10、全部Windows依赖、后端、前端和测试，不需要客户联网下载Python或环境包。模型通过内网API提供，不携带模型权重。

在界面新建项目，导入RR、SR及可选测试Markdown；填写OpenAI兼容Base URL、实际模型标识、凭证和并发。客户提供的Qwen/DeepSeek部署须支持tool_calls；名称以其API实际公布的标识为准。模型配置只保存在本地，项目导出不包含密钥。

端口占用时可运行`start.cmd --port 8766`。模型可在网页配置，也可复制包根目录`.env.example`为`.env`后填写。数据保存在包根目录`data/`，源码提交见`VERSION.json`。

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

默认只监听127.0.0.1。服务端默认读取仓库根目录`.env`中的`ECNU_BASE_URL`、`ECNU_API_KEY`，请求模型默认`ecnu-plus`；可用`python serve.py --env-file /path/to/.env`指定。项目配置优先，未覆盖项继续读取服务端配置。密钥不返回浏览器、不进入项目或Windows导出包。请求模型与服务端实际返回模型分别保存。连接／首响应等待、流中无数据等待、整次生成时限可分别设置：流式默认无数据300秒、总生成900秒，不再把原120秒直接当大产物总时限。超时不自动重POST，错误显示发生阶段及已接收增量；输出上限不等于保证输出长度。

## 实际工作流

1. RR/SR用例目录、系统组成、API映射并行抽取；API目录由映射完整建立后，并行抽取各接口参数。用例识别由模型基于正文完成，不依赖固定编号格式。
2. 建立RR/SR用例对应：支持编号不同和一对多；未对应项明确pending，项目不能标为完成。
3. 对每个confirmed用例组，将两层正向描述一起交给建模器，生成完整SSD及RR步骤—SR展开关系。保留整体系统边界、层级、实际调用及逐层返回；没有AR材料不生成AR。
4. 从完整SSD投影RR/SR视图，整理名称—支持操作，再结合API表、组成身份补全交互。
5. 按实际请求整理独立正向正常规则，再匹配双方及输入/输出关注点，按本次实际操作组合功能与技术扩展。规则、关注点按交互，逆向处理按原分支拆分缓存与审核；生成可执行项和有明示依据的条件级异常G。
6. 检查器并行提取原文异常分支，再绑定融合SSD具体交互、逆向归类和细化E。参数非法可覆盖同交互多个请求细项（含缺失），不覆盖输出。G/E比较输出M及JSON/Markdown报告。测试GT独立绑定、细化后评测。
7. 可选测试GT及抽取Acc评测独立运行。测试操作仅投影对象和支持操作，不向G提供异常答案。新版在M就绪后确定性推荐Q，GT只用于独立评测。

Deep Agents实际承担建模器和检查器的任务执行，加载各自Skill并通过工具提交结构化结果。任务依赖由持久化DAG约束；每个Agent只拿到本任务包和独立虚拟文件系统，无宿主文件/其他角色结果访问。共用原有传输、模型额度与并发控制，最多两轮任务修复。

## 三栏执行工作台

中间结果与节点对话区默认占84%、右侧紧凑任务导航16%，支持调宽、恢复默认和最大化工作区。日志正文至少14px，工具参数默认折叠，输入框在底部。可对节点发指导、提问、回答模型阻断疑问；指导在下一次模型调用生效。旧项目继续运行会保留原记录并创建新版项目。

左侧项目栏可收起，偏好保存在浏览器；中间与右侧可拖动分隔线调整宽度。右侧导航按建模器、检查器、推荐器分组；完整只读执行图可按需展开，节点和连线读取调度器实际DAG，支持缩放、平移、用例筛选和定位当前节点。用例对应完成后展开真实用例节点；历史未保存依赖图的运行只展示原状态，不补造连线。

点击节点，在中间查看实时模型正文、工具参数与返回、校验反馈、文件保存、原文依据和审核版本。等待依赖的节点可点击上游定位。产物通过校验后即可预览与下载；未完成工具参数不会被当成产物。推荐节点按真实M依赖显示，旧版本仍显示“未启用”。阶段由后端提供，不计算虚假的完成百分比。

API映射与参数在页面合并为**API接口总表**：服务名称、API名称、方法、地址及输入／输出参数的类型、必填性、默认值和约束同表展示，可下载JSON/Markdown。内部仍保留服务归属与按接口参数子任务以复用成功结果。总表会显示已完成、待审核和未提取状态；接口身份只按一致ID或双向唯一的地址对应，歧义保留待确认。接口目录节点单独展示标识、名称和原文范围，不能当成参数表。产物预览异常只影响本预览，不会清空工作台。

事件存储在各运行的`execution_events.sqlite3`，先提交后推送；SSE支持`Last-Event-ID`或`after`续接，节点详情按序读取历史。导出包含JSONL事件而不携带数据库锁文件。端点：

- `GET /api/projects/{id}/api-catalog`：合并总表；`?format=json`或`?format=md`下载并保存当前版本，包含中间结果状态。
- `GET /api/projects/{id}/graph`：实际节点、依赖、文件、阻塞、阶段及耗时。
- `GET /api/projects/{id}/events`：SSE增量；`events/history?task_key=...&after=...`读取节点历史。
- `GET /api/projects/{id}/review-history?task_key=...`：审核版本。

系统组成直接使用完整正向RR/SR输入，不重复读取文件。默认采用JSON文本流，适配网关大工具参数迟迟不返回的情况；完整JSON再交给同一提交工具校验并审核，阻断疑问仍进入用户回答流程。可通过服务配置`component_submission_mode=tool_calls`使用工具参数流；两种模式都不接受截断结果。实际请求流断开会显示“模型流中断，可继续”，保留已收字节、模型及完成标记。

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

本轮质量修订与内嵌用量API见[规则说明](docs/scene-workflow-v3/quality-rules-20261025.md)。用量与费用在当前工作区展示，默认轻量统计，原文上下文及请求详情按需加载；单价配置仅给出估算，实际扣费无依据时显示未知。

异常指标只统计类型为“异常”的测试，正常、可选和待确认不参与匹配。最终结果可切换原始/扩展异常测试集，扩展集由独立正向材料补充后自动计分；集合扩充不代表生成质量提升。测试支持Markdown与XLSX，含预览、单元格定位和项目版本切换；[商城Excel示例](examples/tests/mall-exception-tests.xlsx)及[接口/隔离/Token说明](docs/scene-workflow-v3/exception-tests-and-excel.md)可直接使用。

详见[协议与字段](docs/scene-workflow-v3/protocol.md)、[任务依赖](docs/scene-workflow-v3/workflow-map.md)、[关注点体系](docs/scene-workflow-v2/concern-hierarchy.md)及[验证记录](docs/scene-workflow-v3/validation.md)。

项目审核新增“待确认项”和“关注点设置”：按项目保存定义版本与历史报告，支持是否为异常及分类审核；保存审核不会自动调用模型。参见 [项目审核说明](docs/scene-workflow-v3/project-review.md) 和 [质量修订验收](docs/scene-workflow-v3/quality-acceptance-20261025.md)。

最终结果可按用例和具体交互查看发送方、操作、数据、接收方，并列对照需求已有E、生成G、测试GT及缺失标记；图表总览集中预览和下载已抽取图表。待确认项默认只显示异常/归类疑问，规则未声明及结构核查单列，不把内部诊断当作已发现异常。

## 细粒度场景与风险保底推荐
新版网页增加“模式与风险”和“最终结果 → 风险推荐”。关注点下可以有多个异常模式，按具体交互与正向约束实例化；关键低置信候选先待审。推荐只使用缺失M、风险及项目已人工审核历史，不使用测试GT排序。原始/扩展测试分别评测，人工采纳率单列。

详见 [方法、接口、版本与审核边界](docs/scenario-pattern-recommender.md)。旧Windows Release及旧报告保持可读，本轮不制作新Windows包。

## Code Agent CLI与多API Key模型配置

启动`serve.py`后，可用`python scene.py projects/create/configure/run/status/events/artifacts`操作同一个网页工作台。`run --wait`输出JSONL进度，网页实时查看同一节点、事件和文件。更多操作中的模型设置支持多个API Key连接，每个连接维护独立模型允许列表；项目从对应下拉框选模型。

命令示例、凭证保存方式和运行边界见[CLI与模型连接说明](docs/workbench-cli-model-accounts.md)。结果控制区可收起，默认保留紧凑的快捷选择栏。

“模式与风险”和“用量与费用”提供紧凑配置及具体任务瓶颈排行；最终图表增加可下载的SysML BDD。[BDD及用量排行说明](docs/bdd-and-usage-rankings.md)。

当前两层流程使用 `scene-workflow-v4`，此前v2/v3说明及报告保留为历史记录。用量页可整页滚动，并区分累计成本与单次请求峰值；关注点设置按分类树组织，输入/输出共用稳定定义。默认请求上下文上限为200,000 Token，完整请求及输出预留在发送前检查。定向样本对比、质量门禁及未启用的测试补全实验见[上下文优化与网页验收](docs/scene-workflow-v4/context-optimization.md)。
