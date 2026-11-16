# 补充对照：Pi受限文件工具与普通LLM（2026-11-16）

新增显式实验入口 `file_experiment.py`，设计与隔离说明见[FILE_EXPERIMENT.md](FILE_EXPERIMENT.md)。真实72次执行：普通LLM交付35/36、有限原文核对合格26/36；Pi交付36/36、核对合格25/36。Pi自主选工具，实际文件使用0次；不能据此推断真实文件读写的效果。Pi Token多22.35%，当前没有替换运行时的证据。完整记录见[验收报告](../../../docs/history/acceptance/pi-files-real-20261116.md)。以下原Deep Agents/Pi实验及其结果继续独立保留。

---

# Pi 节点对照实验（真实实验 v2）

当前实验只比较 Deep Agents（A）和 Pi SDK 1.5.2（B）。18个不同批次覆盖五用例的绑定/生成/比较，加E架构识别、GT链路/架构识别；两组各两轮，正式结果72次。先运行20次代表执行，再扩样。第一轮先跑方逐批交错，第二轮严格反转；SDK内部拒绝的候选也按实际响应计入首次失败和修复次数。

当前用户授权共享账本总上限100,000,000 Token，包含历史消耗。旧用量始终保留。用户在新连接故障出现后再次明确要求继续：本实验对已足额保守记账的未知用量采用继续策略，失败执行不重发、转入故障清单，继续其他独立节点；正式项目仍保持unknown_usage_policy=stop。供应商额度/鉴权不足、预算上限、账本异常和未结束请求仍阻止继续。配置与授权文字保存在冻结清单，不能把本实验策略扩散到正式模型配置。

真实运行曾发现第二轮先跑顺序和首次失败统计问题，已修复并添加回归。按预先记录的“整体排除第二轮”规则归档了12次调试执行，再生成正式第二轮；没有依据结果挑选更好的输出。调试请求及用量保留在order-debug/及原账本。运行时修订的旧清单和身份保留在manifest-history/，输入、提示、Schema、模型及业务规则未改变。

复现当前实验可使用已有冻结目录执行 status、resume、report；已完成执行不会重发。重新冻结用 `freeze --suite full`（默认full）；`--suite representative`保留五批次小实验。run/resume可用 `--phase pilot` 或 `--phase all`。若要复核本次结论，请使用交付的实际清单、授权记录、原始请求及报告，不以以下历史v1接入测试充当真实模型结果。

---

# 初版接入与命令说明（历史 v1）

这是显式启用的开发实验，不是正式模型运行时。A 使用当前 Deep Agents；B 使用 Pi SDK 1.5.2 的独立进程。两组共用原节点准备、完整中间件提示、传输适配、提交工具、业务校验和错误修复输入。Pi 通过 Python broker 请求模型，不持有真实凭证；不开放 Shell、文件工具、全局配置或跨会话记忆。正式工作流配置、模型提示正文和历史产物均不修改。

## 准备与独立回归

在仓库根目录使用项目 Python；下例 `python` 指项目虚拟环境。实验 Node 依赖不进入正式 Windows 包，也不影响普通 `make check`。首次使用必须安装完整锁定依赖，不静默跳过测试。

```sh
npm ci --ignore-scripts --prefix deployment/experiments/pi_node --registry=https://registry.npmjs.org
python -m pytest deployment/experiments/pi_node/test_experiment.py -q
npm test --prefix deployment/experiments/pi_node
```

## 冻结—运行—恢复—报告

所有命令均支持从其他工作目录执行，脚本路径可使用绝对路径。`PROJECT` 是五用例项目目录；`OUT` 必须是一个新的独立目录，不能放在正式项目内部。参数示例中的路径需要替换为实际路径。

```sh
python deployment/experiments/pi_node/experiment.py freeze \
  --project "$PROJECT" --config "$PROJECT/model.local.json" \
  --env-file "$REPO/.env" --output "$OUT"
python deployment/experiments/pi_node/experiment.py status --output "$OUT"
python deployment/experiments/pi_node/experiment.py run --output "$OUT"
python deployment/experiments/pi_node/experiment.py resume --output "$OUT"
python deployment/experiments/pi_node/experiment.py report --output "$OUT"
```

