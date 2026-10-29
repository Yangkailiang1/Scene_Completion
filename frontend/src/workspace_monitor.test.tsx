import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { expect, test, vi, afterEach } from "vitest";
import { WorkspaceMonitor } from "./WorkspaceMonitor";
const base = {
  generated_at: 200,
  running: true,
  session_started_at: 100,
  measurable_tokens_per_second_estimate: 1.2,
  requests: [
    {
      node: "case:a",
      label: "关注点识别",
      requested_model: "slow",
      model_call_id: "r",
      tokens_per_second_estimate: 1.2,
      status: "low",
      elapsed_seconds: 100,
    },
  ],
  policy: {
    enabled: true,
    min_tokens_per_second: 2,
    grace_seconds: 60,
    window_seconds: 30,
    low_windows: 2,
    no_output_seconds: 120,
    max_switches: 2,
    candidates: [{ model: "fast" }],
  },
  estimate: {
    status: "estimated",
    seconds: 60,
    lower_seconds: 40,
    upper_seconds: 80,
    finish_at: 260,
    known_nodes: 20,
    completed_nodes: 10,
    remaining_nodes: 10,
    notes: ["只按当前已发现DAG估算"],
    unknown_nodes: [],
  },
  switch_events: [
    {
      id: 9,
      at: 190,
      kind: "model_switched",
      previous_model: "old",
      requested_model: "slow",
    },
  ],
};
afterEach(() => vi.restoreAllMocks());
function mock(value: any) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(
      async (url) =>
        ({
          ok: true,
          json: async () =>
            String(url).includes("execution-monitor")
              ? value
              : { points: [], cursor: 0, has_more: false },
        }) as Response,
    );
}
test("workspace offers compact live rates, expandable report and current-run curve without starting a model", async () => {
  const fetch = mock(base),
    settings = vi.fn(),
    select = vi.fn();
  render(
    <WorkspaceMonitor project="p" onSettings={settings} onSelect={select} />,
  );
  await screen.findByText("1.2 估算 tok/s");
  expect(screen.queryByLabelText("模型实时吞吐曲线")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "实时监视" }));
  await screen.findByLabelText("模型实时吞吐曲线");
  expect(screen.getByText(/连续2个窗口/)).toBeTruthy();
  expect(screen.getByText(/old → slow/)).toBeTruthy();
  expect(screen.getByText("只按当前已发现DAG估算")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /关注点识别/ }));
  expect(select).toHaveBeenCalledWith("case:a");
  fireEvent.click(screen.getByRole("button", { name: "切换策略" }));
  expect(settings).toHaveBeenCalledOnce();
  expect(fetch.mock.calls.some(([u]) => String(u).includes("since=100"))).toBe(
    true,
  );
  expect(fetch.mock.calls.every(([, init]) => !init?.method)).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "实时监视" }));
  expect(screen.queryByLabelText("模型实时吞吐曲线")).toBeNull();
});
test("unknown throughput and blocked ETA are never printed as zero or a promised finish time", async () => {
  mock({
    ...base,
    measurable_tokens_per_second_estimate: null,
    requests: [
      {
        ...base.requests[0],
        status: "stale",
        tokens_per_second_estimate: null,
      },
    ],
    estimate: {
      ...base.estimate,
      status: "blocked",
      finish_at: null,
      blockers: [{ id: "x", status: "awaiting_review" }],
    },
  });
  render(
    <WorkspaceMonitor
      project="p"
      onSettings={vi.fn()}
      onSelect={vi.fn()}
      reviewOnly
    />,
  );
  await screen.findByText("暂无可测速率");
  expect(screen.queryByRole("button", { name: "切换策略" })).toBeNull();
  expect(screen.getByText(/解除阻塞后约/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "实时监视" }));
  expect(screen.getByText("暂不能确定")).toBeTruthy();
  expect(screen.getByText(/采样已过期，不能当作0速率/)).toBeTruthy();
});
test("switching projects discards old rates and unavailable telemetry does not clear workspace", async () => {
  const fetch = mock(base);
  const page = render(
    <WorkspaceMonitor project="a" onSettings={vi.fn()} onSelect={vi.fn()} />,
  );
  await screen.findByText("1.2 估算 tok/s");
  fetch.mockRejectedValue(new Error("暂时离线"));
  page.rerender(
    <WorkspaceMonitor project="b" onSettings={vi.fn()} onSelect={vi.fn()} />,
  );
  await screen.findByText(/监测暂不可用：暂时离线/);
  expect(screen.queryByText("1.2 估算 tok/s")).toBeNull();
  expect(screen.getByLabelText("项目实时执行监视")).toBeTruthy();
});
