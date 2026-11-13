import { lazy, Suspense, useEffect, useState } from "react";
import type { SourceDocument, SourceRef } from "./types";
const MarkdownSource = lazy(() =>
  import("../../sources/MarkdownSource").then((module) => ({
    default: module.MarkdownSource,
  })),
);

export function SsdSourceDialog({
  documents,
  refs,
  onClose,
}: {
  documents: SourceDocument[];
  refs: SourceRef[];
  onClose: () => void;
}) {
  const ordered = [...refs].sort((a, b) => {
    const score = (r: SourceRef) =>
      ["RR", "SR"].includes(
        documents.find((d) => d.id === r.document_id)?.role || "",
      )
        ? 0
        : 1;
    return score(a) - score(b);
  });
  const [selected, setSelected] = useState(0);
  const [docId, setDocId] = useState(
    ordered[0]?.document_id ||
      documents.find((d) => d.role === "RR")?.id ||
      documents.find((d) => d.role === "SR")?.id ||
      documents[0]?.id ||
      "",
  );
  const [source, setSource] = useState(false);
  const [jump, setJump] = useState({
    line: ordered[0]?.start_line || 1,
    revision: 0,
  });
  const [outline, setOutline] = useState<any[]>([]);
  const ref = ordered[selected];
  const doc = documents.find((d) => d.id === docId);
  const activeRef = ref?.document_id === docId ? ref : undefined;
  const start = activeRef?.start_line || 1;
  const end = activeRef?.end_line || start;
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [onClose]);
  return (
    <div className="ssd-modal-backdrop">
      <section
        className="ssd-modal ssd-source-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="原始需求与设计文档"
      >
        <header>
          <h3>原始需求与设计文档</h3>
          <button onClick={onClose} autoFocus>
            关闭原文
          </button>
        </header>
        <div className="ssd-toolbar">
          <label>
            来源位置
            <select
              aria-label="来源位置"
              value={selected}
              onChange={(e) => {
                const n = Number(e.target.value);
                setSelected(n);
                setDocId(ordered[n].document_id);
                setJump((old) => ({
                  line: ordered[n].start_line,
                  revision: old.revision + 1,
                }));
              }}
            >
              {ordered.map((r, n) => (
                <option key={n} value={n}>
                  {documents.find((d) => d.id === r.document_id)?.name ||
                    r.document_id}{" "}
                  · 第 {r.start_line}–{r.end_line} 行
                  {r.kind === "context" ? "（关联上下文）" : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            文档
            <select
              aria-label="原文文档"
              value={docId}
              onChange={(e) => {
                setDocId(e.target.value);
                setJump((old) => ({ line: 1, revision: old.revision + 1 }));
              }}
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.role} · {d.name}
                </option>
              ))}
            </select>
          </label>
          <button onClick={() => setSource(!source)}>
            {source ? "阅读模式" : "查看源码"}
          </button>
          <button
            onClick={() =>
              setJump((old) => ({ line: start, revision: old.revision + 1 }))
            }
          >
            返回引用
          </button>
          <select
            aria-label="原文章节"
            value=""
            onChange={(e) =>
              setJump((old) => ({
                line: Number(e.target.value),
                revision: old.revision + 1,
              }))
            }
          >
            <option value="">跳转到章节</option>
            {outline.map((h) => (
              <option key={h.line} value={h.line}>
                {h.title}
              </option>
            ))}
          </select>
        </div>
        {activeRef && (
          <p className="ssd-source-location">
            {doc?.name} · 第 {start}–{end} 行 {activeRef.json_pointer}
            {activeRef.kind === "context" &&
              " · 此处为需求上下文，测试出处见测试来源"}
          </p>
        )}
        {!ordered.length && (
          <p className="ssd-source-location">
            当前记录没有行级引用，可通过文档与章节查看原始需求；此处不将文档首页视作该记录的出处。
          </p>
        )}
        {!doc ? (
          <p role="alert">
            尚未导入此引用对应的原始文档，请补充文档后查看。引用：{ref?.quote}
          </p>
        ) : source || !/\.md$|\.markdown$/i.test(doc.name) ? (
          <div className="ssd-source-code">
            {doc.content.split("\n").map((line, i) => (
              <div
                key={i}
                className={
                  activeRef && i + 1 >= start && i + 1 <= end
                    ? "source-line highlighted"
                    : "source-line"
                }
              >
                <span>{i + 1}</span>
                <code>{line}</code>
              </div>
            ))}
          </div>
        ) : (
          <Suspense fallback={<p>正在渲染原始文档…</p>}>
            <MarkdownSource
              lines={doc.content
                .split("\n")
                .map((text, i) => ({ number: i + 1, text }))}
              highlightStart={activeRef ? start : 0}
              highlightEnd={activeRef ? end : 0}
              jump={jump}
              outlineOpen={false}
              onOutline={setOutline}
              onNavigate={(line) =>
                setJump((old) => ({ line, revision: old.revision + 1 }))
              }
            />
          </Suspense>
        )}
      </section>
    </div>
  );
}
