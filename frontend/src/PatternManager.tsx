import { useEffect, useRef, useState } from "react";
import { SlidersHorizontal, Save, Plus } from "lucide-react";
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
    [text, setText] = useState(""),
    [definitions, setDefinitions] = useState<Record<string, any>>({}),
    [dirty, setDirty] = useState(false),
    [saving, setSaving] = useState(false);
  const editor = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let live = true;
    setView(null);
    setMsg("");
    setDirty(false);
    setDefinitions({});
    Promise.all([
      api(projectUrl(project, "patterns")),
      api(projectUrl(project, "recommendation-history")),
    ])
      .then(([v, h]) => {
        if (live) {
          setView(v);
          setSelected(v.settings.library.patterns[0]?.id || "");
          setHist(h);
        }
      })
      .catch((e) => live && setMsg(e.message));
    api(projectUrl(project, "registry"))
      .then((v) => live && setDefinitions(v.registry?.definitions || {}))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [project]);
  useEffect(() => {
    editor.current?.scrollTo?.({ top: 0 });
  }, [selected]);
  if (!view) return <p>正在读取项目模式库…{msg}</p>;
  const s = view.settings,
    ps = s.library.patterns,
    p = ps.find((r: any) => r.id === selected);
  const edit = (v: any) => {
    setView({ ...view, settings: { ...s, ...v } });
    setDirty(true);
  };
  const patch = (v: any) =>
    edit({
      library: {
        ...s.library,
        patterns: ps.map((r: any) =>
          r.id === selected ? { ...r, ...v, version: r.version + 1 } : r,
        ),
      },
    });
  const risk = (r: any) => s.overrides[r.id]?.risk_level || r.risk_level;
  const filtered = ps.filter(
    (r: any) =>
      (!riskFilter || risk(r) === riskFilter) &&
      [
        r.id,
        r.label,
        ...r.concern_keys.map(
          (k: string) => `${definitions[k]?.label || ""} ${k}`,
        ),
      ]
        .join(" ")
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const concernName = (k: string) => definitions[k]?.label || k;
  async function save() {
    setSaving(true);
    try {
      setView(
        await api(projectUrl(project, "patterns"), {
          method: "PUT",
          body: JSON.stringify({ expected_version: view.version, settings: s }),
        }),
      );
      setDirty(false);
      setMsg("已保存版本。继续运行后生成新结果；旧报告保留原快照。");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setSaving(false);
    }
  }
  function add() {
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
  }
  return (
    <section className="pattern-manager pattern-workbench">
      <header className="pattern-toolbar">
        <div className="insights-heading">
          <h2>模式与风险</h2>
          <p>关注点 → 异常模式 → 具体交互场景</p>
        </div>
        <div className="pattern-counts">
          <span>
            模式 <b>{ps.length}</b>
          </span>
          <span>
            启用 <b>{ps.filter((r: any) => r.enabled).length}</b>
          </span>
          <span>
            关键{" "}
            <b>
              {
                ps.filter((r: any) => risk(r) === "critical" && r.enabled)
                  .length
              }
            </b>
          </span>
        </div>
        <span className="pattern-version">
          项目版本 {view.version.slice(0, 10)}
        </span>
        <span className="pattern-save-status">
          {dirty ? "有未保存修改" : "已保存"}
        </span>
        <button onClick={save} disabled={saving}>
          <Save size={15} />
          {saving ? "保存中…" : "保存版本"}
        </button>
      </header>
      {msg && (
        <p role="status" className="pattern-message">
          {msg}
        </p>
      )}
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
              aria-label="风险权重"
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
              if (e.target.value)
                try {
                  const v = await api(
                    projectUrl(project, "patterns?version=" + e.target.value),
                  );
                  edit(v.settings);
                  setMsg("已载入历史内容，保存后切换设置版本。");
                } catch (error: any) {
                  setMsg(error.message);
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
        <aside className="pattern-library" aria-label="模式库导航">
          <div className="pattern-library-tools">
            <div className="pattern-list-header">
              <h3>模式库</h3>
              <span>
                {filtered.length} / {ps.length}项
              </span>
            </div>
            <input
              aria-label="搜索模式"
              value={search}
              placeholder="搜索名称、关注点或ID"
              onChange={(e) => setSearch(e.target.value)}
            />
            <div className="pattern-filter-row">
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
              <button className="pattern-add" onClick={add}>
                <Plus size={15} />
                新增
              </button>
            </div>
          </div>
          <div className="pattern-library-items" aria-label="模式列表">
            {filtered.map((r: any) => (
              <button
                key={r.id}
                className={r.id === selected ? "active" : ""}
                aria-pressed={r.id === selected}
                onClick={() => setSelected(r.id)}
              >
                <span className="pattern-list-title">
                  <b>{r.label}</b>
                  <i data-risk={risk(r)}>{risks[risk(r)]}</i>
                </span>
                <small>
                  {r.concern_keys.map(concernName).join(" · ")}
                  {!r.enabled ? " · 已停用" : ""}
                </small>
                <code>{r.id}</code>
              </button>
            ))}
            {!filtered.length && (
              <p className="pattern-empty">
                没有匹配的模式，请调整搜索或风险筛选。
              </p>
            )}
          </div>
        </aside>
        <main className="pattern-editor" aria-label="模式编辑区">
          {p ? (
            <>
              <header className="pattern-editor-header">
                <div>
                  <small>当前模式</small>
                  <h3>{p.label}</h3>
                  <code>
                    {p.id} · 修订{p.version}
                  </code>
                </div>
                <span className="risk-pill" data-risk={risk(p)}>
                  {risks[risk(p)]}风险
                </span>
              </header>
              <div className="pattern-editor-body" ref={editor}>
                <section className="pattern-form-section">
                  <header>
                    <span>01</span>
                    <div>
                      <h4>场景定义</h4>
                      <p>
                        明确一个独立失败条件；具体字段与边界由交互和接口约束提供。
                      </p>
                    </div>
                  </header>
                  <label>
                    模式名称
                    <input
                      aria-label="模式名称"
                      value={p.label}
                      onChange={(e) => patch({ label: e.target.value })}
                    />
                  </label>
                  <label>
                    独立失败条件／触发模板
                    <textarea
                      aria-label="独立失败条件"
                      rows={2}
                      value={p.trigger_template}
                      onChange={(e) =>
                        patch({ trigger_template: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    所需证据
                    <textarea
                      aria-label="所需证据"
                      rows={2}
                      value={p.required_evidence}
                      onChange={(e) =>
                        patch({ required_evidence: e.target.value })
                      }
                    />
                  </label>
                </section>
                <section className="pattern-form-section">
                  <header>
                    <span>02</span>
                    <div>
                      <h4>适用范围与关注点</h4>
                      <p>只有适用前提和正常依据满足时，才构造本模式的场景。</p>
                    </div>
                  </header>
                  {p.selector &&
                  p.preconditions.some((line: string) =>
                    line.includes(p.selector),
                  ) ? (
                    <div className="pattern-premises">
                      <span className="pattern-field-label">适用前提</span>
                      <ul>
                        {p.preconditions.map((line: string, i: number) => (
                          <li key={i}>
                            {line.replaceAll(
                              p.selector,
                              "【匹配条件详见高级规则】",
                            )}
                          </li>
                        ))}
                      </ul>
                      <details key={p.id}>
                        <summary>编辑原始前提（含程序表达式）</summary>
                        <label>
                          适用前提（每行一项）
                          <textarea
                            aria-label="适用前提"
                            rows={3}
                            value={p.preconditions.join("\n")}
                            onChange={(e) =>
                              patch({
                                preconditions: e.target.value.split("\n"),
                              })
                            }
                          />
                        </label>
                      </details>
                    </div>
                  ) : (
                    <label>
                      适用前提（每行一项）
                      <textarea
                        aria-label="适用前提"
                        rows={3}
                        value={p.preconditions.join("\n")}
                        onChange={(e) =>
                          patch({ preconditions: e.target.value.split("\n") })
                        }
                      />
                    </label>
                  )}
                  <div className="pattern-concerns">
                    <span className="pattern-field-label">关联具体关注点</span>
                    <div className="pattern-concern-chips">
                      {p.concern_keys.map((k: string) => (
                        <span key={k} title={k}>
                          {concernName(k)}
                        </span>
                      ))}
                    </div>
                    <details>
                      <summary>
                        调整关联关注点 <small>{p.concern_keys.length}项</small>
                      </summary>
                      <div className="pattern-concern-options">
                        {Array.from(
                          new Set<string>([
                            ...p.concern_keys,
                            ...Object.keys(definitions).filter(
                              (k) =>
                                definitions[k].kind === "check" &&
                                definitions[k].enabled !== false,
                            ),
                          ]),
                        ).map((k) => (
                          <label key={k}>
                            <input
                              type="checkbox"
                              checked={p.concern_keys.includes(k)}
                              onChange={(e) =>
                                patch({
                                  concern_keys: e.target.checked
                                    ? [...p.concern_keys, k]
                                    : p.concern_keys.filter(
                                        (v: string) => v !== k,
                                      ),
                                })
                              }
                            />
                            <span>
                              {concernName(k)}
                              <code>{k}</code>
                            </span>
                          </label>
                        ))}
                      </div>
                    </details>
                  </div>
                </section>
                <section className="pattern-form-section">
                  <header>
                    <span>03</span>
                    <div>
                      <h4>项目风险</h4>
                      <p>
                        风险与适用依据分开设置，等级不会自动使不适用的场景进入推荐。
                      </p>
                    </div>
                  </header>
                  <div className="pattern-risk-grid">
                    <label>
                      风险等级
                      <select
                        aria-label="模式风险等级"
                        value={risk(p)}
                        onChange={(e) =>
                          edit({
                            overrides: {
                              ...s.overrides,
                              [p.id]: {
                                risk_level: e.target.value,
                                reason:
                                  s.overrides[p.id]?.reason || "项目风险设置",
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
                    <label className="pattern-enable">
                      <input
                        aria-label="启用模式"
                        type="checkbox"
                        checked={p.enabled}
                        onChange={(e) => patch({ enabled: e.target.checked })}
                      />
                      启用模式
                    </label>
                  </div>
                  <label>
                    项目风险依据
                    <textarea
                      aria-label="项目风险依据"
                      rows={2}
                      value={s.overrides[p.id]?.reason ?? p.risk_reason}
                      onChange={(e) =>
                        edit({
                          overrides: {
                            ...s.overrides,
                            [p.id]: {
                              risk_level: risk(p),
                              reason: e.target.value,
                            },
                          },
                        })
                      }
                    />
                  </label>
                </section>
                <details className="pattern-advanced" key={p.id}>
                  <summary>
                    高级：程序匹配规则与定义标识<span>通常无需修改</span>
                  </summary>
                  <p>
                    以下为程序使用的匹配表达式，不是业务校验条件或异常示例。修改表达式不会自动补充需求约束。
                  </p>
                  <label>
                    正向规则匹配表达式
                    <textarea
                      aria-label="正向规则匹配表达式"
                      className="pattern-code-input"
                      spellCheck={false}
                      rows={3}
                      value={p.selector || ""}
                      placeholder="无自定义表达式"
                      onChange={(e) =>
                        patch({ selector: e.target.value || null })
                      }
                    />
                  </label>
                  <small>
                    {p.id.startsWith("custom.")
                      ? "自定义模式按表达式筛选正向正常规则。"
                      : "预置模式仍按既有工具规则解释；编辑不改变其模式类型。"}{" "}
                    字段模式使用接口真实边界，置信度表示依据充分性。
                  </small>
                  <dl>
                    <dt>稳定ID</dt>
                    <dd>{p.id}</dd>
                    <dt>定义摘要</dt>
                    <dd>{p.definition_hash || "保存后计算"}</dd>
                  </dl>
                </details>
                <div className="pattern-editor-footer">
                  <span>修改保留在当前草稿，点击右上角“保存版本”后生效。</span>
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
                </div>
              </div>
            </>
          ) : (
            <p className="pattern-empty">
              从左侧选择模式查看和编辑。未保存的修改仍保留在当前草稿中。
            </p>
          )}
        </main>
      </div>
      <details className="pattern-history-panel">
        <summary>导入已审核业务历史 · {hist?.items.length || 0}条</summary>
        <div>
          <p>
            仅接受人工审核记录。必需字段：id、pattern_id、pattern_hash、library_version、context、human_reviewed=true、decision(adopt/not_needed)、source_channel、case_id、run_id、reviewed_at、source。禁止导入GT或未经确认的机器结果。
          </p>
          <textarea
            aria-label="历史JSON"
            className="history-input pattern-code-input"
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
        </div>
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
