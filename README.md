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

前端为本地HTML/CSS/JavaScript，服务端使用FastAPI；没有CDN、Node安装或前端依赖下载步骤。默认只监听127.0.0.1。

## 实际工作流

1. RR/SR用例目录、系统组成、API映射、API参数并行抽取。用例识别由模型基于正文完成，不依赖固定编号格式。
2. 建立RR/SR用例对应：支持编号不同和一对多；未对应项明确pending，项目不能标为完成。
3. 对每个confirmed用例组，将两层正向描述一起交给建模器，生成完整SSD及RR步骤—SR展开关系。保留整体系统边界、层级、实际调用及逐层返回；没有AR材料不生成AR。
4. 从完整SSD投影RR/SR视图，整理名称—支持操作，再结合API表、组成身份补全交互。
5. 匹配双方及输入/输出数据的关注点，按本次实际操作组合五类功能与数据库/LLM扩展；生成有明确规则的异常G。
6. 检查器独立提取本用例文档已有异常E；比较G/E，完整语义一一对应计覆盖，部分仅诊断，输出M及JSON/Markdown报告。
7. 可选测试GT及抽取Acc评测独立运行。测试操作仅投影对象和支持操作，不向G提供异常答案。推荐器未启用，不生成Q。

Deep Agents实际承担建模器和检查器的任务执行，加载各自Skill并通过工具提交结构化结果。任务依赖由持久化DAG约束；每个Agent只拿到本任务包和独立虚拟文件系统，无宿主文件/其他角色结果访问。共用原有传输、模型额度与并发控制，最多两轮任务修复。

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

协议为 `scene-workflow-v2`，关注点版本为 `interaction-concerns-v3`。旧协议运行目录必须另开，禁止直接复用。关注点依据用户2026-10-24新版分类图，当前40个定义（含输入/输出两个抽象族及共享七类数据），不再沿用旧45项。

详见[协议与字段](docs/scene-workflow-v2/protocol.md)、[任务依赖](docs/scene-workflow-v2/workflow-map.md)、[关注点体系](docs/scene-workflow-v2/concern-hierarchy.md)及[验证记录](docs/scene-workflow-v2/validation.md)。
