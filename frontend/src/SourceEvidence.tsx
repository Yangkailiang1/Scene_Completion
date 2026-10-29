import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { AlignLeft, BookOpen, Code2, CornerUpLeft, X } from "lucide-react";
import { api, projectUrl } from "./api";
import type { SourceHeading, SourceJump } from "./MarkdownSource";
const MarkdownSource = lazy(() =>
  import("./MarkdownSource").then((module) => ({
    default: module.MarkdownSource,
  })),
);
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
  const [mode, setMode] = useState<"reading" | "source">("reading"),
    [outlineOpen, setOutlineOpen] = useState(false),
    [outline, setOutline] = useState<SourceHeading[]>([]);
  const [jump, setJump] = useState<SourceJump>({
    line: evidence.line_start,
    revision: 0,
  });
  const mark = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setStart(evidence.line_start);
    setOutline([]);
    setOutlineOpen(false);
    setJump((old) => ({
      line: evidence.line_start,
      revision: old.revision + 1,
    }));
  }, [project, evidence]);
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    const line = mode === "reading" ? evidence.line_start : start;
    const query = new URLSearchParams({
      start: String(line),
      end: String(line === evidence.line_start ? evidence.line_end : line),
      context: "60",
      quote: line === evidence.line_start ? evidence.quote || "" : "",
      view: mode === "reading" ? "document" : "window",
    });
    api(
      projectUrl(
        project,
        `sources/${encodeURIComponent(evidence.source_id)}?${query}`,
      ),
    )
      .then((v) => live && setData(v))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [project, evidence, start, mode]);
  useEffect(() => {
    if (
      mode === "source" ||
      (data &&
        data.document_format !== "markdown" &&
        !/\.(md|markdown)$/i.test(data.name || ""))
    )
      mark.current?.scrollIntoView?.({ block: "center" });
  }, [data, mode]);
  const navigate = useCallback((line: number) => {
    setJump((old) => ({ line, revision: old.revision + 1 }));
    setOutlineOpen(false);
  }, []);
  const markdown =
    data?.document_format === "markdown" ||
    /\.(md|markdown)$/i.test(data?.name || "");
  return (
    <section className="source-evidence-pane" aria-label="原文文档查看框">
      <header>
        <div>
          <strong>{data?.name || "原文文档"}</strong>
          <small>
            引用第{evidence.line_start}–{evidence.line_end}行 · 共
            {data?.line_count || "—"}行
          </small>
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
            onClick={() => setMode("reading")}
          >
            <BookOpen size={14} />
            阅读
          </button>
          <button
            aria-pressed={mode === "source"}
            onClick={() => setMode("source")}
          >
            <Code2 size={14} />
            源码
          </button>
        </div>
        <button
          onClick={() => {
            setStart(evidence.line_start);
            navigate(evidence.line_start);
            mark.current?.scrollIntoView?.({ block: "center" });
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
            <button onClick={() => setMode("source")}>切换源码按行查看</button>
          )}
        </div>
      ) : !data ? (
        <p className="source-view-message">正在定位原文…</p>
      ) : mode === "reading" && markdown ? (
        <Suspense
          fallback={<p className="source-view-message">正在渲染Markdown…</p>}
        >
          <MarkdownSource
            lines={data.lines}
            highlightStart={evidence.line_start}
            highlightEnd={evidence.line_end}
            jump={jump}
            outlineOpen={outlineOpen}
            onOutline={setOutline}
            onNavigate={navigate}
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
          <div className="source-document-lines">
            {data.lines.map((r: any) => (
              <div
                key={r.number}
                ref={r.number === evidence.line_start ? mark : undefined}
                className={
                  r.number >= evidence.line_start &&
                  r.number <= evidence.line_end
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
