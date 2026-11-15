import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ReviewHandoff } from "./ReviewHandoff";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
const json = (value: unknown) =>
  ({ ok: true, json: async () => value }) as Response;
const counts = {
  exported: 1,
  covered: 3,
  unfinished: 0,
  inactive: 0,
  source_pending: 5,
  available: true,
  items: [],
};
function setup(post: (url: string, body: any) => Response = () => json({})) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/ssd-review/summary"))
        return json({
          excluded: {
            by_scope: {
              interaction: counts,
              business_chain: counts,
              architecture: { ...counts, exported: 0 },
            },
          },
        });
      if (init?.method === "POST")
        return post(url, JSON.parse(String(init.body)));
      if (url.endsWith("/ssd-results"))
        return json({
          version: "ssd-case-v1",
          cases: [
            { id: "UC-10", name: "第十例" },
            { id: "UC-2", name: "第二例" },
            { id: "UC-1", name: "第一例" },
          ],
        });
      if (url.endsWith("/project-results"))
        return json({
          version: "project-scopes-v1",
          scopes: [{ id: "business_chain", revision: 3 }],
        });
      if (url.includes("/editor"))
        return json({
          bundle: {
            steps: [{ id: "S1", order: 1, operation: { name: "请求" } }],
            anchors: [],
          },
        });
      return json({ snapshots: [] });
    });
}
function file() {
  const f = new File(["review-data"], "review.html");
  Object.defineProperty(f, "text", { value: async () => "review-data" });
  return f;
}
function downloads() {
  vi.stubGlobal(
    "URL",
    Object.assign(class extends URL {}, {
      createObjectURL: vi.fn(() => "blob:review"),
      revokeObjectURL: vi.fn(),
    }),
  );
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
}

test("format detection never flashes legacy controls; legacy is still explicitly selectable", async () => {
  setup();
  render(<ReviewHandoff project="p" />);
  expect(screen.queryByText("导出Windows业务审核包")).toBeNull();
  await screen.findByRole("heading", { name: "导出三层审核 HTML" });
  expect(screen.queryByText("④ 研发定向重跑")).toBeNull();
  fireEvent.change(screen.getByLabelText("审核交接格式"), {
    target: { value: "windows" },
  });
  expect(
    screen.getByRole("button", { name: "导出Windows业务审核包" }),
  ).toBeTruthy();
  fireEvent.change(screen.getByLabelText("审核交接格式"), {
    target: { value: "ssd" },
  });
  expect(screen.getByLabelText("导入 SSD 审核文件")).toBeTruthy();
});

test("default exports all three scopes regardless of current selection; object loading is lazy", async () => {
  const requests: any[] = [];
  const fetcher = setup((url, body) => {
    requests.push({ url, body });
    return { ok: true, blob: async () => new Blob(["review"]) } as Response;
  });
  downloads();
  render(
    <ReviewHandoff
      project="p"
      selection={{
        scope: "business_chain",
        anchorId: "edge",
        caseId: "UC-2",
        stepId: "S1",
      }}
    />,
  );
  const button = await screen.findByRole("button", {
    name: "导出三层审核 HTML",
  });
  await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
  expect(
    (screen.getByLabelText("SSD 审核范围") as HTMLSelectElement).value,
  ).toBe("all");
  expect(fetcher.mock.calls.some(([u]) => String(u).includes("/editor"))).toBe(
    false,
  );
  fireEvent.click(button);
  await screen.findByText(/已导出保存版本/);
  expect(requests[0].body).toEqual({});
  fireEvent.click(screen.getByText("高级筛选（可选）"));
  fireEvent.change(screen.getByLabelText("SSD 审核范围"), {
    target: { value: "step" },
  });
  await screen.findByRole("option", { name: "请求" });
  fireEvent.change(screen.getByLabelText("SSD 审核步骤"), {
    target: { value: "S1" },
  });
  await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
  fireEvent.click(button);
  await waitFor(() => expect(requests).toHaveLength(2));
  expect(requests[1].body).toEqual({
    scopes: ["interaction"],
    case_ids: ["UC-2"],
    anchor_ids: ["S1"],
  });
});

test("case options retain natural order and source names", async () => {
  setup();
  render(<ReviewHandoff project="p" />);
  await screen.findByRole("heading", { name: "导出三层审核 HTML" });
  fireEvent.click(screen.getByText("高级筛选（可选）"));
  fireEvent.change(screen.getByLabelText("SSD 审核范围"), {
    target: { value: "case" },
  });
  expect(
    Array.from(
      (screen.getByLabelText("SSD 审核用例") as HTMLSelectElement).options,
    ).map((o) => o.text),
  ).toEqual(["UC-1 · 第一例", "UC-2 · 第二例", "UC-10 · 第十例"]);
});

