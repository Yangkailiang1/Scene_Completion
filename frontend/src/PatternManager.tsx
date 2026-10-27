import { useEffect, useRef, useState } from "react";
import {
  ShieldCheck,
  Layers,
  SlidersHorizontal,
  Save,
  Plus,
} from "lucide-react";
import { api, projectUrl } from "./api";
import { RecommendationComparison } from "./ResultComparison";
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
export function PatternManager({ project }: { project: string }) {
  const [view, setView] = useState<any>(null),
    [selected, setSelected] = useState(""),
    [riskFilter, setRiskFilter] = useState(""),
    [search, setSearch] = useState(""),
    [msg, setMsg] = useState(""),
    [hist, setHist] = useState<any>(null),
    [text, setText] = useState("");
  useEffect(() => {
    setView(null);
    Promise.all([
      api(projectUrl(project, "patterns")),
      api(projectUrl(project, "recommendation-history")),
    ])
      .then(([v, h]) => {
        setView(v);
        setSelected(v.settings.library.patterns[0]?.id || "");
        setHist(h);
      })
      .catch((e) => setMsg(e.message));
  }, [project]);
  if (!view) return <p>正在读取项目模式库…{msg}</p>;
  const s = view.settings,
    ps = s.library.patterns,
    p = ps.find((p: any) => p.id === selected);
  const edit = (v: any) => setView({ ...view, settings: { ...s, ...v } });
  const patch = (v: any) =>
    edit({
      library: {
        ...s.library,
        patterns: ps.map((r: any) =>
          r.id === selected ? { ...r, ...v, version: r.version + 1 } : r,
        ),
      },
    });
  const save = async () => {
    try {
      setView(
        await api(projectUrl(project, "patterns"), {
          method: "PUT",
          body: JSON.stringify({ expected_version: view.version, settings: s }),
        }),
      );
      setMsg("已保存版本。继续运行后生成新结果；旧报告保留原快照。");
    } catch (e: any) {
      setMsg(e.message);
    }
  };
  return (
    <section className="pattern-manager">
      <div className="pattern-toolbar">
        <div className="insights-heading">
          <span className="eyebrow">PATTERNS & RISK</span>
          <h2>模式与风险</h2>
          <p>关注点 → 异常模式 → 具体交互场景</p>
        </div>
        <span className="pattern-version">
          项目版本 {view.version.slice(0, 10)}
        </span>
        <button onClick={save}>
          <Save size={15} />
          保存版本
        </button>
      </div>
      {msg && <p role="status">{msg}</p>}
      <div className="pattern-overview">
        <div>
          <Layers size={18} />
          <span>
            异常模式<strong>{ps.length}</strong>
          </span>
        </div>
        <div>
          <ShieldCheck size={18} />
          <span>
            已启用<strong>{ps.filter((r: any) => r.enabled).length}</strong>
          </span>
        </div>
        <div>
          <ShieldCheck size={18} />
          <span>
            关键风险模式
            <strong>
              {
                ps.filter(
                  (r: any) =>
                    (s.overrides[r.id]?.risk_level || r.risk_level) ===
                      "critical" && r.enabled,
                ).length
              }
            </strong>
          </span>
        </div>
        <p>
          适用依据不足的候选进入待确认；关键风险优先保底。修改保存为新版本，旧报告保留原快照。
        </p>
      </div>
      <details className="pattern-policy">
        <summary>
          <SlidersHorizontal size={16} />
          推荐策略
          <span>
            证据阈值 {s.threshold} · 每用例 {s.top_k} 项 · 风险/历史{" "}
            {s.risk_weight}/{s.history_weight}
          </span>
        </summary>
        <div className="pattern-controls">
          <label>
            证据阈值
            <input
              aria-label="证据阈值"
              type="number"
              min="0"
              max="1"
              step=".05"
              value={s.threshold}
              onChange={(e) => edit({ threshold: +e.target.value })}
            />
          </label>
          <label>
            每用例K
            <input
              aria-label="每用例K"
              type="number"
              min="1"
              value={s.top_k}
              onChange={(e) => edit({ top_k: +e.target.value })}
            />
          </label>
          <label>
            风险权重
            <input
              type="number"
              min="0"
              max="1"
              step=".1"
              value={s.risk_weight}
              onChange={(e) =>
                edit({
                  risk_weight: +e.target.value,
                  history_weight: +(1 - Number(e.target.value)).toFixed(6),
                })
              }
            />
          </label>
          <span>
            历史权重 {s.history_weight} · 零历史H=0.5；关键项可超过K。
          </span>
          <select
            aria-label="设置历史"
            value=""
            onChange={async (e) => {
              if (e.target.value) {
                const v = await api(
                  projectUrl(project, "patterns?version=" + e.target.value),
                );
                edit(v.settings);
                setMsg("已载入历史内容，保存后切换设置版本。");
              }
            }}
          >
            <option value="">载入历史</option>
            {view.history.map((h: any, i: number) => (
              <option key={i} value={h.version}>
                {h.version.slice(0, 10)} ·{" "}
                {new Date(h.at * 1000).toLocaleString()}
              </option>
            ))}
          </select>
        </div>
      </details>
      <div className="pattern-columns">
        <aside>
          <div className="pattern-list-header">
            <h3>模式库</h3>
            <span>{ps.length}项</span>
          </div>
          <input
            aria-label="搜索模式"
            value={search}
            placeholder="搜索关注点、模式"
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            aria-label="模式风险筛选"
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
          >
            <option value="">全部风险等级</option>
            {Object.entries(risks).map(([k, v]) => (
              <option key={k} value={k}>
                {v}风险
              </option>
            ))}
          </select>
          <button
            className="pattern-add"
            onClick={() => {
              const n = {
                ...ps[0],
                concern_keys: ps[0]?.concern_keys || ["api.data.completeness"],
                risk_level: "normal",
                risk_reason: "项目新增模式，待审核适用条件",
                enabled: true,
                id: "custom." + Date.now(),
                label: "新模式",
                selector: null,
                preconditions: ["待填写适用前提"],
                trigger_template: "待填写独立失败条件",
                required_evidence: "明确正常规则",
                version: 1,
              };
              edit({ library: { ...s.library, patterns: [...ps, n] } });
              setSelected(n.id);
            }}
          >
            <Plus size={15} />
            新增模式
          </button>
          {ps
            .filter(
              (r: any) =>
                !riskFilter ||
                (s.overrides[r.id]?.risk_level || r.risk_level) === riskFilter,
            )
            .filter((r: any) =>
              JSON.stringify([r.id, r.label, r.concern_keys])
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((r: any) => (
              <button
                key={r.id}
                className={r.id === selected ? "active" : ""}
                onClick={() => setSelected(r.id)}
              >
                <span className="pattern-list-title">
                  <b>{r.label}</b>
                  <i data-risk={s.overrides[r.id]?.risk_level || r.risk_level}>
                    {risks[s.overrides[r.id]?.risk_level || r.risk_level]}
                  </i>
                </span>
                <small>
                  {r.id} ·{" "}
                  {risks[s.overrides[r.id]?.risk_level || r.risk_level]}
                  {r.enabled ? "" : " · 已停用"}
                </small>
              </button>
            ))}
        </aside>
        <main>
          {p ? (
            <>
              <div className="pattern-detail-heading">
                <span className="eyebrow">PATTERN DEFINITION</span>
                <h3>{p.label}</h3>
                <span
                  className="risk-pill"
                  data-risk={s.overrides[p.id]?.risk_level || p.risk_level}
                >
                  {risks[s.overrides[p.id]?.risk_level || p.risk_level]}风险
                </span>
              </div>
              <small>
                {p.id} · 修订{p.version} · 定义{" "}
                {p.definition_hash?.slice(0, 12) || "旧快照"}
              </small>
              {[
                ["label", "名称"],
                ["trigger_template", "独立失败条件/触发模板"],
                ["required_evidence", "所需证据"],
                ["selector", "正向规则前提匹配表达式"],
              ].map(([k, l]) => (
                <label key={k}>
                  {l}
                  <input
                    value={p[k] || ""}
                    onChange={(e) => patch({ [k]: e.target.value || null })}
                  />
                </label>
              ))}
              <label>
                关联具体关注点（逗号分隔）
                <input
                  value={p.concern_keys.join(",")}
                  onChange={(e) =>
                    patch({
                      concern_keys: e.target.value
                        .split(",")
                        .map((v) => v.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </label>
              <label>
                适用前提（每行一项）
                <textarea
                  value={p.preconditions.join("\n")}
                  onChange={(e) =>
                    patch({ preconditions: e.target.value.split("\n") })
                  }
                />
              </label>
              <p className="muted">
                custom.模式按表达式匹配正向正常规则；字段模式始终使用接口真实边界。置信度表示依据充分性，不是正确概率。
              </p>
              <label>
                风险等级
                <select
                  value={s.overrides[p.id]?.risk_level || p.risk_level}
                  onChange={(e) =>
                    edit({
                      overrides: {
                        ...s.overrides,
                        [p.id]: {
                          risk_level: e.target.value,
                          reason: s.overrides[p.id]?.reason || "项目风险设置",
                        },
                      },
                    })
                  }
                >
                  {Object.entries(risks).map(([v, n]) => (
                    <option value={v} key={v}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                项目风险依据
                <input
                  value={s.overrides[p.id]?.reason || p.risk_reason}
                  onChange={(e) =>
                    edit({
                      overrides: {
                        ...s.overrides,
                        [p.id]: {
                          risk_level:
                            s.overrides[p.id]?.risk_level || p.risk_level,
                          reason: e.target.value,
                        },
                      },
                    })
                  }
                />
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={p.enabled}
                  onChange={(e) => patch({ enabled: e.target.checked })}
                />
                启用模式
              </label>
              <button
                onClick={() => {
                  edit({
                    library: {
                      ...s.library,
                      patterns: ps.filter((r: any) => r.id !== p.id),
                    },
                  });
                  setSelected("");
                }}
              >
                从当前库删除（保留历史）
              </button>
            </>
          ) : (
            <p>选择模式查看适用前提、证据、触发及风险等级。</p>
          )}
        </main>
      </div>
      <details className="pattern-history-panel">
        <summary>导入已审核业务历史 · {hist?.items.length || 0}条</summary>
        <p>
          仅人工审核记录。必需字段：id、pattern_id、pattern_hash（模式definition_hash）、library_version、context、human_reviewed=true、decision(adopt/not_needed)、source_channel(business_review/business_adoption)、case_id、run_id、reviewed_at、source。禁止GT或未经确认的机器结果。
        </p>
        <textarea
          aria-label="历史JSON"
          className="history-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="JSON记录数组"
        />
        <button
          onClick={async () => {
            try {
              setHist(
                await api(projectUrl(project, "recommendation-history"), {
                  method: "POST",
                  body: JSON.stringify({
                    revision: hist.revision,
                    items: JSON.parse(text),
                  }),
                }),
              );
              setMsg("历史导入完成");
            } catch (e: any) {
              setMsg(e.message);
            }
          }}
        >
          导入
        </button>
      </details>
    </section>
  );
}
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
            "recommendations" + (cid ? "?case=" + encodeURIComponent(cid) : "") + (testSet === "original" ? (cid ? "&" : "?") + "test_set=original" : ""),
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
