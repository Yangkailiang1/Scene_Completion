import { useEffect, useMemo, useRef, useState } from "react";
import {
  applySsdReview,
  exportSsdReview,
  getSsdEditor,
  getReviewSummary,
  previewSsdReview,
} from "../results/ssd/api";
import { getProjectEditor } from "../results/project/api";
import { scopeNames, type AnalysisScope } from "../results/project/types";
import "./ssd-review-handoff.css";

export type SsdReviewSelection = {
  scope?: AnalysisScope;
  anchorId?: string;
  caseId?: string;
  stepId?: string;
  differencesOnly?: boolean;
};
export type SsdReviewApplied = {
  scope?: AnalysisScope;
  anchorId?: string;
  caseIds: string[];
  caseId?: string;
  stepId?: string;
  scopes?: AnalysisScope[];
};
export type SsdReviewCase = { id: string; name?: string };
type ReviewItem = {
  item_id?: string;
  scope?: AnalysisScope;
  case_id: string;
  name?: string;
  status: string;
  changes?: { path: string; before?: unknown; after?: unknown }[];
  conflicts?: (string | { reason?: string })[];
};
type Preview = { cases: ReviewItem[] };
const identity = (item: ReviewItem) =>
  item.item_id || `${item.scope || "interaction"}:${item.case_id}`;
const allScopes: AnalysisScope[] = [
  "interaction",
  "business_chain",
  "architecture",
];

