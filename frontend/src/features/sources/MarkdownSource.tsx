import { createElement, useEffect, useMemo, useRef, useState } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

export type SourceHeading = {
  line: number;
  depth: number;
  title: string;
  anchor: string;
};
export type SourceJump = { line: number; revision: number };
// Citations keep their recorded line; the original line is resolved by text so
// a document that shifted still opens the passage it actually contains.
export type SourceMark = { start: number; end: number; quote?: string };
// Preserve Markdown hard breaks without enabling arbitrary HTML from uploaded files.
function lineBreaks() {
  return (tree: any) => {
    function visit(node: any) {
      if (!Array.isArray(node.children)) return;
      node.children = node.children.map((child: any) => {
        if (
          child.type === "html" &&
          /^<br\s*\/?\s*>$/i.test(child.value.trim())
        )
          return { ...child, type: "break" };
        visit(child);
        return child;
      });
    }
    visit(tree);
  };
}
function slug(title: string) {
  return title
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .replace(/\s+/g, "-");
}
function normalize(text: string) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .join("\n")
    .trim();
}
export function resolveSourceLine(
  lines: { number: number; text: string }[],
  mark?: SourceMark | null,
): { start: number; end: number } | null {
  if (!mark) return null;
  const wanted = normalize(mark.quote || "");
  if (wanted && lines.length) {
    const span = wanted.split("\n");
    const row = (n: number) => lines.find((x) => x.number === n);
    const first = row(mark.start);
    const matches = (first?.text || "").includes(span[0].trim());
    if (first && !matches) {
      const hits = lines.filter((list) => {
        if (!list.text.includes(span[0].trim())) return false;
        for (let k = 1; k < span.length; k += 1) {
          if (!(row(list.number + k)?.text || "").includes(span[k].trim()))
            return false;
        }
        return true;
      });
      if (hits.length === 1)
        return {
          start: hits[0].number,
          end: Math.min(
            hits[0].number + span.length - 1,
            lines.at(-1)?.number || hits[0].number,
          ),
        };
      return null;
    }
  }
  return { start: mark.start, end: mark.end };
}
export function MarkdownSource({
  lines,
  highlightStart,
  highlightEnd,
  jump,
  outlineOpen,
  onOutline,
  onNavigate,
  mark,
}: {
  lines: { number: number; text: string }[];
  highlightStart: number;
  highlightEnd: number;
  jump: SourceJump;
  outlineOpen: boolean;
  onOutline: (headings: SourceHeading[]) => void;
  onNavigate: (line: number) => void;
  mark?: SourceMark | null;
}) {
  const content = useRef<HTMLDivElement>(null);
  const located = mark ? resolveSourceLine(lines, mark) : null;
  const active = located
    ? { start: located.start, end: located.end }
    : { start: highlightStart, end: highlightEnd };
  const [headings, setHeadings] = useState<SourceHeading[]>([]);
  const base = lines[0]?.number || 1;
  const text = useMemo(() => {
    const rows = new Map(lines.map((row) => [row.number, row.text]));
    const last = lines.at(-1)?.number || base;
    return Array.from(
      { length: last - base + 1 },
      (_, i) => rows.get(base + i) || "",
    ).join("\n");
  }, [lines, base]);
  const components = useMemo<Components>(() => {
    const coordinates = (node: any) => ({
      "data-source-start": (node?.position?.start?.line || 1) + base - 1,
      "data-source-end": (node?.position?.end?.line || 1) + base - 1,
    });
    const block =
      (tag: string, highlight = true): any =>
      ({ node, children, className, ...props }: any) => {
        const position = coordinates(node);
        const selected =
          highlight &&
          position["data-source-start"] <= active.end &&
          position["data-source-end"] >= active.start;
        return createElement(
          tag,
          {
            ...props,
            ...position,
            ...(tag.match(/^h[1-6]$/)
              ? { id: `source-heading-${position["data-source-start"]}` }
              : {}),
            className: [className, selected ? "source-block-highlighted" : ""]
              .filter(Boolean)
              .join(" "),
          },
          children,
        );
      };
    return {
      h1: block("h1"),
      h2: block("h2"),
      h3: block("h3"),
      h4: block("h4"),
      h5: block("h5"),
      h6: block("h6"),
      p: block("p"),
      li: block("li"),
      pre: block("pre"),
      tr: block("tr"),
      blockquote: block("blockquote", false),
      table: ({ node, children, ...props }) => (
        <div className="source-md-table">
          <table {...props} {...coordinates(node)}>
            {children}
          </table>
        </div>
      ),
      a: ({ node: _node, href, children, ...props }) => {
        if (!href) return <span>{children}</span>;
        return (
          <a
            {...props}
            href={href}
            target={href.startsWith("#") ? undefined : "_blank"}
            rel="noopener noreferrer"
            onClick={(event) => {
              if (!href.startsWith("#")) return;
              event.preventDefault();
              let fragment: string;
              try {
                fragment = decodeURIComponent(href.slice(1));
              } catch {
                return;
              }
              const counts = new Map<string, number>();
              const target = Array.from(
                content.current?.querySelectorAll("h1,h2,h3,h4,h5,h6") || [],
              ).find((heading) => {
                const key = slug(heading.textContent || "");
                const count = counts.get(key) || 0;
                counts.set(key, count + 1);
                return (
                  fragment === heading.id ||
                  fragment === `${key}${count ? `-${count}` : ""}`
                );
              });
              if (target)
                onNavigate(Number(target.getAttribute("data-source-start")));
            }}
          >
            {children}
          </a>
        );
      },
      // Offline review must not fetch remote tracking images automatically.
      img: ({ src, alt }) => (
        <span className="source-md-image">
          图片：{alt || "未命名"}
          {src && (
            <a href={src} target="_blank" rel="noopener noreferrer">
              点击查看图片
            </a>
          )}
        </span>
      ),
    };
  }, [base, active.start, active.end, onNavigate]);
  useEffect(() => {
    const result = Array.from(
      content.current?.querySelectorAll("h1,h2,h3,h4,h5,h6") || [],
    ).map((heading) => ({
      line: Number(heading.getAttribute("data-source-start")),
      depth: Number(heading.tagName.slice(1)),
      title: heading.textContent || "未命名章节",
      anchor: heading.id,
    }));
    setHeadings(result);
    onOutline(result);
  }, [text, onOutline]);
  useEffect(() => {
    const root = content.current;
    if (!root) return;
    const blocks = Array.from(
      root.querySelectorAll<HTMLElement>("[data-source-start]"),
    );
    const candidates = blocks.filter(
      (el) =>
        Number(el.dataset.sourceStart) <= jump.line &&
        Number(el.dataset.sourceEnd) >= jump.line,
    );
    candidates.sort(
      (a, b) =>
        Number(a.dataset.sourceEnd) -
        Number(a.dataset.sourceStart) -
        (Number(b.dataset.sourceEnd) - Number(b.dataset.sourceStart)),
    );
    const target =
      candidates[0] ||
      blocks.find((el) => Number(el.dataset.sourceStart) >= jump.line) ||
      blocks.at(-1);
    if (target)
      root.scrollTop +=
        target.getBoundingClientRect().top -
        root.getBoundingClientRect().top -
        36;
  }, [jump, text]);
  return (
    <div className="source-markdown-reader">
      {outlineOpen && (
        <nav className="source-outline" aria-label="文档章节大纲">
          <strong>章节大纲</strong>
          {headings.length ? (
            headings.map((h) => (
              <button
                key={h.anchor}
                style={{
                  paddingLeft: `${12 + Math.min(h.depth - 1, 4) * 12}px`,
                }}
                onClick={() => onNavigate(h.line)}
                title={`第${h.line}行`}
              >
                {h.title}
              </button>
            ))
          ) : (
            <p>文档没有标题</p>
          )}
        </nav>
      )}
      <div
        ref={content}
        className="source-markdown-body"
        aria-label="Markdown阅读内容"
      >
        <Markdown
          remarkPlugins={[remarkGfm, lineBreaks]}
          components={components}
          skipHtml
        >
          {text}
        </Markdown>
      </div>
    </div>
  );
}
