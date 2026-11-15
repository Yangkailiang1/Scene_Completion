import { fireEvent, render, screen } from "@testing-library/react";
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
