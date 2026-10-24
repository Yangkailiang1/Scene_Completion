import { beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { layout } from "./flow_layout";
import { NodeConversation } from "./NodeConversation";
import type { GraphNode } from "./types";
const make = (
  id: string,
  deps: string[] = [],
  role: any = "modeler",
): GraphNode => ({
  id,
  stage: id,
  label: id,
  deps,
  case: "shared",
  role,
  status: "pending",
  phase: "pending",
  expected_files: [id + ".json"],
  failure: null,
  blocked_by: [],
  elapsed_seconds: null,
  attempt: 1,
  last_event_at: null,
});
describe("actual dependency layout", () => {
  it("shows independent tasks side by side and dependent tasks below", () => {
    const nodes = layout([make("a"), make("b"), make("c", ["a", "b"])], null);
    const a = nodes.find((n) => n.id === "a")!,
      b = nodes.find((n) => n.id === "b")!,
      c = nodes.find((n) => n.id === "c")!;
    expect(a.position.y).toBe(b.position.y);
    expect(a.position.x).not.toBe(b.position.x);
    expect(c.position.y).toBeGreaterThan(a.position.y);
  });
  it("keeps checker and recommender lanes even when only modeling is running", () => {
    const n = layout([make("a")], null);
    expect(n.some((n) => n.id === "lane-checker")).toBe(true);
    expect(n.some((n) => n.id === "lane-recommender")).toBe(true);
  });
});
describe("node conversation", () => {
  it("persists guidance and shows when it becomes applied", async () => {
    const messages: any[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: any) => ({
        ok: true,
        json: async () => {
          if (init?.method === "POST") {
            const body = JSON.parse(init.body);
            messages.push({
              id: 1,
              kind: "guidance",
              text: body.text,
              at: 1,
              revision: 1,
              applied: false,
              detail: {},
            });
            return messages[0];
          }
          return { messages: [...messages], question: null };
        },
      })),
    );
    render(<NodeConversation projectId="p" taskKey="G" onChanged={() => {}} />);
    fireEvent.change(screen.getByRole("textbox", { name: "节点指导或回答" }), {
      target: { value: "只读，不推导写入" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送指导" }));
    expect(await screen.findByText("只读，不推导写入")).toBeTruthy();
    expect(screen.getByText("已接收 · 待模型调用")).toBeTruthy();
  });
  it("answers a persisted question and requests continuation only for that node", async () => {
    const sent: any[] = [];
    const question = {
      text: "ID格式是什么？",
      detail: {
        question_id: "q",
        basis: "仅有必填定义",
        decision: "确认具体规则",
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: any) => ({
        ok: true,
        json: async () => {
          if (init?.method === "POST") {
            sent.push({ url, body: JSON.parse(init.body) });
            return {};
          }
          return { messages: [], question };
        },
      })),
    );
    render(<NodeConversation projectId="p" taskKey="G" onChanged={() => {}} />);
    await screen.findByText(/ID格式是什么/);
    fireEvent.change(screen.getByRole("textbox", { name: "节点指导或回答" }), {
      target: { value: "待确认" },
    });
    fireEvent.click(screen.getByRole("button", { name: "回答并继续" }));
    await waitFor(() => expect(sent.length).toBe(1));
    expect(sent[0].url).toContain("/answer");
    expect(sent[0].body).toMatchObject({
      task_key: "G",
      question_id: "q",
      text: "待确认",
    });
  });
});
