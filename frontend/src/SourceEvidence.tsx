import { useEffect, useRef, useState } from "react";
import { api, projectUrl } from "./api";
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
  const mark = useRef<HTMLDivElement>(null);
  useEffect(() => setStart(evidence.line_start), [evidence]);
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    const query = new URLSearchParams({
      start: String(start),
      end: String(start === evidence.line_start ? evidence.line_end : start),
      context: "60",
      quote: start === evidence.line_start ? evidence.quote : "",
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
  }, [project, evidence, start]);
  useEffect(() => {
    mark.current?.scrollIntoView?.({ block: "center" });
  }, [data]);
  return (
    <section className="source-evidence-pane" aria-label="原文文档查看框">
      <header>
        <div>
          <strong>{data?.name || "原文文档"}</strong>
          <small>
            {data?.section || evidence.source_id} · 引用第{evidence.line_start}–
            {evidence.line_end}行
          </small>
        </div>
        <button onClick={onClose} aria-label="关闭原文">
          关闭
        </button>
      </header>
      <div className="source-evidence-toolbar">
        <button
          disabled={start <= 1}
          onClick={() => setStart(Math.max(1, start - 100))}
        >
          向前查看
        </button>
        <button onClick={() => setStart(evidence.line_start)}>返回引用</button>
        <button
          disabled={!data || start + 100 > data.line_count}
          onClick={() => setStart(start + 100)}
        >
          向后查看
        </button>
        <span>{data?.line_count || "—"}行</span>
      </div>
      <div className="source-document-lines">
        {error ? (
          <p role="alert">{error}</p>
        ) : !data ? (
          <p>正在定位原文…</p>
        ) : (
          data.lines.map((r: any) => (
            <div
              key={r.number}
              ref={r.number === evidence.line_start ? mark : undefined}
              className={
                r.number >= evidence.line_start && r.number <= evidence.line_end
                  ? "source-line highlighted"
                  : "source-line"
              }
            >
              <span>{r.number}</span>
              <pre>{r.text || " "}</pre>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
