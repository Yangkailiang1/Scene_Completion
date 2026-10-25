import { useEffect, useState } from "react";
import { api, projectUrl, fileUrl } from "./api";
import { AlignmentTable, MetricsPanel } from "./ResultComparison";
import { ArtifactView } from "./ArtifactView";

const labels: Record<string, string> = {
  E: "需求文档已有 E",
  G: "本方法生成 G",
  GT: "独立测试真值 GT",
};
const sourceLabels: Record<string, string> = {
  explicit: "原文明示",
  framework_inferred: "框架推导",
};
function show(value: any): string {
  return value == null
    ? "待确认"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
}
function Evidence({ rows }: { rows: any[] }) {
  return rows?.length ? (
    <details className="result-evidence">
      <summary>原文依据（{rows.length}处）</summary>
      {rows.map((r, i) => (
        <blockquote key={i}>
          <small>
            {r.source_id} · 第{r.line_start}–{r.line_end}行
          </small>
          <p>{r.quote}</p>
        </blockquote>
      ))}
    </details>
  ) : null;
}
function Scenario({
  s,
  defs,
  missing,
  detailUrl,
}: {
  detailUrl: string;
  s: any;
  defs: any;
  missing: boolean;
}) {
  const [full, setFull] = useState<any>(null),
    [loading, setLoading] = useState(false),
    [failure, setFailure] = useState("");
  const detail = full || s;
  async function open(e: React.SyntheticEvent<HTMLDetailsElement>) {
    if (!e.currentTarget.open || !s.lazy_detail || full || loading) return;
    setLoading(true);
    try {
      setFull(await api(detailUrl));
    } catch (e: any) {
      setFailure(e.message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <article className="result-scenario">
      <header>
        <strong>{defs[s.concern_key]?.label || s.concern_key}</strong>
        {missing && <span className="result-missing">文档未覆盖</span>}
      </header>
      <p>
        {s.coverage_description ||
          s.steps?.trigger ||
          s.conditions?.join("；") ||
          s.cause}
      </p>
      <small>
        {s.field || s.object} ·{" "}
        {sourceLabels[s.source_status] || s.source_status}
        {s.executable === false ? " · 条件级，尚不可直接执行" : ""}
      </small>
      <details onToggle={open}>
        <summary>异常步骤与归类依据</summary>
        {loading && <p>正在读取证据…</p>}
        {failure && <p role="alert">{failure}</p>}
        <p>失败原因：{detail.cause}</p>
        <p>
          正常上下文：{detail.steps?.normal_context?.join("；") || "未提供"}
        </p>
        <p>触发条件：{detail.conditions?.join("；") || "未提供"}</p>
        <p>
          原文明示后续：
          {detail.steps?.documented_follow_up
            ?.map((r: any) => (typeof r === "string" ? r : r.action))
            .join("；") || "未明示，不补造"}
        </p>
        <p>{detail.derivation}</p>
        {detail.quality_notes?.map((n: string, index: number) => (
          <p className="quality-note" key={index}>
            {n}
          </p>
        ))}
        <small>
          异常ID：{detail.id}
          {detail.original_branch_id
            ? " · 原分支：" + detail.original_branch_id
            : ""}
        </small>
        <Evidence rows={detail.source_refs} />
      </details>
    </article>
  );
}

export function ResultsView({ project }: { project: string }) {
  const [onlyUnmatched, setOnlyUnmatched] = useState(false);
  const [index, setIndex] = useState<any>(null),
    [cid, setCase] = useState(""),
    [detail, setDetail] = useState<any>(null),
    [step, setStep] = useState(""),
    [mode, setMode] = useState("steps"),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0);
  const [artifactKey, setArtifact] = useState(""),
    [artifactValue, setArtifactValue] = useState<any>(null),
    [zoom, setZoom] = useState(1);
  useEffect(() => {
    let live = true;
    api(projectUrl(project, "results"))
      .then((r) => {
        if (live) {
          setIndex(r);
          setCase((c) =>
            r.cases.some((x: any) => x.id === c) ? c : r.cases[0]?.id || "",
          );
        }
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [project, reload]);
  useEffect(() => {
    if (!cid) return;
    let live = true;
    setDetail(null);
    api(projectUrl(project, "results/" + encodeURIComponent(cid)))
      .then((r) => {
        if (live) {
          setDetail(r);
          const target = onlyUnmatched
            ? r.interactions.find((x: any) =>
                x.alignment_rows?.some((a: any) => a.status !== "triple"),
              )
            : null;
          setStep((target || r.interactions[0])?.interaction.id || "");
        }
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [project, cid, reload]);
  const catalog =
    index?.artifacts.filter(
      (a: any) => a.case === "shared" || a.case === cid,
    ) || [];
  const artifact =
    catalog.find((a: any) => a.key === artifactKey) || catalog[0];
  useEffect(() => {
    if (mode !== "diagrams" || !artifact) return;
    let live = true;
    setArtifactValue(null);
    setZoom(1);
    const json = artifact.files.find((f: any) => f.name.endsWith(".json"));
    if (json)
      api(fileUrl(project, json.path))
        .then((v) => live && setArtifactValue(v.payload || v))
        .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [project, mode, artifact?.key, reload]);
  const row = detail?.interactions.find((r: any) => r.interaction.id === step),
    i = row?.interaction,
    defs = detail?.definitions || {};
  const diagram = artifact?.files.find((f: any) => f.name.endsWith(".svg"));
  const unresolved =
    detail && Object.values(detail.unbound).some((a: any) => a.length);
  return (
    <div className="management-view results-view">
      <div className="results-toolbar">
        <select
          aria-label="结果用例"
          value={cid}
          onChange={(e) => setCase(e.target.value)}
        >
          <option value="" disabled>
            选择用例
          </option>
          {index?.cases.map((c: any) => (
            <option key={c.id} value={c.id}>
              {c.id} · {c.name}
            </option>
          ))}
        </select>
        <div className="view-segments">
          <button
            className={mode === "steps" ? "active" : ""}
            onClick={() => setMode("steps")}
          >
            交互对照
          </button>
          <button
            className={mode === "metrics" ? "active" : ""}
            onClick={() => setMode("metrics")}
          >
            指标总览
          </button>
          <button
            className={mode === "diagrams" ? "active" : ""}
            onClick={() => setMode("diagrams")}
          >
            图表总览
          </button>
        </div>
        <span className="muted">
          {index?.complete
            ? "本轮执行已完成"
            : "展示已保存的结果，未完成项不视为空集合"}
        </span>
        <button onClick={() => setReload((x) => x + 1)}>刷新</button>
      </div>
      {error && (
        <div role="alert" className="management-notice">
          {error}
        </div>
      )}
      {!index ? (
        <p className="management-loading">正在读取结果目录…</p>
      ) : !index.cases.length ? (
        <p className="management-loading">用例对应完成后显示结果。</p>
      ) : mode === "metrics" ? (
        <MetricsPanel
          project={project}
          onCase={(id) => {
            setCase(id);
            setMode("steps");
            setOnlyUnmatched(true);
            if (id === cid && detail) {
              const target = detail.interactions.find((x: any) =>
                x.alignment_rows?.some((a: any) => a.status !== "triple"),
              );
              if (target) setStep(target.interaction.id);
            }
          }}
        />
      ) : mode === "diagrams" ? (
        <div className="results-diagrams">
          <div className="results-diagram-controls">
            <select
              aria-label="结果图表"
              value={artifact?.key || ""}
              onChange={(e) => setArtifact(e.target.value)}
            >
              {catalog.map((a: any) => (
                <option key={a.key} value={a.key}>
                  {a.case === "shared" ? "项目共享" : cid} · {a.label}
                </option>
              ))}
            </select>
            {artifact?.files.map((f: any) => (
              <a key={f.path} href={fileUrl(project, f.path)} download={f.name}>
                下载{f.name.split(".").pop()?.toUpperCase()}
              </a>
            ))}
            {diagram && (
              <select
                aria-label="图形缩放"
                value={zoom}
                onChange={(e) => setZoom(Number(e.target.value))}
              >
                <option value={1}>适应宽度</option>
                <option value={2}>放大2倍</option>
                <option value={4}>放大4倍</option>
              </select>
            )}
          </div>
          {diagram ? (
            <div className="results-diagram-canvas">
              <img
                alt={artifact.label}
                src={fileUrl(project, diagram.path)}
                style={{ width: `${zoom * 100}%`, maxWidth: "none" }}
              />
            </div>
          ) : artifactValue ? (
            <div className="results-table">
              <ArtifactView
                key={artifact.key}
                projectId={project}
                artifacts={artifact.files}
                value={artifactValue}
                definitions={defs}
                taskKey={artifact.key}
              />
            </div>
          ) : (
            <p className="management-loading">
              {catalog.length ? "正在读取图表…" : "暂无已保存图表"}
            </p>
          )}
        </div>
      ) : !detail ? (
        <p className="management-loading">正在读取本用例…</p>
      ) : (
        <div className="results-step-body">
          <aside className="results-step-list" aria-label="结果交互步骤">
            {detail.interactions.map((r: any) => {
              const x = r.interaction;
              return (
                <button
                  key={x.id}
                  className={step === x.id ? "active" : ""}
                  onClick={() => setStep(x.id)}
                >
                  <small>
                    步骤{x.sequence} · {x.id} ·{" "}
                    {x.direction === "return" ? "返回" : "请求"}
                  </small>
                  <strong>{x.operation.name}</strong>
                  <span>
                    {x.sender.name} → {x.receiver.name}
                  </span>
                  <small>
                    E {r.channels.E.length} · G {r.channels.G.length} · GT{" "}
                    {r.channels.GT.length}
                  </small>
                </button>
              );
            })}
            {unresolved && (
              <details>
                <summary>尚未绑定到展示交互的异常</summary>
                {Object.entries(detail.unbound).map(([k, v]) => (
                  <p key={k}>
                    {labels[k]}：{(v as any[]).length}条
                  </p>
                ))}
                <pre>{JSON.stringify(detail.unbound, null, 2)}</pre>
              </details>
            )}
          </aside>
          <section className="results-reading">
            {!i ? (
              <p>本用例的交互尚未保存。</p>
            ) : (
              <>
                <div className="results-step-meta">
                  <strong>
                    步骤{i.sequence} · {i.id}
                  </strong>
                  <span>
                    {i.layer} · {i.direction === "return" ? "返回" : "请求"}
                    {i.parent_id ? " · 展开自 " + i.parent_id : ""}
                  </span>
                </div>
                <div className="interaction-four">
                  <div>
                    <small>发送方</small>
                    <strong>{i.sender.name}</strong>
                    <p>{i.sender.position}</p>
                  </div>
                  <div>
                    <small>操作</small>
                    <strong>{i.operation.name}</strong>
                    {i.operation.sequence?.length > 0 && (
                      <p>操作序列：{i.operation.sequence.join(" → ")}</p>
                    )}
                    {i.operation.optional?.length > 0 && (
                      <p>可选操作：{i.operation.optional.join("、")}</p>
                    )}
                  </div>
                  <div>
                    <small>数据</small>
                    <strong>
                      {i.data.sequence.map((p: any) => p.name).join("、") ||
                        "未明示数据"}
                    </strong>
                    <p>{i.api_id ? "接口 " + i.api_id : "未关联具体接口"}</p>
                  </div>
                  <div>
                    <small>接收方</small>
                    <strong>{i.receiver.name}</strong>
                    <p>{i.receiver.position}</p>
                  </div>
                </div>
                <details className="result-data">
                  <summary>数据属性、交互双方关注点及原文依据</summary>
                  <div className="result-data-scroll">
                    <table>
                      <thead>
                        <tr>
                          {[
                            "数据",
                            "位置",
                            "类型",
                            "必填／可选",
                            "默认值",
                            "约束",
                          ].map((t) => (
                            <th key={t}>{t}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {i.data.sequence.map((p: any, n: number) => (
                          <tr key={n}>
                            <td>{p.name}</td>
                            <td>{p.location}</td>
                            <td>{show(p.data_type)}</td>
                            <td>
                              {p.required === true
                                ? "必填"
                                : p.required === false
                                  ? "可选"
                                  : "待确认"}
                            </td>
                            <td>{show(p.default)}</td>
                            <td>
                              {p.constraints
                                ?.map((c: any) => `${c.kind}：${show(c.value)}`)
                                .join("；") || "未明示"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {["sender", "receiver"].map((k) => (
                    <p key={k}>
                      {k === "sender" ? "发送方" : "接收方"}适用关注点：
                      {(i[k].concerns || [])
                        .filter((c: any) => c.status === "applicable")
                        .map(
                          (c: any) =>
                            defs[c.concern_key]?.label || c.concern_key,
                        )
                        .filter(
                          (v: string, n: number, a: string[]) =>
                            a.indexOf(v) === n,
                        )
                        .join("、") || "暂无已确认项"}
                    </p>
                  ))}
                  <Evidence rows={i.source_refs} />
                </details>
                <label className="alignment-filter">
                  <input
                    type="checkbox"
                    checked={onlyUnmatched}
                    onChange={(e) => setOnlyUnmatched(e.target.checked)}
                  />
                  只看未完整对应／冲突项
                </label>
                <AlignmentTable
                  rows={row.alignment_rows || []}
                  missing={row.missing_ids}
                  onlyUnmatched={onlyUnmatched}
                  renderCell={(s: any, missing: boolean, channel: string) => (
                    <Scenario
                      s={s}
                      defs={defs}
                      missing={missing}
                      detailUrl={projectUrl(
                        project,
                        "results/" +
                          encodeURIComponent(cid) +
                          "/scenarios/" +
                          channel +
                          "/" +
                          encodeURIComponent(s.id),
                      )}
                    />
                  )}
                />
                <p className="muted">
                  E为原文已有异常的逆向归类；GT含独立测试的明示项及框架推导项，仍需审核。显示执行时的关注点版本，未重新匹配或计分。
                </p>
                <details className="result-data">
                  <summary>本用例已保存的覆盖匹配与指标</summary>
                  <pre>
                    {JSON.stringify(
                      {
                        metrics: detail.metrics,
                        full_matches: detail.full_matches,
                        partial_diagnostics: detail.partial_diagnostics,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
