import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ProjectScopeResultsView } from "./ProjectScopeResultsView";
import fixture from "./fixture.test.json";
afterEach(() => {
  vi.unstubAllGlobals();
});
test("project scope keeps three-way layout, dependencies, source reader and review entry", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => structuredClone(fixture),
    })),
  );
  const onReviewRequest = vi.fn();
  render(
    <ProjectScopeResultsView
      project="P"
      scope="business_chain"
      navigation={<div>范围导航</div>}
      onReviewRequest={onReviewRequest}
    />,
  );
  await screen.findByText("范围导航");
  await screen.findByRole("button", { name: "展开工具栏" });
  fireEvent.click(screen.getByRole("button", { name: "展开工具栏" }));
  fireEvent.click(await screen.findByRole("button", { name: "交给业务审核" }));
  expect(onReviewRequest).toHaveBeenCalledWith(
    expect.objectContaining({
      scope: "business_chain",
      anchorId: fixture.bundle.anchors[0].id,
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "阅读原始 RR / SR" }));
  await screen.findByRole("dialog");
  expect(screen.getAllByText(/需求/).length).toBeGreaterThan(0);
});

test.each(["business_chain", "architecture"] as const)(
  "%s uses the same per-pair drafts, detail feedback and saved revision",
  async (scope) => {
    const data: any = structuredClone(fixture);
    data.bundle.scope.id = scope;
    if (scope === "architecture")
      data.bundle.anchors[0] = {
        ...data.bundle.anchors[0],
        kind: "external_service",
        name: "外部库存服务",
      };
    data.bundle.channels.G.scenarios = data.bundle.channels.G.scenarios.slice(
      0,
      2,
    );
    data.bundle.channels.E.scenarios = data.bundle.channels.G.scenarios.map(
      (r: any, i: number) => ({
        ...r,
        id: "original-" + i,
        condition: "原文失败 " + i,
      }),
    );
    data.bundle.semantic_pending = data.bundle.channels.G.scenarios.map(
      (r: any, i: number) => ({
        pair: "G_E",
        left_id: r.id,
        right_id: "original-" + i,
        anchor_id: data.bundle.anchors[0].id,
      }),
    );
    let submitted: any;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url, init) => {
        if (init?.method === "POST") {
          submitted = JSON.parse(init.body);
          data.bundle = structuredClone(submitted.bundle);
          data.bundle.semantic_pending = [];
          data.revision += 1;
        }
        return { ok: true, json: async () => structuredClone(data) };
      }),
    );
    render(
      <ProjectScopeResultsView
        project="P"
        scope={scope}
        navigation={<span>范围导航</span>}
      />,
    );
    await screen.findByText(/尚未完成的语义比较（2 对）/);
    fireEvent.click(screen.getByText(/尚未完成的语义比较（2 对）/));
    const cards = screen.getAllByRole("article", { name: /^配对 / });
    fireEvent.click(within(cards[0]).getByRole("button", { name: "确认匹配" }));
    fireEvent.click(within(cards[1]).getByRole("button", { name: "确认匹配" }));
    expect(screen.getByText(/匹配判定修改 2 条 · 其他修改 0 项/)).toBeTruthy();
    fireEvent.click(within(cards[0]).getByRole("button", { name: "查看详情" }));
    fireEvent.change(screen.getByLabelText("匹配判定"), {
      target: { value: "partial" },
    });
    fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
    expect(within(cards[0]).getByText("部分匹配 · 未保存")).toBeTruthy();
    expect(screen.getByText(/匹配判定修改 2 条/)).toBeTruthy();
    fireEvent.click(
      within(cards[1]).getByRole("button", { name: "取消本次匹配" }),
    );
    expect(screen.getByText(/匹配判定修改 1 条/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
    await screen.findByText(/修订已保存/);
    expect(
      submitted.bundle.decisions.filter((d: any) => d.origin === "manual"),
    ).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "保存修改并重算" })).toBeNull();
  },
);
