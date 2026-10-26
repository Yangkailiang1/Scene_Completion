import { render, screen, fireEvent } from "@testing-library/react";
import { test, expect, vi, afterEach } from "vitest";
import {
  ConcernAlignmentTable,
  AlignmentTable,
  MetricsPanel,
} from "./ResultComparison";
afterEach(() => vi.restoreAllMocks());

test("a recognized concern remains visible without scenes and drills by binding identity", () => {
  const select = vi.fn();
  const m = {
    binding_id: "c1",
    target: "data",
    object: "pageSize",
    data_location: "query",
    concern_key: "range",
    basis: "明确1至100",
  };
  render(
    <ConcernAlignmentTable
      rows={[
        {
          id: "c1",
          anchor: m,
          cells: { E: [m], G: [m], GT: [m] },
          status: "triple",
          reason: "相同稳定定位",
          generated_scenario_ids: [],
        },
      ]}
      definitions={{ range: { label: "数据范围" } }}
      onlyUnmatched={false}
      onSelect={select}
    />,
  );
  expect(screen.getByText("三方完整对应")).toBeTruthy();
  expect(screen.getByText(/已识别关注点，尚无确定场景/)).toBeTruthy();
  expect(screen.getByText("LLM识别 G_c")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "查看该关注点的场景 →" }));
  expect(select).toHaveBeenCalledWith("c1");
});

test("scene rows retain element ancestry and Q selection independently of concern coverage", () => {
  const s = {
    id: "s1",
    object: "pageSize",
    conditions: ["pageSize>100"],
    element_anchors: [
      {
        binding_id: "c1",
        target: "data",
        data_location: "query",
        object: "pageSize",
        concern_key: "range",
      },
    ],
    recommendation: { selected: true, rank: 1, reason: "关键风险保底" },
  };
  render(
    <AlignmentTable
      rows={[
        {
          id: "r",
          anchor: s,
          cells: { E: [], G: [s], GT: [s] },
          status: "pair",
        },
      ]}
      missing={["s1"]}
      onlyUnmatched={false}
      renderCell={(v: any) => <span>{v.conditions[0]}</span>}
    />,
  );
  expect(screen.getByText(/数据序列 · query.pageSize → range/)).toBeTruthy();
  expect(screen.getByText(/已纳入 Q_s · 第1位/)).toBeTruthy();
});

test("the metrics view explicitly distinguishes concern and scenario counting units", async () => {
  const rate = { value: 50, numerator: 1, denominator: 2, status: "适用" };
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({
      matching_version: "two-level-concern-scenario-v1",
      metrics: { generation_validity: rate, recommendation_adoption: rate },
      cases: [],
      history: [],
      truth_source: "独立测试",
      recommendation: "已启用",
    }),
  } as Response);
  render(<MetricsPanel project="p" onCase={() => {}} />);
  await screen.findByText(/两层计分/);
  expect(screen.getByText("关注点层 · 四要素对象—关注点")).toBeTruthy();
  expect(screen.getByText("场景层 · 独立失败条件")).toBeTruthy();
  expect(screen.queryByText(/当前GT规模支持/)).toBeNull();
});