test("one HTML previews and applies precise cross-scope items with ready items selected by default", async () => {
  const writes: any[] = [];
  const onApplied = vi.fn();
  setup((url, body) => {
    writes.push({ url, body });
    return json({
      cases: [
        {
          item_id: "interaction:business_chain",
          case_id: "business_chain",
          scope: "interaction",
          name: "查询",
          status: url.endsWith("/preview") ? "ready" : "applied",
        },
        {
          item_id: "business_chain:business_chain",
          case_id: "business_chain",
          scope: "business_chain",
          name: "链路",
          status: url.endsWith("/preview") ? "ready" : "applied",
        },
        {
          item_id: "architecture:architecture",
          case_id: "architecture",
          scope: "architecture",
          name: "外部服务",
          status: "conflict",
          conflicts: ["基线版本已变化"],
        },
      ],
    });
  });
  render(<ReviewHandoff project="p" onApplied={onApplied} />);
  fireEvent.change(await screen.findByLabelText("导入 SSD 审核文件"), {
    target: { files: [file()] },
  });
  await screen.findByText("基线版本已变化");
  expect(writes).toHaveLength(1);
  expect((screen.getByLabelText("应用 查询") as HTMLInputElement).checked).toBe(
    true,
  );
  expect((screen.getByLabelText("应用 链路") as HTMLInputElement).checked).toBe(
    true,
  );
  expect(
    (screen.getByLabelText("应用 外部服务") as HTMLInputElement).disabled,
  ).toBe(true);
  fireEvent.click(
    screen.getByRole("button", { name: "应用选定三层修改并返回结果" }),
  );
  await waitFor(() => expect(onApplied).toHaveBeenCalled());
  expect(writes[1].body).toEqual({
    content: "review-data",
    item_ids: ["interaction:business_chain", "business_chain:business_chain"],
  });
  expect(onApplied.mock.calls[0][0].scopes).toEqual([
    "interaction",
    "business_chain",
  ]);
});

test("apply-time conflict stays on the preview and does not claim successful application", async () => {
  const onApplied = vi.fn();
  setup((url) =>
    json({
      cases: [
        {
          case_id: "UC-1",
          name: "查询",
          status: url.endsWith("/preview") ? "ready" : "conflict",
          conflicts: url.endsWith("/preview") ? [] : ["保存前版本已变化"],
        },
      ],
    }),
  );
  render(<ReviewHandoff project="p" onApplied={onApplied} />);
  fireEvent.change(await screen.findByLabelText("导入 SSD 审核文件"), {
    target: { files: [file()] },
  });
  await screen.findByLabelText("应用 查询");
  fireEvent.click(
    screen.getByRole("button", { name: "应用选定三层修改并返回结果" }),
  );
  await screen.findByText("保存前版本已变化");
  expect(onApplied).not.toHaveBeenCalled();
});

test("network failure never falls back to legacy and retry recovers", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockRejectedValue(new Error("offline"));
  render(<ReviewHandoff project="p" />);
  await screen.findByRole("alert");
  expect(screen.queryByText("导出Windows业务审核包")).toBeNull();
  fetcher.mockImplementation(async (input) =>
    String(input).endsWith("/ssd-results")
      ? json({ version: "ssd-case-v1", cases: [{ id: "C1" }] })
      : String(input).endsWith("/ssd-review/summary")
        ? json({ excluded: { by_scope: {} } })
        : json({ scopes: [] }),
  );
  fireEvent.click(screen.getByRole("button", { name: "重试" }));
  await screen.findByRole("heading", { name: "导出三层审核 HTML" });
});

test("late responses for another project cannot replace the selected project", async () => {
  let resolve: (r: Response) => void = () => {};
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
    String(input).includes("/old/")
      ? new Promise<Response>((r) => {
          resolve = r;
        })
      : String(input).endsWith("/ssd-results")
        ? json({ version: "ssd-case-v1", cases: [{ id: "new-case" }] })
        : String(input).endsWith("/ssd-review/summary")
          ? json({})
          : json({ scopes: [] }),
  );
  const view = render(<ReviewHandoff project="old" />);
  view.rerender(<ReviewHandoff project="new" />);
  await screen.findByRole("heading", { name: "导出三层审核 HTML" });
  await act(async () =>
    resolve(json({ version: "ssd-case-v1", cases: [{ id: "old-case" }] })),
  );
  expect(screen.queryByText("old-case")).toBeNull();
});
