import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ScopeReview } from "./ScopeReview";
afterEach(() => vi.restoreAllMocks());
test("scope review loads on expansion and saves a versioned answer without running models", async () => {
  const unit = {
    source_id: "e1",
    trigger: "重复更新",
    scope: "interaction",
    global_kind: null,
    entity_ids: ["Product"],
    related_cases: ["G-003"],
    reason: "旧判定",
  };
  const calls: { url: string; body?: string }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    calls.push({ url: String(url), body: options?.body as string | undefined });
    return {
      ok: true,
      json: async () =>
        options?.method === "PUT"
          ? { affected_nodes: ["source", "child"] }
          : {
              records: [
                {
                  task_key: "G-003:existing-scope",
                  expected_version: "version1",
                  value: { units: [unit] },
                },
              ],
              entities: [{ id: "Product", name: "商品" }],
              cases: [{ id: "G-003", name: "更新商品" }],
            },
    } as Response;
  });
  const { container } = render(<ScopeReview project="p" />);
  expect(calls).toHaveLength(0);
  const details = container.querySelector("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  await waitFor(() => expect(calls).toHaveLength(1));
  fireEvent.change(screen.getByLabelText("来源及用例"), {
    target: { value: "G-003:existing-scope" },
  });
  fireEvent.change(screen.getByLabelText("分析粒度"), {
    target: { value: "global" },
  });
  fireEvent.change(screen.getByLabelText("审核依据"), {
    target: { value: "独立重复更新义务" },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存归属判定" }));
  await screen.findByRole("status");
  const saved = JSON.parse(calls.find((c) => c.body)?.body || "{}");
  expect(saved.expected_version).toBe("version1");
  expect(saved.units[0].global_kind).toBe("idempotency");
  expect(saved.units[0].reason).toBe("独立重复更新义务");
  expect(calls.every((c) => c.url.endsWith("/analysis-scopes"))).toBe(true);
});
