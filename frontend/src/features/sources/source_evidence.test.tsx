import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SourceEvidence } from "./SourceEvidence";
const text = `# 浏览商品

**调用方**：顾客

## 参数约束

| 字段 | 约束 |
| --- | --- |
| pageSize | 1–100 |

> 必填字段必须提供。

- 可选参数可以省略
- [ ] 业务确认

\`\`\`json
# 不是标题
{"pageSize":20}
\`\`\`

## 返回结果

1. 返回列表<br/>保留分页信息
2. 返回总数

[跳转到参数](#参数约束)

![外部图片](https://example.com/tracker.png)
<script>alert('unsafe')</script>
[不安全链接](javascript:alert%281%29)

## 返回结果

[重复标题](#返回结果-1)`;
const lines = text.split("\n").map((text, n) => ({ number: n + 1, text }));
const evidence = {
  source_id: "sr",
  line_start: 9,
  line_end: 9,
  quote: "| pageSize | 1–100 |",
};
function mockSource() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(
    async (url) =>
      ({
        ok: true,
        json: async () => ({
          name: "SR.md",
          document_format: "markdown",
          line_count: lines.length,
          lines: String(url).includes("view=window")
            ? lines.slice(5, 15)
            : lines,
        }),
      }) as Response,
  );
}
afterEach(() => vi.restoreAllMocks());
test("Markdown reader renders tables, emphasis, lists and code with citation highlight and safe links", async () => {
  const fetch = mockSource();
  render(<SourceEvidence project="p" evidence={evidence} onClose={vi.fn()} />);
  await screen.findByRole("heading", { name: "浏览商品" });
  expect(
    document.querySelector(".source-markdown-body strong")?.textContent,
  ).toBe("调用方");
  expect(screen.getByRole("table")).toBeTruthy();
  expect(
    document.querySelector("tr.source-block-highlighted")?.textContent,
  ).toContain("pageSize");
  expect(document.querySelector("pre code")?.textContent).toContain(
    "# 不是标题",
  );
  expect(screen.getByText("返回列表", { exact: false }).innerHTML).toContain(
    "<br>",
  );
  expect(document.querySelector(".source-markdown-body script")).toBeNull();
  expect(document.querySelector(".source-markdown-body img")).toBeNull();
  expect(
    screen.getByRole("link", { name: "点击查看图片" }).getAttribute("href"),
  ).toBe("https://example.com/tracker.png");
  expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
  expect(String(fetch.mock.calls[0][0])).toContain("view=document");
});
test("outline uses parsed headings, jumps locally including Chinese anchors and duplicate headings", async () => {
  const fetch = mockSource();
  render(<SourceEvidence project="p" evidence={evidence} onClose={vi.fn()} />);
  await waitFor(() =>
    expect(
      screen.getByLabelText("文档大纲跳转").querySelectorAll("option"),
    ).toHaveLength(5),
  );
  expect(screen.queryByRole("option", { name: /不是标题/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /大纲 4/ }));
  const outline = screen.getByRole("navigation", { name: "文档章节大纲" });
  fireEvent.click(within(outline).getByRole("button", { name: "参数约束" }));
  expect(screen.queryByRole("navigation", { name: "文档章节大纲" })).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "跳转到参数" }));
  fireEvent.click(screen.getByRole("link", { name: "重复标题" }));
  fireEvent.change(screen.getByLabelText("文档大纲跳转"), {
    target: { value: "21" },
  });
  fireEvent.click(screen.getByRole("button", { name: "返回引用" }));
  expect(fetch).toHaveBeenCalledTimes(1);
});
test("raw view preserves original line numbers and paged source retrieval", async () => {
  const fetch = mockSource();
  render(<SourceEvidence project="p" evidence={evidence} onClose={vi.fn()} />);
  await screen.findByRole("heading", { name: "浏览商品" });
  fireEvent.click(screen.getByRole("button", { name: "源码" }));
  await waitFor(() =>
    expect(
      document.querySelector(".source-line.highlighted pre")?.textContent,
    ).toBe(evidence.quote),
  );
  expect(String(fetch.mock.calls.at(-1)?.[0])).toContain("view=window");
  expect(screen.queryByLabelText("文档大纲跳转")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "阅读" }));
  await screen.findByRole("heading", { name: "浏览商品" });
});
test("failed full-document retrieval offers raw mode without discarding the viewer", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).includes("view=document")
      ? ({ ok: false, text: async () => "文档超过2MB" } as Response)
      : ({
          ok: true,
          json: async () => ({
            name: "SR.md",
            lines,
            line_count: lines.length,
          }),
        } as Response),
  );
  render(<SourceEvidence project="p" evidence={evidence} onClose={vi.fn()} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "切换源码按行查看" }),
  );
  await waitFor(() =>
    expect(document.querySelector(".source-line.highlighted")).toBeTruthy(),
  );
});

