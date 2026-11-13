import { useEffect, useRef, useState } from "react";
import { api, projectUrl } from "../../shared/api";
import { RecommendationComparison } from "../results/shared/RecommendationComparison";
const risks: Record<string, string> = {
  low: "低",
  normal: "普通",
  high: "高",
  critical: "关键",
};
const feedbacks: Record<string, string> = {
  adopt: "采纳",
  not_needed: "明确无需纳入",
  already_covered: "已经覆盖",
  defer: "暂缓",
  not_applicable: "不适用",
};
export function RecommendationsView({
  project,
  caseId,
  testSet = "expanded",
}: {
  project: string;
  caseId?: string;
  testSet?: string;
}) {
  const [data, setData] = useState<any>(null),
    [localCase, setLocalCase] = useState(""),
    [hist, setHist] = useState<any>(null),
    [msg, setMsg] = useState(""),
    [notes, setNotes] = useState<Record<string, string>>({}),
    [premises, setPremises] = useState<Record<string, string>>({});
  const cid = caseId ?? localCase;
  const contextKey = project + "\0" + cid + "\0" + testSet;
  const activeContext = useRef(contextKey);
  activeContext.current = contextKey;
  const requestVersion = useRef(0);
  const load = async () => {
    if (activeContext.current !== contextKey) return;
    const version = ++requestVersion.current;
    setData(null);
    setMsg("");
    try {
      const [d, h] = await Promise.all([
        api(
          projectUrl(
            project,
            "recommendations" +
              (cid ? "?case=" + encodeURIComponent(cid) : "") +
              (testSet === "original"
                ? (cid ? "&" : "?") + "test_set=original"
                : ""),
          ),
        ),
        api(projectUrl(project, "recommendation-history")),
      ]);
      if (
        activeContext.current !== contextKey ||
        version !== requestVersion.current
      )
        return;
      setData(d);
      setHist(h);
      if (caseId === undefined && !cid && d.cases.length)
        setLocalCase(d.cases[0].id);
    } catch (e: any) {
      if (
        activeContext.current === contextKey &&
        version === requestVersion.current
      )
        setMsg(e.message);
    }
  };
  useEffect(() => {
    load();
    return () => {
      ++requestVersion.current;
    };
  }, [project, cid, testSet]);
  const act = async (path: string, body: any) => {
    try {
      await api(projectUrl(project, path), {
        method: "POST",
        body: JSON.stringify(body),
      });
      await load();
      setMsg("已保存业务审核。当前冻结排序/GT不变；继续运行后生效。");
    } catch (e: any) {
      setMsg(e.message);
    }
  };
  const result = data?.result;
  return (
    <section className="recommendations-view">
      <div className="pattern-toolbar">
        <b>风险保底推荐</b>
        {caseId === undefined && (
          <select
            aria-label="推荐用例"
            value={cid}
            onChange={(e) => setLocalCase(e.target.value)}
          >
            {data?.cases.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
        <button onClick={load}>刷新</button>
      </div>
      {msg && <p role="status">{msg}</p>}
      {data && <RecommendationComparison data={data.comparison} />}
      {!data ? (
        <p>正在读取当前用例的推荐…</p>
      ) : !result?.enabled ? (
        <p>
          本运行尚未形成推荐。旧版本报告仍为“未启用”；新版本在缺失比较后执行推荐。
        </p>
      ) : (
        <>
          {data.current_settings_hash !== result.settings_hash && (
            <p className="management-notice">
              设置已变化，当前显示执行时冻结结果，请继续运行更新。
            </p>
          )}
          <p>
            候选来自M · {result.formula} · K={result.top_k} · Q=
            {result.Q.length}
            {result.critical_overflow > 0 &&
              ` · 关键项超过K ${result.critical_overflow}条`}{" "}
            · 人工采纳率{" "}
            {data.human_adoption.value == null
              ? "待审核"
              : data.human_adoption.value.toFixed(2) + "%"}
            （{data.human_adoption.numerator}/{data.human_adoption.denominator}
            ，与GT命中率分开）
          </p>
          <div className="pattern-table">
            <table>
              <thead>
                <tr>
                  <th>优先级/模式</th>
                  <th>交互与独立失败条件</th>
                  <th>证据/风险/历史</th>
                  <th>业务反馈</th>
                </tr>
              </thead>
              <tbody>
                {result.ranked.map((r: any) => (
                  <tr key={r.scenario_id}>
                    <td>
                      <b>
                        #{r.rank} · {r.priority.toFixed(3)}
                      </b>
                      <p>{r.pattern_id}</p>
                      {r.selected ? "纳入Q" : "未入选"}
                      {r.mandatory && " · 关键保底"}
                    </td>
                    <td>
                      {r.scenario.interaction_id}
                      <p>{r.scenario.conditions.join("；")}</p>
                      <details>
                        <summary>关联关注点及证据</summary>
                        <p>{r.scenario.concern_origins?.join("、")}</p>
                        {r.scenario.source_refs.map((ref: any, i: number) => (
                          <blockquote key={i}>
                            {ref.quote}
                            <small>
                              {" "}
                              {ref.source_id}:{ref.line_start}–{ref.line_end}
                            </small>
                          </blockquote>
                        ))}
                      </details>
                    </td>
                    <td>
                      C={r.confidence.score} · {r.confidence.basis}
                      <p>
                        R={r.risk.score}（{risks[r.risk.level]}） · H=
                        {r.history_score.toFixed(3)}
                      </p>
                      {r.risk.reason}
                      <p>
                        {r.reason}
                        {r.scenario.executable === false
                          ? " · 条件级不可直接执行"
                          : ""}
                      </p>
                      <details>
                        <summary>历史来源 {r.history_sources.length}条</summary>
                        <pre>{JSON.stringify(r.history_sources, null, 2)}</pre>
                      </details>
                    </td>
                    <td>
                      <input
                        placeholder="审核说明"
                        value={notes[r.scenario_id] || ""}
                        onChange={(e) =>
                          setNotes({
                            ...notes,
                            [r.scenario_id]: e.target.value,
                          })
                        }
                      />
                      <select
                        aria-label={"反馈 " + r.scenario_id}
                        value=""
                        onChange={(e) =>
                          e.target.value &&
                          act("recommendations/feedback", {
                            case_id: cid,
                            scenario_id: r.scenario_id,
                            choice: e.target.value,
                            settings_hash: result.settings_hash,
                            revision: hist.revision,
                            note: notes[r.scenario_id] || "",
                          })
                        }
                      >
                        <option value="">提交反馈</option>
                        {Object.entries(feedbacks).map(([v, n]) => (
                          <option key={v} value={v}>
                            {n}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="concern-pattern-tree">
            <summary>
              关注点 → 模式 → 场景实例（同一失败多关联不重复计分）
            </summary>
            {Array.from(
              new Set<string>(
                (data.matrix?.instances || []).flatMap(
                  (x: any) =>
                    x.scenario.concern_origins || [x.scenario.concern_key],
                ),
              ),
            ).map((key) => {
              const items = (data.matrix?.instances || []).filter((x: any) =>
                (
                  x.scenario.concern_origins || [x.scenario.concern_key]
                ).includes(key),
              );
              return (
                <details key={key}>
                  <summary>
                    {key} · {items.length}个实例，已接受
                    {items.filter((x: any) => x.status === "accepted").length}个
                  </summary>
                  <div className="pattern-table">
                    <table>
                      <thead>
                        <tr>
                          <th>交互/模式</th>
                          <th>独立失败条件</th>
                          <th>适用性与证据</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((x: any) => (
                          <tr key={x.id}>
                            <td>
                              {x.scenario.interaction_id}
                              <p>{x.pattern_id}</p>
                            </td>
                            <td>{x.scenario.conditions.join("；")}</td>
                            <td>
                              {
                                (
                                  {
                                    accepted: "进入G",
                                    pending: "待确认，不计分",
                                    excluded: "明确排除",
                                  } as Record<string, string>
                                )[x.status]
                              }{" "}
                              · C={x.scenario.confidence.score}
                              <p>{x.scenario.confidence.basis}</p>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              );
            })}
          </details>
          <h3>关键待审 / 模式缺项（不进入G或Q）</h3>
          {!result.critical_review.length && <p>无关键待审候选。</p>}
          {result.critical_review.map((r: any) => (
            <article className="pattern-review" key={r.candidate_id}>
              <b>{r.scenario?.pattern_id || "模式缺项"}</b>
              {r.scenario && (
                <p>
                  交互 {r.scenario.interaction_id} ·{" "}
                  {r.scenario.scenario_context?.caller} →{" "}
                  {r.scenario.scenario_context?.provider} ·{" "}
                  {r.scenario.operation}
                </p>
              )}
              <p>{r.scenario?.conditions.join("；") || r.issue?.reason}</p>
              <small>{r.reason}</small>
              {r.scenario && (
                <details>
                  <summary>正常依据与缺少的前提</summary>
                  <p>{r.scenario.confidence.basis}</p>
                  {r.scenario.source_refs.map((ref: any, i: number) => (
                    <blockquote key={i}>
                      {ref.quote}
                      <small>
                        {" "}
                        {ref.source_id}:{ref.line_start}–{ref.line_end}
                      </small>
                    </blockquote>
                  ))}
                </details>
              )}
              {r.scenario && (
                <>
                  <input
                    placeholder="明确正常业务规则（确认适用必填）"
                    value={premises[r.candidate_id] || ""}
                    onChange={(e) =>
                      setPremises({
                        ...premises,
                        [r.candidate_id]: e.target.value,
                      })
                    }
                  />
                  <input
                    placeholder="审核说明"
                    value={notes[r.candidate_id] || ""}
                    onChange={(e) =>
                      setNotes({ ...notes, [r.candidate_id]: e.target.value })
                    }
                  />
                  {[
                    ["confirm", "确认适用"],
                    ["reject", "不适用"],
                    ["needs_info", "待补材料"],
                  ].map(([v, n]) => (
                    <button
                      key={v}
                      onClick={() =>
                        act("patterns/review", {
                          case_id: cid,
                          candidate_id: r.candidate_id,
                          choice: v,
                          expected_version: data.current_settings_hash,
                          note: notes[r.candidate_id],
                          positive_condition: premises[r.candidate_id],
                        })
                      }
                    >
                      {n}
                    </button>
                  ))}
                </>
              )}
            </article>
          ))}
        </>
      )}
    </section>
  );
}
