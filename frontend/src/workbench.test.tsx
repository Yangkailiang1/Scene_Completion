import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./app/App";
import { NodeOutput, segments } from "./features/execution/NodeOutput";
import type { ExecutionEvent, GraphNode } from "./shared/types";
vi.mock("./ExecutionFlow", () => ({
  ExecutionFlow: ({ graph, onSelect }: any) => (
    <div data-testid="graph">
      {graph.nodes.map((n: any) => (
        <button key={n.id} onClick={() => onSelect(n.id)}>
          {n.label}
        </button>
      ))}
    </div>
  ),
}));
const node: GraphNode = {
  id: "api-map",
  stage: "api-map",
  role: "modeler",
  case: "shared",
  label: "API 接口映射",
  status: "running",
  phase: "streaming",
  deps: [],
  expected_files: ["api-map.json"],
  blocked_by: [],
  failure: null,
  attempt: 1,
  elapsed_seconds: 3,
  last_event_at: null,
};
const project = {
  id: "a".repeat(32),
  name: "商城测试",
  review_mode: "auto",
  case_ids: ["UC-1"],
  sources: { RR: [], SR: [], test: [] },
};
const stream = (
  id: number,
  text: string,
  call = "one",
  attempt = 1,
): ExecutionEvent => ({
  id,
  kind: "stream_delta",
  at: 100,
  task_key: "api-map",
  role: "modeler",
  case: "shared",
  attempt,
  data: { channel: "tool_arguments", model_call_id: call, tool_index: 0, text },
});
class Source {
  static latest: Source;
  listeners: Record<string, any> = {};
  onopen: any;
  onerror: any;
  constructor(public url: string) {
    Source.latest = this;
  }
  addEventListener(k: string, v: any) {
    this.listeners[k] = v;
  }
  close() {}
}
beforeEach(() => {
  vi.stubGlobal("EventSource", Source);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url === "/api/projects"
          ? [project]
          : url === "/api/registry"
            ? { definitions: {} }
            : url.endsWith("/graph")
              ? {
                  nodes: [node],
                  edges: [],
                  roles: [],
                  definition_available: true,
                  case_expansion_pending: false,
                }
              : url.includes("events/history")
                ? { events: [stream(1, '{"services":')] }
                : url.includes("conversation")
                  ? { messages: [], question: null }
                  : url.includes("review-history")
                    ? { versions: [] }
                    : url.endsWith("/run")
                      ? { status: "running" }
                      : {
                          project,
                          job: { status: "running" },
                          reviews: [],
                          artifacts: [],
                          config: {
                            agent_model: "ecnu-plus",
                            credential_configured: true,
                          },
                          tasks: { tasks: {}, events: [] },
                          manifest: null,
                        },
    })),
  );
});
describe("real output grouping", () => {
  it("joins fragmented tools but separates attempts and model requests", () => {
    const result = segments([
      stream(1, "{"),
      stream(2, "}"),
      stream(3, "new", "two"),
      stream(4, "retry", "two", 2),
    ]);
    expect(result.map((r) => r.text)).toEqual(["{}", "new", "retry"]);
  });
  it("renders long tool arguments without interpreting them as markup", () => {
    render(
      <NodeOutput
        events={[stream(1, "<script>" + "a".repeat(30000))]}
        loading={false}
      />,
    );
    expect(screen.getByText(/<script>/).textContent?.length).toBe(30008);
    expect(document.querySelector("script")).toBeNull();
  });
});
describe("workspace interactions", () => {
  it("keeps SSD results accessible when execution passed but records still need confirmation", async () => {
    const previousFetch = globalThis.fetch;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url === `/api/projects/${project.id}`) {
          return {
            ok: true,
            json: async () => ({
              project,
              job: { status: "complete_with_questions" },
              reviews: [],
              artifacts: [],
              config: {},
              tasks: { tasks: {}, events: [] },
              review_summary: { unresolved: 0, counts: {} },
              manifest: {
                workflow: "ssd-case-v1",
                execution_complete: true,
                analysis_complete: true,
                complete: false,
                pending_count: 7,
                live_cases: {
                  "UC-1": { analysis_ready: true, evaluation_ready: true },
                },
              },
            }),
          };
        }
        if (url.endsWith("/graph")) {
          return {
            ok: true,
            json: async () => ({
              nodes: [{ ...node, status: "passed", phase: "complete" }],
              edges: [],
              roles: [],
              definition_available: true,
              case_expansion_pending: false,
            }),
          };
        }
        return previousFetch(url, init);
      }),
    );
    render(<App />);
    fireEvent.click(await screen.findByText("商城测试"));
    expect(await screen.findByText("执行完成 · 7 项待确认")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "查看三方结果并确认" }),
    ).toBeTruthy();
    expect(
      screen.getByText("待确认结果").previousElementSibling?.textContent,
    ).toBe("7");
    expect(screen.getByText(/执行阶段已全部完成；请在三方结果页/)).toBeTruthy();
    expect(screen.queryByText(/点击“开始运行”建立任务计划/)).toBeNull();
  });
  it("collapses project list, saves preference and restores it", async () => {
    const v = render(<App />);
    await screen.findByText("商城测试");
    fireEvent.click(screen.getByRole("button", { name: "收起项目栏" }));
    expect(localStorage.getItem("scene-sidebar-collapsed")).toBe("true");
    expect(screen.getByRole("button", { name: "展开项目栏" })).toBeTruthy();
    v.unmount();
    render(<App />);
    expect(screen.getByRole("button", { name: "展开项目栏" })).toBeTruthy();
  });
  it("node selection loads historical real output and live deltas with resumable cursor", async () => {
    sessionStorage.setItem("scene-cursor-" + project.id, "8");
    render(<App />);
    fireEvent.click(await screen.findByText("商城测试"));
    fireEvent.click(
      await screen.findByRole("button", { name: "API 接口映射" }),
    );
    expect(await screen.findByText('{"services":')).toBeTruthy();
    expect(Source.latest.url).toContain("after=8");
    Source.latest.listeners.execution({
      data: JSON.stringify(stream(9, "[]}")),
    });
    await waitFor(() =>
      expect(screen.getByText('{"services":[]}')).toBeTruthy(),
    );
    expect(sessionStorage.getItem("scene-cursor-" + project.id)).toBe("9");
    expect(screen.getByRole("tab", { name: /产物/ })).toBeTruthy();
  });
  it("shows actual server failure and upstream links rather than guessed progress", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () =>
          url === "/api/projects"
            ? [project]
            : url === "/api/registry"
              ? { definitions: {} }
              : url.endsWith("/graph")
                ? {
                    nodes: [
                      {
                        ...node,
                        status: "failed",
                        phase: "failed",
                        failure: { error: "actual tool failure" },
                      },
                    ],
                    edges: [],
                    roles: [],
                    definition_available: true,
                    case_expansion_pending: false,
                  }
                : url.includes("events/history")
                  ? { events: [] }
                  : url.includes("conversation")
                    ? { messages: [], question: null }
                    : url.includes("review-history")
                      ? { versions: [] }
                      : {
                          project,
                          job: { status: "waiting" },
                          reviews: [],
                          artifacts: [],
                          config: {},
                          tasks: { tasks: {}, events: [] },
                        },
      })),
    );
    render(<App />);
    fireEvent.click(await screen.findByText("商城测试"));
    fireEvent.click(
      await screen.findByRole("button", { name: "API 接口映射" }),
    );
    expect(await screen.findByText("actual tool failure")).toBeTruthy();
    expect(screen.queryByText(/100%/)).toBeNull();
  });
});

it("running workspace exposes pause and stop controls that call the project API", async () => {
  const old = globalThis.fetch as any;
  const calls: any[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: any, init: any) => {
      if (String(url).endsWith("/execution-control")) {
        calls.push(JSON.parse(init.body));
        return { ok: true, json: async () => ({ message: "已保存执行控制" }) };
      }
      return old(url, init);
    }),
  );
  render(<App />);
  fireEvent.click(await screen.findByText("商城测试"));
  fireEvent.click(await screen.findByRole("button", { name: "暂停任务" }));
  await waitFor(() => expect(calls).toContainEqual({ action: "pause" }));
  fireEvent.click(screen.getByRole("button", { name: "停止任务" }));
  await waitFor(() => expect(calls).toContainEqual({ action: "stop" }));
});