test("a citation with a verified original line opens that document on demand", async () => {
  const fetch = mockSource();
  const traced = {
    ...evidence,
    origin: {
      document: "功能设计_spec.md",
      match: "located",
      start_line: 4,
      end_line: 4,
      quote: "**调用方**：顾客",
      declared_line: "L2",
    },
  };
  render(<SourceEvidence project="p" evidence={traced} onClose={vi.fn()} />);
  await screen.findByRole("heading", { name: "浏览商品" });
  const button = screen.getByRole("button", {
    name: "功能设计_spec.md 第4行",
  });
  fireEvent.click(button);
  await waitFor(() =>
    expect(decodeURIComponent(String(fetch.mock.calls.at(-1)?.[0]))).toContain(
      "/sources/origin:功能设计_spec.md",
    ),
  );
  await waitFor(() =>
    expect(document.querySelector("header")?.textContent).toContain(
      "来自中间产物第9–9行",
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "返回中间产物" }));
  await waitFor(() =>
    expect(document.querySelector("header")?.textContent).toContain(
      "按引文定位",
    ),
  );
  await waitFor(() =>
    expect(decodeURIComponent(String(fetch.mock.calls.at(-1)?.[0]))).toContain(
      "/sources/sr?",
    ),
  );
});

test("an untraced citation keeps the intermediate file and states why", async () => {
  const fetch = mockSource();
  render(
    <SourceEvidence
      project="p"
      evidence={{
        ...evidence,
        origin: {
          document: "功能设计_spec.md",
          match: "pending",
          reason: "原文未包含该引文",
        },
      }}
      onClose={vi.fn()}
    />,
  );
  await screen.findByRole("heading", { name: "浏览商品" });
  expect(screen.getByRole("note").textContent).toContain("原文未包含该引文");
  expect(screen.queryByRole("button", { name: /第4行/ })).toBeNull();
  expect(String(fetch.mock.calls.at(-1)?.[0])).toContain("/sources/sr?");
});

test("opening and returning to a late citation scrolls only the document reader", async () => {
  const citation = { ...evidence, line_start: 6222, line_end: 6222 };
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({
      name: "SysOperation.json",
      document_format: "json",
      line_count: 6500,
      lines: [
        { number: 6162, text: "上下文" },
        { number: 6222, text: citation.quote },
      ],
    }),
  } as Response);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
    function (this: HTMLElement) {
      if (this.dataset.sourceLine === "6222") {
        return { top: 1340 - (this.parentElement?.scrollTop || 0) } as DOMRect;
      }
      return { top: 100 } as DOMRect;
    },
  );
  const { container } = render(
    <SourceEvidence project="p" evidence={citation} onClose={vi.fn()} />,
  );
  container.scrollTop = 80;
  const reader = await waitFor(() => {
    const element = container.querySelector<HTMLElement>(
      ".source-document-lines",
    );
    expect(element?.scrollTop).toBe(1216);
    return element!;
  });
  expect(
    reader.querySelector(".highlighted")?.getAttribute("data-source-line"),
  ).toBe("6222");
  reader.scrollTop = 50;
  fireEvent.click(screen.getByRole("button", { name: "返回引用" }));
  await waitFor(() => expect(reader.scrollTop).toBe(1216));
  expect(container.scrollTop).toBe(80);
});
