import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./App";
import { segments, NodeOutput } from "./NodeOutput";
import type { ExecutionEvent, GraphNode } from "./types";
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
