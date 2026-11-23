import { useEffect, useState } from "react";
import {
  applyProjectReview,
  exportProjectReview,
  getProjectEditor,
  previewProjectReview,
} from "../results/project/api";
import {
  anchorName,
  scopeNames,
  type ProjectBundle,
  type ProjectScope,
} from "../results/project/types";
import type { SsdReviewApplied, SsdReviewSelection } from "./SsdReviewHandoff";
import "./ssd-review-handoff.css";
export function ProjectReviewHandoff({
  project,
  scope,
  selection,
  onApplied,
}: {
  project: string;
  scope: ProjectScope;
  selection?: SsdReviewSelection;
  onApplied?: (result: SsdReviewApplied) => void;
}) {
  const [editor, setEditor] = useState<any>(null),
    [anchorId, setAnchor] = useState(
      selection?.scope === scope ? selection.anchorId || "" : "",
    );
  const [kind, setKind] = useState("both"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [content, setContent] = useState(""),
    [preview, setPreview] = useState<any>(null),
    [selected, setSelected] = useState(false);
  useEffect(() => {
    let active = true;
    setEditor(null);
    setPreview(null);
    setContent("");
    setSelected(false);
    setError("");
    setNotice("");
    setAnchor(selection?.scope === scope ? selection.anchorId || "" : "");
    getProjectEditor(project, scope)
      .then((value) => {
        if (active) setEditor(value);
      })
      .catch((error) => {
        if (active) setError(error.message);
      });
    return () => {
      active = false;
    };
  }, [project, scope, selection?.anchorId]);
  const bundle: ProjectBundle | undefined = editor?.bundle;
  async function exportFile() {
    setBusy(true);
    setError("");
    try {
      const body: {
        scope: ProjectScope;
        anchor_ids?: string[];
        record_ids?: string[];
      } = { scope };
      if (anchorId) body.anchor_ids = [anchorId];
      if (kind !== "both")
        body.record_ids = (editor?.comparison?.[kind] || [])
          .filter(
            (row: any) =>
              row.status !== "triple" &&
              (!anchorId || row.anchor_id === anchorId),
          )
          .flatMap((row: any) =>
            Object.values(row.cells).flatMap((records: any) =>
              records.map((record: any) => record.id),
            ),
          );
      const blob = await exportProjectReview(project, body),
        url = URL.createObjectURL(blob),
        link = document.createElement("a");
      link.href = url;
      link.download = `${scopeNames[scope]}-差异审核.html`;
      link.click();
      URL.revokeObjectURL(url);
      setNotice("已导出离线差异文件；业务保存后在本入口预览并回收修改。");
    } catch (error: any) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function previewFile(file: File) {
    setBusy(true);
    setError("");
    setPreview(null);
    setSelected(false);
    try {
      const text = await file.text();
      const result = await previewProjectReview(project, scope, text);
      if (result.scope !== scope)
        throw new Error(
          "审核文件分析范围与当前选择不一致，请切换对应范围后导入。",
        );
      setContent(text);
      setPreview(result);
    } catch (error: any) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function apply() {
    if (!selected || preview?.status !== "ready") return;
    setBusy(true);
    setError("");
    try {
      const result = await applyProjectReview(project, scope, content);
      setPreview(result);
      setSelected(false);
      if (result.status === "applied") {
        setNotice("选定范围修改已应用，分层与项目汇总指标已更新。");
        onApplied?.({ scope, anchorId: anchorId || undefined, caseIds: [] });
      }
    } catch (error: any) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {error && (
        <p className="management-notice" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="management-notice" role="status">
          {notice}
        </p>
      )}
      <article>
        <h3>导出{scopeNames[scope]}差异审核 HTML</h3>
        <p>
          只导出已完成匹配、GT没有覆盖的G场景。业务仅采纳或填写意见；原文、四元组、E和G只读。
        </p>
        <div className="management-filters">
          <label>
            审核对象
            <select
              aria-label="项目审核对象"
              value={anchorId}
              disabled={busy}
              onChange={(event) => setAnchor(event.target.value)}
            >
              <option value="">本层全部对象</option>
              {bundle?.anchors.map((anchor) => (
                <option key={anchor.id} value={anchor.id}>
                  {anchorName(anchor)}
                </option>
              ))}
            </select>
          </label>
          <label>
            不一致内容
            <select
              aria-label="项目不一致内容"
              value={kind}
              disabled={busy}
              onChange={(event) => setKind(event.target.value)}
            >
              <option value="both">G有、GT未覆盖的已完成场景</option>
            </select>
          </label>
          <button disabled={busy || !bundle} onClick={() => void exportFile()}>
            导出差异 HTML
          </button>
        </div>
      </article>
      <article>
        <h3>回收{scopeNames[scope]}审核修改</h3>
        <p>先预览差异，再勾选当前范围应用；不会自动调用模型。</p>
        <input
          type="file"
          accept=".html,.htm,.json"
          aria-label="导入项目审核文件"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void previewFile(file);
            event.target.value = "";
          }}
        />
        {preview && (
          <div className="handoff-feedback-case">
            <label>
              <input
                aria-label={`应用${scopeNames[scope]}修改`}
                type="checkbox"
                checked={selected}
                disabled={busy || preview.status !== "ready"}
                onChange={(event) => setSelected(event.target.checked)}
              />
              {scopeNames[scope]} ·{" "}
              {(
                {
                  ready: "可应用",
                  conflict: "版本冲突",
                  unchanged: "无变化",
                  applied: "已应用",
                } as Record<string, string>
              )[preview.status] || preview.status}{" "}
              · {preview.changes?.length || 0} 处修改
            </label>
            {preview.conflicts?.map((conflict: any, index: number) => (
              <p key={index} role="alert">
                {typeof conflict === "string"
                  ? conflict
                  : conflict.reason || JSON.stringify(conflict)}
              </p>
            ))}
            <details>
              <summary>修改明细</summary>
              {preview.changes?.map((change: any, index: number) => (
                <div className="handoff-feedback-change" key={index}>
                  <strong>{change.path}</strong>
                  <pre>{JSON.stringify(change.before, null, 2)}</pre>
                  <span>→</span>
                  <pre>{JSON.stringify(change.after, null, 2)}</pre>
                </div>
              ))}
            </details>
            <button
              disabled={busy || !selected || preview.status !== "ready"}
              onClick={() => void apply()}
            >
              应用选定范围修改并重算
            </button>
          </div>
        )}
      </article>
    </>
  );
}
