import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, it, expect, afterEach } from "vitest";
import { PatternManager, RecommendationsView } from "./PatternManager";
import { api } from "./api";
vi.mock("./api", () => ({
  api: vi.fn(),
  projectUrl: (p: string, s: string) => `/api/projects/${p}/${s}`,
}));
afterEach(() => vi.resetAllMocks());
const settings = {
  threshold: 0.85,
  top_k: 10,
  risk_weight: 0.7,
  history_weight: 0.3,
  overrides: {},
  library: {
    version: "v1",
    patterns: [
      {
        id: "data.minimum",
        label: "下界违反",
        concern_keys: ["api.data.range"],
        preconditions: ["明确下界"],
        trigger_template: "低于下界",
        required_evidence: "接口约束",
        risk_level: "normal",
        risk_reason: "默认",
        enabled: true,
        version: 1,
      },
    ],
  },
};
it("edits threshold/K and saves an optimistic project version", async () => {
  const mock = vi.mocked(api);
  mock.mockImplementation(async (path: any, init: any) =>
    path.includes("recommendation-history")
      ? { revision: 0, items: [] }
      : init
        ? {
            version: "new",
            history: [],
            settings: JSON.parse(init.body).settings,
          }
        : { version: "old", history: [], settings },
  );
  render(<PatternManager project="p" />);
  await screen.findByLabelText("证据阈值");
  fireEvent.change(screen.getByLabelText("每用例K"), {
    target: { value: "5" },
  });
  fireEvent.click(screen.getByRole("button", { name: /下界违反/ }));
  expect(screen.getByDisplayValue("低于下界")).toBeTruthy();
  fireEvent.click(screen.getByText("保存版本"));
  await waitFor(() =>
    expect(mock).toHaveBeenCalledWith(
      "/api/projects/p/patterns",
      expect.objectContaining({
        method: "PUT",
        body: expect.stringContaining('"expected_version":"old"'),
      }),
    ),
  );
  const call = mock.mock.calls.find((c) => c[1]?.method === "PUT");
  expect(JSON.parse(call![1]!.body as string).settings.top_k).toBe(5);
});
it("old run does not claim recommendation is completed", async () => {
  vi.mocked(api).mockImplementation(async (path: any) =>
    path.includes("recommendation-history")
      ? { revision: 0, items: [] }
      : { cases: [], result: {}, human_adoption: { value: null } },
  );
  render(<RecommendationsView project="p" />);
  await screen.findByText(/旧版本报告仍为/);
  expect(screen.queryByText("已推荐")).toBeNull();
});

it("recommendations follow the final-results case without a second selector", async () => {
  const mock = vi.mocked(api);
  mock.mockImplementation(async (path: any) =>
    path.includes("recommendation-history")
      ? { revision: 0, items: [] }
      : {
          cases: [
            { id: "c1", name: "one" },
            { id: "c2", name: "two" },
          ],
          result: {},
          human_adoption: { value: null },
        },
  );
  const { rerender } = render(<RecommendationsView project="p" caseId="c1" />);
  await waitFor(() =>
    expect(mock).toHaveBeenCalledWith(
      "/api/projects/p/recommendations?case=c1",
    ),
  );
  expect(screen.queryByLabelText("推荐用例")).toBeNull();
  rerender(<RecommendationsView project="p" caseId="c2" />);
  await waitFor(() =>
    expect(mock).toHaveBeenCalledWith(
      "/api/projects/p/recommendations?case=c2",
    ),
  );
});

it("keeps policy controls compact and filters the pattern library by risk", async () => {
  vi.mocked(api).mockImplementation(async (path: any) =>
    path.includes("recommendation-history")
      ? { revision: 0, items: [] }
      : { version: "one", history: [], settings },
  );
  render(<PatternManager project="layout" />);
  await screen.findByText("模式库");
  const policy = screen.getByText("推荐策略").closest("details");
  expect(policy?.open).toBe(false);
  fireEvent.change(screen.getByLabelText("模式风险筛选"), {
    target: { value: "critical" },
  });
  expect(screen.queryByRole("button", { name: /下界违反/ })).toBeNull();
  fireEvent.change(screen.getByLabelText("模式风险筛选"), {
    target: { value: "" },
  });
  expect(screen.getByRole("button", { name: /下界违反/ })).toBeTruthy();
});
