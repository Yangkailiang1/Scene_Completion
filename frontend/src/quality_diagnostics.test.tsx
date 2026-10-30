import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { test, expect, vi, afterEach } from "vitest";
import { QualityDiagnostics } from "./QualityDiagnostics";
afterEach(() => vi.restoreAllMocks());
const report = {
  id: "d",
  created_at: 1,
  status: "partial",
  test_set: "original",
  snapshot_hash: "s",
  versions: { execution: "round" },
  coverage: { enumerated: 1, evidence_reviewed: 0, unresolved: 1 },
  cards: [
    {
      id: "C:current:generation_validity",
      case_id: "C",
      scope: "current",
      metric: "generation_validity",
      unit: "关注点绑定",
      label: "生成有效率",
      direction: "↑",
      value: 50,
      numerator: 1,
      denominator: 2,
      status: "适用",
      loss_count: 1,
      formula: "|G∩GT|/|G|",
      causes: { unverified: 1 },
    },
  ],
  integrity: [],
  losses: [
    {
      id: "loss",
      case_id: "C",
      metric: "generation_validity",
      scope: "current",
      anchor: {
        interaction_id: "m1",
        object: "pageSize",
        concern_key: "api.data.range",
      },
      cells: { E: [], G: [{ id: "g", cause: "超过上界" }], GT: [] },
      certainty: "待查明",
      primary_cause: "unverified",
      reason: "GT未验证，不能直接判错",
      evidence: [],
    },
  ],
  proposals: [
    {
      id: "p",
      kind: "recommendation",
      target: "ranking",
      applicable: true,
      status: "待人工确认",
      patch: { top_k: 12 },
      reason: "正向关键风险依据",
      loss_ids: ["loss"],
      risk: "排序变化",
      validation: "冻结样本重放",
    },
  ],
  excluded: {},
};
function mock(readonly = false) {
  const writes: any[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (u, init) => {
    let value: any = report;
    const url = String(u);
    if (init?.method === "POST") {
      writes.push({ url, body: JSON.parse(String(init.body)) });
      value = url.endsWith("/impact")
        ? { ranking_only: true, affected: ["C:gap-recommend"], case_ids: ["C"] }
        : { ...report, applied: {} };
    } else if (url.endsWith("quality-diagnostics"))
      value = { items: [report], review_only: readonly };
    return { ok: true, json: async () => value } as Response;
  });
  return writes;
}
test("saved loss reasons and direction stay inline; impact preview precedes explicit apply", async () => {
  const writes = mock();
  render(<QualityDiagnostics project="p" caseId="C" testSet="original" />);
  await screen.findByText("50.00%");
  expect(screen.getByText("GT未验证，不能直接判错")).toBeTruthy();
  expect(screen.getByText("1 / 2 · 清单 1")).toBeTruthy();
  fireEvent.click(
    screen.getByRole("checkbox", { name: /recommendation · ranking/ }),
  );
  fireEvent.change(screen.getByLabelText("确认人"), {
    target: { value: "业务负责人" },
  });
  fireEvent.click(screen.getByText("预览影响范围"));
  await screen.findByText(/仅推荐与下游计分/);
  expect(writes).toHaveLength(1);
  expect(writes[0].body.snapshot_hash).toBe("s");
  expect(writes[0].body.approvals).toEqual(["p"]);
  fireEvent.click(screen.getByText("确认应用并重跑"));
  await waitFor(() => expect(writes).toHaveLength(2));
  expect(writes[1].body.rerun).toBe(true);
});
test("business package can only read saved quality report", async () => {
  mock(true);
  render(<QualityDiagnostics project="p" caseId="C" testSet="original" />);
  await screen.findByText("50.00%");
  expect(screen.queryByText("开始诊断")).toBeNull();
  expect(screen.queryByText("预览影响范围")).toBeNull();
  expect(
    (
      screen.getByRole("checkbox", {
        name: /recommendation · ranking/,
      }) as HTMLInputElement
    ).disabled,
  ).toBe(true);
});
