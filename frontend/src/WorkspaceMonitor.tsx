import { useEffect, useState } from "react";
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Clock3,
  Settings2,
  Download,
} from "lucide-react";
import { api, projectUrl } from "./api";
import { ThroughputView } from "./ThroughputView";
import { duration } from "./utils";
const rate = (value: any) =>
  typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(1)} 估算 tok/s`
    : "暂无可测速率";
function remaining(estimate: any) {
  if (estimate?.status === "complete") return "本轮已完成";
  if (estimate?.status === "discovering") return "后续任务发现中";
  if (estimate?.seconds == null) return "样本不足，暂不能预计";
  const text = `${duration(estimate.lower_seconds)}–${duration(estimate.upper_seconds)}`;
  return estimate.status === "blocked"
    ? `解除阻塞后约 ${text}`
    : estimate.status === "paused"
      ? `恢复运行后约 ${text}`
      : `约 ${text}`;
}
const eventNames: Record<string, string> = {
  model_switched: "已切换模型",
  model_degraded: "模型已降级",
  model_switch_skipped: "跳过候选",
  rate_limit_wait: "限流冷却",
};
export function WorkspaceMonitor({
  project,
  onSettings,
  onSelect,
  reviewOnly = false,
}: {
  project: string;
  onSettings: () => void;
  onSelect: (node: string) => void;
  reviewOnly?: boolean;
}) {
  const [data, setData] = useState<any>(null),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true,
      busy = false;
    setData(null);
    setError("");
    async function load() {
      if (busy) return;
      busy = true;
      try {
        const next = await api(projectUrl(project, "execution-monitor"));
        if (live && next?.estimate && Array.isArray(next.requests)) {
          setData(next);
          setError("");
        }
      } catch (e: any) {
        if (live) setError(e.message);
      } finally {
        busy = false;
      }
    }
    void load();
    const timer = setInterval(load, 3000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [project]);
  const eta = data?.estimate,
    policy = data?.policy,
    requests = data?.requests || [],
    switches = data?.switch_events || [];
  const autoSwitch = Boolean(
    policy?.enabled && policy.candidates?.length && policy.max_switches > 0,
  );
  function download() {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      }),
      url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download = "execution-monitor-report.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <section
      className={`workspace-monitor ${open ? "expanded" : ""}`}
      aria-label="项目实时执行监视"
    >
      <div className="workspace-monitor-bar">
        <button
          className="monitor-expand"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <Activity size={15} />
          <strong>实时监视</strong>
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
        <span className="monitor-current-rate">
          {data?.running
            ? rate(data.measurable_tokens_per_second_estimate)
            : data
              ? "当前没有执行中的模型请求"
              : "正在读取监测…"}
        </span>
        <span className="monitor-eta">
          <Clock3 size={13} />
          剩余：{remaining(eta)}
        </span>
        <span className={`monitor-policy ${autoSwitch ? "enabled" : ""}`}>
          {autoSwitch
            ? `自动切换已启用 · 阈值 ${policy.min_tokens_per_second} tok/s`
            : "仅监视 · 自动切换未启用"}
        </span>
        {!reviewOnly && (
          <button className="monitor-settings" onClick={onSettings}>
            <Settings2 size={13} />
            切换策略
          </button>
        )}
      </div>
      {error && (
        <p className="monitor-message">
          监测暂不可用：{error}（不影响执行和已保存结果）
        </p>
      )}
      {open && (
        <div className="workspace-monitor-details">
          <div className="monitor-summary">
            <article>
              <small>当前请求</small>
              <b>{requests.length} 路</b>
              <span>活跃节点请求（含排队）；网关全局最多3并发</span>
            </article>
            <article>
              <small>预计完成时间</small>
              <b>
                {eta?.finish_at
                  ? new Date(eta.finish_at * 1000).toLocaleTimeString()
                  : "暂不能确定"}
              </b>
              <span>
                {eta?.reason || "等待当前DAG及历史样本"}
                {eta?.confidence === "low"
                  ? "；样本少或运行偏慢，可靠性较低"
                  : ""}
              </span>
            </article>
            <article>
              <small>已发现任务</small>
              <b>
                {eta?.completed_nodes ?? "—"} / {eta?.known_nodes ?? "—"}
              </b>
              <span>
                剩余{eta?.remaining_nodes ?? "—"}项；人工等待不计入净耗时
              </span>
            </article>
          </div>
          <p className="monitor-message">
            {data?.measurement || "速率为可测内容估算，不是计费Token。"}
          </p>
          {!!requests.length && (
            <div className="monitor-request-list">
              {requests.map((r: any) => (
                <article
                  key={r.model_call_id || r.node}
                  className={r.status === "low" ? "low" : ""}
                >
                  <button onClick={() => onSelect(r.node)}>
                    <strong>{r.label || r.node}</strong>
                    <span>{r.requested_model || "模型待识别"}</span>
                  </button>
                  <b>{rate(r.tokens_per_second_estimate)}</b>
                  <small>
                    {r.status === "stale"
                      ? "采样已过期，不能当作0速率"
                      : r.status === "no_measurable_output"
                        ? "等待可测正文／工具参数／公开推理内容"
                        : r.status === "low"
                          ? "低于阈值，按连续窗口判定"
                          : "输出中"}{" "}
                    · 已等待{duration(r.elapsed_seconds)}
                  </small>
                </article>
              ))}
            </div>
          )}
          <div className="monitor-policy-description">
            <strong>{autoSwitch ? "低吞吐切换策略" : "监视模式"}</strong>
            <p>
              {autoSwitch
                ? `宽限${policy.grace_seconds}秒后，每${policy.window_seconds}秒观察；连续${policy.low_windows}个窗口低于${policy.min_tokens_per_second}估算tok/s，或${policy.no_output_seconds}秒无可测输出，取消当前未完成请求并尝试已配置候选。每次最多切换${policy.max_switches}次，降级模型冷却${policy.cooldown_seconds ?? 300}秒。`
                : "配置候选、允许切换次数并启用自动切换后才会更换模型；无候选时只监视，不中断请求。不会擅自使用其他账号或未配置模型。"}
            </p>
            <span>
              候选：
              {policy?.candidates?.length
                ? policy.candidates
                    .map(
                      (c: any) =>
                        `${c.account_id ? c.account_id + " / " : ""}${c.model}`,
                    )
                    .join(" → ")
                : "尚未配置"}
              。成功节点继续复用；关闭连接不保证供应商停止计费，未知用量保留。
            </span>
          </div>
          {!!switches.length && (
            <div className="monitor-recent-switch">
              <strong>最近切换与限流</strong>
              {switches.slice(0, 4).map((e: any) => (
                <p key={e.id}>
                  <time>{new Date(e.at * 1000).toLocaleTimeString()}</time>{" "}
                  {eventNames[e.kind] || e.kind} ·{" "}
                  {e.previous_model ? `${e.previous_model} → ` : ""}
                  {e.requested_model || "候选模型"}{" "}
                  <small>{e.failure_category || e.reason || ""}</small>
                </p>
              ))}
            </div>
          )}
          <details className="monitor-estimate-method">
            <summary>预计时间依据与限制</summary>
            {(eta?.notes || []).map((n: string) => (
              <p key={n}>{n}</p>
            ))}
            {!!eta?.unknown_nodes?.length && (
              <p>
                尚无样本：
                {eta.unknown_nodes
                  .slice(0, 6)
                  .map((n: any) => n.label)
                  .join("、")}
                {eta.unknown_nodes.length > 6 ? "…" : ""}
              </p>
            )}
            {!!eta?.blockers?.length && (
              <p>
                有{eta.blockers.length}
                个节点等待审核、配置或技术修复，不预测人工处理时间。
              </p>
            )}
          </details>
          <div className="monitor-report-actions">
            <strong>吞吐变化报表</strong>
            <button disabled={!data} onClick={download}>
              <Download size={13} />
              下载执行监测JSON
            </button>
          </div>
          <ThroughputView
            project={project}
            since={data?.session_started_at}
            threshold={policy?.min_tokens_per_second}
          />
        </div>
      )}
    </section>
  );
}
