import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { layout } from "../execution/flow_layout";
import { ImportDependencyPlan } from "./ImportDependencyPlan";
vi.mock("../execution/ExecutionFlow", () => ({
  ExecutionFlow: ({ graph, onSelect }: any) => (
    <div data-testid="dependency-graph">
      {graph.nodes.map((n: any) => (
        <button key={n.id} onClick={() => onSelect(n.id)}>
          {n.label}图节点
        </button>
      ))}
    </div>
  ),
}));
const a: any = {
  id: "planned:sr-api-map",
  target_key: "sr-api-map",
  stage: "api-map",
  case: "shared",
  role: "modeler",
  label: "SR内部接口映射",
  planned: true,
  status: "planned",
  phase: "planned",
  deps: [],
  expected_files: ["sr-api-map.json"],
  input_bindings: [
    {
      file_id: "api",
      name: "api_extraction.json",
      purpose: "API提取结果",
      revision: 0,
      original: "imports/api.json",
      explanation: "完整映射可复用",
      mode: "reuse",
    },
  ],
  import_mode: "reuse",
  import_label: "复用输入，跳过对应LLM抽取",
};
const b: any = {
  ...a,
  id: "planned:parameters",
  target_key: "parameters",
  label: "SR接口参数",
  deps: [a.id],
  import_mode: "partial",
  import_label: "部分已提供，仍补缺项",
};
test("import plan shows real dependencies, file mapping and node explanations before execution", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        nodes: [a, b],
        edges: [{ source: a.id, target: b.id }],
        files: a.input_bindings,
        summary: { reuse: 1, partial: 1 },
        roles: [],
        preview_only: true,
      }),
    })),
  );
  render(<ImportDependencyPlan project="p" onClose={() => {}} />);
  await screen.findByText("SR内部接口映射图节点");
  fireEvent.click(screen.getByText("SR内部接口映射图节点"));
  expect(screen.getAllByText("API提取结果").length).toBeGreaterThan(0);
  expect(screen.getByText("完整映射可复用")).toBeTruthy();
  expect(
    screen.getByRole("link", { name: "查看来源文件" }).getAttribute("href"),
  ).toContain("imports%2Fapi.json");
  expect(screen.getByText(/不是执行进度/)).toBeTruthy();
  fireEvent.click(screen.getByText("SR接口参数图节点"));
  expect(screen.getAllByText("部分已提供，仍补缺项").length).toBeGreaterThan(0);
});
test("planned nodes keep parallel depths and actual dependency order", () => {
  const parallel = { ...a, id: "planned:rr-api-map" };
  const positions = layout([a, parallel, b], null).filter(
    (n) => n.type === "task",
  );
  const get = (id: string) => positions.find((n) => n.id === id)!.position;
  expect(get(a.id).y).toBe(get(parallel.id).y);
  expect(get(b.id).y).toBeGreaterThan(get(a.id).y);
});
