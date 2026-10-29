import { useEffect, useState } from "react";
import { api, projectUrl } from "./api";
export function ManagerModelProfile({ project }: { project: string }) {
  const [data, setData] = useState<any>(null),
    [accounts, setAccounts] = useState<any[]>([]),
    [account, setAccount] = useState(""),
    [model, setModel] = useState(""),
    [message, setMessage] = useState("");
  useEffect(() => {
    Promise.all([
      api(projectUrl(project, "manager/model")),
      api("/api/model-accounts"),
    ])
      .then(([v, a]) => {
        setData(v);
        setAccounts(a.accounts || []);
        setAccount(v.settings?.model_account_id || "");
        setModel(v.settings?.agent_model || "");
      })
      .catch((e) => setMessage(e.message));
  }, [project]);
  const selected = accounts.find((a) => a.id === account);
  return (
    <section className="manager-model-profile" id="model-manager">
      <h3>管理Agent模型</h3>
      <p>
        独立保存连接、模型和上下文预算；与流水线共享账号额度及网关并发限制。
      </p>
      {message && <p role="status">{message}</p>}
      {data && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            try {
              const v = await api(projectUrl(project, "manager/model"), {
                method: "PUT",
                body: JSON.stringify({
                  expected_revision: data.revision,
                  config: {
                    model_account_id: account,
                    agent_model: model,
                    max_tokens: Number(f.get("max_tokens")),
                    max_context_tokens: Number(f.get("context")),
                    thinking_override:
                      f.get("thinking") === "off" ? false : null,
                    thinking_api: "chat_template_kwargs",
                  },
                }),
              });
              setData(v);
              setMessage("管理Agent模型已独立保存，下一请求生效。");
            } catch (e: any) {
              setMessage(e.message);
            }
          }}
        >
          <div className="form-grid">
            <label>
              管理Agent的API连接
              <select
                value={account}
                onChange={(e) => {
                  setAccount(e.target.value);
                  setModel(
                    accounts.find((a) => a.id === e.target.value)?.models[0] ||
                      model,
                  );
                }}
              >
                <option value="">服务端 .env / 项目初始连接</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              管理Agent模型
              {selected ? (
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {selected.models.map((m: string) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  required
                />
              )}
            </label>
            <label>
              输出预留
              <input
                type="number"
                name="max_tokens"
                min={256}
                defaultValue={data.settings?.max_tokens || 12000}
              />
            </label>
            <label>
              上下文上限
              <input
                type="number"
                name="context"
                min={4096}
                defaultValue={data.settings?.max_context_tokens || 200000}
              />
            </label>
            <label>
              思考模式
              <select
                name="thinking"
                defaultValue={
                  data.settings?.thinking_override === false ? "off" : "auto"
                }
              >
                <option value="off">关闭（客户模板参数）</option>
                <option value="auto">跟随网关</option>
              </select>
            </label>
          </div>
          <button className="model-primary-button">保存管理Agent模型</button>
        </form>
      )}
    </section>
  );
}
