import { it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { NodeOutput, segments } from "./NodeOutput";
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

it('thinking-only stream progress is not presented as empty stalled body output',()=>{
 const result=segments([{id:1,kind:'stream_progress',at:1,attempt:1,data:{elapsed_seconds:20,output_bytes:0,reasoning_bytes:2048}} as any]);
 expect(result[0].text).toContain('另收到2048字节思考数据');
 expect(result[0].text).toContain('未开启原文显示');
});

it("shows provider thinking separately, does not count it as answer and can hide it",()=>{
 render(<NodeOutput active loading={false} events={[
  event(1,"request_started",{model_call_id:"a",reasoning_display_enabled:true}),
  event(2,"stream_delta",{model_call_id:"a",channel:"reasoning",text:"provider fragment"}),
 ]}/>);
 expect(screen.getByRole("status").textContent).toContain("模型正在思考，尚无正文／工具参数");
 expect(screen.getByRole("status").textContent).toContain("已收到 0 字符正文／工具参数");
 expect(screen.getByText("provider fragment")).toBeTruthy();
 expect(screen.getByText("模型思考流 · 网关返回，非正式产物")).toBeTruthy();
 fireEvent.click(screen.getByRole("checkbox",{name:"显示模型思考流"}));
 expect(screen.queryByText("provider fragment")).toBeNull();
});

it("distinguishes enabled thinking display from a gateway that sends no readable text",()=>{
 render(<NodeOutput active loading={false} events={[
  event(1,"request_started",{model_call_id:"a",reasoning_display_enabled:true}),
  event(2,"stream_progress",{model_call_id:"a",elapsed_seconds:10,output_bytes:0,reasoning_bytes:0,reasoning_fields:["reasoning_details"]}),
 ]}/>);
 expect(screen.getByRole("status").textContent).toContain("思考显示已开启，但尚未收到网关公开的思考文本");
 expect(screen.getByText(/网关包含reasoning_details字段，但尚无可显示/)).toBeTruthy();
});
