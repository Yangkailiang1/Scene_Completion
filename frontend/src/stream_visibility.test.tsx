import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NodeOutput } from "./NodeOutput";
import type { ExecutionEvent } from "./types";
const event = (id: number, kind: string, data: any): ExecutionEvent => ({
  id,
  kind,
  data,
  at: Date.now() / 1000,
  task_key: "task",
  role: "modeler",
  case: "shared",
  attempt: 1,
});
it("distinguishes empty tool-name deltas from real parameter output", () => {
  render(
    <NodeOutput
      active
      loading={false}
      events={[
        event(1, "request_started", {
          model_call_id: "call",
          requested_model: "ecnu-plus",
        }),
        event(2, "stream_delta", {
          model_call_id: "call",
          channel: "tool_arguments",
          tool_name: "submit_result",
          tool_index: 0,
          text: "",
        }),
      ]}
    />,
  );
  expect(screen.getByRole("status").textContent).toContain(
    "正在等待结构化产物正文",
  );
  expect(screen.getByRole("status").textContent).toContain("已收到 0 字符");
});
it("opens submitted artifact parameters by default while auxiliary tools stay folded", () => {
  render(
    <NodeOutput
      loading={false}
      events={[
        event(1, "stream_delta", {
          model_call_id: "one",
          channel: "tool_arguments",
          tool_name: "read_file",
          tool_index: 0,
          text: '{"path":"source"}',
        }),
        event(2, "stream_delta", {
          model_call_id: "two",
          channel: "tool_arguments",
          tool_name: "submit_result",
          tool_index: 0,
          text: '{"payload":{"services":[]}}',
        }),
      ]}
    />,
  );
  const artifact = screen.getByText(/查看结构化产物正文/).closest("details");
  const auxiliary = screen.getByText(/查看工具参数增量/).closest("details");
  expect(artifact?.open).toBe(true);
  expect(auxiliary?.open).toBe(false);
});
it("does not keep a waiting banner after the model request has finished", () => {
  render(
    <NodeOutput
      active
      loading={false}
      events={[
        event(1, "request_started", { model_call_id: "call" }),
        event(2, "request_finished", {
          model_call_id: "call",
          provider_model: "actual",
        }),
      ]}
    />,
  );
  expect(screen.queryByRole("status")).toBeNull();
});