export function SsdReviewHandoff({
  project,
  cases,
  selection,
  onApplied,
}: {
  project: string;
  cases: SsdReviewCase[];
  selection?: SsdReviewSelection;
  onApplied?: (result: SsdReviewApplied) => void;
}) {
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);
  const [range, setRange] = useState("all"),
    [caseId, setCase] = useState(selection?.caseId || cases[0]?.id || "");
  const [anchorId, setAnchor] = useState(
      selection?.stepId || selection?.anchorId || "",
    ),
    [editor, setEditor] = useState<any>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [summary, setSummary] = useState<any>(null),
    [refresh, setRefresh] = useState(0);
  const [feedback, setFeedback] = useState(""),
    [preview, setPreview] = useState<Preview | null>(null),
    [selected, setSelected] = useState<string[]>([]);
  const scoped = range === "business_chain" || range === "architecture";
  const body = useMemo(
    () =>
      range === "all"
        ? {}
        : scoped
          ? { scopes: [range], ...(anchorId ? { anchor_ids: [anchorId] } : {}) }
          : {
              scopes: ["interaction"],
              case_ids: [caseId],
              ...(range === "step" && anchorId
                ? { anchor_ids: [anchorId] }
                : {}),
            },
    [range, scoped, caseId, anchorId],
  );
  useEffect(() => {
    let active = true;
    setSummary(null);
    setError("");
    getReviewSummary(project, body)
      .then((value) => {
        if (active) setSummary(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [project, body, refresh]);
  useEffect(() => {
    let active = true;
    setEditor(null);
    const request = scoped
      ? getProjectEditor(project, range as "business_chain" | "architecture")
      : range === "step" && caseId
        ? getSsdEditor(project, caseId)
        : null;
    request
      ?.then((value) => {
        if (active) setEditor(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [project, range, caseId, scoped]);
  async function exportFile() {
    setBusy(true);
    setError("");
    try {
      const blob = await exportSsdReview(project, body);
      if (!live.current) return;
      const url = URL.createObjectURL(blob),
        link = document.createElement("a");
      link.href = url;
      link.download =
        range === "all"
          ? "三层场景审核与完整参考.html"
          : "场景审核与完整参考.html";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice(
        "已导出保存版本：一个HTML包含所选范围的差异审核及完整参考；保存后可在下方一次回导。",
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function previewFile(file: File) {
    setBusy(true);
    setError("");
    setPreview(null);
    setSelected([]);
    setFeedback("");
    try {
      const text = await file.text(),
        value = (await previewSsdReview(project, text)) as Preview;
      if (!live.current) return;
      setFeedback(text);
      setPreview(value);
      setSelected(
        value.cases.filter((i) => i.status === "ready").map(identity),
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function apply() {
    setBusy(true);
    setError("");
    try {
      const value = (await applySsdReview(
        project,
        feedback,
        selected,
      )) as Preview;
      if (!live.current) return;
      setPreview(value);
      setSelected([]);
      const applied = value.cases.filter((i) => i.status === "applied");
      if (applied.length) {
        const target = applied[0];
        setRefresh((v) => v + 1);
        setNotice("已应用所选三层反馈，结果与指标已更新。");
        onApplied?.({
          scope: target.scope || "interaction",
          caseId:
            target.scope && target.scope !== "interaction"
              ? undefined
              : target.case_id,
          caseIds: applied
            .filter((i) => !i.scope || i.scope === "interaction")
            .map((i) => i.case_id),
          scopes: [...new Set(applied.map((i) => i.scope || "interaction"))],
        });
      } else setNotice("没有新增修改；请核对无变化项与版本冲突。");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {error && (
        <p role="alert" className="management-notice">
          {error} <button onClick={() => setRefresh((v) => v + 1)}>重试</button>
        </p>
      )}
      {notice && (
        <p role="status" className="management-notice">
          {notice}
        </p>
      )}
      <article>
        <h3>导出三层审核 HTML</h3>
        <p>
          默认包含全部用例、业务链路和项目架构。差异审核仅采纳已完成且GT未覆盖的G场景；完整参考可阅读三层全部E／G／GT及原文，不能修改。
        </p>
        <p>
          导出以已保存修订为准；结果页有草稿时请先保存。当前选中的步骤不会自动限制导出。
        </p>
        <details>
          <summary>高级筛选（可选）</summary>
          <div className="management-filters">
            <label>
              审核范围
              <select
                aria-label="SSD 审核范围"
                value={range}
                disabled={busy}
                onChange={(e) => {
                  setRange(e.target.value);
                  setAnchor("");
                }}
              >
                <option value="all">三层全部结果</option>
                <option value="case">交互级 · 当前用例</option>
                <option value="step">交互级 · 当前步骤</option>
                <option value="business_chain">业务链路</option>
                <option value="architecture">项目架构</option>
              </select>
            </label>
            {(range === "case" || range === "step") && (
              <label>
                用例
                <select
                  aria-label="SSD 审核用例"
                  value={caseId}
                  disabled={busy}
                  onChange={(e) => {
                    setCase(e.target.value);
                    setAnchor("");
                  }}
                >
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.id} · {c.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {(range === "step" || scoped) && (
              <label>
                步骤／对象
                <select
                  aria-label="SSD 审核步骤"
                  disabled={busy || !editor}
                  value={anchorId}
                  onChange={(e) => setAnchor(e.target.value)}
                >
                  <option value="">
                    {scoped ? "本层全部对象" : "选择步骤"}
                  </option>
                  {(editor?.bundle.steps || editor?.bundle.anchors || []).map(
                    (a: any) => (
                      <option key={a.id} value={a.id}>
                        {a.operation?.name ||
                          a.name ||
                          `${a.from_case_id} → ${a.to_case_id}`}
                      </option>
                    ),
                  )}
                </select>
              </label>
            )}
          </div>
        </details>
        {!summary && !error && <p role="status">正在核对保存版本与导出资格…</p>}
        {summary?.excluded?.by_scope && (
          <div className="review-scope-summary">
            {allScopes
              .filter((s) => summary.excluded.by_scope[s])
              .map((s) => {
                const r = summary.excluded.by_scope[s];
                return (
                  <div key={s}>
                    <strong>{scopeNames[s]}</strong>：可审核 {r.exported} ·
                    已覆盖 {r.covered} · 未完成 {r.unfinished} · 挂载待修正{" "}
                    {r.inactive}
                    {!r.available ? " · 暂无已保存结果" : ""}
                    <details>
                      <summary>保存版本、完整结果数量及排除原因</summary>
                      {r.items.map((i: any) => (
                        <p key={i.id}>
                          {i.name} · 修订 {i.revision} · E/G/GT场景{" "}
                          {i.counts.E.scenarios}/{i.counts.G.scenarios}/
                          {i.counts.GT.scenarios}
                        </p>
                      ))}
                      <p>
                        另有 {r.source_pending}{" "}
                        条测试待定位或确认；仅阻断明确关联的场景。
                      </p>
                    </details>
                  </div>
                );
              })}
          </div>
        )}
        <button
          disabled={
            busy ||
            !summary ||
            (range === "step" && !anchorId) ||
            ((range === "case" || range === "step") && !caseId)
          }
          onClick={() => void exportFile()}
        >
          {busy ? "处理中…" : "导出三层审核 HTML"}
        </button>
      </article>
      <article>
        <h3>回收三层审核修改</h3>
        <p>
          上传一个已保存HTML或JSON即可预览全部三层；默认选中无冲突修改，确认应用后才更新。
        </p>
        <input
          aria-label="导入 SSD 审核文件"
          type="file"
          accept=".html,.htm,.json"
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void previewFile(f);
            e.target.value = "";
          }}
        />
        {preview && (
          <p role="status">
            仅预览；可应用{" "}
            {preview.cases.filter((i) => i.status === "ready").length} 项，冲突{" "}
            {preview.cases.filter((i) => i.status === "conflict").length} 项。
          </p>
        )}
        {preview?.cases.map((item) => (
          <div className="handoff-feedback-case" key={identity(item)}>
            <label>
              <input
                type="checkbox"
                aria-label={`应用 ${item.name || item.case_id}`}
                disabled={busy || item.status !== "ready"}
                checked={selected.includes(identity(item))}
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? [...selected, identity(item)]
                      : selected.filter((id) => id !== identity(item)),
                  )
                }
              />
              {scopeNames[item.scope || "interaction"]} ·{" "}
              {item.name || item.case_id} ·{" "}
              {(
                {
                  ready: "可应用",
                  unchanged: "无变化",
                  conflict: "版本冲突",
                  applied: "已应用",
                } as Record<string, string>
              )[item.status] || item.status}{" "}
              · {item.changes?.length || 0} 处修改
            </label>
            {item.conflicts?.map((c, i) => (
              <p key={i} role="alert">
                {typeof c === "string" ? c : c.reason}
              </p>
            ))}
            <details>
              <summary>修改明细</summary>
              {item.changes?.map((c, i) => (
                <div className="handoff-feedback-change" key={i}>
                  <strong>{c.path}</strong>
                  <pre>{JSON.stringify(c.before, null, 2)}</pre>
                  <span>→</span>
                  <pre>{JSON.stringify(c.after, null, 2)}</pre>
                </div>
              ))}
            </details>
          </div>
        ))}
        {preview && (
          <button
            disabled={busy || !selected.length}
            onClick={() => void apply()}
          >
            应用选定三层修改并返回结果
          </button>
        )}
      </article>
    </>
  );
}
