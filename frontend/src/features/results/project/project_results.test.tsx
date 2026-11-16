import type { ReactNode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { ResultsView } from "../ResultsView";
import { ScopeMetrics } from "./ScopeMetrics";

const ssd = vi.hoisted(() => ({ getSsdResultIndex: vi.fn() }));
const projectApi = vi.hoisted(() => ({
  getProjectResultIndex: vi.fn(),
  getProjectEditor: vi.fn(),
  saveProjectRevision: vi.fn(),
  exportProjectReview: vi.fn(),
  previewProjectReview: vi.fn(),
  applyProjectReview: vi.fn(),
}));
vi.mock("../ssd/api", () => ssd);
vi.mock("./api", () => projectApi);
vi.mock("../ssd/SsdResultsView", () => ({
  SsdResultsView: (props: { scopeNavigation?: ReactNode }) => (
    <div>交互级结果页{props.scopeNavigation}</div>
  ),
}));
vi.mock("./ProjectScopeResultsView", () => ({
  ProjectScopeResultsView: (props: {
    scope: string;
    navigation?: ReactNode;
  }) => (
    <div>
      {props.navigation}项目范围页：{props.scope}
    </div>
  ),
}));

const rate = {
  missing_exception_miss_rate: {
    value: 25,
    numerator: 1,
    denominator: 4,
    status: "适用",
  },
  generation_validity: {
    value: 50,
    numerator: 2,
    denominator: 4,
    status: "适用",
  },
};

function scopeMetrics() {
  return {
    concern: rate,
    scenario: rate,
    complete: true,
  };
}

beforeEach(() => {
  ssd.getSsdResultIndex.mockReset().mockResolvedValue({
    version: "ssd-case-v1",
    cases: [{ id: "UC-001", name: "创建商品", revision: 1 }],
    metrics: rate,
  });
  projectApi.getProjectResultIndex.mockReset().mockResolvedValue({
    version: "project-scopes-v1",
    scopes: [
      {
        id: "shared_services",
        name: "共用外部服务",
        available: true,
        revision: 1,
        anchor_count: 1,
      },
    ],
    legacy_scopes: ["business_chain", "architecture"],
    metrics: {
      by_scope: {
        interaction: scopeMetrics(),
        shared_services: scopeMetrics(),
      },
      overall: { concern: rate, scenario: rate },
      complete: true,
    },
  });
});

test("keeps interaction results and shared services together, with separate project totals", async () => {
  render(<ResultsView project="P1" />);
  for (const name of ["交互级", "项目指标"])
    expect(await screen.findByRole("tab", { name })).toBeTruthy();
  expect(screen.queryByRole("tab", { name: "业务链路" })).toBeNull();
  expect(screen.queryByRole("tab", { name: "项目架构" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "共用外部服务" }));
  expect(await screen.findByText("项目范围页：shared_services")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: "项目指标" }));
  expect(await screen.findByText("项目分层与汇总指标")).toBeTruthy();
  expect(screen.getAllByText("项目汇总").length).toBeGreaterThan(0);
  expect(screen.getAllByText("共用外部服务").length).toBeGreaterThan(0);
  expect(screen.getAllByText("25.00%（1/4）").length).toBeGreaterThan(0);
});

test("scope metrics show concern and scenario levels separately", () => {
  render(
    <ScopeMetrics
      snapshot={{
        metrics: rate,
        metrics_by_level: { concern: rate, scenario: rate },
        completeness: { complete: true },
      }}
    />,
  );
  expect(screen.getByText("当前修订 · 关注点层")).toBeTruthy();
  expect(screen.getByText("当前修订 · 场景层")).toBeTruthy();
});
