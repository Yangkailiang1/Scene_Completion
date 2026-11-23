# 给内部 Coding Agent 的项目执行提示词

将本文件发给终端 Coding Agent。请同时提供 Windows 包的解压路径、材料清单、目标用例、交付目录，以及获授权的模型账号、模型和额度。如需接手既有项目，也请提供工作台返回的项目 ID 和数据目录。凭证通过工作台模型设置或包根目录的本地 `.env` 配置。

包内源码沿运行顺序的索引为 `app/docs/architecture/ssd-walkthrough.md`。从 SysOperation、核心分件、语义批次到报告的字段例子都在该页。源码仓库另附可复现的合成验收，Windows 包使用 `check.cmd` 执行便携检查。

## 任务目标

请用这个 Windows 离线包，把指定用例从同事交付的结构化材料跑到可查看、可编辑的 E／G／GT 三方结果，再导出《异常场景完整性补全识别结果》HTML。实际执行并核验每个阶段。首个用例通过后按用户给定的范围继续；有独立用例因缺材料、业务歧义或模型问题卡住时，记录原因，继续可独立完成的用例。

E 是需求或设计已写明的异常，G 是根据正向材料和关注点体系生成的场景，GT 是从测试材料独立识别的异常。模型运行、Code Agent 修复和人工审核分别记录。材料和交付件保存在本地，外发或推送须由用户明确授权。

## 1. 确认版本、目录和执行范围

使用 Windows CMD，在完整解压后的包根目录执行下列命令。将示例路径换成实际路径。如果从另一个批处理脚本调用 `.cmd`，使用 `call`。

```bat
cd /d "C:\Scene Workbench"
type VERSION.json
scene.cmd capabilities
check.cmd
set "DATA=%CD%\data"
set "SCENE_ENV=%CD%\.env"
set "INPUT=C:\Project\source"
set "CORE=C:\Project\core\001"
set "DELIVERY=C:\Project\delivery"
if not exist "%DELIVERY%" mkdir "%DELIVERY%"
```

