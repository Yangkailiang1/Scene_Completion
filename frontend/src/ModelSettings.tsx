import { useEffect, useState } from "react";
import { ManagerModelProfile } from "./ManagerModelProfile";
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
  const [managerOpen, setManagerOpen] = useState(false);
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
    body.resilience = {
      ...(config.resilience || {}),
      enabled: raw.failover_enabled === "on",
      candidates: [
        ...(config.resilience?.candidates || []).filter(
          (v: any) => v.account_id,
        ),
        ...String(raw.failover_models || "")
          .split(/[\n,，]/)
          .map((s) => s.trim())
          .filter(Boolean)
          .map((model) => ({ model })),
      ],
      min_tokens_per_second: Number(raw.failover_rate || 2),
      window_seconds: Number(raw.failover_window || 30),
      low_windows: Number(raw.failover_low_windows || 2),
      max_switches: Number(raw.failover_max_switches || 0),
      cooldown_seconds: Number(raw.failover_cooldown || 0),
      grace_seconds: Number(raw.failover_grace || 60),
      no_output_seconds: Number(raw.failover_stall || 120),
    };
    for (const k of Object.keys(body))
      if (k.startsWith("failover_")) delete body[k];
    body.thinking = raw.thinking === "auto" ? null : raw.thinking === "on";
    body.stream_reasoning = raw.stream_reasoning === "on";
    body.supplement_tests = raw.supplement_tests === "on";
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
      <h2>模型与连接设置</h2>
      <p>
        每个API
        Key管理独立的可用模型列表。网页与CLI使用同一服务端配置，密钥不会返回浏览器或包含在项目导出中。
      </p>
      {message && (
        <p role="status" className="management-notice">
          {message}
        </p>
      )}
      <nav className="model-section-nav" aria-label="模型设置分组">
        {[
          ["model-connections", "API连接"],
          ["model-pipeline", "流水线模型"],
          ["model-manager", "管理Agent模型"],
          ["model-runtime", "运行与切换策略"],
        ].map(([id, label]) => (
          <button
            type="button"
            key={id}
            onClick={() => {
              if (id === "model-manager") setManagerOpen(true);
              document
                .getElementById(id)
                ?.scrollIntoView?.({ behavior: "smooth", block: "start" });
            }}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="connection-overview" id="model-connections">
        <h3>API连接</h3>
        <div>
          {catalog.accounts.map((a) => (
            <button
              type="button"
              key={a.id}
              onClick={() => {
                choose(a.id);
                setEditing(a.id);
              }}
            >
              <strong>{a.name}</strong>
              <small>
                {a.models.length} 个模型 ·{" "}
                {a.credential_configured ? "已配置密钥" : "待配置"}
              </small>
            </button>
          ))}
        </div>
        <button type="button" onClick={() => setEditing("")}>
          新增API Key连接
        </button>
      </div>
      <form
        className="pipeline-model-form"
        onSubmit={submit}
        id="model-pipeline"
      >
        <h3>流水线模型</h3>
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
        <details className="model-advanced" id="model-runtime">
          <summary>运行参数（可选）</summary>
          <div className="form-grid">
            <label>
              思考模式
              <select
                name="thinking"
                defaultValue={
                  (config.thinking_override ?? config.thinking) === false
                    ? "off"
                    : (config.thinking_override ?? config.thinking) === true
                      ? "on"
                      : "auto"
                }
              >
                <option value="auto">跟随网关／模型配置</option>
                <option value="on">请求开启思考</option>
                <option value="off">请求关闭思考</option>
              </select>
            </label>
            <label>
              网关思考开关格式
              <select
                name="thinking_api"
                defaultValue={config.thinking_api || "legacy"}
              >
                <option value="legacy">thinking.type（DeepSeek格式）</option>
                <option value="enable_thinking">enable_thinking（布尔）</option>
                <option value="chat_template_kwargs">
                  chat_template_kwargs.enable_thinking（客户网关）
                </option>
                <option value="omit">不发送开关</option>
              </select>
            </label>
            <label>
              模型思考流
              <select
                name="stream_reasoning"
                defaultValue={config.stream_reasoning ? "on" : "off"}
              >
                <option value="off">仅显示思考进度</option>
                <option value="on">显示并保存供应商思考文本</option>
              </select>
            </label>
            <label>
              程序补充测试场景
              <select
                name="supplement_tests"
                defaultValue={config.supplement_tests ? "on" : "off"}
              >
                <option value="off">关闭，仅使用原始测试</option>
                <option value="on">开启，单独保存扩展测试指标</option>
              </select>
            </label>
            {[
              ["max_concurrency", "并发任务数", 2, 1, 8],
              [
                "max_tokens",
                "输出Token上限（含思考，依网关）",
                12000,
                256,
                2000000,
              ],
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
            显示思考会把网关返回的思考字段保存到本地节点事件及结果导出包，独立于正式JSON产物；只对后续请求生效。关闭思考需要网关支持，不等于隐藏思考流。输出上限不是保证长度；超时不自动重复POST。模型是否支持工具调用与流式输出，仍以供应方接口能力为准。
          </p>
        </details>
        <details className="model-advanced">
          <summary>吞吐监视与模型切换</summary>
          <p>
            只影响后续请求，已通过产物继续校验复用。在途请求保留原配置；关闭低吞吐流不保证供应商停止计算，未知用量保留。
          </p>
          <label>
            <input
              type="checkbox"
              name="failover_enabled"
              defaultChecked={config.resilience?.enabled || false}
            />
            启用按候选模型切换
          </label>
          <label>
            同一API Key的候选模型（每行一个，按顺序）
            <textarea
              name="failover_models"
              rows={3}
              defaultValue={(config.resilience?.candidates || [])
                .filter((c: any) => !c.account_id)
                .map((c: any) => c.model)
                .join("\n")}
              placeholder="必须包含在该连接允许模型列表中"
            />
          </label>
          <div className="form-grid">
            {[
              [
                "failover_rate",
                "min_tokens_per_second",
                "低吞吐阈值（估算Token/秒）",
                2,
                0,
              ],
              ["failover_window", "window_seconds", "观察窗口（秒）", 30, 5],
              ["failover_low_windows", "low_windows", "连续低速窗口数", 2, 1],
              [
                "failover_max_switches",
                "max_switches",
                "每次最多切换次数",
                2,
                0,
              ],
              [
                "failover_cooldown",
                "cooldown_seconds",
                "降级模型冷却（秒）",
                300,
                0,
              ],
              ["failover_grace", "grace_seconds", "开始生成宽限（秒）", 60, 0],
              [
                "failover_stall",
                "no_output_seconds",
                "无生成内容时限（秒）",
                120,
                10,
              ],
            ].map(([name, key, label, fallback, min]) => (
              <label key={String(name)}>
                {label}
                <input
                  type="number"
                  step={name === "failover_rate" ? "0.1" : "1"}
                  name={String(name)}
                  min={Number(min)}
                  defaultValue={config.resilience?.[String(key)] ?? fallback}
                />
              </label>
            ))}
          </div>
          <p>
            速率为正文、工具参数及供应商公开思考的UTF-8字节÷4估算值，不是计费Token。默认连续两个低速窗口才切换；仅SSE心跳不视为生成。候选预算不足或不在允许列表时不会绕过保护。
          </p>
        </details>
        <button className="model-primary-button" type="submit" disabled={busy}>
          保存项目配置
        </button>
      </form>
      <details
        className="model-manager-section"
        id="model-manager"
        open={managerOpen}
        onToggle={(e) => setManagerOpen(e.currentTarget.open)}
      >
        <summary>管理Agent模型</summary>
        {managerOpen && <ManagerModelProfile project={project} />}
      </details>
      <section
        className={
          editing !== null
            ? "model-account-editor open"
            : "model-account-editor"
        }
      >
        {editing !== null && (
          <div className="account-drawer-heading">
            <h3>{editing ? "编辑API连接" : "新增API连接"}</h3>
            <button type="button" onClick={() => setEditing(null)}>
              关闭
            </button>
          </div>
        )}
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
