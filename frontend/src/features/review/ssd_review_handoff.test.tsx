import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ReviewHandoff } from "./ReviewHandoff";
import { invalidateResults } from "../results/shared/resultRequests";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  invalidateResults();
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
test("a current handoff starts with one summary request", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      format: "business-adoption-v3",
      excluded: {
        by_scope: {
          interaction: {
            ...counts,
            items: [
              {
                id: "interaction:C1",
                name: "原用例",
                revision: 1,
                counts: {
                  E: { scenarios: 0 },
                  G: { scenarios: 1 },
                  GT: { scenarios: 0 },
                },
              },
            ],
          },
          shared_services: { ...counts, available: false, exported: 0 },
        },
      },
    }),
  );
  render(<ReviewHandoff project="current" />);
  await screen.findByRole("heading", {
    name: "导出异常场景完整性补全识别报告",
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(String(fetcher.mock.calls[0][0])).toMatch(/\/ssd-review\/summary$/);
});
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
              shared_services: { ...counts, exported: 0 },
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
  await screen.findByRole("heading", {
    name: "导出异常场景完整性补全识别报告",
  });
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
  expect(screen.queryByLabelText("导入 SSD 审核文件")).toBeNull();
  expect(screen.getByRole("button", { name: "导出报告 HTML" })).toBeTruthy();
});

test("default exports interactions and shared services regardless of current selection; object loading is lazy", async () => {
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
    name: "导出报告 HTML",
  });
  await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
  expect(
    (screen.getByLabelText("SSD 报告范围") as HTMLSelectElement).value,
  ).toBe("all");
  expect(fetcher.mock.calls.some(([u]) => String(u).includes("/editor"))).toBe(
    false,
  );
  fireEvent.click(button);
  await screen.findByText(/报告已导出/);
  expect(requests[0]).toEqual({
    url: "/api/projects/p/ssd-review/report",
    body: {},
  });
  fireEvent.click(screen.getByText("导出范围（可选）"));
  fireEvent.change(screen.getByLabelText("SSD 报告范围"), {
    target: { value: "case" },
  });
  await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
  fireEvent.click(button);
  await waitFor(() => expect(requests).toHaveLength(2));
  expect(requests[1].body).toEqual({
    scopes: ["interaction"],
    case_ids: ["UC-2"],
  });
});

test("case options retain natural order and source names", async () => {
  setup();
  render(<ReviewHandoff project="p" />);
  await screen.findByRole("heading", {
    name: "导出异常场景完整性补全识别报告",
  });
  fireEvent.click(screen.getByText("导出范围（可选）"));
  fireEvent.change(screen.getByLabelText("SSD 报告范围"), {
    target: { value: "case" },
  });
  expect(
    Array.from(
      (screen.getByLabelText("SSD 报告用例") as HTMLSelectElement).options,
    ).map((o) => o.text),
  ).toEqual(["UC-1 · 第一例", "UC-2 · 第二例", "UC-10 · 第十例"]);
});

test("a failed report download leaves the export button available for retry", async () => {
  let failures = 1;
  setup(() =>
    failures-- > 0
      ? ({
          ok: false,
          json: async () => ({ detail: "报告暂不可用" }),
        } as Response)
      : ({ ok: true, blob: async () => new Blob(["report"]) } as Response),
  );
  downloads();
  render(<ReviewHandoff project="p" />);
  const button = await screen.findByRole("button", { name: "导出报告 HTML" });
  fireEvent.click(button);
  await screen.findByText("报告暂不可用");
  expect(button.hasAttribute("disabled")).toBe(false);
  fireEvent.click(button);
  await screen.findByText(/报告已导出/);
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
  await screen.findByRole("heading", {
    name: "导出异常场景完整性补全识别报告",
  });
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
  await screen.findByRole("heading", {
    name: "导出异常场景完整性补全识别报告",
  });
  await act(async () =>
    resolve(json({ version: "ssd-case-v1", cases: [{ id: "old-case" }] })),
  );
  expect(screen.queryByText("old-case")).toBeNull();
});
