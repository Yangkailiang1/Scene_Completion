# 交给 Coding Agent 的项目执行提示词

将下方内容发给你的终端 Coding Agent，并提供解压目录、实际输入目录、目标用例以及已授权的模型账号。示例命令使用 Windows CMD，请把路径和 ID 换成实际值。

## 项目任务

请使用此 Windows 离线包里的场景完整性工作台，把我指定的用例从结构化输入跑到 E／G／GT 三方结果，核对结果和原文定位，导出业务审核 HTML。请执行并跟进到完成。只有在缺少材料、业务判定、模型授权或额度时请我处理，并说明受影响的用例或批次。

### 1. 确认环境和输入

- 在当前包根目录执行 `scene.cmd capabilities` 和 `check.cmd`。工作台默认使用包根目录的 `data` 与 `.env`。使用完整路径指定数据目录，确保 CLI、工作台及恢复命令访问同一份项目。
- 把用户提供的 `功能树.json`、`recovered_usecases.json` 和整个行为模型目录放进本次输入目录。保留 `行为模型/<实体>/<用例>/SysOperation.json` 层级。分别使用 `SysOperation.use_case`、功能树 `functions[].name` 和测试逆向的 `name` 对齐用例，保留各文件自己的编号。实体目录帮助区分同名用例。
- 向用户取得每份原始 RR／SR Markdown、测试 Markdown 和 XLSX 的实际路径，把原件复制到输入目录并保持约定的文件名。把文件的输入目录相对路径、角色和引用别名写入根目录的 `source-documents.json`。结构化来源使用文件名或登记别名定位。配置示例如下。
  `{"documents":[{"path":"originals/需求.md","role":"RR","aliases":["rrSpec"]},{"path":"originals/设计.md","role":"SR","aliases":["srSpec","sr"]},{"path":"originals/测试用例.xlsx","role":"test","aliases":["testcase.xlsx"]}]}`
- 检查 Markdown 引文的 `location`，例如 `L1726-L1726`。Excel 坐标必须是 `测试用例!A120:O120` 这样的实际范围。对于同名文件、找不到的原件、坐标错误或引文不一致，逐条记下受影响的记录并请用户核对。
- 依据主成功流、功能树和已验证来源运行 G。读取 E 与 GT 时使用独立来源。检查每条测试扩展的识别与挂载结果，报告已挂载、正常、范围外及待确认数量。
- 先查 `app/.cac/skills/scene-structured-input/SKILL.md`；已提供核心 JSON 时直接校验。格式有差异时先盘点，只用有原始证据的字段补齐转换，遇到歧义保留待确认。

```bat
cd /d "C:\Scene Workbench"
scene.cmd core-input inspect --input "C:\Project\source" --case CASE_ID
scene.cmd core-input convert --input "C:\Project\source" --output "C:\Project\core\001" --case CASE_ID
scene.cmd core-input validate --input "C:\Project\core\001" --case CASE_ID
```

转换结果放在独立版本目录。多用例项目重复传入 `--case` 选择多个用例，或在盘点和转换时省略它。保留完整目录与来源文件。用 JSON 输出的 `issues` 检查阻塞项，使用校验结果中的实际用例 ID。

### 2. 建档、单用例试跑和并发

以下命令使用整个已校验的核心目录建档。记录命令返回的项目 ID，已有项目用 `projects` 查找。运行前通过网页模型设置选取获授权的账号，或使用包根目录的本地 `.env`。确认模型与额度后再开始推理。

```bat
set "DATA=%CD%\data"
set "SCENE_ENV=%CD%\.env"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" create --name "示例项目" --input-dir "C:\Project\core\001" --adopt-partial
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project PROJECT_ID --case CASE_1 --wait
```

- 逐个跑时，等当前用例退出后，对下一用例执行同一个 `run --case`。同一份项目保留各用例发布结果。单用例返回只核验本轮范围，再用结果命令检查目标列表是否齐全。
- 并发跑时，在同一个项目 worker 内调度多个选中用例。按已授权的账号并发限制配置槽位，例如 `configure --project PROJECT_ID --concurrency 2`，然后一次运行 `run --project PROJECT_ID --case CASE_1 --case CASE_2 --wait`。全部用例可用 `--all-cases`。在这两条命令的子命令前加上同样的 `--local --data-dir "%DATA%" --env-file "%SCENE_ENV%"`。调度会等待每个节点的依赖就绪，实际并发受账号、网关和额度约束。
- 同一项目共用 worker 与项目锁。已在运行时用 `status` 查看，或用相同范围的 `run --wait` 继续观察。执行退出码 0 后检查 `execution_complete` 和 `review_complete`，两者分别反映执行与业务审核。退出码 2 时诊断，退出码 3 时先查 worker 状态，等待超时后 worker 可能仍在运行。

### 3. 接管失败节点

先看 `app/.cac/skills/scene-terminal-recovery/SKILL.md`。从 `status` 取得节点 ID，再查看诊断里的错误、交接类型和批次标识。以下代码以失败的生成节点为例。多批次必须使用实际的失败批次 ID；仅有一个批次时可以省略 `--batch`。

```bat
set "NODE=CASE_1:ssd-generate"
set "BATCH=FAILED_BATCH_ID"
set "REPAIR=C:\Project\node-repair.json"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" status --project PROJECT_ID
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" diagnose --project PROJECT_ID --node "%NODE%"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" repair-export --project PROJECT_ID --node "%NODE%" --batch "%BATCH%" --out "%REPAIR%"
```

对有模型交接包的失败，仅编辑导出包中的 `payload` 和 `note`，保留绑定身份、输入和 Schema。G 修复只看允许的正向材料，E 与 GT 分别使用各自的独立上下文，比较节点仅看它指定的两侧。按冻结 Schema、来源、字段、锚点与固定模板完成修复，未知事实保留待确认。确认 worker 已结束后先校验，校验成功再正式提交。

```bat
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" repair-submit --project PROJECT_ID --node "%NODE%" --batch "%BATCH%" --file "%REPAIR%" --validate-only
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" repair-submit --project PROJECT_ID --node "%NODE%" --batch "%BATCH%" --file "%REPAIR%"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project PROJECT_ID --case CASE_1 --wait
```

恢复时使用原运行范围。若原范围选了多个用例，复用相同的 `--case` 列表或 `--all-cases`，这样可以同时续跑原任务。成功批次在身份与校验仍有效时复用。结果记录应标记为 Code Agent 提交。代码故障按诊断堆栈修复源码并验证，再以相同全局参数执行 `rerun --project PROJECT_ID --node NODE_ID` 并继续等待。需要业务答复、额度不足或请求用量未决时，把具体问题交给用户处理。正式产物通过工作台校验与发布接口写入，项目文件、修复包、账号密钥和运行日志留在本地。

### 4. 核对并交付

```bat
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" results --project PROJECT_ID --case CASE_1
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" results --project PROJECT_ID --analysis-scope all
start.cmd
```

在同一项目的「最终结果」查看交互四元组、E／G／GT、匹配依据、跨步骤出处和指标。人工编辑使用工作台的修订入口。到「审核交接」导出离线 HTML。交付项目 ID、各用例执行状态、仍待确认的问题、采用的接管批次、结果和报告位置。
