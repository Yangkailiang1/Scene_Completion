import { Plus, Save, SlidersHorizontal } from "lucide-react";
import { api, projectUrl } from "../../shared/api";
import type { PatternDefinition, RiskLevel } from "./types";
import { usePatternManagerController } from "./usePatternManagerController";
export function PatternManager({ project }: { project: string }) {
  const {
    risks,
    view,
    selected,
    setSelected,
    riskFilter,
    setRiskFilter,
    search,
    setSearch,
    msg,
    setMsg,
    hist,
    setHist,
    text,
    setText,
    definitions,
    dirty,
    saving,
    editor,
    s,
    ps,
    p,
    edit,
    patch,
    risk,
    filtered,
    concernName,
    save,
    add,
  } = usePatternManagerController({ project });
  if (!view) return <p>正在读取项目模式库…{msg}</p>;
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
            启用 <b>{ps.filter((r: PatternDefinition) => r.enabled).length}</b>
          </span>
          <span>
            关键{" "}
            <b>
              {
                ps.filter(
                  (r: PatternDefinition) => risk(r) === "critical" && r.enabled,
                ).length
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
            {filtered.map((r: PatternDefinition) => (
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
                    line.includes(p.selector!),
                  ) ? (
                    <div className="pattern-premises">
                      <span className="pattern-field-label">适用前提</span>
                      <ul>
                        {p.preconditions.map((line: string, i: number) => (
                          <li key={i}>
                            {line.replaceAll(
                              p.selector!,
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
                                risk_level: e.target.value as RiskLevel,
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
                          patterns: ps.filter(
                            (r: PatternDefinition) => r.id !== p.id,
                          ),
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
export { RecommendationsView } from "./RecommendationsView";
