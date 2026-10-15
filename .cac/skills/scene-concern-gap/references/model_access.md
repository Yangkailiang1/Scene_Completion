# 模型可用性与并发配置

运行前先读当前配置及环境变量；不得从 Skill 中选择固定模型。语义、embedding 和独立效果审查可以分别配置。使用 `check-models --config <配置> --output-dir <检查目录>` 串行检查当前语义模型；其他候选通过重复的 `--candidate-model <ID>` 指定。需要向量或独立审查时，增加 `--include-embedding`、`--include-review`，独立向量端点使用 `--embedding-config`。`--discover` 只列出端点目录，目录中的名字不等于已验证可调用。

根据 `available_models.json` 选择当前地址、凭证和执行设置下检查成功的模型，再用 `configure-models --config <原配置> --checked-report <检查报告> --agent-model <已通过ID> --max-concurrency <正整数> --output-config <本地运行配置>` 保存选择。embedding 和审查选择使用 `--embedding-model`、`--review-model`；独立 embedding 配置另用 `--embedding-config` 和 `--output-embedding-config` 保存。运行及续跑使用保存的配置，不重标旧执行身份，不把失败模型静默替换为另一模型。

首次未知并发能力默认设为 1。Agent 根据客户给出的限制、调用成功情况及限流记录，通过配置或 `--max-concurrency` 调整整个运行的上限；不要并行启动多个 worker 来绕开共享上限。默认 `adaptive_concurrency=true`，DAG 遇限流会把实际并发减半至至少 1，并在 `concurrency_status.json` 保存下降值；成功请求不证明可以提高并发，提升须有实际依据。需要重新试验上限时先结束当前运行，再调整本地配置；同一上限续跑保留已降低的实际值。

自动预检仅在需要新的外部调用时进行；有效的成功产物续跑不为检查模型而新增调用。可用性记录绑定地址、凭证指纹、模型、运行方式和推理设置，保存时不包含密钥。不可访问、无权限或鉴权失败进入待配置，不消耗语义修复预算；同一配置在记录有效期内不重复请求。已确认额度恢复或权限变更可用 `check-models --refresh` 重检；不要对仍不可访问的模型不断重试。网络或限流失败保留传输分类，不将其当成语义缺陷。默认成功记录有效 900 秒，拒绝记录有效 300 秒，可用 `availability_ttl_seconds` 调整。

`model_preflight=off` 仅用于受控离线测试；正式运行保留 `auto`。所有阶段仍核验实际请求和结果身份，探测通过不代替内容、来源或结构检查。

不同提供方的思考参数由配置选择：`thinking_api=enable_thinking`明确传递布尔开关；默认`legacy`保留兼容格式。不要只改模型名却继续套用另一端点的参数。流式用量可配置`include_usage=true`。语义及embedding可分开地址、凭证和模型配置。

有限实验额度使用`token_budget_limit`、`token_budget_ledger`约束语义API，不包含其他端点的embedding或宿主主控请求。工具按输入字节代理和输出预留共享额度，完成后按提供方返回的总tokens结算；输出上限不含思考时，须配置`token_budget_reasoning_reserve`为本次档位的思考上限。未知用量保守占用并阻止新请求，预算模式取消隐式HTTP重试。预检、诊断、修复及独立审查的语义调用也使用同一账本，不能通过新配置、换目录或续跑重置已用额度。账本是本地请求保护，不是账户剩余额度证明。
