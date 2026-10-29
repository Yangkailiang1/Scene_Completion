# 项目管理Agent与同事材料接入

网页右下角“项目管理Agent”提供持久对话、计划、操作与补丁、记忆、吞吐监视和独立模型设置。浮窗可收起或最大化；关闭网页不会停止已启用的后台托管。

## 开始使用

1. 在“模型配置→API连接”保存OpenAI兼容连接及该Key的允许模型。
2. “管理Agent模型”独立选择连接、模型、上下文及输出预算。没有单独设置时继承当前项目的连接引用；密钥不进入对话或浏览器响应。
3. 默认协作模式：查询和诊断可直接进行；采用材料、修复和执行需明确确认。启用Auto后可自动执行已授权的操作；业务问题仍保留为问题，不把缺失事实当成已确认。
4. 暂停托管后不再发起新的工具操作。已发出的HTTP不能撤销计费；其状态和未知用量保留。暂停前排队消息不会因守护器重启而偷偷执行；新消息或重新启用是显式恢复。

所有模型、导入转换、恢复和管理调用共享网关最多3并发，保留账号/模型各自的额度账本。管理Agent无法清空账本或修改凭证。

## CLI

先启动服务，再使用包内`scene.cmd`（Mac/Linux用`python scene.py`）：

```bat
scene.cmd capabilities
scene.cmd manager --project PROJECT_ID --action status
scene.cmd manager --project PROJECT_ID --action chat --text "查询阻塞节点并制定首个用例的推进计划"
scene.cmd manager --project PROJECT_ID --action configure --file manager-config.json --dry-run
scene.cmd manager --project PROJECT_ID --action configure --file manager-config.json
scene.cmd manager --project PROJECT_ID --action operate --file operation.json
```

配置文件使用当前状态中的版本号：

```json
{"expected_revision":0,"settings":{"mode":"auto","enabled":true}}
```

操作示例：

```json
{"action":"strategies","arguments":{},"request_id":"inspect-strategies-1"}
```

`history`支持`after/before/limit`分页；`strategies`查询已尝试操作、未决写操作、修复预算、补丁续接和记忆。实际修改统一走业务接口和原校验器，不能通过CLI直接改通过状态。`--dry-run`目前用于配置预览，不表示任意工具均可无副作用试运行。

## 修复与重启

节点修复只获得该节点允许的材料、Skill、Schema及诊断，不注入全局聊天或其他通道的G/E/GT。每个输入/配置绑定最多2次管理修复。未知POST不自动重发。

程序补丁在隔离工作副本运行安装版本的冻结测试，模型不能修改测试、存储、权限、账本或管理守护代码。此工作副本不是操作系统沙箱。前端源码补丁需研发构建，不能在没有Node的客户包里当成已部署网页。

测试通过的补丁等待所有工作进程结束，持久保存激活任务。到安全边界后自动续接应用、停止已认证的本地服务、启动、核对PID及健康检查；不依赖再次聊天。维护标记存在时拒绝新执行。新服务未就绪先终止并回收本次子进程，再回退及恢复旧服务；两次启动均失败时保持维护状态并保留日志，由研发核查，不能伪装恢复成功。

查看项目`manager/patches/PATCH_ID/change.patch`、`test.log`、`restart.log`及数据根目录`server.log`。不确定的写操作保留`started`记录；新会话应先核对真实状态，不重复提交。

## 记忆、试跑和材料隔离

会话原文、摘要游标、决定、计划、故障、问题及操作保存到项目SQLite。长历史按游标连续压缩，不只读取最后500条；较早会话可分页查看，摘要调用也计费。长工具结果落盘后按行查询。

假设试跑创建独立项目，原始RR/SR/测试不增加假设材料。假设仅作为显式指定的正向规则/关注点/场景节点指导；E、GT没有该指导，证据校验不放宽。没有可校验依据的假设仍须待确认，不能因为在试跑中便成为已确认需求。试跑与正式报告分开，不能将其GT合并回正式结果。

## 导入与吞吐

“输入与导入”展示文件用途、原件、转换预览、目标节点和实际引用。已登记测试源与已被某节点引用分开显示；刷新状态保留未保存的JSON草稿。测试只将明确异常投入GT，正常和待定可查看但不计分。

吞吐图可按账号、模型、节点和内容类型筛选。PNG/SVG导出当前曲线，CSV/JSON导出同一筛选范围及估算速率；缺测值为空，不把未知写成0。图中速率是接收字节/4的估算，不等于账单Token。导出只包含白名单遥测字段，不含密钥、请求正文或推理原文。

## 升级与验证边界

升级前停止旧服务并备份`data`、本地配置、凭证和账本。包内只替换程序及环境；原数据按原目录保留。成功产物仍要核对输入、Skill、Schema、来源及任务逻辑。6bb19f6适配器迁移仅接受提交内记录的精确证明，不代表所有旧节点都能复用。

公开Windows包不含项目、密钥、账本、验收快照或模型缓存。Mac隔离服务测试不能替代Windows原生和客户网关验收。
