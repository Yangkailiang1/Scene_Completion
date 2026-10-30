import { useEffect, useState } from "react";
import { api, projectUrl } from "./api";
import { SourceEvidence } from "./SourceEvidence";
import {
  Activity,
  ArrowRight,
  Download,
  RefreshCw,
  SearchCheck,
} from "lucide-react";

const causeLabel: Record<string, string> = {
  recognition: "识别或适用条件",
  localization: "交互或对象定位",
  taxonomy: "分类与定义",
  patterns: "模式与粒度",
  truth: "测试真值与覆盖",
  matching: "场景与覆盖匹配",
  ranking: "推荐与风险排序",
  incomplete: "材料或任务未完成",
  unverified: "GT未验证",
  unknown: "待查明",
};
const statusLabel: Record<string, string> = {
  queued: "等待诊断",
  running: "诊断中",
  partial: "部分完成",
  complete: "已完成",
};
const sourceLabel: Record<string, string> = {
  original: "原始测试",
  expanded: "扩展测试",
  business: "业务审核后",
};
const scopeLabel: Record<string, string> = {
  current: "当前层级",
  baseline: "推荐前M",
  recommended: "推荐后Q",
};
type Props = { project: string; caseId: string; testSet: string };
export function QualityDiagnostics({ project, caseId, testSet }: Props) {
  const [page, setPage] = useState(0);
  const [items, setItems] = useState<any[]>([]),
    [report, setReport] = useState<any>(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [metric, setMetric] = useState("");
  const [selected, setSelected] = useState<string[]>([]),
    [reviewer, setReviewer] = useState(""),
    [impact, setImpact] = useState<any>(null);
  const [showAll, setShowAll] = useState(false),
    [comparison, setComparison] = useState<any>(null);
  const [evidence, setEvidence] = useState<any>(null),
    [readonly, setReadonly] = useState(true),
    [caseOnly, setCaseOnly] = useState(false);
  const base = projectUrl(project, "quality-diagnostics");
  async function refresh(id?: string) {
    const r = await api(base);
    setItems(r.items);
    setReadonly(r.review_only);
    const chosen =
      (id === "" ? undefined : id || report?.id) ||
      r.items.find(
        (v: any) =>
          v.test_set === testSet && (!v.case_id || v.case_id === caseId),
      )?.id;
    if (chosen) {
      const query = new URLSearchParams({
        view: "compact",
        offset: String(page * 100),
        limit: "100",
      });
      if (!showAll && caseId) query.set("case_id", caseId);
      if (metric) query.set("metric", metric);
      const v = await api(base + "/" + chosen + "?" + query.toString());
      setReport(v);
    }
  }
  useEffect(() => {
    setReport(null);
    setImpact(null);
    setSelected([]);
    refresh("").catch((e) => setError(e.message));
  }, [project, testSet]);
  useEffect(() => {
    setPage(0);
    setMetric("");
  }, [caseId, showAll]);
  useEffect(() => {
    if (report?.id) refresh(report.id).catch((e) => setError(e.message));
  }, [caseId, showAll, metric, page]);
  useEffect(() => {
    if (!report || !["queued", "running"].includes(report.status)) return;
    const t = setInterval(
      () => refresh(report.id).catch((e) => setError(e.message)),
      2500,
    );
    return () => clearInterval(t);
  }, [report?.id, report?.status]);
  async function action(fn: () => Promise<any>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const approval = {
    snapshot_hash: report?.snapshot_hash,
    approvals: selected,
    reviewer,
  };
  const losses = (report?.losses || []).filter(
    (l: any) =>
      (showAll || !caseId || l.case_id === caseId) &&
      (!metric || `${l.case_id}:${l.scope}:${l.metric}` === metric),
  );
  const cards = (report?.cards || []).filter(
    (c: any) =>
      showAll || !caseId || c.case_id === caseId || c.case_id === "shared",
  );
  return (
    <section className="quality-view">
      <header className="quality-toolbar">
        <div>
          <h2>
            <SearchCheck size={20} /> 指标诊断
          </h2>
          <p>
            冻结结果 → 核对损失 → 证据归因 → 人工确认。诊断不会修改正式指标。
          </p>
        </div>
        <div className="quality-controls">
          <select
            aria-label="已保存诊断"
            value={report?.id || ""}
            onChange={(e) => action(() => refresh(e.target.value))}
          >
            <option value="">选择诊断报告</option>
            {items.map((v) => (
              <option key={v.id} value={v.id}>
                {new Date(v.created_at * 1000).toLocaleString()} ·{" "}
                {sourceLabel[v.test_set] || v.test_set} ·{" "}
                {v.case_id || "全项目"} · {statusLabel[v.status] || v.status}
              </option>
            ))}
          </select>
          <button disabled={busy} onClick={() => action(() => refresh())}>
            <RefreshCw size={14} />
            刷新
          </button>
          {!readonly && (
            <>
              <label>
                <input
                  type="checkbox"
                  checked={caseOnly}
                  onChange={(e) => setCaseOnly(e.target.checked)}
                />
                仅当前用例
              </label>
              <button
                className="primary"
                disabled={busy || (caseOnly && !caseId)}
                onClick={() =>
                  action(async () => {
                    const v = await api(base, {
                      method: "POST",
                      body: JSON.stringify({
                        test_set: testSet,
                        case_id: caseOnly ? caseId : null,
                      }),
                    });
                    setReport(v);
                    setImpact(null);
                    setSelected([]);
                    await refresh(v.id);
                  })
                }
              >
                开始诊断
              </button>
            </>
          )}
        </div>
      </header>
      {!readonly && report?.status === "partial" && (
        <button
          disabled={busy}
          onClick={() =>
            action(async () => {
              const v = await api(base + "/" + report.id + "/resume", {
                method: "POST",
                body: "{}",
              });
              setReport(v);
            })
          }
        >
          继续未完成诊断（保留原预算）
        </button>
      )}
      {error && (
        <div role="alert" className="management-notice">
          {error}
        </div>
      )}
      {!report ? (
        <div className="quality-empty">
          <Activity />
          <h3>尚未保存当前测试来源的诊断</h3>
          <p>新完成的评测轮自动创建一次。旧报告只在手动发起时诊断。</p>
        </div>
      ) : (
        <>
          <div className="quality-snapshot">
            <span>状态：{statusLabel[report.status] || report.status}</span>
            <span>
              {report.scope_complete ? "完整评测范围" : "按部分已保存结果诊断"}
            </span>
            <span>
              测试来源：{sourceLabel[report.test_set] || report.test_set}
            </span>
            <span>执行：{report.versions.execution || "未记录"}</span>
            <span>
              损失清单 {report.coverage.enumerated} · 模型已查{" "}
              {report.coverage.evidence_reviewed} · 待查明{" "}
              {report.coverage.unresolved}
            </span>
            <span>
              诊断预算：
              {report.budget?.charged_tokens?.toLocaleString() ||
                "尚无报告用量"}{" "}
              / 100,000 Token
            </span>
            <a href={base + "/" + report.id + "?format=md"}>
              <Download size={14} />
              MD
            </a>
            <a href={base + "/" + report.id} download>
              JSON
            </a>
          </div>
          {report.error && (
            <p className="management-notice">
              {report.error}。已完成清单和判断保留。
            </p>
          )}
          <div className="quality-controls">
            <label>
              <input
                type="checkbox"
                checked={showAll}
                onChange={(e) => {
                  setShowAll(e.target.checked);
                  setMetric("");
                }}
              />
              查看全部用例（默认当前用例）
            </label>
            <span>
              {caseId || "全项目"} · {cards.length}项指标
            </span>
          </div>
          <div className="quality-cards">
            {cards.map((c: any) => (
              <button
                key={c.id}
                className={
                  "quality-card " + (metric === c.id ? "selected" : "")
                }
                onClick={() => setMetric(metric === c.id ? "" : c.id)}
              >
                <small>
                  {c.case_id} · {scopeLabel[c.scope] || c.scope} ·{" "}
                  {c.unit || "保存口径"}
                </small>
                <strong>
                  {c.label} {c.direction}
                </strong>
                <b>{c.value == null ? c.status : `${c.value.toFixed(2)}%`}</b>
                <span>
                  {c.numerator ?? "—"} / {c.denominator ?? "—"} · 清单{" "}
                  {c.loss_count}
                </span>
                <small>{c.formula}</small>
                <span>
                  {Object.entries(c.causes)
                    .map(([k, n]) => `${causeLabel[k] || k}: ${n}`)
                    .join(" · ") || "无已展开损失"}
                </span>
              </button>
            ))}
          </div>
          {report.integrity.length > 0 && (
            <details className="quality-integrity">
              <summary>
                计数／版本核对待查明 {report.integrity.length} 项
              </summary>
              {report.integrity.map((r: any, i: number) => (
                <p key={i}>
                  {r.metric}：{r.reason}{" "}
                  {r.saved_loss_count != null &&
                    `正式 ${r.saved_loss_count} / 清单 ${r.enumerated}`}
                </p>
              ))}
            </details>
          )}
          <h3>
            逐项证据与原因{" "}
            <small>
              {report.pagination?.total ?? losses.length}项；每项仅一个主因
            </small>
          </h3>
          <div className="quality-table">
            <table>
              <thead>
                <tr>
                  <th>定位／指标</th>
                  <th>需求已有 E</th>
                  <th>方法生成 G</th>
                  <th>测试真值 GT</th>
                  <th>原因与依据</th>
                </tr>
              </thead>
              <tbody>
                {losses.map((l: any) => (
                  <tr key={l.id}>
                    <td>
                      <strong>
                        {l.case_id} · {l.anchor.interaction_id || "待定位"}
                      </strong>
                      <p>
                        {l.anchor.target} · {l.anchor.object || l.anchor.field}
                      </p>
                      <p>{l.anchor.concern_key}</p>
                      <small>{l.metric}</small>
                    </td>
                    {["E", "G", "GT"].map((k) => (
                      <td key={k}>
                        {l.cells[k]?.length
                          ? l.cells[k].map((s: any) => (
                              <div key={s.id || s.binding_id}>
                                <small>{s.id || s.binding_id}</small>
                                <p>
                                  {s.cause ||
                                    s.basis ||
                                    s.concrete_rule ||
                                    s.concern_key}
                                </p>
                              </div>
                            ))
                          : "无完整对应项"}
                      </td>
                    ))}
                    <td>
                      <span className="quality-certainty">
                        {l.certainty} ·{" "}
                        {causeLabel[l.primary_cause] || l.primary_cause}
                      </span>
                      <p>{l.reason}</p>
                      {l.evidence.map((e: any, i: number) => (
                        <button key={i} onClick={() => setEvidence(e)}>
                          点击以查看文档 · {e.line_start}行
                        </button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.pagination?.total > 100 && (
            <div className="quality-controls">
              <button disabled={!page} onClick={() => setPage(page - 1)}>
                上一页
              </button>
              <span>
                第{page + 1}页／{Math.ceil(report.pagination.total / 100)}页
              </span>
              <button
                disabled={(page + 1) * 100 >= report.pagination.total}
                onClick={() => setPage(page + 1)}
              >
                下一页
              </button>
            </div>
          )}
          <h3>
            优化建议 <small>人工确认后应用；不直接改写需求、测试或计分</small>
          </h3>
          {report.proposals.length === 0 && (
            <p className="quality-empty">
              暂无可核实的配置修改建议。证据不足的损失保持待查明。
            </p>
          )}
          {report.proposals.map((p: any) => (
            <article className="quality-proposal" key={p.id}>
              <header>
                <label>
                  <input
                    type="checkbox"
                    disabled={readonly || !p.applicable || !!report.applied}
                    checked={selected.includes(p.id)}
                    onChange={(e) => {
                      setSelected(
                        e.target.checked
                          ? [...selected, p.id]
                          : selected.filter((id) => id !== p.id),
                      );
                      setImpact(null);
                    }}
                  />
                  {p.kind} · {p.target}
                </label>
                <span>{p.status}</span>
              </header>
              <p>{p.reason}</p>
              <div className="quality-diff">
                <div>
                  <small>当前内容</small>
                  <pre>
                    {JSON.stringify(p.current ?? "影响预览时核对", null, 2)}
                  </pre>
                </div>
                <div>
                  <small>建议内容</small>
                  <pre>{JSON.stringify(p.suggested || p.patch, null, 2)}</pre>
                </div>
              </div>
              <div>
                <p>风险：{p.risk}</p>
                <p>验证：{p.validation}</p>
                <p>关联损失：{p.loss_ids.join("、")}</p>
              </div>
            </article>
          ))}
          {!readonly && selected.length > 0 && !report.applied && (
            <div className="quality-approval">
              <input
                aria-label="确认人"
                placeholder="确认人"
                value={reviewer}
                onChange={(e) => {
                  setReviewer(e.target.value);
                  setImpact(null);
                }}
              />
              <button
                disabled={busy || !reviewer}
                onClick={() =>
                  action(async () =>
                    setImpact(
                      await api(base + "/" + report.id + "/impact", {
                        method: "POST",
                        body: JSON.stringify(approval),
                      }),
                    ),
                  )
                }
              >
                预览影响范围
              </button>
              {impact && (
                <>
                  <p>
                    {impact.ranking_only
                      ? "仅推荐与下游计分"
                      : "相关识别／场景链及下游"}{" "}
                    · {impact.affected.length}个节点 ·{" "}
                    {impact.case_ids.join("、")}
                  </p>
                  <details>
                    <summary>查看修改前后与受影响节点</summary>
                    <pre>{JSON.stringify(impact, null, 2)}</pre>
                  </details>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() =>
                      action(async () => {
                        await api(base + "/" + report.id + "/apply", {
                          method: "POST",
                          body: JSON.stringify({ ...approval, rerun: true }),
                        });
                        setImpact(null);
                        await refresh(report.id);
                      })
                    }
                  >
                    确认应用并重跑 <ArrowRight size={14} />
                  </button>
                </>
              )}
            </div>
          )}
          {report.applied && (
            <div className="management-notice">
              已应用，原报告保留。
              <button
                onClick={() =>
                  action(async () =>
                    setComparison(
                      await api(base + "/" + report.id + "/comparison"),
                    ),
                  )
                }
              >
                查看重跑前后对照
              </button>
              {comparison && (
                <>
                  <p>
                    {comparison.basis_change
                      ? "存在口径变化，不能直接解释成质量提升"
                      : "同口径对照"}
                  </p>
                  <div className="quality-table">
                    <table>
                      <thead>
                        <tr>
                          <th>用例／指标</th>
                          <th>修改前</th>
                          <th>修改后</th>
                          <th>变化</th>
                        </tr>
                      </thead>
                      <tbody>
                        {comparison.changes.map((c: any) => (
                          <tr key={c.case_id + c.metric}>
                            <td>
                              {c.case_id} · {c.metric}
                            </td>
                            <td>
                              {c.before.value ?? c.before.status}（
                              {c.before.numerator}/{c.before.denominator}）
                            </td>
                            <td>
                              {c.after.value ?? c.after.status}（
                              {c.after.numerator}/{c.after.denominator}）
                            </td>
                            <td>
                              {c.denominator_changed
                                ? "分母变化／口径变化"
                                : c.delta == null
                                  ? "待评测"
                                  : c.delta.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <details>
                    <summary>执行版本、Token与耗时</summary>
                    <pre>
                      {JSON.stringify(
                        {
                          versions_before: comparison.versions_before,
                          versions_after: comparison.versions_after,
                          usage_before: comparison.usage_before,
                          usage_after: comparison.usage_after,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </>
              )}
            </div>
          )}
          <details>
            <summary>
              排除项：正常、可选、不适用及待确认（不进入确定集合）
            </summary>
            <pre>{JSON.stringify(report.excluded, null, 2)}</pre>
          </details>
        </>
      )}
      {evidence && (
        <aside className="quality-source-overlay">
          <SourceEvidence
            project={project}
            evidence={evidence}
            onClose={() => setEvidence(null)}
          />
        </aside>
      )}
    </section>
  );
}
