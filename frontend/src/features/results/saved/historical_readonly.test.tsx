import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SavedResultsView } from "./SavedResultsView";

afterEach(() => vi.restoreAllMocks());

test("historical tabs retain viewing and downloads while all shared write controls stay read-only", async () => {
  const writes: string[] = [];
  const scenario = {
    interaction_id: "s1",
    conditions: ["页面大小超过100"],
    source_refs: [],
    concern_origins: ["api.data.range"],
    pattern_id: "range",
    confidence: { basis: "字段约束" },
  };
  const quality = {
    id: "diagnostic",
    created_at: 1,
    status: "partial",
    test_set: "original",
    snapshot_hash: "saved-snapshot",
    versions: { execution: "historical-run" },
    coverage: { enumerated: 1, evidence_reviewed: 1, unresolved: 0 },
    cards: [],
    losses: [],
    integrity: [],
    excluded: {},
    proposals: [
      {
        id: "proposal",
        kind: "recommendation",
        target: "ranking",
        applicable: true,
        status: "待人工确认",
        reason: "保存的优化建议",
        loss_ids: [],
      },
    ],
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = new URL(String(input), "http://localhost").pathname;
    if (init?.method && init.method !== "GET")
      writes.push(`${init.method} ${path}`);
    let value: any;
    if (path.endsWith("/results"))
      value = {
        cases: [{ id: "C", name: "历史用例" }],
        artifacts: [],
        historical: true,
        supplement_tests: false,
      };
    else if (path.endsWith("/results/global"))
      value = {
        status: "历史已保存",
        metrics: {},
        concerns: [],
        scenarios: [],
        recommendations: [],
      };
    else if (path.endsWith("/analysis-scopes"))
      value = {
        records: [
          {
            task_key: "C:existing-scope",
            expected_version: "saved-version",
            value: {
              units: [
                {
                  source_id: "E1",
                  trigger: "重复更新",
                  scope: "interaction",
                  global_kind: null,
                  entity_ids: [],
                  related_cases: ["C"],
                  reason: "保存的归属依据",
                },
              ],
            },
          },
        ],
        entities: [],
        cases: [{ id: "C", name: "历史用例" }],
      };
    else if (path.endsWith("/test-sources"))
      value = {
        version: "tests-v1",
        versions: [{ id: "tests-v1" }, { id: "tests-v2" }],
        preview: {
          counts: { exception: 1, normal: 0, optional: 0, pending: 0 },
          records: [
            { id: "T1", source_id: "test-doc", row: 1, 测试名称: "已保存测试" },
          ],
        },
      };
    else if (path.endsWith("/recommendation-history"))
      value = { revision: 1, items: [] };
    else if (path.endsWith("/recommendations"))
      value = {
        cases: [{ id: "C", name: "历史用例" }],
        current_settings_hash: "saved-settings",
        human_adoption: { value: null, numerator: 0, denominator: 0 },
        result: {
          enabled: true,
          settings_hash: "saved-settings",
          formula: "C × R",
          top_k: 1,
          Q: [scenario],
          ranked: [
            {
              scenario_id: "g1",
              scenario,
              rank: 1,
              priority: 1,
              pattern_id: "range",
              selected: true,
              confidence: { score: 1, basis: "字段约束" },
              risk: { score: 1, level: "normal", reason: "保存的风险依据" },
              history_score: 0,
              history_sources: [],
              reason: "保存的推荐依据",
            },
          ],
          critical_review: [
            { candidate_id: "candidate", scenario, reason: "保存的待审候选" },
          ],
        },
      };
    else if (path.endsWith("/quality-diagnostics"))
      value = { items: [quality], review_only: false };
    else if (path.endsWith("/quality-diagnostics/diagnostic")) value = quality;
    else
      value = {
        case: { id: "C" },
        interactions: [],
        definitions: {},
        unbound: {},
      };
    return { ok: true, json: async () => value } as Response;
  });

  render(<SavedResultsView project="historical" />);
  await screen.findByRole("option", { name: "C · 历史用例" });
  fireEvent.click(screen.getByRole("tab", { name: "全局业务分析" }));
  const summary =
    await screen.findByText("查看异常的交互／全局归属（历史只读）");
  const details = summary.closest("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  await screen.findByRole("option", { name: "C:existing-scope" });
  fireEvent.change(screen.getByLabelText("来源及用例"), {
    target: { value: "C:existing-scope" },
  });
  expect(screen.getByLabelText("分析粒度").matches(":disabled")).toBe(true);
  expect((screen.getByLabelText("审核依据") as HTMLTextAreaElement).value).toBe(
    "保存的归属依据",
  );
  expect(screen.queryByRole("button", { name: "保存归属判定" })).toBeNull();

  fireEvent.click(screen.getByRole("tab", { name: "用例结果" }));
  fireEvent.change(screen.getByLabelText("当前范围视图"), {
    target: { value: "tests" },
  });
  await screen.findByText("已保存测试");
  expect(
    (screen.getByLabelText("上传测试文件") as HTMLInputElement).disabled,
  ).toBe(true);
  expect(
    (screen.getByLabelText("测试集版本") as HTMLSelectElement).disabled,
  ).toBe(true);
  expect(
    screen.getByRole("link", { name: "下载商城14用例Excel示例" }),
  ).toBeTruthy();
  fireEvent.change(screen.getByLabelText("测试集版本"), {
    target: { value: "tests-v2" },
  });

  fireEvent.change(screen.getByLabelText("当前范围视图"), {
    target: { value: "recommendations" },
  });
  await screen.findByText("保存的待审候选");
  expect((screen.getByLabelText("反馈 g1") as HTMLSelectElement).disabled).toBe(
    true,
  );
  expect(
    (screen.getByRole("button", { name: "确认适用" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  fireEvent.change(screen.getByLabelText("反馈 g1"), {
    target: { value: "adopt" },
  });

  fireEvent.change(screen.getByLabelText("当前范围视图"), {
    target: { value: "quality" },
  });
  await screen.findByText("保存的优化建议");
  expect(screen.queryByRole("button", { name: "开始诊断" })).toBeNull();
  expect(screen.queryByRole("button", { name: /继续未完成诊断/ })).toBeNull();
  expect(screen.queryByRole("button", { name: "确认应用并重跑" })).toBeNull();
  expect(
    (
      screen.getByRole("checkbox", {
        name: /recommendation · ranking/,
      }) as HTMLInputElement
    ).disabled,
  ).toBe(true);
  expect(screen.getByRole("link", { name: "MD" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "JSON" })).toBeTruthy();
  await waitFor(() => expect(writes).toEqual([]));
});
