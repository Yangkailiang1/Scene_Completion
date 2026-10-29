import { useEffect, useRef, useState } from "react";
import { api, projectUrl } from "./api";
const palette = ["#3468e8", "#0f9c89", "#bb67dc", "#e49b2b", "#e26776"];
export function ThroughputView({
  project,
  since,
  threshold,
}: {
  project: string;
  since?: number;
  threshold?: number;
}) {
  const [points, setPoints] = useState<any[]>([]),
    [model, setModel] = useState(""),
    [node, setNode] = useState(""),
    [account, setAccount] = useState(""),
    [error, setError] = useState(""),
    [metric, setMetric] = useState("all");
  const cursor = useRef(0),
    svg = useRef<SVGSVGElement>(null);
  useEffect(() => {
    let live = true;
    cursor.current = 0;
    setPoints([]);
    let busy = false;
    async function load() {
      if (busy) return;
      busy = true;
      try {
        let more = true,
          rounds = 0;
        while (more && rounds++ < 10) {
          const v = await api(
            projectUrl(
              project,
              "throughput?after=" +
                cursor.current +
                "&limit=2000" +
                (since != null ? "&since=" + since : ""),
            ),
          );
          if (!live) return;
          if (!Array.isArray(v.points)) return;
          cursor.current = v.cursor;
          setPoints((p) =>
            [
              ...new Map(
                [...p, ...v.points].map((point) => [point.id, point]),
              ).values(),
            ].slice(-30000),
          );
          setError("");
          more = v.has_more;
        }
      } catch (e: any) {
        if (live) setError(e.message);
      } finally {
        busy = false;
      }
    }
    load();
    const id = setInterval(load, 3000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [project, since]);
  const requests = new Map<string, any>();
  const nodeRequests = new Map<string, string>();
  const all = points.map((point) => {
    if (point.kind === "request_started") {
      const key = point.model_call_id || `legacy:${point.node}:${point.id}`;
      nodeRequests.set(point.node, key);
      requests.set(key, point);
    }
    const key =
      point.model_call_id ||
      nodeRequests.get(point.node) ||
      `unknown:${point.node}`;
    return { ...requests.get(key), ...point, model_call_id: key };
  });
  const models = [
      ...new Set(all.map((p) => p.requested_model).filter(Boolean)),
    ],
    nodes = [...new Set(all.map((p) => p.node).filter(Boolean))],
    accounts = [...new Set(all.map((p) => p.account_id).filter(Boolean))];
  const selected = all.filter(
    (p) =>
      (!model || p.requested_model === model) &&
      (!node || p.node === node) &&
      (!account || p.account_id === account),
  );
  const previous = new Map<string, any>();
  const samples = selected
    .filter((p) => p.kind === "throughput_sample")
    .map((p) => {
      const before = previous.get(p.model_call_id);
      previous.set(p.model_call_id, p);
      return metric === "all"
        ? p
        : {
            ...p,
            tokens_per_second_estimate:
              typeof p[metric] === "number" &&
              typeof before?.[metric] === "number" &&
              p.at > before.at &&
              p.at - before.at <= 15
                ? Math.max(0, p[metric] - before[metric]) /
                  4 /
                  (p.at - before.at)
                : null,
          };
    })
    .filter((p) => typeof p.tokens_per_second_estimate === "number");
  const lo = selected[0]?.at || 0,
    hi = selected.at(-1)?.at || lo + 1,
    max = Math.max(
      5,
      (threshold || 0) * 1.2,
      ...samples.map((p) => p.tokens_per_second_estimate),
    );
  const curves = new Map<string, any[]>();
  samples.forEach((p) => {
    const key = p.model_call_id || p.requested_model || p.node;
    curves.set(key, [...(curves.get(key) || []), p]);
  });
  function download(type: "svg" | "png" | "json" | "csv") {
    const exported = {
      filters: { account, model, node, content_type: metric, since },
      measurement: "UTF-8 bytes/4 estimate; not billing",
      points: selected,
      samples,
    };
    if (type === "csv") {
      const fields = [
        "id",
        "at",
        "kind",
        "node",
        "account_id",
        "requested_model",
        "content_type",
        "tokens_per_second_estimate",
        "output_bytes",
        "content_bytes",
        "tool_argument_bytes",
        "reasoning_bytes",
      ];
      const rates = new Map(
        samples.map((p) => [p.id, p.tokens_per_second_estimate]),
      );
      const cell = (v: any) =>
        '"' + String(v ?? "").replaceAll('"', '""') + '"';
      save(
        new Blob(
          [
            "\uFEFF" +
              [
                fields,
                ...selected.map((p) =>
                  fields.map((f) =>
                    f === "content_type"
                      ? metric
                      : f === "tokens_per_second_estimate"
                        ? rates.get(p.id)
                        : p[f],
                  ),
                ),
              ]
                .map((r) => r.map(cell).join(","))
                .join("\r\n"),
          ],
          { type: "text/csv;charset=utf-8" },
        ),
        "throughput.csv",
      );
      return;
    }
    if (type === "json") {
      save(
        new Blob([JSON.stringify(exported, null, 2)], {
          type: "application/json",
        }),
        "throughput.json",
      );
      return;
    }
    if (!svg.current) return;
    const raw = new XMLSerializer().serializeToString(svg.current),
      blob = new Blob([raw], { type: "image/svg+xml" });
    if (type === "svg") {
      save(blob, "throughput.svg");
      return;
    }
    const url = URL.createObjectURL(blob),
      img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = 1000;
      canvas.height = 350;
      const ctx = canvas.getContext("2d");
      ctx?.drawImage(img, 0, 0, 1000, 350);
      canvas.toBlob((b) => b && save(b, "throughput.png"));
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }
  return (
    <section className="throughput-view">
      <div className="throughput-heading">
        <div>
          <h3>模型吞吐监视</h3>
          <p>
            实时速率为接收内容的估算值；不等于账单Token。未公开的推理内容无法测量。
          </p>
        </div>
        <div className="throughput-downloads">
          <button onClick={() => download("png")}>PNG</button>
          <button onClick={() => download("svg")}>SVG</button>
          <button onClick={() => download("json")}>JSON</button>
          <button onClick={() => download("csv")}>CSV</button>
        </div>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="throughput-filters">
        <select
          aria-label="吞吐账号"
          value={account}
          onChange={(e) => setAccount(e.target.value)}
        >
          <option value="">全部账号</option>
          {accounts.map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
        <select
          aria-label="吞吐模型"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        >
          <option value="">全部模型</option>
          {models.map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
        <select
          aria-label="吞吐节点"
          value={node}
          onChange={(e) => setNode(e.target.value)}
        >
          <option value="">全部节点</option>
          {nodes.map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
        <select
          aria-label="吞吐内容类型"
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
        >
          <option value="all">全部可测内容</option>
          <option value="content_bytes">正文</option>
          <option value="tool_argument_bytes">工具参数</option>
          <option value="reasoning_bytes">公开推理内容</option>
        </select>
        <span>
          {samples.length} 个速率采样 · {requests.size} 次已记录请求
        </span>
      </div>
      <div className="throughput-chart">
        <svg
          ref={svg}
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 1000 350"
          role="img"
          aria-label="模型实时吞吐曲线"
        >
          <rect width="1000" height="350" fill="white" />
          <text x="55" y="24" fill="#536b88" fontSize="13">
            Estimated generated tokens / second (not billing)
          </text>
          {[0, 0.25, 0.5, 0.75, 1].map((v) => (
            <g key={v}>
              <line
                x1="55"
                x2="970"
                y1={290 - v * 235}
                y2={290 - v * 235}
                stroke="#e6edf5"
              />
              <text x="8" y={294 - v * 235} fill="#69809c" fontSize="12">
                {(v * max).toFixed(1)}
              </text>
            </g>
          ))}
          {threshold != null && (
            <g>
              <line
                x1="55"
                x2="970"
                y1={290 - (threshold / max) * 235}
                y2={290 - (threshold / max) * 235}
                stroke="#db9453"
                strokeDasharray="5 5"
              />
              <text
                x="970"
                y={280 - (threshold / max) * 235}
                textAnchor="end"
                fill="#a36231"
                fontSize="11"
              >
                阈值 {threshold} tok/s（连续窗口判断）
              </text>
            </g>
          )}
          {selected
            .filter((p) => p.kind === "model_switched")
            .map((p) => (
              <g key={"switch-" + p.id}>
                <line
                  x1={55 + ((p.at - lo) / Math.max(1, hi - lo)) * 915}
                  x2={55 + ((p.at - lo) / Math.max(1, hi - lo)) * 915}
                  y1="50"
                  y2="290"
                  stroke="#9c6bcc"
                  strokeDasharray="3 5"
                />
                <title>切换到 {p.requested_model}</title>
              </g>
            ))}
          {[...curves.entries()].map(([id, ps], i) => (
            <g key={id}>
              {segments(ps).map((part, index) => (
                <polyline
                  key={index}
                  fill="none"
                  stroke={palette[i % palette.length]}
                  strokeWidth="2"
                  points={part
                    .map(
                      (p) =>
                        `${55 + ((p.at - lo) / Math.max(1, hi - lo)) * 915},${290 - (p.tokens_per_second_estimate / max) * 235}`,
                    )
                    .join(" ")}
                />
              ))}
              {ps.map((p) => (
                <circle
                  key={p.id}
                  cx={55 + ((p.at - lo) / Math.max(1, hi - lo)) * 915}
                  cy={290 - (p.tokens_per_second_estimate / max) * 235}
                  r="2.5"
                  fill={palette[i % palette.length]}
                >
                  <title>
                    {p.requested_model} · {p.node} ·{" "}
                    {p.tokens_per_second_estimate} est tok/s · {p.output_bytes}{" "}
                    bytes
                  </title>
                </circle>
              ))}
            </g>
          ))}
          <text x="55" y="325" fill="#69809c" fontSize="12">
            {lo
              ? new Date(lo * 1000).toLocaleString()
              : "No measured samples yet"}
          </text>
          <text x="970" y="325" textAnchor="end" fill="#69809c" fontSize="12">
            {hi ? new Date(hi * 1000).toLocaleTimeString() : ""}
          </text>
        </svg>
      </div>
      {!samples.length && (
        <p className="empty-hint">
          尚无可绘制速率采样；旧记录或未返回可测内容的请求显示为未知。
        </p>
      )}
      <div className="throughput-events">
        <h4>请求与切换时间线</h4>
        {selected
          .filter(
            (p) =>
              p.kind !== "throughput_sample" && p.kind !== "stream_progress",
          )
          .slice(-40)
          .reverse()
          .map((p) => (
            <div key={p.id}>
              <time>{new Date(p.at * 1000).toLocaleTimeString()}</time>
              <strong>{p.requested_model || "模型事件"}</strong>
              <span>
                {(
                  {
                    model_switched: "已切换模型",
                    model_degraded: "降级冷却",
                    model_switch_skipped: "跳过候选",
                    request_started: "请求开始",
                    request_finished: "请求完成",
                    request_failed: "请求失败",
                    rate_limit_wait: "限流冷却",
                  } as Record<string, string>
                )[p.kind] || p.kind}
              </span>
              <small>
                {p.node} {p.failure_category || p.reason || ""}
              </small>
            </div>
          ))}
      </div>
    </section>
  );
}
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function segments(points: any[]) {
  const groups: any[][] = [];
  for (const point of points) {
    const previous = groups.at(-1)?.at(-1);
    if (!previous || point.at - previous.at > 15) groups.push([]);
    groups[groups.length - 1].push(point);
  }
  return groups;
}
