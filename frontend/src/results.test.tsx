import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { test, expect, vi, afterEach } from "vitest";
import { ResultsView } from "./ResultsView";
import { MetricsPanel } from "./ResultComparison";
afterEach(() => vi.restoreAllMocks());
test("metrics are visible with counts and cases can be opened without a new page", async () => {
  const select = vi.fn();
  const rate = {
    value: 53.846,
    numerator: 21,
    denominator: 39,
    status: "适用",
  };
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({
      metrics: {
        missing_exception_miss_rate: rate,
        generation_validity: { value: 14.55, numerator: 55, denominator: 378 },
      },
      cases: [
        {
          id: "C",
          name: "查询",
          counts: { G: 10, E: 2, GT: 4, M: 8 },
          metrics: { missing_exception_miss_rate: rate },
          status: "已评测",
        },
      ],
      history: [],
      truth_source: "测试文档经机器整理",
      recommendation: "未启用",
    }),
  } as Response);
  render(<MetricsPanel project="p" onCase={select} />);
  await screen.findAllByText("53.85%");
  expect(screen.getByText("（55/378）")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "C · 查询" }));
  expect(select).toHaveBeenCalledWith("C");
});
test("result view loads one case on demand and shows all three evidence channels and diagrams", async () => {
  const image = {
    name: "components.svg",
    path: "run/artifacts/shared/components.svg",
    bytes: 20,
  };
  const artifact = {
    key: "components",
    label: "系统组成",
    case: "shared",
    stage: "components",
    files: [image],
  };
  const requests: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const path = String(url);
    requests.push(path);
    let data: any;
    if (path.endsWith("/results"))
      data = {
        complete: true,
        cases: [
          { id: "C", name: "查询记忆库" },
          { id: "D", name: "创建记忆库" },
        ],
        artifacts: [artifact],
      };
    else
      data = {
        definitions: { key: { label: "数据范围" } },
        case: { id: "C" },
        unbound: { G: [], E: [], GT: [] },
        interactions: [
          {
            interaction: {
              id: "i1",
              sequence: 1,
              layer: "SR",
              direction: "request",
              sender: { name: "开发者", position: "外部Actor" },
              receiver: { name: "平台", position: "内部Service" },
              operation: { name: "查询记忆库" },
              data: { sequence: [{ name: "pageSize", location: "query" }] },
            },
            channels: {
              E: [
                {
                  id: "e",
                  concern_key: "key",
                  conditions: ["原文已有范围错误"],
                },
              ],
              G: [
                {
                  id: "g",
                  concern_key: "key",
                  conditions: ["pageSize大于100"],
                },
              ],
              GT: [
                {
                  id: "gt",
                  concern_key: "key",
                  conditions: ["测试pageSize越界"],
                  source_status: "explicit",
                },
              ],
            },
            concerns: { E: ["key"], G: ["key"], GT: ["key"] },
            missing_ids: ["g"],
          },
        ],
      };
    if (data.interactions) {
      const r = data.interactions[0];
      r.alignment_rows = [
        {
          id: "row1",
          status: "conflict",
          anchor: r.channels.G[0],
          cells: r.channels,
          matching: [],
          shared_e_ids: [],
        },
      ];
    }
    return { ok: true, json: async () => data } as Response;
  });
  render(<ResultsView project="p" />);
  await screen.findAllByText("pageSize大于100");
  expect(
    screen.getByRole("columnheader", { name: /需求文档已有 E/ }),
  ).toBeTruthy();
  expect(
    screen.getByRole("columnheader", { name: /本方法生成 G/ }),
  ).toBeTruthy();
  expect(
    screen.getByRole("columnheader", { name: /独立测试真值 GT/ }),
  ).toBeTruthy();
  expect(screen.getByText("文档未覆盖")).toBeTruthy();
  expect(requests.some((x) => x.endsWith("/results/D"))).toBe(false);
  fireEvent.click(screen.getByText("图表总览"));
  await screen.findByRole("img", { name: "系统组成" });
  expect(
    screen.getByRole("link", { name: "下载SVG" }).getAttribute("href"),
  ).toContain("components.svg");
  fireEvent.change(screen.getByLabelText("结果用例"), {
    target: { value: "D" },
  });
  await waitFor(() =>
    expect(requests.some((x) => x.endsWith("/results/D"))).toBe(true),
  );
});
