import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { NodePrompts } from "./NodePrompts";
afterEach(() => vi.restoreAllMocks());
test("shows actual system, tool schema and blocked request budget", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (url) =>
      ({
        ok: true,
        json: async () =>
          String(url).includes("request_id=")
            ? {
                id: "one",
                model: "test-model",
                at: 1,
                status: "context_blocked",
                attempt: 2,
                budget: {
                  estimated_input_tokens: 164000,
                  input_budget_tokens: 180000,
                  request_bytes: 804670,
                  context_tokenizer: "o200k_base",
                  tokenizer_basis: "proxy",
                  tokenizer_margin_percent: 10,
                  output_reserve: 32000,
                  max_context_tokens: 200000,
                },
                request: {
                  messages: [
                    { role: "system", content: "actual Skill instructions" },
                    { role: "user", content: "scoped source evidence" },
                  ],
                  tools: [
                    { type: "function", function: { name: "submit_result" } },
                  ],
                },
              }
            : {
                requests: [
                  {
                    id: "one",
                    model: "test-model",
                    at: 1,
                    status: "context_blocked",
                    attempt: 2,
                    budget: {},
                  },
                ],
                latest: "one",
              },
      }) as Response,
  );
  render(<NodePrompts projectId="project" taskKey="G-003:fused-ssd" />);
  await waitFor(() =>
    expect(screen.getByText("actual Skill instructions")).toBeTruthy(),
  );
  expect(screen.getByText("scoped source evidence")).toBeTruthy();
  expect(screen.getByText(/此请求在HTTP发送前被阻止/)).toBeTruthy();
  expect(screen.getByText(/本地 o200k_base 分词估计.*请求大小/)).toBeTruthy();
  fireEvent.click(screen.getByText("工具与输出Schema"));
  expect(screen.getByText(/submit_result/)).toBeTruthy();
});
test("missing historical request is explicit rather than inventing prompt", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({ requests: [], latest: null }),
  } as Response);
  render(<NodePrompts projectId="old" taskKey="old-node" />);
  await waitFor(() =>
    expect(screen.getByText(/此节点暂无完整请求记录/)).toBeTruthy(),
  );
});
