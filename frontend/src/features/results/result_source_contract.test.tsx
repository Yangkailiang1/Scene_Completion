import type { ReactNode } from "react";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ResultsView } from "./ResultsView";

const probe = vi.hoisted(() => ({ getSsdResultIndex: vi.fn() }));
const projectProbe = vi.hoisted(() => ({
  getProjectResultIndex: vi.fn(),
  getProjectEditor: vi.fn(),
  saveProjectRevision: vi.fn(),
  exportProjectReview: vi.fn(),
  previewProjectReview: vi.fn(),
  applyProjectReview: vi.fn(),
}));
vi.mock("./ssd/api", () => probe);
vi.mock("./project/api", () => projectProbe);
vi.mock("./ssd/SsdResultsView", () => ({
  SsdResultsView: (props: {
    project: string;
    initialIndex: { cases: { id: string }[] };
    requestedCaseId?: string;
    requestedStepId?: string;
    resultSourceControl?: ReactNode;
    onDirtyChange?: (dirty: boolean) => void;
  }) => (
    <section aria-label="SSD result route">
      {props.resultSourceControl}
      <p data-testid="ssd-route-selection">
        {props.project}:
        {props.requestedCaseId || props.initialIndex.cases[0].id}:
        {props.requestedStepId || "first-step"}
      </p>
      <button onClick={() => props.onDirtyChange?.(true)}>
        Make SSD draft dirty
      </button>
      <button onClick={() => props.onDirtyChange?.(false)}>
        Finish SSD draft
      </button>
    </section>
  ),
}));

const imported = {
  id: "a".repeat(64),
  case: { id: "IMPORTED", name: "独立导入用例" },
  scope: "SR",
  imported_at: "2026-11-13T00:00:00Z",
};
const savedCase = { id: "HISTORY", name: "历史工作流用例" };
const ssdIndex = (id = "CURRENT") => ({
  version: "ssd-case-v1",
  cases: [{ id, name: "当前SSD用例", revision: 1 }],
});
let requests: string[];

beforeEach(() => {
  requests = [];
  localStorage.clear();
  probe.getSsdResultIndex.mockReset().mockResolvedValue(ssdIndex());
  projectProbe.getProjectResultIndex.mockReset().mockResolvedValue({
    version: "project-scopes-v1",
    scopes: [],
    metrics: { by_scope: {}, overall: {}, complete: false },
  });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    requests.push(url);
    const selected = url.includes(`import_id=${imported.id}`);
    const detailCase = selected ? imported.case : savedCase;
    const data = url.split("?")[0].endsWith("/results")
      ? {
          cases: [detailCase],
          artifacts: [],
          historical: true,
          case_result_imports: [imported],
          supplement_tests: false,
        }
      : {
          case: detailCase,
          interactions: [],
          definitions: {},
          unbound: {},
        };
    return { ok: true, json: async () => data } as Response;
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("initial and new-project probes show loading without mounting historical results, with an explicit retry on failure", async () => {
  let failInitial!: (reason: Error) => void;
  let finishNext!: (value: ReturnType<typeof ssdIndex>) => void;
  probe.getSsdResultIndex.mockImplementation((project: string) =>
    project === "legacy"
      ? new Promise((_, reject) => {
          failInitial = reject;
        })
      : new Promise((resolve) => {
          finishNext = resolve;
        }),
  );
  const view = render(<ResultsView project="legacy" />);
  expect(screen.getByRole("status").textContent).toBe("正在加载结果来源…");
  expect(screen.queryByLabelText("结果来源")).toBeNull();
  expect(requests).toEqual([]);

  await act(async () => failInitial(new Error("SSD index unavailable")));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "结果加载失败",
  );
  expect(screen.queryByLabelText("结果来源")).toBeNull();
  expect(requests).toEqual([]);

  view.rerender(<ResultsView project="next" />);
  expect(screen.getByRole("status").textContent).toBe("正在加载结果来源…");
  expect(screen.queryByLabelText("结果来源")).toBeNull();
  expect(requests.some((url) => url.includes("/projects/next/"))).toBe(false);
  await act(async () => finishNext(ssdIndex("NEXT-CASE")));
  expect(screen.getByTestId("ssd-route-selection").textContent).toBe(
    "next:NEXT-CASE:first-step",
  );
});

test("SSD results keep historical and independent import routes selectable across live refreshes", async () => {
  const view = render(<ResultsView project="both" liveVersion="1" />);
  await screen.findByRole("region", { name: "SSD result route" });
  fireEvent.change(screen.getByLabelText("结果视图来源"), {
    target: { value: "saved" },
  });
  const source = await screen.findByLabelText("结果来源");
  await screen.findByRole("option", { name: "HISTORY · 历史工作流用例" });
  fireEvent.change(source, { target: { value: imported.id } });
  await screen.findByRole("option", { name: "IMPORTED · 独立导入用例" });
  await waitFor(() => {
    expect(
      requests.some(
        (url) =>
          url.includes("/results/IMPORTED?") && url.includes(imported.id),
      ),
    ).toBe(true);
  });

  let finishRefresh!: (value: ReturnType<typeof ssdIndex>) => void;
  probe.getSsdResultIndex.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishRefresh = resolve;
      }),
  );
  await act(async () => {
    view.rerender(<ResultsView project="both" liveVersion="2" />);
  });
  await waitFor(() => expect(probe.getSsdResultIndex).toHaveBeenCalledTimes(2));
  expect(
    (screen.getByLabelText("结果视图来源") as HTMLSelectElement).value,
  ).toBe("saved");
  expect((screen.getByLabelText("结果来源") as HTMLSelectElement).value).toBe(
    imported.id,
  );
  expect(screen.queryByRole("region", { name: "SSD result route" })).toBeNull();

  await act(async () => finishRefresh(ssdIndex()));
  expect((screen.getByLabelText("结果来源") as HTMLSelectElement).value).toBe(
    imported.id,
  );

  fireEvent.change(screen.getByLabelText("结果来源"), {
    target: { value: "" },
  });
  await screen.findByRole("option", { name: "HISTORY · 历史工作流用例" });
  await waitFor(() => {
    expect(
      requests.some(
        (url) =>
          url.includes("/results/HISTORY?") && !url.includes("import_id="),
      ),
    ).toBe(true);
  });
  fireEvent.change(screen.getByLabelText("结果视图来源"), {
    target: { value: "ssd" },
  });
  expect(screen.getByTestId("ssd-route-selection").textContent).toBe(
    "both:CURRENT:first-step",
  );
});

