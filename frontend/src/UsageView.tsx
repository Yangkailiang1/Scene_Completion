import { useEffect, useState } from "react";
import { Button } from "./components/ui/button";
import { api, projectUrl } from "./api";
import { duration } from "./utils";

const number = (n: number | undefined) => (n || 0).toLocaleString();
const cache = new Map<string, { at: number; data: any }>();
export function UsageView({
  project,
  task,
  onClose,
  onSelect,
}: {
  project: string;
  task: string | null;
  onClose: () => void;
  onSelect: (key: string) => void;
}) {
  const [session, setSession] = useState(""),
    [account, setAccount] = useState("");
  const [view, setView] = useState("tasks"),
    [scope, setScope] = useState(task || ""),
    [role, setRole] = useState(""),
    [model, setModel] = useState(""),
    [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0),
    [data, setData] = useState<any>(null),
    [summary, setSummary] = useState<any>(null),
    [context, setContext] = useState<any>(null),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0),
    [round, setRound] = useState("");
  useEffect(() => {
    setScope(task || "");
    setOffset(0);
    setContext(null);
    setSession("");
  }, [project, task]);
  useEffect(() => {
    const controller = new AbortController();
    api(projectUrl(project, "usage"), { signal: controller.signal })
      .then(setSummary)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [project, reload]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const p = new URLSearchParams({
        view,
        offset: String(offset),
        limit: "50",
        search: query,
      });
      if (account) p.set("account", account);
      if (session) p.set("session_id", session);
      if (scope) p.set("task_key", scope);
      if (role) p.set("role", role);
      if (model) p.set("model", model);
      if (round) p.set("after", round);
      const url = projectUrl(project, "usage?" + p.toString()),
        saved = cache.get(url);
      if (saved && Date.now() - saved.at < 5000 && !reload) {
        setData(saved.data);
        return;
      }
      api(url, { signal: controller.signal })
        .then((d) => {
          cache.set(url, { at: Date.now(), data: d });
          setData(d);
          setError("");
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
    }, 180);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    project,
    view,
    scope,
    role,
    model,
    query,
    offset,
    reload,
    round,
    session,
    account,
  ]);
  useEffect(() => {
    const timer = setInterval(() => {
      if (!document.hidden) setReload((v) => v + 1);
    }, 15000);
    return () => clearInterval(timer);
  }, [project]);
  const totals = data?.totals || summary?.totals || {};
  function filter(fn: () => void) {
    fn();
    setOffset(0);
    setContext(null);
  }
  return (
    <div className="usage-view panel-scroll">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" onClick={onClose}>
          返回工作区
        </Button>
        <h2>用量与费用</h2>
        <Button variant="outline" onClick={() => setReload((v) => v + 1)}>
          刷新统计
        </Button>
        <a href={projectUrl(project, "usage?format=csv")}>下载CSV</a>
        <a
          href={projectUrl(project, "usage?format=download")}
          download="usage.json"
        >
          下载JSON
        </a>
      </div>
      <div className="usage-totals">
        {[
          ["输入 Token", totals.input_tokens],
          ["缓存输入（输入子集）", totals.cached_input_tokens],
          ["输出 Token", totals.output_tokens],
          ["其中思考（输出子集）", totals.reasoning_tokens],
          ["已报告总 Token", totals.reported_total_tokens],
          ["未知用量请求", totals.unknown_usage_calls],
        ].map(([label, value]) => (
          <div key={String(label)}>
            <span>{label}</span>
            <strong>{number(value as number)}</strong>
          </div>
        ))}
      </div>
      <p>
        实际费用：未知；
        {totals.estimated_cost == null
          ? "尚未配置估算单价"
          : "估算费用：" + totals.estimated_cost}
        。免费额度、预留额度与实际扣费分开核算。
      </p>
      <p>
        已发起 {number((totals.calls || 0) - (totals.not_sent_calls || 0))}{" "}
        次；发送前阻止 {number(totals.not_sent_calls)} 次；累计请求耗时{" "}
        {duration(totals.request_seconds)}。累计请求时间不是项目墙钟时间。
      </p>
      <div className="flex flex-wrap gap-2 my-4">
        <select
          aria-label="用量视图"
          value={view}
          onChange={(e) => filter(() => setView(e.target.value))}
        >
          <option value="tasks">按任务</option>
          <option value="requests">逐请求明细</option>
        </select>
        <select
          aria-label="执行轮"
          value={session}
          onChange={(e) => filter(() => setSession(e.target.value))}
        >
          <option value="">全部历史尝试</option>
          {summary?.sessions
            ?.slice()
            .reverse()
            .map((s: any, n: number) => (
              <option key={s.id} value={s.id}>
                {n === 0 ? "当前执行轮 · " : "历史执行轮 · "}
                {new Date(s.started_at * 1000).toLocaleString()}
              </option>
            ))}
        </select>
        <select
          aria-label="账号筛选"
          value={account}
          onChange={(e) => filter(() => setAccount(e.target.value))}
        >
          <option value="">全部账号（独立额度池）</option>
          {summary?.groups?.account?.map((a: any) => (
            <option key={a.name}>{a.name}</option>
          ))}
        </select>
        <select
          aria-label="角色筛选"
          value={role}
          onChange={(e) => filter(() => setRole(e.target.value))}
        >
          <option value="">全部角色</option>
          <option value="modeler">建模器</option>
          <option value="checker">检查器</option>
          <option value="recommender">推荐器</option>
        </select>
        <select
          aria-label="模型筛选"
          value={model}
          onChange={(e) => filter(() => setModel(e.target.value))}
        >
          <option value="">全部模型</option>
          {summary?.groups?.model?.map((m: any) => (
            <option key={m.name}>{m.name}</option>
          ))}
        </select>
        <input
          aria-label="搜索用量任务"
          placeholder="搜索任务、用例或状态"
          value={query}
          onChange={(e) => filter(() => setQuery(e.target.value))}
        />
        <input
          aria-label="执行轮起始时间"
          type="datetime-local"
          onChange={(e) =>
            filter(() =>
              setRound(
                e.target.value
                  ? String(new Date(e.target.value).getTime() / 1000)
                  : "",
              ),
            )
          }
        />
        {scope && (
          <Button variant="outline" onClick={() => filter(() => setScope(""))}>
            全部任务（当前：{scope}）
          </Button>
        )}
      </div>
      <details className="my-4">
        <summary>按任务／角色／模型／用例汇总</summary>
        {Object.entries(data?.groups || summary?.groups || {}).map(
          ([dimension, rows]) => (
            <div key={dimension}>
              <h3>
                {
                  (
                    {
                      account: "账号（独立额度池）",
                      role: "角色",
                      model: "模型",
                      case: "用例",
                      stage: "任务类别",
                    } as Record<string, string>
                  )[dimension]
                }
              </h3>
              {(rows as any[]).map((r) => (
                <p key={r.name}>
                  {r.name} · {number(r.tokens)} Token（输入{" "}
                  {number(r.input_tokens)}，输出 {number(r.output_tokens)}
                  ，其中思考 {number(r.reasoning_tokens)}） · {r.requests} 请求
                  · {duration(r.seconds)}
                </p>
              ))}
            </div>
          ),
        )}
      </details>
      <details className="my-4">
        <summary>配置估算单价（人民币／百万Token）</summary>
        <form
          className="flex flex-wrap gap-2 my-4"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget),
              name = String(f.get("price_model"));
            const price: Record<string, number> = {
              input: Number(f.get("price_input")),
              output: Number(f.get("price_output")),
            };
            if (f.get("price_cached") !== "")
              price.cached_input = Number(f.get("price_cached"));
            api(projectUrl(project, "usage/prices"), {
              method: "PUT",
              body: JSON.stringify({ ...summary?.prices, [name]: price }),
            })
              .then(() => setReload((v) => v + 1))
              .catch((e) => setError(e.message));
          }}
        >
          <input
            name="price_model"
            aria-label="估算模型标识"
            placeholder="模型标识"
            required
          />
          <input
            name="price_input"
            aria-label="输入单价"
            type="number"
            min="0"
            step="any"
            placeholder="输入单价"
            required
          />
          <input
            name="price_output"
            aria-label="输出单价"
            type="number"
            min="0"
            step="any"
            placeholder="输出单价"
            required
          />
          <input
            name="price_cached"
            aria-label="缓存输入单价"
            type="number"
            min="0"
            step="any"
            placeholder="缓存输入单价（可选）"
          />
          <Button type="submit">保存估算单价</Button>
        </form>
        <p>仅提供估算，不代表实际扣费；不自动假设计费模型、折扣或免费额度。</p>
      </details>
      <p>
        当前统计范围复用事件：{data?.reuse_events ?? summary?.reuse_events ?? 0}
        。复用不是新的扣费请求；历史累计包含此前尝试，执行轮筛选仅显示本轮增量。
      </p>
      {error && <p role="alert">{error}</p>}
      {!data ? (
        <p>正在读取统计…</p>
      ) : (
        <div className="usage-table">
          <table>
            <thead>
              <tr>
                <th>任务／请求模型</th>
                <th>状态</th>
                <th>输入</th>
                <th>输出</th>
                <th>其中思考</th>
                <th>总Token</th>
                <th>请求／未发出</th>
                <th>累计耗时</th>
                <th>估算费用（元）</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r: any) => (
                <tr key={r.id || r.task_key}>
                  <td>
                    <button onClick={() => onSelect(r.task_key)}>
                      {r.label || r.task_key}
                    </button>
                    <small>
                      {r.task_key}
                      <br />
                      {(r.models || [r.model]).join("、")}
                      <br />
                      {r.account ||
                        (r.accounts || []).join("、") ||
                        "历史未标注账号"}
                    </small>
                  </td>
                  <td>{r.status}</td>
                  <td>{number(r.usage?.prompt_tokens ?? r.input_tokens)}</td>
                  <td>
                    {number(r.usage?.completion_tokens ?? r.output_tokens)}
                  </td>
                  <td>
                    {number(
                      r.usage?.completion_tokens_details?.reasoning_tokens ??
                        r.reasoning_tokens,
                    )}
                  </td>
                  <td>
                    {r.usage
                      ? number(r.usage.total_tokens)
                      : r.reported_total_tokens != null
                        ? number(r.reported_total_tokens)
                        : "未知"}
                  </td>
                  <td>
                    {r.calls != null
                      ? `${r.calls - r.not_sent_calls} / ${r.not_sent_calls}`
                      : r.status === "not_sent"
                        ? "未发出"
                        : "1"}
                  </td>
                  <td>{duration(r.seconds ?? r.request_seconds)}</td>
                  <td>
                    {r.estimated_cost == null
                      ? "未知"
                      : r.estimated_cost.toFixed(6)}
                    <small>实际扣费未知</small>
                  </td>
                  <td>
                    <button
                      onClick={() => {
                        api(
                          projectUrl(
                            project,
                            "context?task_key=" +
                              encodeURIComponent(r.task_key),
                          ),
                        )
                          .then(setContext)
                          .catch((e) => setError(e.message));
                      }}
                    >
                      按需查看上下文
                    </button>
                    {view === "requests" && (
                      <details>
                        <summary>请求诊断</summary>
                        <pre>{JSON.stringify(r, null, 2)}</pre>
                      </details>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex gap-3 items-center my-4">
        <Button
          disabled={!offset}
          onClick={() => setOffset((v) => Math.max(0, v - 50))}
        >
          上一页
        </Button>
        <span>
          {offset + 1}–{Math.min(offset + 50, data?.count || 0)} /{" "}
          {data?.count || 0}
        </span>
        <Button
          disabled={offset + 50 >= (data?.count || 0)}
          onClick={() => setOffset((v) => v + 50)}
        >
          下一页
        </Button>
      </div>
      {context && (
        <details open>
          <summary>当前节点模型上下文（不含凭证）</summary>
          <pre className="usage-context">
            {JSON.stringify(context, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
