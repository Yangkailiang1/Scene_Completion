import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, it, expect, afterEach } from "vitest";
import { ManagerPanel } from "./ManagerPanel";
import { ThroughputView } from "./ThroughputView";
afterEach(() => vi.unstubAllGlobals());
it("opens a persistent floating manager and sends a project-scoped message", async () => {
  const writes: any[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: any, init: any) => ({
      ok: true,
      json: async () => {
        if (init?.method) {
          writes.push({ url, body: JSON.parse(init.body) });
          return { entry_id: 1 };
        }
        if (String(url).includes("history")) return { events: [] };
        return {
          configuration: {
            revision: 0,
            settings: { mode: "collaborative", enabled: false },
          },
          runtime: { status: "paused" },
          messages: [],
          memory: [],
          operations: [],
          patches: [],
          plan: { items: [] },
        };
      },
    })),
  );
  render(<ManagerPanel project="project-a" />);
  fireEvent.click(screen.getByLabelText("打开项目管理Agent"));
  await screen.findByText("让管理Agent协助推进项目");
  fireEvent.change(screen.getByLabelText("发送给管理Agent"), {
    target: { value: "请检查首例" },
  });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(writes[0].body.text).toBe("请检查首例"));
  expect(String(writes[0].url)).toContain("project-a/manager/messages");
  fireEvent.click(screen.getByLabelText("最大化管理窗口"));
  expect(screen.getByLabelText("项目管理Agent").className).toContain(
    "maximized",
  );
  fireEvent.click(screen.getByLabelText("收起管理Agent"));
  expect(screen.getByLabelText("打开项目管理Agent")).toBeTruthy();
});
it("renders explicit estimates and never claims hidden thinking is measurable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        cursor: 2,
        has_more: false,
        points: [
          {
            id: 1,
            at: 1,
            kind: "request_started",
            requested_model: "qwen",
            node: "n",
            model_call_id: "r",
          },
          {
            id: 2,
            at: 2,
            kind: "throughput_sample",
            tokens_per_second_estimate: 2,
            model_call_id: "r",
            node: "n",
            output_bytes: 40,
          },
        ],
      }),
    })),
  );
  render(<ThroughputView project="p" />);
  await screen.findByRole("option", { name: "qwen" });
  expect(screen.getByLabelText("模型实时吞吐曲线")).toBeTruthy();
  expect(screen.getByText(/未公开的推理内容无法测量/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "SVG" })).toBeTruthy();
});
it("keeps the support window outside clipped pages and open across project navigation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        configuration: {
          revision: 0,
          settings: { mode: "collaborative", enabled: false },
        },
        messages: [],
        memory: [],
        operations: [],
        patches: [],
        plan: { items: [] },
        events: [],
        runtime: { status: "paused" },
      }),
    })),
  );
  const page = render(
    <div style={{ overflow: "hidden", height: 1 }}>
      <ManagerPanel project="first" projectName="首个项目" />
    </div>,
  );
  expect(page.container.querySelector(".manager-fab")).toBeNull();
  expect(document.body.querySelector(".manager-fab")).toBeTruthy();
  fireEvent.click(screen.getByLabelText("打开项目管理Agent"));
  await screen.findByText(/首个项目/);
  fireEvent.change(screen.getByLabelText("发送给管理Agent"), {
    target: { value: "仅属于首个项目的草稿" },
  });
  fireEvent.click(screen.getByLabelText("最大化管理窗口"));
  page.rerender(
    <div style={{ overflow: "hidden", height: 1 }}>
      <ManagerPanel project="second" projectName="第二个项目" />
    </div>,
  );
  expect(screen.getByLabelText("项目管理Agent").className).toContain(
    "maximized",
  );
  expect(
    (screen.getByLabelText("发送给管理Agent") as HTMLTextAreaElement).value,
  ).toBe("");
  expect(localStorage.getItem("scene.manager.open")).toBe("true");
  page.unmount();
  render(<ManagerPanel project="second" projectName="第二个项目" />);
  expect(screen.getByLabelText("项目管理Agent")).toBeTruthy();
});
it("shows the support entry even before a project has been selected", async () => {
  const calls = vi.fn();
  vi.stubGlobal("fetch", calls);
  render(<ManagerPanel project="" />);
  fireEvent.click(screen.getByLabelText("打开项目管理Agent"));
  expect(screen.getByText(/先在左侧选择项目/)).toBeTruthy();
  expect(
    (screen.getByLabelText("发送给管理Agent") as HTMLTextAreaElement).disabled,
  ).toBe(true);
  expect(calls).not.toHaveBeenCalled();
});
it("keeps legacy requests without call IDs separated by node in throughput filters", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        cursor: 4,
        has_more: false,
        points: [
          {
            id: 1,
            at: 1,
            kind: "request_started",
            node: "a",
            requested_model: "model-a",
          },
          {
            id: 2,
            at: 2,
            kind: "request_started",
            node: "b",
            requested_model: "model-b",
          },
          {
            id: 3,
            at: 3,
            kind: "throughput_sample",
            node: "a",
            tokens_per_second_estimate: 3,
            output_bytes: 24,
          },
          {
            id: 4,
            at: 4,
            kind: "throughput_sample",
            node: "b",
            tokens_per_second_estimate: 4,
            output_bytes: 48,
          },
        ],
      }),
    })),
  );
  render(<ThroughputView project="p" />);
  await screen.findByRole("option", { name: "model-a" });
  fireEvent.change(screen.getByLabelText("吞吐模型"), {
    target: { value: "model-a" },
  });
  expect(document.querySelectorAll(".throughput-chart circle")).toHaveLength(1);
  expect(
    document.querySelector(".throughput-chart circle title")?.textContent,
  ).toContain("model-a · a");
});
it("does not draw a continuous rate across an unmeasured gap", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        cursor: 4,
        has_more: false,
        points: [
          {
            id: 1,
            at: 1,
            kind: "request_started",
            node: "n",
            model_call_id: "r",
            requested_model: "m",
          },
          {
            id: 2,
            at: 2,
            kind: "throughput_sample",
            node: "n",
            model_call_id: "r",
            tokens_per_second_estimate: 3,
          },
          {
            id: 3,
            at: 7,
            kind: "throughput_sample",
            node: "n",
            model_call_id: "r",
            tokens_per_second_estimate: 2,
          },
          {
            id: 4,
            at: 100,
            kind: "throughput_sample",
            node: "n",
            model_call_id: "r",
            tokens_per_second_estimate: 1,
          },
        ],
      }),
    })),
  );
  render(<ThroughputView project="p" />);
  await screen.findByRole("option", { name: "m" });
  expect(document.querySelectorAll(".throughput-chart polyline")).toHaveLength(
    2,
  );
});
