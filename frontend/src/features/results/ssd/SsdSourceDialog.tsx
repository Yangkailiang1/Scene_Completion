import {
  lazy,
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  afterSourceLayout,
  scrollSourceAnchor,
} from "../../sources/sourceScroll";
import {
  SpreadsheetSource,
  workbookSheet,
} from "../../sources/SpreadsheetSource";
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
  const expanded = refs.flatMap((ref) => {
    const origin = typeof ref.origin === "object" ? ref.origin : undefined;
    const document =
      origin && ["exact", "located"].includes(origin.match)
        ? documents.find((doc) => doc.name === origin.document)
        : undefined;
    if (
      !document ||
      !origin?.start_line ||
      refs.some(
        (r) =>
          r.document_id === document.id && r.start_line === origin.start_line,
      )
    ) {
      return [ref];
    }
    return [
      {
        ...ref,
        document_id: document.id,
        start_line: origin.start_line,
        end_line: origin.end_line || origin.start_line,
        quote: origin.quote || "",
        kind: "origin",
        json_pointer: undefined,
      },
      ref,
    ];
  });
  const ordered = expanded
    .map((r, index) => ({ r, index }))
    .sort((a, b) => {
      const score = (ref: SourceRef) => {
        const doc = documents.find((d) => d.id === ref.document_id);
        if (typeof ref.origin === "object" && ref.origin.document === doc?.name)
          return 0;
        return ["RR", "SR"].includes(doc?.role || "") ? 1 : 2;
      };
      return score(a.r) - score(b.r) || a.index - b.index;
    })
    .map(({ r }) => r);
  const manual = ordered.filter((r) => r.origin === "manual");
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
  const origin =
    typeof activeRef?.origin === "object" ? activeRef.origin : undefined;
  const start = activeRef?.start_line ?? 1;
  const end = activeRef?.end_line || start;
  const lines = useMemo(() => doc?.content.split("\n") || [], [doc]);
  const sheet = workbookSheet(doc?.name);
  const sheetLines = useMemo(
    () =>
      sheet ? lines.map((text, index) => ({ number: index + 1, text })) : [],
    [lines, sheet],
  );
  const markdown = /\.(md|markdown)$/i.test(doc?.name || "");
  const codeView = !sheet && (source || !markdown);
  const rawReader = useRef<HTMLDivElement>(null);
  const invalidLine =
    !!doc && !!activeRef && (start < 1 || end < start || end > lines.length);
  useLayoutEffect(() => {
    if (!codeView) return;
    return afterSourceLayout(() => {
      const reader = rawReader.current;
      if (reader)
        scrollSourceAnchor(
          reader,
          reader.querySelector<HTMLElement>(
            `[data-source-line="${jump.line}"]`,
          ),
        );
    });
  }, [codeView, doc, jump]);
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
                if (!ordered[n]) return;
                setSelected(n);
                setDocId(ordered[n].document_id);
                setJump((old) => ({
                  line: ordered[n].start_line,
                  revision: old.revision + 1,
                }));
              }}
            >
              {selected < 0 && (
                <option value={-1} disabled>
                  当前文档无引用
                </option>
              )}
              {ordered.map((r, n) => (
                <option key={n} value={n}>
                  {documents.find((d) => d.id === r.document_id)?.name ||
                    r.document_id}{" "}
                  · 第 {r.start_line}–{r.end_line} 行
                  {r.kind === "context" ? "（关联上下文）" : ""}
                  {r.origin === "manual" ? "（人工补录）" : ""}
                </option>
              ))}
            </select>
          </label>
          {manual.length > 0 && (
            <button
              className="ssd-manual-source"
              onClick={() => {
                const n = ordered.indexOf(manual[0]);
                setSelected(n);
                setDocId(ordered[n].document_id);
                setJump((old) => ({
                  line: ordered[n].start_line,
                  revision: old.revision + 1,
                }));
              }}
            >
              跳到人工补录出处（{manual.length}）
            </button>
          )}
          <label>
            文档
            <select
              aria-label="原文文档"
              value={docId}
              onChange={(e) => {
                const id = e.target.value;
                const next = ordered.findIndex(
                  (item) => item.document_id === id,
                );
                setDocId(id);
                setSelected(next);
                setJump((old) => ({
                  line: ordered[next]?.start_line || 1,
                  revision: old.revision + 1,
                }));
              }}
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.role} · {d.name}
                </option>
              ))}
            </select>
          </label>
          {markdown && (
            <button
              onClick={() => {
                setSource(!source);
                setJump((old) => ({ line: start, revision: old.revision + 1 }));
              }}
            >
              {source ? "阅读模式" : "查看源码"}
            </button>
          )}
          <button
            onClick={() =>
              setJump((old) => ({ line: start, revision: old.revision + 1 }))
            }
          >
            返回引用
          </button>
          <select
            aria-label="原文章节"
            disabled={!markdown || source || !outline.length}
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
            {origin?.cell_range &&
              " · " + origin.sheet + "!" + origin.cell_range}
            {origin?.match === "pending" &&
              " · 原文未定位：" + (origin.reason || "待核对")}
            {activeRef.kind === "context" &&
              " · 此处为需求上下文，测试出处见测试来源"}
            {invalidLine && " · 引用行超出文档范围"}
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
        ) : sheet ? (
          <SpreadsheetSource
            key={docId}
            sheet={sheet}
            lines={sheetLines}
            start={invalidLine || !activeRef ? 0 : start}
            end={invalidLine || !activeRef ? 0 : end}
            address={
              origin?.document === doc.name && origin.sheet === sheet
                ? origin.cell_range
                : undefined
            }
            jump={jump}
          />
        ) : codeView ? (
          <div className="ssd-source-code" ref={rawReader}>
            {lines.map((line, i) => (
              <div
                key={i}
                data-source-line={i + 1}
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
              lines={lines.map((text, i) => ({ number: i + 1, text }))}
              highlightStart={activeRef ? start : 0}
              highlightEnd={activeRef ? end : 0}
              jump={jump}
              outlineOpen={false}
              onOutline={setOutline}
              onNavigate={(line) =>
                setJump((old) => ({ line, revision: old.revision + 1 }))
              }
              onRawLine={(line) => {
                setSource(true);
                setJump((old) => ({ line, revision: old.revision + 1 }));
              }}
            />
          </Suspense>
        )}
      </section>
    </div>
  );
}