冻结只读取真实任务包和模型配置，不读取历史模型答案。五类各一个真实完整批次、两组各两次，共20次节点执行。E/GT交互识别已脚本完成时，采用已有项目范围识别任务，并在清单注明范围。每个样本都记录原任务身份、原文件哈希、输入/Schema/Skill及代码身份；去除历史失败候选。每次使用新目录和新会话，不复用模型结果。A/B顺序交错，单节点累计最多五次请求，包括格式与业务校验修复。成功记录在恢复时只跳过，不再次发送。

当前项目配置为 `json_text` 提交时，两组均保留相同传输：现有适配器将完整业务JSON交给相同 `submit_result` 校验，Pi 仍实际执行自己的工具循环。不会为了让 Pi 使用原生 tool calls 而改变 A 的提交方式。首次请求（含 Deep Agents 自动追加的中间件说明）有模拟回归验证完全一致。

预算沿用原授权账本（用户追加4M后总额6M），额外的 `experiment-cap.json` 仅作250k子上限，不替代原账本。任何未决用量、在途请求或配对预算不足都会阻止派发；连接失败不自动重复。全局和实验记账均保留保守用量。退出码0表示命令执行完成，2表示门槛或执行失败；`execution_complete`不等于业务审核通过。若进程在一次执行中途退出而没有完整审计总结，`resume`停止并要求审计，不盲目重发。

## 独立业务审核

`report`生成HTML/JSON报告及 `blind-review/`：结果隐藏运行方式，允许的冻结输入在 `blind-review/inputs/`，原文核对清单在 `checklists/`。导入时保存的原始RR/SR Markdown另外冻结在 `review-sources/`并校验文件哈希，仅供审核，不注入模型。`blinding-private.json`及完整运行轨迹包含分组，不交给盲审者。审核草稿和已采纳审核都不会被重新生成报告覆盖。

审核者需逐条核对输入与原文，填写工作表的 `rubric`、`source_checks`，置 `reviewed=true`。错误计数为非负整数，模板完整度/匹配准确度填写 `{"passed":N,"total":N}`；填写出处位置和核对结论。旧模型结果不是标准答案，也不以另一个LLM的赞同替代核对。

```sh
python deployment/experiments/pi_node/experiment.py review-submit \
  --output "$OUT" --file "$REVIEWED_FILE"
python deployment/experiments/pi_node/experiment.py report --output "$OUT"
```

审核绑定匿名编号、输入及结果哈希；修订保留历史。Schema通过单独计为交付，业务正确性在独立审核后计分。报告列出首次交付、最终交付、遗漏/错绑/无据补充/引用错误、修复次数、输入输出Token、耗时、每份合格产物Token。未返回用量保守记账并单列；不虚构货币价格。实际供应商模型不同、用量未知或审核未完成的配对不作能力优劣比较。

每类两轮配对和审核齐备后才给节点建议：Pi合格数更高且错误不增，或同样全部合格且Token/耗时降低至少20%、另一项不增超过10%，标记“适合试用 Pi”。否则保持当前实现；不完整则“证据不足”。这是小样本试用建议，不宣称普遍优胜，不自动切换正式工作流。

## 2026-11-14 当前门槛

用户已追加4M Token，原账本总额6,000,000，保守已用1,715,564，剩余4,284,436；原请求 `b174f91ddacd42c69da75701cd51db68` 的69,098 Token用量仍未核对。需真实供应商记录解决该笔未决用量后才能运行；本实验没有结算命令，不清空、不重置、不另建授权绕过。模拟测试仅验证适配器，不构成Pi效果实验结果。

上游依据：[Pi SDK](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/docs/sdk.md)、[OpenClaw嵌入Pi的官方历史架构说明](https://github.com/openclaw/openclaw/blob/v2026.3.2/docs/pi.md)。本实验没有引入OpenClaw网关或其其他功能。