test("review re-entry routes to the requested SSD case and step after viewing an import", async () => {
  const first = render(<ResultsView project="review" />);
  await screen.findByRole("region", { name: "SSD result route" });
  fireEvent.change(screen.getByLabelText("结果视图来源"), {
    target: { value: "saved" },
  });
  fireEvent.change(await screen.findByLabelText("结果来源"), {
    target: { value: imported.id },
  });
  await screen.findByRole("option", { name: "IMPORTED · 独立导入用例" });
  first.unmount();

  render(
    <ResultsView
      project="review"
      liveVersion="after-feedback"
      requestedCaseId="UC-004"
      requestedStepId="A_S4"
    />,
  );
  await screen.findByRole("region", { name: "SSD result route" });
  expect(screen.getByTestId("ssd-route-selection").textContent).toBe(
    "review:UC-004:A_S4",
  );
  expect(
    (screen.getByLabelText("结果视图来源") as HTMLSelectElement).value,
  ).toBe("ssd");
});

test("a late previous-project SSD probe never replaces the newly selected project", async () => {
  let finishOld!: (value: ReturnType<typeof ssdIndex>) => void;
  probe.getSsdResultIndex.mockImplementation((project: string) =>
    project === "old"
      ? new Promise((resolve) => {
          finishOld = resolve;
        })
      : Promise.resolve(ssdIndex("NEW-CASE")),
  );
  const view = render(<ResultsView project="old" />);
  view.rerender(<ResultsView project="new" />);
  await screen.findByRole("region", { name: "SSD result route" });
  expect(screen.getByTestId("ssd-route-selection").textContent).toBe(
    "new:NEW-CASE:first-step",
  );
  await act(async () => finishOld(ssdIndex("OLD-CASE")));
  expect(screen.getByTestId("ssd-route-selection").textContent).toBe(
    "new:NEW-CASE:first-step",
  );
});

test("source navigation preserves an unsaved SSD draft until explicitly saved or discarded", async () => {
  render(<ResultsView project="draft" />);
  await screen.findByRole("region", { name: "SSD result route" });
  fireEvent.click(screen.getByRole("button", { name: "Make SSD draft dirty" }));
  fireEvent.change(screen.getByLabelText("结果视图来源"), {
    target: { value: "saved" },
  });
  expect(screen.getByRole("status").textContent).toContain(
    "请先保存或放弃修改",
  );
  expect(screen.getByRole("region", { name: "SSD result route" })).toBeTruthy();
  expect(
    (screen.getByLabelText("结果视图来源") as HTMLSelectElement).value,
  ).toBe("ssd");
  fireEvent.click(screen.getByRole("button", { name: "Finish SSD draft" }));
  fireEvent.change(screen.getByLabelText("结果视图来源"), {
    target: { value: "saved" },
  });
  await screen.findByLabelText("结果来源");
  expect(screen.queryByRole("region", { name: "SSD result route" })).toBeNull();
});
