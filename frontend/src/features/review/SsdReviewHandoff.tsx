import { useEffect, useMemo, useRef, useState } from "react";
import { exportSsdBusinessReport, getReviewSummary } from "../results/ssd/api";
import type { AnalysisScope } from "../results/project/types";

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
type Category = "covered" | "g_only" | "gt_only";
type Count = { total: number; cases: number; shared_services: number };
type ReportSummary = {
  report?: { counts?: Record<Category, Count> };
  excluded?: { unfinished?: number };
};
type Range = "all" | "case" | "shared_services";

export function SsdReviewHandoff({
  project,
  cases,
  selection,
  initialSummary,
}: {
  project: string;
  cases: SsdReviewCase[];
  selection?: SsdReviewSelection;
  initialSummary?: ReportSummary | null;
}) {
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);

  const [range, setRange] = useState<Range>("all");
  const [selectedCase, setSelectedCase] = useState("");
  const caseId =
    [selectedCase, selection?.caseId].find((id) =>
      cases.some((item) => item.id === id),
    ) ||
    cases[0]?.id ||
    "";
  const body = useMemo(
    () =>
      range === "case"
        ? { scopes: ["interaction"], case_ids: [caseId] }
        : range === "shared_services"
          ? { scopes: [range] }
          : {},
    [range, caseId],
  );
  const [summary, setSummary] = useState<ReportSummary | null>(
    initialSummary ?? null,
  );
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [summaryError, setSummaryError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    setSummaryError("");
    if (range === "all" && initialSummary && retry === 0) {
      setSummary(initialSummary);
      return;
    }
    setSummary(null);
    getReviewSummary(project, body)
      .then((value) => {
        if (active) setSummary(value);
      })
      .catch((e: Error) => {
        if (active) setSummaryError(e.message);
      });
    return () => {
      active = false;
    };
  }, [project, body, range, retry, initialSummary]);

  async function exportFile() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const blob = await exportSsdBusinessReport(project, body);
      if (!live.current) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "异常场景完整性补全识别结果.html";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice("报告已导出。离线编辑后，点击报告内的「保存含修改的 HTML」。");
    } catch (e) {
      if (live.current) setError((e as Error).message);
    } finally {
      if (live.current) setBusy(false);
    }
  }

  const counts = summary?.report?.counts;
  return (
    <article>
      <h3>导出异常场景完整性补全识别报告</h3>
      <p>
        按用例列出生成与测试共有、仅生成有、仅测试有三类场景。可离线编辑并另存
        HTML，第二项支持按关注点筛选。
      </p>
      <p>报告使用已保存的修订。结果页有草稿时请先保存。</p>
      <details>
        <summary>导出范围（可选）</summary>
        <div className="management-filters">
          <label>
            报告范围
            <select
              aria-label="SSD 报告范围"
              value={range}
              disabled={busy}
              onChange={(event) => setRange(event.target.value as Range)}
            >
              <option value="all">全部用例与共用服务</option>
              <option value="case" disabled={!cases.length}>
                指定用例
              </option>
              <option value="shared_services">共用外部服务</option>
            </select>
          </label>
          {range === "case" && (
            <label>
              用例
              <select
                aria-label="SSD 报告用例"
                value={caseId}
                disabled={busy}
                onChange={(event) => setSelectedCase(event.target.value)}
              >
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name ? `${item.id} · ${item.name}` : item.id}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </details>
      {counts ? (
        <p>
          生成与测试共有 {counts.covered.total} 项 · 仅生成有{" "}
          {counts.g_only.total} 项 · 仅测试有 {counts.gt_only.total} 项 ·
          未纳入统计 {summary?.excluded?.unfinished ?? 0} 项
        </p>
      ) : (
        !summary && !summaryError && <p>正在计算报告数量…</p>
      )}
      {summaryError && (
        <p role="alert">
          {summaryError}{" "}
          <button onClick={() => setRetry((n) => n + 1)}>重试</button>
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <button
        onClick={() => void exportFile()}
        disabled={busy || (range === "case" && !caseId)}
      >
        {busy ? "正在导出…" : "导出报告 HTML"}
      </button>
    </article>
  );
}