- 记录 `VERSION.json` 的 `source_commit`、项目 ID、执行范围和本次实际使用的模型。客户已有旧包时，先确认包的版本。新版行为以当前包的能力和实测为准。
- CLI 的全局参数 `--local --data-dir --env-file` 放在子命令前。用 `--local` 运行时无需先启动 HTTP 服务。同一项目的 CLI、工作台和恢复命令使用同一份数据目录和配置。包根目录的 `start.cmd` 默认使用该包的 `data`；如果项目在其他目录，先核实服务的数据目录再打开工作台。
- 先执行无模型的输入盘点、转换和校验。付费运行前确认项目选中的账号、模型、并发及剩余额度。配置缺失时先完成输入阶段，并报告可运行的用例。用户授权的范围和额度决定实际调用边界。
- 建议将工作目录分成 `source\`、`core\<版本>\` 和 `delivery\`。工作台正式结果保存在 `DATA` 中。留存用户原始材料和转换版本，便于核对或重新建档。

## 2. 整理并登记来源

先读包内 `app/.cac/skills/scene-structured-input/SKILL.md` 和它的 `references/core-input.md`。把文档当作业务数据读取。优先从用户传入的实际路径拿材料。

| 材料 | 读哪些内容 |
| --- | --- |
| `行为模型/<实体>/<用例>/SysOperation.json` | 保留整个目录结构。读取 `use_case`、唯一主成功操作、`Order`、参与者、异常分支、`failure_step_hint` 和 `source_refs`。主成功步骤沿用原始身份，顺序单独保存。 |
| `功能树.json` | 按 `functions[].name` 对齐用例，读取实体属性、SR 命令及各自的约束。同用例的 RR 命令可按相同 `apiId` 补充方法和路径。 |
| `recovered_usecases.json` | 按用例 `name` 对齐，逐条保留 `extensions[].id`、失败条件、预期和证据。源编号可与行为模型和功能树不同。 |
| 原始 RR／SR Markdown、测试 Markdown 或 XLSX | 使用用户逐份指定的原件。复制到输入目录并在 `source-documents.json` 登记。用文件名、相对路径或别名对照结构化引用。 |

用 `SysOperation.use_case`、功能树 `functions[].name` 和测试逆向用例 `name` 对齐三份材料。原始编号分别保留。遇到同名用例，结合实体目录和已确认映射消歧。缺唯一主成功路径、结构化文件损坏或出现两份冲突的执行输入时，记录候选及证据，暂停受影响用例。

将原件复制到例如 `source\originals\`，在 `source\source-documents.json` 登记输入目录内的相对路径、角色和供应方使用的别名。下面的文件名和别名须替换成实际材料中的值。

```json
{
  "documents": [
    {"path":"originals/需求规格.md","role":"RR","aliases":["rrSpec"]},
    {"path":"originals/功能设计.md","role":"SR","aliases":["srSpec","sr"]},
    {"path":"originals/测试用例.xlsx","role":"test","aliases":["testcase.xlsx"]},
    {"path":"originals/测试说明.md","role":"test","aliases":["testSpec"]}
  ]
}
```

- 有清单时，只从已经登记的文件追溯。`structure_model_fusion/RR` 或 `SR` 下的派生副本通常留作中间材料。供应方在 `source_refs` 写了绝对路径时，保留该引用，仍把原件复制到输入目录并登记相对路径。程序可用唯一的目录后缀或文件名识别原件。同名仍无法区分时，把供应方原路径作为该原件的唯一别名登记。
- Markdown 定位使用原件全文件行号，例如 `L1726-L1726` 或 `start_line/end_line`。声明位置与引文有偏差时，程序先核验其上下各两行，再在同一文件检索唯一引文。核实后高亮实际位置。Excel 使用工作表和标准范围，例如 `测试用例!A120:O120`，后一段的 `O` 是列名。缺原件、坐标无效或引文无法核实时，记录文件、位置和受影响记录。
- `SysOperation.json` 提供步骤及发送方、接收方。当前结构化流程将 `srLayer.commands[].attributes` 视为同一接口发送的数据，只使用接口 ID 和字段名定位。直接使用功能树的字段名、类型、约束、标签及其出处，无需补写字段的 `location` 或 `direction`。Excel 或 Markdown 的原文定位仍照原样登记。
- 功能树的每条 `constraints[]` 用该约束自己的 `source.doc`、`line` 和 `quote`。有独立出处的标签保留自身来源，例如 `{"name":"必填","source":{...}}`；字符串标签或类型使用字段声明的来源。接口命令出处用于关联调用，字段约束出处用于证明约束。
- 人类 Actor、外部服务、内部服务按参与者声明和确切原文区分。转换把主成功流参与者的 `name/role/kind/element_type` 及 `participant.source_refs[].quote` 保留给正式 `ssd-resolve`。有引文的参与者先由模型核对，同一引文提到的依赖或适配器按自己的声明识别。人工 `kind_override` 优先，缺少引文或模型明确说明引文不足时保留脚本分类。旧核心文件缺少参与者引文时，从保留的供应方输入转换到新目录，再按现有升级流程核对。例如 `actor-001|AI原生应用开发者|actor|主(人)|` 可用于确认该开发者是外部人类 Actor；同一引文中提到的服务仍按服务自己的声明处理。人工更正须带确切证据。明确是数据库的服务另保留 `technology=database`。

## 3. 盘点、转换并核对核心 JSON

先用 `inspect` 查出实际用例 ID 和 `issues`。如果本轮只试跑首个用例，仍可先转换全部获授权的用例，建成同一个项目，再用 `run --case` 控制付费范围。只获授权处理单用例时，在 `inspect`、`convert` 和 `validate` 追加该用例的 `--case`。重复 `--case` 可选多个用例。

```bat
scene.cmd core-input inspect --input "%INPUT%"
scene.cmd core-input convert --input "%INPUT%" --output "%CORE%"
scene.cmd core-input validate --input "%CORE%"
```

- 转换输出应为输入目录外的新目录。已有可复用的核心目录时，先校验并核对输入版本。新转换默认使用 `command-interaction-v3`，SR 数据义务按 `interface_field_policy=sr-input-by-name-v1` 输出。核对 `data_obligations` 中的接口、字段、主步骤和稳定 ID。旧核心目录可继续读取，已有人工修订会按接口与字段的唯一对应迁移。
- 先处理 `issues` 中的阻塞项，再选通过校验的用例建档。可确认的问题按核心输入 Skill 的 `core-input-overrides-v1` 契约处理，使用本次 `inspect` 的 `input_hash` 和证据。用 `convert --overrides` 写入另一个新版本目录，再执行 `validate`。无法确认的事实留待确认。
- Windows 若提示核心分件缺失，核对实际缺的是哪份文件，并检查建档错误中的 `create_failure.stage`、`relative_path`、`path_characters` 和 `winerror`。先用本包 CLI 和完整解压目录复验。旧 Agent 自行用未处理的长路径调用 `Path.is_file()`，其结果需要用工作台校验复核。

| 产物 | 核对内容 |
| --- | --- |
| `architecture.json` | `elements[].id` 被各步发送方和接收方引用。核对 `kind` 和数据库标识。 |
| `cases/<用例目录>/main-success.json` | `case.id` 是后续运行 ID，`function_tree.uc_id` 保留功能树编号。核对每步的发送方、接收方、操作、数据、稳定 ID 和顺序。 |
| `existing-exceptions.json` | E 保留原始异常分支、条件、预期及证据。伸展分支的 ID 和锚点是定位线索。 |
| `extension-mapping.json` 与 `test-exceptions.json` | 按 `source_uc_id` 和 `extension_id` 逐条对账。一个扩展可有多个确有依据的独立挂载。正常、范围外和待确认也有出处。缺测试来源的用例显示未评估。 |
| `source-map.json` | 能从目标字段回查原路径、原件行号或 JSON Pointer。变更后的原件不要覆盖当前冻结版本。 |

检查当前用例的每个实际 SR 接口只在一个主调用步骤展开。接口字段约束与同一步的实体属性约束，只有明确等价时才去重，保留两处出处。分页、页码等接口专有字段应留在接口数据里。实体在后续传递步骤重复出现时只保留引用。CRUD 可有多个，结合操作语义、方法及出处判断。纯转发、本地参数校验和返回可无 CRUD。无 RR API 时流程照常运行，接口可显示「未关联接口」。外部服务在实际调用处生成可用性，项目内同服务、同故障类型汇总一次。数据库按技术规则挂载，第三层当前暂停生成。

## 4. 建档，从一个用例开始运行

用已校验的核心目录建档。记下实际返回的 `id`，再将示例值替换成该 ID 和 `main-success.case.id`。若目标项目已存在，先用 `projects` 查询当前数据目录并复用对应项目。

```bat
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" projects
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" create --name "场景识别项目" --input-dir "%CORE%" --adopt-partial
set "PROJECT_ID=替换为实际项目ID"
set "CASE_ID=替换为实际用例ID"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project "%PROJECT_ID%" --case "%CASE_ID%" --preview-supplied
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project "%PROJECT_ID%" --case "%CASE_ID%" --wait
```

正式流水线依次是 `ssd-prepare`、`ssd-resolve`、`ssd-generate`、`ssd-compare`。成功用例可发布交互结果，随后脚本更新共用服务汇总。首个用例完成后先做第 5 节的逐条核对，再继续该项目的其他用例。

- **逐个运行**。一个 `run --case` 退出后再运行下一个用例。每轮记录实际用例范围。
- **并发运行**。在同一个项目 worker 内一次提交多个用例。按用户授权的账号并发限制配置 `configure --project "%PROJECT_ID%" --concurrency 2`，再执行 `run --project "%PROJECT_ID%" --case CASE_1 --case CASE_2 --wait`。用户明确要求全量时才使用 `--all-cases`。这些命令也使用上面相同的本地全局参数。
- **等待与恢复**。同一项目只有一个运行中的 worker。退出码 0 表示执行完成，仍应分别核对 `execution_complete` 与 `review_complete`。退出码 2 时查 `status` 和 `diagnose`，区分失败、接管和业务阻塞。退出码 3 表示 CLI 等待超时，先查看 worker 是否仍存活。已在运行时用 `status` 观察，或用原范围的 `run --wait` 继续等待。待确认的业务问题和额度状态按实际情况报告。

### 在同一个项目分批追加 SSD

功能树和测试逆向 JSON 可以从第一批就放全。首批只把已经交付的 `SysOperation.json`、配套分支及可用原件放进来源目录，运行通过预检的用例。用同一份用例清单记录已完成、待追加 SSD、输入阻塞、执行失败和业务待确认的用例；缺 SSD 的用例列为待追加，暂不参与本轮统计。

1. **保留项目及稳定身份。** 继续使用原 `PROJECT_ID`、`DATA`、模型配置和额度账本。追加前用 `status` 确认本轮 worker 已结束，并用 `results --project "%PROJECT_ID%" --case "%CASE_ID%"` 记录已发布用例的 ID 和修订号。
2. **更新来源并生成完整快照。** 把新增用例的 `SysOperation.json`、配套分支和原件加入原 `source`，保持旧用例的目录、用例 ID 和步骤 ID，沿用全量功能树和测试逆向 JSON。需要时补充 `source-documents.json`。将 `CORE` 指向新的版本目录（如 `core\002`），执行第 3 节的 `inspect`、`convert`、`validate`。这次转换要包含已交付的旧、新用例；转换时仅选新增 `--case` 会产生不完整的导入快照。
3. **导入原项目并预检。** 从包根目录执行 `start.cmd`，打开原项目的「输入与导入 → 添加文件夹」，选择这一版完整核心目录。预览后采用已校验的部分事实，再点「预检已有 SSD」。这次导入会切换项目的当前输入快照，所以要交付完整目录。只追加时不勾选替换既有成功产物。若旧用例实际也有材料变更，把受影响范围列出来，按用户授权另行重跑。
4. **只运行本批新增用例。** 用预检返回的真实用例 ID 替换下列示例值。需要运行更多新增用例时，重复 `--case`。本批结束后核对项目结果包含新旧用例，新用例已发布，旧用例未变的修订仍可查；记录仍缺材料的用例。

已有项目也可用 CLI 完成第 3 步。先启动同一数据目录的工作台服务。下面两条导入命令通过 HTTP，使用工作台实际端口，省略 `--local`；后续运行可继续使用本地模式。

```bat
set "BASE_URL=http://127.0.0.1:8765"
set "NEW_CASE_1=替换为第一个新增用例ID"
set "NEW_CASE_2=替换为第二个新增用例ID"
scene.cmd --server "%BASE_URL%" input-bundle --project "%PROJECT_ID%" --directory "%CORE%" --dry-run
scene.cmd --server "%BASE_URL%" input-bundle --project "%PROJECT_ID%" --directory "%CORE%" --adopt-partial
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project "%PROJECT_ID%" --case "%NEW_CASE_1%" --case "%NEW_CASE_2%" --preview-supplied
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project "%PROJECT_ID%" --supplied-only --case "%NEW_CASE_1%" --case "%NEW_CASE_2%" --wait
```

只新增一个用例时，去掉第二个 `--case`。核对预检的 `accepted` 涵盖本轮要跑的所有新增用例，再发起执行。

## 5. 按记录核对匹配和出处

```bat
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" results --project "%PROJECT_ID%" --case "%CASE_ID%" > "%DELIVERY%\case-result.json"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" results --project "%PROJECT_ID%" --analysis-scope all > "%DELIVERY%\project-result.json"
```

在「最终结果」打开三方表，结合 CLI 的用例结果做以下核查。

1. **查四元组**。看步骤顺序、调用双方、接口主挂载、实体和数据约束。抽查一个重复传递的实体字段，确认生成只在主挂载步展开，实际校验和响应仍可回查。抽查一个外部服务，确认项目共用服务按身份与故障合并。
2. **查来源隔离**。G 使用主成功流、功能树、正向接口和规则。E 和 GT 分别从各自来源识别。新版先分类，最终 G 生成后再分别对齐，可以跨步骤。关注点相同还需核对失败条件、责任对象和处理预期。无法对齐现有 G 时，有证据才独立挂载。正常备选、合法边界与范围外记录单列。
3. **查测试扩展去向**。按原始 `extension_id` 核对已挂载、正常、范围外、待定位及其依据。当前结构化结果用匹配／不匹配计分，允许多对多。只检查返回值异常的记录归范围外，校验失败后返回错误仍计入输入校验。一条来源明确列出多个失败时可以拆分。宽泛来源可关联多个 G，保留同一个来源身份。缺测试或匹配未完成要标明未评估或待确认。
4. **查实际失败位置**。以认证为例，人发起的请求与服务间请求分别用 `human.authentication` 和 `service_relation.authentication`。结合 `failure_step_hint`、原分支、主成功 SSD 和候选 G 核对。已有可信 G 匹配但实际失败步骤不明时，保留匹配并显示「实际失败步骤待定位」。检查能从记录打开原文并跳到高亮行。没有原文行号时回查冻结的行为模型分支及 JSON Pointer。GT 的测试出处与关联需求分别核对。
5. **查单条异常**。`exception` 但 `bindings=[]` 或 `parts=[]` 时，该条应保留原条件和证据，单独待定位，同批有效记录应继续。若模型把 `human`、`service` 填进 `target`，检查修正依据。只有证据唯一时，可纠正为 `sender` 或 `receiver`；方向有歧义时留待定位。`entity` 和 `interface` 用于分别定位实体及接口字段。缺失、重复或越权引用的身份仍需校验。若旧包整批拒绝，记录版本、节点、失败批次和具体字段。

「待定位／本轮不计分」中的「定位与挂载」默认提供独立挂载。选择交互步骤、挂载对象和启用的关注点，再应用到草稿。需要关联已有记录时切换到「匹配已有」。来源和实际失败位置随原记录保留，保存后才重算指标。

若旧核心文件中 GaussDB 等外部数据库的 `technology` 为空，先确认原始 `SysOperation.json` 的参与者角色，再用新版重新转换到新的完整核心目录。明确的 `role: "外部数据库"` 可直接识别。核对 `architecture.json` 的相关参与者为 `external_service`、`technology: "database"`。在同一项目更新输入快照，保留已有修订，再仅运行目标用例。

```bat
scene.cmd core-input convert --input "%INPUT%" --output "%CORE%"
scene.cmd core-input validate --input "%CORE%"
scene.cmd --server "%BASE_URL%" input-bundle --project "%PROJECT_ID%" --directory "%CORE%" --dry-run
scene.cmd --server "%BASE_URL%" input-bundle --project "%PROJECT_ID%" --directory "%CORE%" --adopt-partial
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project "%PROJECT_ID%" --case "%CASE_ID%" --preview-supplied
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project "%PROJECT_ID%" --supplied-only --case "%CASE_ID%" --wait
```

结果中核对外部数据库首次出现在主成功流的位置。可用性和数据库特殊字符关注点挂到该步骤的实际角色，返回步骤和空 CRUD 也适用。无 G 对应的 E／GT 若有充分出处，应保留为原通道的独立场景。仍待定位的条目应指出需要补充的证据或挂载对象。

## 6. 接管失败节点并继续等待

先读 `app/.cac/skills/scene-terminal-recovery/SKILL.md`。主会话负责观察、判断和恢复。业务 JSON 修复使用节点独立上下文，源码故障和业务结果修复分开记。先查真实的节点和批次身份，再决定下一步。

```bat
set "NODE=%CASE_ID%:ssd-generate"
set "BATCH=替换为实际失败批次ID"
set "REPAIR=%DELIVERY%\node-repair.json"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" status --project "%PROJECT_ID%"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" diagnose --project "%PROJECT_ID%" --node "%NODE%"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" repair-export --project "%PROJECT_ID%" --node "%NODE%" --batch "%BATCH%" --out "%REPAIR%"
```

- 多批次节点用实际失败批次 ID，仅单批次节点可省略 `--batch`。保留诊断里的分类、失败字段、运行参数、检查点和原报错。导出版本过期时按诊断刷新受影响的任务后重新导出。
- 若旧版转换把 `failure_step_hint.ref` 写成了核心文件的 `failure_step_id`，先依据原始 `SysOperation.json` 重新转换受影响的用例，再定向运行并重新导出对应批次。保留原件明确声明的失败步骤。分支锚点和恢复步骤可供定位判断，G 的挂载位置也可能与实际失败位置不同。
- **工具提交形状错误**。例如 `submit_result` 的 `supplements` 出现在顶层。当前实现可把可确认且无冲突的业务字段放回 `payload`。若仍拒绝，按诊断区分未知顶层键、内外重复键、错误类型或业务校验错误，保留原始参数，修复时使用导出包内的冻结 Schema。
- **模型业务 JSON 交接**。仅编辑导出文件的 `payload` 和 `note`。note 写具体修改和证据。保留冻结输入、Schema、节点身份、批次身份、短编号映射和版本字段。生成节点只使用正向材料，E、GT 各用本方来源，比较节点使用获授权的指定两侧。补交须保留固定模板、合法字段和锚点，未确认事实按契约留待确认。
- **`ssd-entity-inference` 批次误带操作判定**。实际失败批次的冻结 `input.operations` 为 `[]` 时，补交的 `payload.operations` 也填 `[]`。保留并逐条核对 `payload.constraints`，兼顾规则 ID、关注点和失败条件。若冻结输入列出了待判定的操作 ID，逐项提交对应判定。
- **证据分类及认证对齐**。逐项核对本批来源和原文片段。`ssd-evidence-classify` 的 `condition`／`expected` 可直接复制同一条记录的连续证据原文。非连续摘录对应字段留空，使用 `condition_fragments`／`expected_fragments`，填写 `field=evidence`、本条冻结任务的零基 `index` 和逐字 `quote`。缺少预期依据时留空。不要改字段名大小写、枚举值或阈值。无效片段单条待复核。`ssd-ground-align` 的每条 `parts[i]` 和每条 `matches[j]` 各自填写 `reason`。认证候选和独立挂载使用同一条实际请求，依据不足时保留待定位。`ssd-generate` 的问题引用诊断可在 `run/question_rejections/` 核对。
- **脚本或调度故障**。诊断为 `code_failure` 时检查堆栈、检查点和复现入口。修改源码须在授权范围内，完成针对性验证，然后执行下面的 `rerun --wait`。若 `ssd-prepare` 报核心快照写入失败，记录诊断中的 `operation`、`relative_path`、`winerror` 和 `retries`。工作流会复用可用的快照，正式产物由工作流执行和发布。
- **业务、额度与在途请求**。需要业务裁决、额度不足或已有请求用量未决时，报告确定的阻塞、影响范围及需用户确认的事项。保留请求和账本记录，核对后再恢复。用量未知的请求不盲目重发。

修复脚本或文件系统故障后，使用下面的命令派发并等待该轮结束。重跑保留包含目标节点的上轮用例范围。旧记录缺少范围时，用例节点按其所属用例恢复。超时只结束 CLI 等待，通过 `status` 或 `events` 查看仍在运行的 worker。

```bat
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" rerun --project "%PROJECT_ID%" --node "%NODE%" --wait --timeout 3600 --poll 2
```

确认 worker 已结束后，先校验再提交。以下恢复命令以单用例为例，多用例和全量恢复使用原运行范围。已由用户暂停的项目按授权执行 `execution-control --project "%PROJECT_ID%" --action resume`，随后查看状态。合法修复应用后复用仍有效的成功批次。

```bat
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" repair-submit --project "%PROJECT_ID%" --node "%NODE%" --batch "%BATCH%" --file "%REPAIR%" --validate-only
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" repair-submit --project "%PROJECT_ID%" --node "%NODE%" --batch "%BATCH%" --file "%REPAIR%"
scene.cmd --local --data-dir "%DATA%" --env-file "%SCENE_ENV%" run --project "%PROJECT_ID%" --case "%CASE_ID%" --wait
```

只有 `--validate-only` 返回有效，才正式提交。正式提交检查 `saved` 和修订号，恢复后核对修复是否采用、正确批次是否完成，以及成功批次是否复用。将这次结果标记为 Code Agent 修复。查看或保存业务人工修订，使用工作台有版本检查的编辑入口。

## 7. 导出业务审核 HTML 并交付

需要打开网页时，从包根目录执行 `start.cmd`，在工作台打开同一项目。检查三方表保存版本，未保存草稿由有权限的操作者保存或确认后再导出。在「审核交接」生成《异常场景完整性补全识别结果》HTML，核对实际用例数和未完成状态。

- **G ∩ 测试逆向**。被任一 GT 确认覆盖的 G，每条 G 义务计一次。
- **G 有、测试逆向没有**。识别、生成、匹配均完成且确认无 GT 覆盖的 G。可按关注点筛选并填写归因、解决方案。
- **G 没有、测试逆向有**。相关任务完成后，确认没有 G 覆盖的 GT。待定位与未完成内容另列，共用外部服务按合并单位计数。

### 从同一次导出另存两份 HTML

1. **固定导出版本。** 把同一次导出的原始 HTML 留作底稿，从该文件分别制作两份交付件。先核对导出用例、三类数量、待定位及未完成项；所有分析和填写都在离线报告中完成。需要分批交付时，在文件名或交付清单标出批次。
2. **`01-待审空白版.html`。** 打开底稿的副本，将第二项「仅 G 有」的理由、问题归因、归因说明和解决方案留空，将第三项「仅 GT 有」的归因、归因说明和解决方案留空。系统导出可能已经给第二项带了生成理由，也要清空这些预填理由。保留三类场景、关注点、用例、自动计数和原文链接。点「保存含修改的 HTML」，将下载文件另存为上述名称。
3. **`02-Agent预填稿.html`。** 打开同一底稿的另一份副本，在报告标题中追加「Agent 预填 · 待人工审核」。用下表逐行填写。写明能从报告的「原文与依据」或冻结材料找到的证据。只有证据支持时才选归因；无法确认时留空归因选项，在归因说明写「待核实」及具体核验点。解决方案写可以执行并核验的下一步。证据不足时先写核验动作。保存并另存为上述名称。

| 报告页 | 预填内容 |
| --- | --- |
| 交集 | 保留确认对应的场景及依据。 |
| 仅 G 有 | 补写理由，说明基于哪个步骤、对象、约束或关注点生成了这个场景。核对测试范围与原文后再选择「关注点无用」「前置抽取问题」或「需求文档漏写」，填写依据、解决方案和验收条件。不能单凭测试未覆盖就断定需求漏写。 |
| 仅 GT 有 | 用归因说明记录测试证据、缺口和核对结果。证据支持时选「关注点不够」或「前置抽取问题」，再写补全方案和验收条件。这一页没有独立的理由列。 |

分别离线重开两个文件，核对空白版的审核字段为空、预填稿的填写项可继续编辑，并抽查原文跳转与三类计数。两份 HTML 使用同一版项目结果及来源，审核填写留在各自文件。不要用预填意见改写工作台正式三方结果或将判断标为已审核。

当前报告导出接口是 `POST /api/projects/{rid}/ssd-review/report`。收到历史可回导审核包时，仍按原 `/ssd-review/preview`、`/ssd-review/apply` 协议核对可应用项、冲突和修订身份。

最后给用户一份简短交付清单，包含项目 ID 与版本、每个用例执行和审核状态、原始测试扩展对账、仍待确认项及出处、Code Agent 采用的批次、修订身份以及待审空白版和 Agent 预填稿的各自路径。若某项只用夹具、模拟响应或非 Windows 环境验证，注明验收范围。完整资料、凭证、模型轨迹和修复包留在本地。
