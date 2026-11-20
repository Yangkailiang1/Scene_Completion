import { AlignLeft, BookOpen, Code2, CornerUpLeft, X } from "lucide-react";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { api, fileUrl, projectUrl } from "../../shared/api";
import type { SourceHeading, SourceJump } from "./MarkdownSource";
import { afterSourceLayout, scrollSourceAnchor } from "./sourceScroll";
import { SpreadsheetSource, workbookSheet } from "./SpreadsheetSource";
const MarkdownSource = lazy(() =>
  import("./MarkdownSource").then((module) => ({
    default: module.MarkdownSource,
  })),
);
export type TracedOrigin = {
  document: string;
  start_line: number;
  end_line: number;
  quote?: string;
  match: "exact" | "located";
  sheet?: string;
  cell_range?: string;
};

// Only verified lines are offered: a shipped original is opened by its own
// document name, not by guessing which file the citation "probably" meant.
export function resolvedOrigin(evidence: any): TracedOrigin | null {
  const value = evidence?.origin;
  if (
    !value ||
    !["exact", "located"].includes(value.match) ||
    !value.document ||
    !Number.isInteger(value.start_line)
  )
    return null;
  return {
    document: value.document,
    start_line: value.start_line,
    end_line: value.end_line || value.start_line,
    quote: value.quote,
    match: value.match,
    ...(value.cell_range
      ? { sheet: value.sheet, cell_range: value.cell_range }
      : {}),
  };
}
function originSource(traced: TracedOrigin) {
  return "origin:" + traced.document;
}
function matchLabel(match: string) {
  return match === "exact" ? "声明行逐字核对" : "按引文定位";
}
export function SourceEvidence({
  project,
  evidence,
  onClose,
}: {
  project: string;
  evidence: any;
  onClose: () => void;
}) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [start, setStart] = useState(evidence.line_start);
  // ``null`` = the intermediate file this citation was recorded in; otherwise
  // the original requirement/design document behind it.
  const [origin, setOrigin] = useState<null | {
    source_id: string;
    line_start: number;
    line_end: number;
    quote: string;
  }>(null);
  const [mode, setMode] = useState<"reading" | "source">("reading"),
    [outlineOpen, setOutlineOpen] = useState(false),
    [outline, setOutline] = useState<SourceHeading[]>([]);
  const [jump, setJump] = useState<SourceJump>({
    line: evidence.line_start,
    revision: 0,
  });
  const rawReader = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setOrigin(null);
    setStart(evidence.line_start);
    setOutline([]);
    setOutlineOpen(false);
    setJump((old) => ({
      line: evidence.line_start,
      revision: old.revision + 1,
    }));
  }, [project, evidence]);
  // A resolved origin opens its own document; an unresolved one keeps the
  // intermediate file so the reviewer still sees what the citation came from.
  const current = origin || {
    source_id: evidence.source_id,
    line_start: evidence.line_start,
    line_end: evidence.line_end,
    quote: evidence.quote,
  };
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    const line = mode === "reading" ? current.line_start : start;
    const query = new URLSearchParams({
      start: String(line),
      end: String(line === current.line_start ? current.line_end : line),
      context: "60",
      quote: line === current.line_start ? current.quote || "" : "",
      view: mode === "reading" ? "document" : "window",
    });
    api(
      projectUrl(
        project,
        `sources/${encodeURIComponent(current.source_id)}?${query}`,
      ),
    )
      .then((v) => live && setData(v))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [project, evidence, start, mode, origin]);
  const navigate = useCallback((line: number) => {
    setJump((old) => ({ line, revision: old.revision + 1 }));
    setOutlineOpen(false);
  }, []);
  const traced = resolvedOrigin(evidence);
  const originPending =
    !traced && evidence?.origin?.match === "pending"
      ? evidence.origin.reason || "原文未提供"
      : "";
  const markdown =
    data?.document_format === "markdown" ||
    /\.(md|markdown)$/i.test(data?.name || "");
  const sheet = workbookSheet(data?.name);
  useLayoutEffect(() => {
    if (!data || (mode === "reading" && (markdown || sheet))) return;
    return afterSourceLayout(() => {
      const reader = rawReader.current;
      if (!reader) return;
      const line = mode === "source" ? start : jump.line;
      scrollSourceAnchor(
        reader,
        reader.querySelector<HTMLElement>(`[data-source-line="${line}"]`),
      );
    });
  }, [data, mode, markdown, sheet, start, jump]);
  function switchView(next: "reading" | "source", line = current.line_start) {
    setMode(next);
    setStart(line);
    navigate(line);
  }
  return (
    <section className="source-evidence-pane" aria-label="原文文档查看框">
      <header>
        <div>
          <strong>{data?.name || "原文文档"}</strong>
          <small>
            引用第{current.line_start}–{current.line_end}行 · 共
            {data?.line_count || "—"}行
            {traced &&
              (origin
                ? ` · 来自中间产物第${evidence.line_start}–${evidence.line_end}行`
                : ` · 原始出处：${traced.document}第${traced.start_line}–${traced.end_line}行（${matchLabel(traced.match)}）`)}
          </small>
          {data?.line_count != null &&
            (current.line_start < 1 ||
              current.line_end < current.line_start ||
              current.line_end > data.line_count) && (
              <small role="note">引用行超出文档范围</small>
            )}
          {traced?.cell_range && (
            <small>
              {traced.sheet}!{traced.cell_range}
            </small>
          )}
          {originPending && (
            <small role="note">原文未定位：{originPending}</small>
          )}
          {data?.original_path && (
            <small>
              <a
                href={fileUrl(project, data.original_path)}
                target="_blank"
                rel="noreferrer"
              >
                查看原始文件（点击打开）
              </a>
              {data.json_locations?.find(
                (r: any) => r.line === evidence.line_start,
              )?.json_pointer && (
                <code>
                  {" "}
                  {
                    data.json_locations.find(
                      (r: any) => r.line === evidence.line_start,
                    ).json_pointer
                  }
                </code>
              )}
            </small>
          )}
        </div>
        <button onClick={onClose} aria-label="关闭原文">
          <X size={16} />
        </button>
      </header>
      <div className="source-evidence-toolbar">
        <div
          className="source-view-switch"
          role="group"
          aria-label="原文查看方式"
        >
          <button
            aria-pressed={mode === "reading"}
            onClick={() => switchView("reading")}
          >
            <BookOpen size={14} />
            {sheet ? "表格" : "阅读"}
          </button>
          <button
            aria-pressed={mode === "source"}
            onClick={() => switchView("source")}
          >
            <Code2 size={14} />
            源码
          </button>
        </div>
        {traced && (
          <button
            aria-pressed={!!origin}
            title={
              origin
                ? "回到中间产物中的记录行"
                : `打开原文第${traced.start_line}–${traced.end_line}行`
            }
            onClick={() => {
              switchView(
                "reading",
                origin ? evidence.line_start : traced.start_line,
              );
              if (origin) {
                setOrigin(null);
                return;
              }
              setOrigin({
                source_id: originSource(traced),
                line_start: traced.start_line,
                line_end: traced.end_line,
                quote: traced.quote || "",
              });
            }}
          >
            <BookOpen size={14} />
            {origin
              ? "返回中间产物"
              : `${traced.document} 第${traced.start_line}行`}
          </button>
        )}
        <button
          onClick={() => {
            setStart(current.line_start);
            navigate(current.line_start);
          }}
        >
          <CornerUpLeft size={14} />
          返回引用
        </button>
        {mode === "reading" && markdown && (
          <button
            disabled={!outline.length}
            aria-expanded={outlineOpen}
            onClick={() => setOutlineOpen(!outlineOpen)}
          >
            <AlignLeft size={14} />
            大纲 {outline.length}
          </button>
        )}
      </div>
      {mode === "reading" && markdown && (
        <div className="source-outline-jump">
          <select
            aria-label="文档大纲跳转"
            value=""
            disabled={!outline.length}
            onChange={(e) => navigate(Number(e.target.value))}
          >
            <option value="">
              {outline.length ? "跳转到章节…" : "文档没有标题"}
            </option>
            {outline.map((h) => (
              <option key={h.anchor} value={h.line}>
                {"　".repeat(Math.min(h.depth - 1, 4))}
                {h.title}
              </option>
            ))}
          </select>
          <small>黄色标记引用内容</small>
        </div>
      )}
      {error ? (
        <div className="source-view-message" role="alert">
          <p>{error}</p>
          {mode === "reading" && (
            <button onClick={() => switchView("source")}>
              切换源码按行查看
            </button>
          )}
        </div>
      ) : !data ? (
        <p className="source-view-message">正在定位原文…</p>
      ) : mode === "reading" && sheet ? (
        <SpreadsheetSource
          key={data.name}
          sheet={sheet}
          lines={data.lines}
          start={current.line_start}
          end={current.line_end}
          address={
            traced?.document === data.name && traced?.sheet === sheet
              ? traced.cell_range
              : undefined
          }
          jump={jump}
        />
      ) : mode === "reading" && markdown ? (
        <Suspense
          fallback={<p className="source-view-message">正在渲染Markdown…</p>}
        >
          <MarkdownSource
            lines={data.lines}
            highlightStart={current.line_start}
            highlightEnd={current.line_end}
            mark={{
              start: current.line_start,
              end: current.line_end,
              quote: current.quote,
            }}
            jump={jump}
            outlineOpen={outlineOpen}
            onOutline={setOutline}
            onNavigate={navigate}
            onRawLine={(line) => switchView("source", line)}
          />
        </Suspense>
      ) : (
        <div className="source-raw-reader">
          {mode === "source" && (
            <div className="source-evidence-toolbar">
              <button
                disabled={start <= 1}
                onClick={() => setStart(Math.max(1, start - 100))}
              >
                向前查看
              </button>
              <button
                disabled={start + 100 > data.line_count}
                onClick={() => setStart(start + 100)}
              >
                向后查看
              </button>
              <span>按原始行号显示</span>
            </div>
          )}
          <div className="source-document-lines" ref={rawReader}>
            {data.lines.map((r: any) => (
              <div
                key={r.number}
                data-source-line={r.number}
                className={
                  r.number >= current.line_start && r.number <= current.line_end
                    ? "source-line highlighted"
                    : "source-line"
                }
              >
                <span>{r.number}</span>
                <pre>{r.text || " "}</pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
