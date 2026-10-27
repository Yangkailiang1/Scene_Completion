import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { test, expect, vi, afterEach } from "vitest";
import { PendingView } from "./PendingView";
import { BusinessRecommendations } from "./BusinessRecommendations";
import { ReviewHandoff } from "./ReviewHandoff";
afterEach(() => vi.restoreAllMocks());
const response = (v: any) => ({ ok: true, json: async () => v }) as Response;
test("rule questions ask for actual validation and keep draft while opening line evidence", async () => {
  const writes: any[] = [];
  const item = {
    id: "q",
    case: "C",
    interaction_id: "m1",
    origins: ["C:normal-rules"],
    reason: "categoryId校验条件未知",
    required_answer: "有效性需要满足哪些校验条件？",
    question_type: "rule_completion",
    answer_spec: {
      label: "补充正常校验规则",
      choices: {
        provide_rule: "补充规则",
        not_required: "不要求此校验",
        needs_info: "仍待补充",
      },
    },
    source_refs: [
      {
        source_id: "SR",
        line_start: 4,
        line_end: 4,
        quote: "校验categoryId有效。",
      },
    ],
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (u, init) => {
    const url = String(u);
    if (init?.method === "POST") {
      writes.push({ url, body: JSON.parse(String(init.body)) });
      return response({ saved: true });
    }
    if (url.includes("/sources/"))
      return response({
        name: "SR.md",
        section: "# 浏览商品",
        line_count: 6,
        lines: [{ number: 4, text: "校验categoryId有效。" }],
      });
    if (url.endsWith("/registry"))
      return response({ registry: { definitions: {} } });
    return response({
      items: [item],
      count: 1,
      cases: ["C"],
      counts: { unresolved: 1 },
      queue_counts: {
        business: { total: 1 },
        rules: { total: 0 },
        structure: { total: 0 },
      },
    });
  });
  const opened = vi.fn();
  render(
    <PendingView project="p" onSelect={vi.fn()} onEvidenceOpen={opened} />,
  );
  await screen.findByRole("heading", { name: item.reason });
  expect(screen.queryByLabelText("是否为异常场景")).toBeNull();
  fireEvent.change(screen.getByLabelText("待确认审核说明"), {
    target: { value: "必须存在且启用，由商城入口校验" },
  });
  fireEvent.click(screen.getByRole("button", { name: /点击以查看文档/ }));
  await screen.findByLabelText("原文文档查看框");
  expect(opened).toHaveBeenCalledOnce();
  expect(
    (screen.getByLabelText("待确认审核说明") as HTMLTextAreaElement).value,
  ).toBe("必须存在且启用，由商城入口校验");
  expect(
    document.querySelector(".source-line.highlighted pre")?.textContent,
  ).toContain("categoryId");
  fireEvent.change(screen.getByLabelText("审核人"), {
    target: { value: "审核甲" },
  });
  fireEvent.change(screen.getByLabelText("业务回答方式"), {
    target: { value: "provide_rule" },
  });
  fireEvent.click(screen.getByText("保存回答"));
  await waitFor(() => expect(writes.length).toBe(1));
  expect(writes[0].body).toMatchObject({
    choice: "provide_rule",
    reviewer: "审核甲",
    revision: 0,
  });
  expect(writes[0].url).toContain("/pending/q");
});
test("recommendation review saves an explicit adoption and refreshes business GT without running a model", async () => {
  const writes: any[] = [];
  let saved = false;
  const s = {
    id: "G1",
    interaction_id: "m1",
    conditions: ["pageSize超过100"],
    concern_key: "range",
    source_refs: [],
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (u, init) => {
    const url = String(u);
    if (init?.method === "POST") {
      writes.push({ url, body: JSON.parse(String(init.body)) });
      saved = true;
      return response({ saved: true });
    }
    if (url.endsWith("/results"))
      return response({ cases: [{ id: "C", name: "查询" }] });
    if (url.endsWith("/registry"))
      return response({ registry: { definitions: {} } });
    return response({
      result: {
        enabled: true,
        Q: [s],
        ranked: [{ scenario_id: "G1", rank: 1 }],
        run_id: "run",
        settings_hash: "v",
      },
      comparison: {},
      evaluation_metrics: {},
      business_truth: { added: saved ? [s] : [] },
      feedback: [],
      feedback_revision: 0,
      human_adoption: { status: "待审核" },
    });
  });
  render(<BusinessRecommendations project="p" />);
  await screen.findByText("pageSize超过100");
  fireEvent.change(screen.getByLabelText("推荐审核人"), {
    target: { value: "业务甲" },
  });
  fireEvent.change(screen.getByLabelText("审核说明 G1"), {
    target: { value: "应覆盖上界" },
  });
  fireEvent.click(screen.getByText("保存审核"));
  await screen.findByText(/推荐审核已保存/);
  expect(writes).toHaveLength(1);
  expect(writes[0].url).toContain("/recommendations/feedback");
  expect(writes[0].body.choice).toBe("adopt");
  expect(writes[0].body.reviewer).toBe("业务甲");
});
test("feedback preview and import never start execution until the separate affected-run button", async () => {
  const writes: any[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (u, init) => {
    const url = String(u);
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      writes.push({ url, body });
      if (url.endsWith("/rerun-affected")) return response({ started: true });
      return response({
        ready_count: 1,
        conflicts: [],
        saved: !body.dry_run,
        impact: body.dry_run
          ? undefined
          : {
              plan_id: "v",
              roots: ["x"],
              affected: ["x", "y"],
              nodes: [
                { id: "x", label: "原节点" },
                { id: "y", label: "下游" },
              ],
              conflicts: [],
            },
      });
    }
    return response({ snapshots: [] });
  });
  render(<ReviewHandoff project="p" />);
  const file = new File(["{}"], "feedback.json", { type: "application/json" });
  Object.defineProperty(file, "text", { value: async () => "{}" });
  fireEvent.change(screen.getByLabelText("选择业务反馈包"), {
    target: { files: [file] },
  });
  await screen.findByText(/仅预览/);
  expect(writes[0].body.dry_run).toBe(true);
  fireEvent.click(screen.getByText("保存有效反馈（不重跑）"));
  await screen.findByText("按此范围重跑");
  expect(writes).toHaveLength(2);
  expect(writes.every((x) => x.url.endsWith("/feedback/import"))).toBe(true);
  fireEvent.click(screen.getByText("按此范围重跑"));
  await waitFor(() => expect(writes[2].body.plan_id).toBe("v"));
});
test("review-only handoff has feedback download but no execution, config or package export controls", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ snapshots: [] }));
  render(<ReviewHandoff project="p" reviewOnly />);
  expect(
    screen.getByRole("link", { name: "导出业务反馈包" }).getAttribute("href"),
  ).toContain("/feedback/export");
  expect(screen.queryByText("导出Windows业务审核包")).toBeNull();
  expect(screen.queryByText("按此范围重跑")).toBeNull();
});
