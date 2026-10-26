import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { vi, test, expect, afterEach } from "vitest";
import { UsageView } from "./UsageView";
afterEach(() => vi.restoreAllMocks());
test("usage stays embedded and fetches context only on demand", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(
    async (url) =>
      ({
        ok: true,
        json: async () =>
          String(url).includes("context?")
            ? { input: { scoped: true } }
            : {
                totals: {
                  input_tokens: 80,
                  output_tokens: 20,
                  reasoning_tokens: 10,
                  reported_total_tokens: 100,
                },
                groups: {},
                items: String(url).includes("view=tasks")
                  ? [
                      {
                        task_key: "case:task",
                        label: "规则整理",
                        models: ["model"],
                        calls: 1,
                        not_sent_calls: 0,
                        input_tokens: 80,
                        output_tokens: 20,
                        reported_total_tokens: 100,
                        request_seconds: 2,
                      },
                    ]
                  : [],
                count: 1,
                sessions: [],
              },
      }) as Response,
  );
  const close = vi.fn(),
    select = vi.fn();
  render(
    <UsageView
      project="usage-test"
      task={null}
      onClose={close}
      onSelect={select}
    />,
  );
  await waitFor(() => expect(screen.getByText("规则整理")).toBeTruthy());
  expect(
    fetcher.mock.calls.some(([url]) => String(url).includes("context?")),
  ).toBe(false);
  expect(document.querySelector('a[target="_blank"]')).toBeNull();
  fireEvent.click(screen.getByText("按需查看上下文"));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([url]) => String(url).includes("context?")),
    ).toBe(true),
  );
  fireEvent.click(screen.getByText("规则整理"));
  expect(select).toHaveBeenCalledWith("case:task");
  fireEvent.click(screen.getByText("返回工作区"));
  expect(close).toHaveBeenCalled();
});

test("bottleneck rankings select concrete nodes and sort requests on the server", async () => {
  const select = vi.fn();
  const base = {
    calls: 2,
    not_sent_calls: 0,
    reported_total_tokens: 900,
    input_tokens: 800,
    output_tokens: 100,
    request_seconds: 65,
  };
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(
      async () =>
        ({
          ok: true,
          json: async () => ({
            totals: base,
            groups: {},
            sessions: [],
            count: 0,
            items: [],
            rankings: {
              tokens: [
                {
                  ...base,
                  task_key: "C:big",
                  label: "具体大任务",
                  role: "modeler",
                  case: "C",
                },
              ],
              seconds: [
                {
                  ...base,
                  task_key: "D:slow",
                  label: "具体慢任务",
                  role: "checker",
                  case: "D",
                },
              ],
            },
          }),
        }) as Response,
    );
  render(
    <UsageView
      project="ranked"
      task={null}
      onClose={() => {}}
      onSelect={select}
    />,
  );
  await screen.findByText("具体大任务");
  fireEvent.click(screen.getByRole("button", { name: /具体慢任务/ }));
  expect(select).toHaveBeenCalledWith("D:slow");
  fireEvent.change(screen.getByLabelText("用量排序"), {
    target: { value: "seconds" },
  });
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([url]) => String(url).includes("sort=seconds")),
    ).toBe(true),
  );
  expect(screen.getByText("最耗Token的节点")).toBeTruthy();
});
