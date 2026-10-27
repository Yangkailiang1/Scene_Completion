import { useEffect, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { api, projectUrl } from "./api";
import { RecommendationComparison } from "./ResultComparison";
import { SourceEvidence } from "./SourceEvidence";
const labels: Record<string, string> = {
  adopt: "采纳并加入业务GT",
  not_applicable: "不适用",
  not_needed: "无需纳入",
  already_covered: "已有覆盖",
  defer: "暂缓",
  withdraw: "撤回采纳／反馈",
};
export function BusinessRecommendations({
  project,
  onEvidenceOpen,
}: {
  project: string;
  onEvidenceOpen?: () => void;
}) {
  const [cases, setCases] = useState<any[]>([]),
    [cid, setCase] = useState(""),
    [basis, setBasis] = useState("business"),
    [data, setData] = useState<any>(null),
    [notice, setNotice] = useState(""),
    [reload, setReload] = useState(0),
    [busy, setBusy] = useState("");
  const [reviewer, setReviewer] = useState(
      () => localStorage.getItem("scene-reviewer") || "",
    ),
    [edits, setEdits] = useState<Record<string, any>>({}),
    [evidence, setEvidence] = useState<any>(null),
    [defs, setDefs] = useState<any>({});
  useEffect(() => {
    api(projectUrl(project, "results"))
      .then((v) => {
        setCases(v.cases);
        setCase(v.cases[0]?.id || "");
      })
      .catch((e) => setNotice(e.message));
    api(projectUrl(project, "registry"))
      .then((v) => setDefs(v.registry.definitions))
      .catch(() => {});
  }, [project]);
  useEffect(() => {
    if (!cid) return;
    let live = true;
    setData(null);
    api(
      projectUrl(
        project,
        `recommendations?case=${encodeURIComponent(cid)}&test_set=${basis}`,
      ),
    )
      .then((v) => live && setData(v))
      .catch((e) => live && setNotice(e.message));
    return () => {
      live = false;
    };
  }, [project, cid, basis, reload]);
  const result = data?.result,
    latest: Record<string, any> = {};
  for (const r of data?.feedback || [])
    if (r.case_id === cid && r.run_id === result?.run_id)
      latest[r.scenario_id] = r;
  async function save(id: string) {
    const old = latest[id],
      edit = edits[id] || {};
    setBusy(id);
    try {
      await api(projectUrl(project, "recommendations/feedback"), {
        method: "POST",
        body: JSON.stringify({
          case_id: cid,
          scenario_id: id,
          settings_hash: result.settings_hash,
          revision: data.feedback_revision,
          choice: edit.choice || old?.decision || "adopt",
          note: edit.note ?? old?.note ?? "",
          reviewer,
          truth_resolution: edit.resolution
            ? edit.resolution === "new"
              ? { choice: "new" }
              : { choice: "link", truth_id: edit.resolution }
            : undefined,
        }),
      });
      localStorage.setItem("scene-reviewer", reviewer);
      setEdits((v) => {
        const n = { ...v };
        delete n[id];
        return n;
      });
      setNotice(
        "推荐审核已保存；业务GT及指标已更新，未调用模型，也未改变本轮M/Q和排序。",
      );
      setReload((v) => v + 1);
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy("");
    }
  }
  const patch = (id: string, value: any) =>
    setEdits((v) => ({ ...v, [id]: { ...v[id], ...value } }));
  const format = (x: any) =>
    x?.value == null
      ? x?.status || "未评测"
      : `${x.value.toFixed(2)}%（${x.numerator}/${x.denominator}）`;
  return (
    <div className="business-recommendation-view management-view">
      <div className="management-filters">
        <strong>推荐审核</strong>
        <select
          aria-label="推荐审核用例"
          value={cid}
          onChange={(e) => {
            setCase(e.target.value);
            setEdits({});
          }}
        >
          {cases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.id} · {c.name}
            </option>
          ))}
        </select>
        <select
          aria-label="推荐指标依据"
          value={basis}
          onChange={(e) => setBasis(e.target.value)}
        >
          <option value="business">业务审核后GT</option>
          <option value="expanded">冻结扩展测试GT</option>
          <option value="original">原始测试GT</option>
        </select>
        <label>
          审核人{" "}
          <input
            aria-label="推荐审核人"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="姓名或业务标识"
          />
        </label>
        <button onClick={() => setReload((v) => v + 1)}>刷新</button>
      </div>
      {notice && (
        <p role="status" className="management-notice">
          {notice}
        </p>
      )}
      <PanelGroup direction="horizontal" className="review-answer-panels">
        <Panel defaultSize={50} minSize={30}>
          <div className="recommendation-review-scroll">
            <p className="management-notice">
              本页只审核本轮算法选出的Q。采纳只增补业务GT，不改动原始／扩展测试GT，不重排本轮推荐。GT扩充引起的指标变化不代表模型质量提升。
            </p>
            {!data ? (
              <p>正在读取推荐与业务GT…</p>
            ) : (
              <>
                <div className="review-metric-strip">
                  <article>
                    <small>关注点漏报率 ↓</small>
                    <b>
                      {format(
                        data.evaluation_metrics?.missing_exception_miss_rate,
                      )}
                    </b>
                  </article>
                  <article>
                    <small>关注点生成有效率 ↑</small>
                    <b>
                      {format(data.evaluation_metrics?.generation_validity)}
                    </b>
                  </article>
                  <article>
                    <small>人工采纳率</small>
                    <b>{format(data.human_adoption)}</b>
                  </article>
                  <article>
                    <small>人工新增场景</small>
                    <b>{data.business_truth?.added?.length ?? "—"}</b>
                  </article>
                </div>
                {data.business_truth?.pending_duplicates?.length > 0 && (
                  <p className="management-notice">
                    有{data.business_truth.pending_duplicates.length}
                    项疑似GT重复，确认关联或新增独立失败后才进入业务GT。
                  </p>
                )}
                <RecommendationComparison data={data.comparison} />
                {!result?.enabled ? (
                  <p>尚未形成推荐，未完成不按0处理。</p>
                ) : result.Q.length === 0 ? (
                  <p>本轮没有选出的推荐场景。</p>
                ) : (
                  result.Q.map((s: any) => {
                    const rank = result.ranked.find(
                        (r: any) => r.scenario_id === s.id,
                      ),
                      old = latest[s.id],
                      edit = edits[s.id] || {};
                    const choice = edit.choice || old?.decision || "adopt";
                    return (
                      <article
                        className="business-recommendation-card"
                        key={s.id}
                      >
                        <header>
                          <span>
                            #{rank?.rank} · {s.interaction_id} ·{" "}
                            {s.field ||
                              s.subject ||
                              s.scenario_context?.provider}
                          </span>
                          <b>{old ? labels[old.decision] : "未审核"}</b>
                        </header>
                        <h3>{s.conditions?.join("；") || s.title || s.id}</h3>
                        <p>
                          {(s.concern_origins || [s.concern_key])
                            .map((k: string) => defs[k]?.label || k)
                            .join(" · ")}
                        </p>
                        <p>
                          风险：{rank?.risk?.level} · {rank?.risk?.reason} ·{" "}
                          {rank?.reason}
                        </p>
                        {s.source_refs?.map((r: any, i: number) => (
                          <button
                            key={i}
                            className="evidence-link-card"
                            onClick={() => {
                              setEvidence(r);
                              onEvidenceOpen?.();
                            }}
                          >
                            <small>
                              第{r.line_start}–{r.line_end}行 · 点击以查看文档
                            </small>
                            <p>{r.quote}</p>
                          </button>
                        ))}
                        <div className="recommendation-decision">
                          <select
                            aria-label={`审核决定 ${s.id}`}
                            value={choice}
                            onChange={(e) =>
                              patch(s.id, { choice: e.target.value })
                            }
                          >
                            {Object.entries(labels).map(([k, v]) => (
                              <option value={k} key={k}>
                                {v}
                              </option>
                            ))}
                          </select>
                          <input
                            aria-label={`审核说明 ${s.id}`}
                            placeholder="填写采纳依据或不采纳理由"
                            value={edit.note ?? old?.note ?? ""}
                            onChange={(e) =>
                              patch(s.id, { note: e.target.value })
                            }
                          />
                          {data.duplicate_candidates?.[s.id]?.length > 0 &&
                            choice === "adopt" && (
                              <select
                                aria-label={`GT去重 ${s.id}`}
                                value={edit.resolution || ""}
                                onChange={(e) =>
                                  patch(s.id, { resolution: e.target.value })
                                }
                              >
                                <option value="">
                                  按已保存完整匹配去重；未决则待确认
                                </option>
                                <option value="new">确认为新增独立失败</option>
                                {data.duplicate_candidates[s.id].map(
                                  (t: any) => (
                                    <option key={t.id} value={t.id}>
                                      关联：{t.conditions.join("；")}
                                    </option>
                                  ),
                                )}
                              </select>
                            )}
                          <button
                            className="primary-action"
                            disabled={!!busy || !reviewer.trim()}
                            onClick={() => save(s.id)}
                          >
                            {busy === s.id ? "保存中…" : "保存审核"}
                          </button>
                        </div>
                        <details className="review-history">
                          <summary>查看该场景审核历史</summary>
                          {data.feedback
                            .filter(
                              (r: any) =>
                                r.case_id === cid && r.scenario_id === s.id,
                            )
                            .map((r: any) => (
                              <article key={r.id}>
                                <b>
                                  {labels[r.decision]} ·{" "}
                                  {r.reviewer || "历史用户"}
                                </b>
                                <p>{r.note || "无补充说明"}</p>
                                <small>
                                  {new Date(
                                    r.reviewed_at * 1000,
                                  ).toLocaleString()}{" "}
                                  · {r.via || "历史记录"}
                                </small>
                              </article>
                            ))}
                        </details>
                        {old && (
                          <small>
                            上次审核：{old.reviewer || "历史用户"} ·{" "}
                            {new Date(old.reviewed_at * 1000).toLocaleString()}
                          </small>
                        )}
                      </article>
                    );
                  })
                )}
              </>
            )}
          </div>
        </Panel>
        {evidence && (
          <>
            <PanelResizeHandle className="review-resize-handle" />
            <Panel minSize={30} defaultSize={50}>
              <SourceEvidence
                project={project}
                evidence={evidence}
                onClose={() => setEvidence(null)}
              />
            </Panel>
          </>
        )}
      </PanelGroup>
    </div>
  );
}
