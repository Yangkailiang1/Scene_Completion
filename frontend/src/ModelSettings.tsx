import { useEffect, useState } from "react";
import { api, projectUrl } from "./api";

type Account = {
  id: string;
  name: string;
  base_url: string;
  models: string[];
  credential_configured: boolean;
};
export function ModelSettings({
  project,
  config,
  onSaved,
}: {
  project: string;
  config: Record<string, any>;
  onSaved: () => void;
}) {
  const [catalog, setCatalog] = useState<{
    revision: number;
    accounts: Account[];
  }>({ revision: 0, accounts: [] });
  const [account, setAccount] = useState(config.model_account_id || ""),
    [model, setModel] = useState(config.agent_model || "ecnu-plus"),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const load = () =>
    api("/api/model-accounts")
      .then(setCatalog)
      .catch((e: any) => setMessage(e.message));
  useEffect(() => {
    load();
  }, []);
  const selected = catalog.accounts.find((a) => a.id === account);
  useEffect(() => {
    if (selected && !selected.models.includes(model))
      setModel(selected.models[0]);
  }, [selected, model]);

  const choose = (id: string) => {
    setAccount(id);
    const a = catalog.accounts.find((a) => a.id === id);
    if (a && !a.models.includes(model)) setModel(a.models[0]);
  };
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    const raw = Object.fromEntries(new FormData(e.currentTarget));
    const body: any = { ...raw, agent_model: model, model_account_id: account };
    for (const k of [
      "max_concurrency",
      "max_tokens",
      "max_context_tokens",
      "timeout_seconds",
      "stream_idle_timeout_seconds",
      "stream_total_timeout_seconds",
    ])
      if (raw[k]) body[k] = Number(raw[k]);
    try {
      await api(projectUrl(project, "config"), {
        method: "PUT",
        body: JSON.stringify(body),
      });
      onSaved();
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };
  const saveAccount = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    const form = e.currentTarget;
    const raw = Object.fromEntries(new FormData(form));
    try {
      const data = await api("/api/model-accounts", {
        method: "PUT",
        body: JSON.stringify({
          ...raw,
          id: editing || undefined,
          expected_revision: catalog.revision,
          models: String(raw.models)
            .split(/[\n,，]/)
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      });
      setCatalog(data);
      const id = editing || data.accounts[data.accounts.length - 1].id;
      setAccount(id);
      setModel(data.accounts.find((a: Account) => a.id === id).models[0]);
      form.reset();
      setEditing(null);
      setMessage(
        "连接已保存，密钥仅保存在本机服务端。请选择模型并保存项目配置。",
      );
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };
  const draft = catalog.accounts.find((a) => a.id === editing);
  return (
    <div className="model-account-settings">
      <span className="eyebrow">MODEL CONNECTIONS</span>
      <h2>模型连接</h2>
      <p>
        每个API
        Key管理独立的可用模型列表。网页与CLI使用同一服务端配置，密钥不会返回浏览器或包含在项目导出中。
      </p>
      {message && (
        <p role="status" className="management-notice">
          {message}
        </p>
      )}
      <form onSubmit={submit}>
        <label>
          API Key连接
          <select
            aria-label="API Key连接"
            value={account}
            onChange={(e) => choose(e.target.value)}
          >
            <option value="">当前项目 / .env 旧配置</option>
            {catalog.accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
                {a.credential_configured ? "" : "（密钥未配置）"}
              </option>
            ))}
          </select>
        </label>
        {selected ? (
          <>
            <div className="credential-note">
              {selected.credential_configured
                ? "✓ 密钥已配置"
                : "需要在服务端配置对应环境变量"}{" "}
              · {selected.base_url}
              <button type="button" onClick={() => setEditing(selected.id)}>
                编辑此连接
              </button>
            </div>
            <label>
              请求模型
              <select
                aria-label="请求模型"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                {selected.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
          </>
        ) : (
          <>
            {config.credential_configured && (
              <div className="credential-note">✓ 当前服务端已配置凭证</div>
            )}
            <label>
              OpenAI兼容Base URL
              <input
                name="base_url"
                required
                defaultValue={config.base_url || ""}
                placeholder="https://服务地址/v1"
              />
            </label>
            <label>
              请求模型
              <input
                aria-label="请求模型"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                required
              />
            </label>
            <label>
              API Key
              <input
                type="password"
                name="api_key"
                autoComplete="off"
                placeholder="留空保留已有凭证"
              />
            </label>
          </>
        )}
        <details className="model-advanced">
          <summary>运行参数（可选）</summary>
          <div className="form-grid">
            {[
              ["max_concurrency", "并发任务数", 2, 1, 8],
              ["max_tokens", "输出Token上限", 12000, 256, 64000],
              [
                "max_context_tokens",
                "上下文总上限（含输出预留）",
                200000,
                1024,
                2000000,
              ],
              ["timeout_seconds", "连接等待（秒）", 120, 10, 1800],
              [
                "stream_idle_timeout_seconds",
                "流中无数据等待（秒）",
                300,
                10,
                1800,
              ],
              [
                "stream_total_timeout_seconds",
                "生成总时限（秒）",
                900,
                30,
                3600,
              ],
            ].map(([k, label, fallback, min, max]) => (
              <label key={String(k)}>
                {label}
                <input
                  name={String(k)}
                  type="number"
                  min={Number(min)}
                  max={Number(max)}
                  defaultValue={config[String(k)] ?? fallback}
                />
              </label>
            ))}
          </div>
          <p>
            输出上限不是保证长度；超时不自动重复POST。模型是否支持工具调用与流式输出，仍以供应方接口能力为准。
          </p>
        </details>
        <button className="model-primary-button" type="submit" disabled={busy}>
          保存项目配置
        </button>
      </form>
      <section className="model-account-editor">
        <button
          type="button"
          aria-expanded={editing !== null}
          onClick={() => setEditing(editing === null ? "" : null)}
        >
          {editing !== null ? "收起连接编辑" : "新增API Key连接"}
        </button>
        {editing !== null && (
          <form key={editing ?? "new"} onSubmit={saveAccount}>
            <label>
              连接名称
              <input
                name="name"
                required
                defaultValue={draft?.name || ""}
                placeholder="例如：百炼账号A、内网模型"
              />
            </label>
            <label>
              Base URL
              <input
                name="base_url"
                required
                defaultValue={draft?.base_url || ""}
                placeholder="OpenAI兼容接口地址，包含/v1"
              />
            </label>
            <label>
              API Key（隐藏输入）
              <input
                name="api_key"
                type="password"
                autoComplete="new-password"
                placeholder={
                  draft ? "留空保留已有Key" : "填写API Key，或下方填环境变量名"
                }
              />
            </label>
            <label>
              服务端环境变量名（可选）
              <input
                name="api_key_env"
                placeholder="例如 Bailian_API_Key2；填此项时使用.env中的对应值"
              />
            </label>
            <label>
              此Key允许调用的模型
              <textarea
                name="models"
                required
                rows={4}
                defaultValue={draft?.models.join("\n") || ""}
                placeholder={
                  "每行一个实际模型ID\n模型权限由供应商决定，本列表不授予新权限"
                }
              />
            </label>
            <button type="submit" disabled={busy}>
              保存连接
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
