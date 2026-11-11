# Windows x64离线包

下载对应GitHub Release中的scene-completion-windows-x64.zip，完整解压至可写目录后双击start.cmd。包中自带CPython 3.12.10、已安装的Windows依赖和编译后的网页，客户无需安装Python、Node或pip，无需联网下载环境。模型权重不在包内，调用客户现有内网模型。

启动器等待本地服务就绪后打开浏览器。默认地址为http://127.0.0.1:8765，端口占用时运行`start.cmd --port 8766`。仅监听本机，不自动开放局域网端口。

在网页配置内网模型地址、实际模型名称和密钥，也可复制包根目录.env.example为.env后填写。不要把填写后的.env上传到GitHub。新项目、上传文档、审核记录和运行结果保存在包根目录data中。升级前保留原包和data，源码提交见VERSION.json。

- start.cmd：启动本地工作台，服务就绪后打开浏览器。
- check.cmd：使用包内Python检查依赖并运行离线测试，不调用付费模型。
- scene.cmd：使用包内Python调用CLI，例如 `scene.cmd projects`；先启动start.cmd，网页和CLI查看同一运行进度。
- .env.example：空白模型配置模板。
- app/examples/tests/mall-exception-tests.xlsx：可编辑测试集示例。
- VERSION.json：源码提交、Python版本和依赖锁摘要。
- SHA256SUMS.json：包内文件摘要；ZIP的.sha256附件用于下载校验。

仓库提供Windows原生验收工作流，检查系统Python、包内嵌入式Python、中文及空格路径下的启动器、独立项目／管理Agent worker、网页HTTP和Excel导入。独立worker以隔离模式从非程序目录启动，不能只以主网页可打开判定子进程正常。手工交叉制作的Release明确标注原生验证状态；macOS交叉检查不能代替Windows原生验证。包内不含开发机.env、凭证、.workbench运行数据、虚拟环境或node_modules。

没有Windows环境时可以单独发布交叉制作的离线包，但Release说明必须标注“Windows原生验证待用户完成”，不声称通过上述原生验收。此类包使用`windows-x64-*`标签，与触发原生工作流的`scene-workbench-*`标签区分；旧Release保留。

维护者可用 `python tools/build_windows_bundle.py --offline --output-dir dist` 复用此前锁定的Windows轮子及Python缓存；缓存不完整时构建失败，不下载或混入本机macOS环境。

构建同时按Windows x64/Python 3.12的依赖标记检查已安装轮子的依赖闭包，不使用打包机的macOS标记推断。锁文件包含Windows下pytest所需的colorama；此静态检查仍不能替代Windows实际启动。

专用业务审核包由本地“审核交接”页生成，包含当前项目快照并强制review-only，不含Key或模型缓存。业务无需Python/Node，回答和审核推荐后导出小型反馈JSON；研发导入预览后手动重跑。`check.cmd`能识别审核包，采用只读HTTP/来源定位及禁止执行检查。公共Release程序包始终不含业务数据。见[business-offline-review](business-offline-review.md)。

管理Agent的Skill、代码补丁和内部日志采用UTF-8；内部Python子进程显式启用UTF-8模式，不依赖Windows系统区域设置。遇到旧包的GBK解码错误时，停止服务后升级程序并重启管理Agent，保留原data和.env。源文件仍严格按UTF-8读取；仅子进程展示日志对无效字节作替换，不修改业务材料。

接口参数采用三类展示：请求、成功响应、失败响应（按状态码分支）。历史JSON的`parameters`仍兼容，新增可选`responses`保存响应变体；失败分支不进入正常交互的参数要求或G生成上下文。成功响应表中名为`name`的实际字段不能被误认成英文表头。最终结果的数据属性以已通过API结果按明确接口身份关联，`business`占位仅在字段及方向唯一时解析成具体位置；存在多个候选时保持待确认。该展示关联不会修改历史匹配与指标。旧项目需补抽未保存的响应分支时，定向重跑对应API参数节点；属性影响关注点和场景时再重跑交互补全及其下游，无需重新抽取全部文档。

RR/SR接口分层版本：RR对外接口、SR内部接口分别保存映射和参数表（`rr-api-*`／`sr-api-*`），汇总接口身份使用`RR::原编号`与`SR::原编号`。原编号、层级、路径和原文依据均保留；请求、成功响应及各失败响应分别处理。同一次实际请求的RR/SR重复视图只有在同用例、发送方、接收方、方向及接口不冲突且有确认对应时合并，SR身份保留两层数据和依据。调用链A→B→C必须分为A→B、B→C，参数及本地校验不能跨接口上移。测试与已有异常按其自身接口和实际校验职责定位。旧报告不会被展示层自动重算；采用新口径时需重跑分层API参数及受影响的交互分析、E/GT定位和评测，共享组成与未变的SSD可复用校验。

新增[恢复用例JSON及SR指标视图](recovered-json-and-sr-metrics.md)：测试可直接上传含extensions的JSON，保存原文件及真实分支位置。测试目录工具解析不调用LLM，具体用例对应、交互定位、关注点与场景仍独立整理。结果页默认SR，可切换层级并下载当前范围指标；筛选仅复用已保存匹配重新计数，不修改历史正式产物。没有来源层级或无法绑定接口的历史项不会凭路径前缀猜测；补齐接口归属及必要定位后再评测。Windows原生验证仍由客户执行。

### 仅运行已校验的用例

在「输入与导入」选取输入目录，采用已校验的字段、属性和行为文件，点击「预检已有 SSD」。清单显示每个 SysOperation 文件的实际用例、目标节点和校验结果。点击「仅运行已校验的用例」后，本轮固定使用清单中的用例。文件更新后重新预检并运行即可追加，已完成用例的未变产物继续复用。

```bat
scene.cmd input-bundle --project PROJECT_ID --directory C:\SceneCompletion\input --adopt-partial
scene.cmd run --project PROJECT_ID --preview-supplied
scene.cmd run --project PROJECT_ID --supplied-only --case G-001 --wait
```

省略 `--case` 时运行所有已通过预检的用例。SR 接口表使用已提供且绑定到当前用例的契约，保留成功和失败响应的缺项。RR 交互继续用于分析。项目级全局分析本轮不调度，缺失测试的用例显示未评测。
