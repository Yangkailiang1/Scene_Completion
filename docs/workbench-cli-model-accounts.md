# Code Agent CLI、网页实时进度与API Key模型连接

## 一套执行记录

`scene.py`是本机工作台API的CLI客户端，不是另一套流水线。CLI启动任务后由工作台服务执行，浏览器通过原有SSE和持久化事件读取进度。CLI关闭或等待超时不会终止服务端运行；可以重新查询状态。先保持服务运行：

```sh
python serve.py --data-dir .workbench --env-file .env --port 8765
```

所有命令都输出JSON；`run --wait`输出JSONL。将下面命令交给Code Agent即可；把`PROJECT_ID`、`ACCOUNT_ID`换成前面命令返回的真实ID。

```sh
python scene.py projects
python scene.py create --name 新项目 --rr 系统需求_spec.md --sr 功能设计_spec.md --test test_spec.md --mode auto
python scene.py accounts
python scene.py configure --project PROJECT_ID --account ACCOUNT_ID --model 实际模型ID --concurrency 2
python scene.py run --project PROJECT_ID --wait --mode auto
python scene.py status --project PROJECT_ID
python scene.py events --project PROJECT_ID --node 'G-001:fused-ssd' --after 0
python scene.py artifacts --project PROJECT_ID
```

- `--server http://127.0.0.1:8765`放在子命令之前。首版CLI只连接本机地址，避免把凭证或项目材料误发到其他服务器。
- Markdown RR/SR和Markdown/XLSX测试文件与网页相同。重复`--rr`、`--sr`、`--test`可导入多份文件；重复`--case`可指定用例范围。
- 不加`--wait`时立即返回实际project_id，执行仍继续；旧项目升级时可能返回新project_id，应继续使用返回值。
- `run --wait --timeout 3600 --poll 2`从当前事件游标输出本轮新增事件，不重放全部历史。网页仍显示模型流，CLI输出的事件也带节点和序号。
- 返回码0：完成或成功提交非运行操作；2：等待审核/问题/配置或执行未完成；3：CLI等待超时，服务端继续。结束记录保留`event_cursor`，可用`events --after`继续读取。
- `status`只按实际执行图统计，忽略旧版本孤立节点，不扫描全部产物或模型上下文。

节点指导与回答：

```sh
python scene.py guide --project PROJECT_ID --node 'G-001:fused-ssd' --text '请核对第二次请求的展开依据'
python scene.py answer --project PROJECT_ID --node 'G-001:fused-ssd' --question QUESTION_ID --text '业务确认内容'
```

问题ID和具体阻塞事项可从事件或网页取得。指导仍按既有规则在下一次模型调用前生效，不能即时改写已经发出的请求。手动审核仍在网页查看、编辑并确认，CLI可用`run --wait --mode manual`等待审核状态。

## 每个API Key有自己的模型列表

网页“更多操作→模型配置”现为“模型连接”：

1. 新增连接，填写名称、OpenAI兼容Base URL、API Key，以及该Key允许调用的模型ID（每行一个）。
2. 在项目中选择连接，再从该连接的模型下拉框选择请求模型，保存项目配置。
3. 同一模型可以出现在多个连接下；调用时使用所选连接的Key和URL。不自动切换账号、枚举供应商权限或进行付费探测。

API Key不能独自确定服务地址，Base URL需要填写一次。模型列表是本机允许列表，不授予供应商权限；模型实际仍需支持相应接口能力。

密钥可以隐藏输入，也可以引用服务端.env变量。CLI示例：

```sh
python scene.py save-account --name 百炼账号A --base-url https://供应商地址/v1 --api-key-env BAILIAN_ACCOUNT_A_KEY --model 模型A --model 模型B
python scene.py save-account --name 内网服务 --base-url http://内网地址/v1 --prompt-key --model 内网模型ID
```

不提供`--api-key`命令行参数，避免密钥进入进程参数和Shell历史。`--prompt-key`在终端隐藏输入；自动化建议用服务端.env变量引用。

连接保存在工作台数据目录`model-accounts.local.json`，POSIX权限为0600；项目只保存连接ID和模型。接口只返回名称、URL、模型及凭证是否已配置，不回传Key。连接文件不进入Git、项目导出或前端localStorage。编辑Key时留空保留原值；有并发版本校验，正在使用的连接不能改写。

项目运行前、任务路由和HTTP调用前均检查所选模型属于该Key；没有凭证或模型被移出列表时停止请求，不回退到另一账号。旧报告仍可读，可重新配置后继续。

旧项目的直接配置/.env继续兼容。切换到新的账号连接时移除另一个账号的路由、特殊请求参数和预算路径，旧账本文件不会修改或重置；同一账号的已有预算路径保持。新增连接不会擅自假定供应商额度或单价，若需配额限制应独立配置与实际账号/模型对应的账本。不会因新增连接重置已知的历史额度。

## 精简结果控制区

结果页默认一条紧凑栏（快捷用例、视图、当前产物摘要、展开按钮）。点击“展开工具栏”显示原有完整控制，点击“收起工具栏”释放高度，状态保存在浏览器。测试场景、评测依据、文件下载及缩放功能保留。

## 验收范围

离线验证账号隔离、凭证不回传、不跨Key回退、模型允许列表、并发编辑、旧报告可读、CLI共用项目/API/事件、状态忽略旧节点，以及折叠偏好。没有为本轮UI/CLI修改调用真实模型或重算既有指标。

## 客户模型运行参数及失败节点接管

现已支持`config`、`diagnose`、`configure --max-output-tokens`、思考/流式兼容参数及按任务预算；`repair-export`/`repair-submit`提供输入绑定的Code Agent修复。完整Windows命令与网关差异说明见[客户模型调试](customer-model-debugging.md)。

## business-review-v1更新

现行业务提问为非阻断记录，不再默认暂停节点。`answer`仅保存，typed pending回答按来源节点版本保存。保存或导入不自动执行。`run --wait`以execution_complete区分可执行工作完成与审核完成；详细命令和交接流程见[business-offline-review](business-offline-review.md)。本文件早期“问题阻断后恢复”说明仅适用于旧存档。
