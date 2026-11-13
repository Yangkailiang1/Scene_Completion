import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { MetricsPanel } from "./ResultComparison";
import { ResultsView } from "../ResultsView";
afterEach(() => vi.restoreAllMocks());

test("case metrics use their own endpoint and global/project hide the case selector", async () => {
  localStorage.setItem("scene-result-controls-collapsed", "true");
  const requests: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const path = String(url);
    requests.push(path);
    const data = path.split("?")[0].endsWith("/results")
      ? {
          cases: [{ id: "G-001", name: "创建" }],
          artifacts: [],
          historical: true,
        }
      : {
          metrics: {},
          history: [],
          cases: [],
          interactions: [],
          definitions: {},
          unbound: {},
          case: { id: "G-001", name: "创建" },
          counts: {},
          concern_level: {},
          scenario_level: {},
          test_set: "original",
          complete: false,
        };
    return { ok: true, json: async () => data } as Response;
  });
  render(<ResultsView project="navigation-scope" />);
  await screen.findByRole("option", { name: "G-001 · 创建" });
  fireEvent.change(screen.getByLabelText("当前范围视图"), {
    target: { value: "metrics" },
  });
  await waitFor(() =>
    expect(requests.some((p) => p.includes("/results/G-001/metrics?"))).toBe(
      true,
    ),
  );
  expect(requests.some((p) => p.includes("/results/metrics?"))).toBe(false);
  fireEvent.click(screen.getByRole("tab", { name: "全局业务分析" }));
  expect(screen.queryByLabelText("结果用例")).toBeNull();
  expect(screen.queryByLabelText("当前范围视图")).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "项目指标" }));
  expect(screen.queryByLabelText("结果用例")).toBeNull();
  expect(screen.getByLabelText("当前范围视图").textContent).toContain(
    "项目总指标",
  );
  fireEvent.click(screen.getByRole("tab", { name: "用例结果" }));
  expect((screen.getByLabelText("结果用例") as HTMLSelectElement).value).toBe(
    "G-001",
  );
  expect(
    (screen.getByLabelText("当前范围视图") as HTMLSelectElement).value,
  ).toBe("metrics");
});
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
    if (path.split("?")[0].endsWith("/results"))
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
  fireEvent.click(screen.getByRole("button", { name: "展开工具栏" }));
  expect(screen.getByRole("button", { name: "测试场景" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "测试集" })).toBeNull();
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
  expect(requests.some((x) => x.split("?")[0].endsWith("/results/D"))).toBe(
    false,
  );
  fireEvent.click(screen.getByRole("button", { name: "用例图表" }));
  await screen.findByRole("img", { name: "系统组成" });
  expect(
    screen.getByRole("link", { name: "下载SVG" }).getAttribute("href"),
  ).toContain("components.svg");
  fireEvent.change(screen.getByLabelText("结果用例"), {
    target: { value: "D" },
  });
  expect(requests.some((x) => x.split("?")[0].endsWith("/results/D"))).toBe(
    false,
  );
  fireEvent.click(screen.getByRole("button", { name: "交互对照" }));
  await waitFor(() =>
    expect(
      requests.some(
        (x) => x.split("?")[0].endsWith("/results/D") && x.includes("scope=SR"),
      ),
    ).toBe(true),
  );
  fireEvent.change(screen.getByLabelText("指标接口层级"), {
    target: { value: "RR" },
  });
  await waitFor(() =>
    expect(
      requests.some((x) => x.includes("/results/D?") && x.includes("scope=RR")),
    ).toBe(true),
  );
});

test("results controls collapse to a compact bar and persist the choice", async () => {
  localStorage.setItem("scene-result-controls-collapsed", "true");
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({ complete: true, cases: [], artifacts: [] }),
  } as Response);
  render(<ResultsView project="compact" />);
  expect(screen.getByLabelText("当前范围视图")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "测试场景" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "展开工具栏" }));
  expect(screen.getByRole("button", { name: "测试场景" })).toBeTruthy();
  expect(localStorage.getItem("scene-result-controls-collapsed")).toBe("false");
  fireEvent.click(screen.getByRole("button", { name: "收起工具栏" }));
  expect(screen.getByLabelText("当前范围视图")).toBeTruthy();
  expect(localStorage.getItem("scene-result-controls-collapsed")).toBe("true");
});

test("BDD is selectable with SVG preview and editable PlantUML download", async () => {
  localStorage.setItem("scene-result-controls-collapsed", "false");
  const files = ["svg", "json", "puml"].map((ext) => ({
    name: "system-bdd." + ext,
    path: "run/artifacts/shared/system-bdd." + ext,
    bytes: 10,
  }));
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (url) =>
      ({
        ok: true,
        json: async () =>
          String(url).split("?")[0].endsWith("/results")
            ? {
                cases: [{ id: "C", name: "查询" }],
                artifacts: [
                  {
                    key: "components:bdd",
                    label: "BDD 块定义图（系统上下文）",
                    case: "shared",
                    stage: "bdd",
                    files,
                  },
                ],
              }
            : {
                interactions: [],
                unbound: {},
                definitions: {},
                payload: { blocks: [] },
              },
      }) as Response,
  );
  render(<ResultsView project="bdd-view" />);
  await screen.findByRole("button", { name: "用例图表" });
  fireEvent.click(screen.getByRole("button", { name: "用例图表" }));
  const img = await screen.findByAltText("BDD 块定义图（系统上下文）");
  expect(img.getAttribute("src")).toContain("system-bdd.svg");
  expect(
    screen.getByRole("link", { name: "下载PUML" }).getAttribute("download"),
  ).toBe("system-bdd.puml");
});

test("frozen results distinguish pending recognition from current successful checks", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (url) =>
      ({
        ok: true,
        json: async () =>
          String(url).split("?")[0].endsWith("/results")
            ? {
                complete: true,
                cases: [{ id: "C", name: "创建" }],
                artifacts: [],
              }
            : {
                case: { id: "C" },
                matching_version: "old",
                recognition_outdated: true,
                definitions: { type: { label: "数据类型" } },
                unbound: {},
                interactions: [
                  {
                    interaction: {
                      id: "i",
                      sequence: 1,
                      layer: "SR",
                      direction: "request",
                      sender: { name: "P" },
                      receiver: { name: "A" },
                      operation: { name: "创建" },
                      data: { sequence: [] },
                    },
                    channels: { E: [], G: [], GT: [] },
                    concerns: { E: [], G: [], GT: [] },
                    concern_rows: [],
                    alignment_rows: [],
                    missing_ids: [],
                    recognition_summary: {
                      applicable: 0,
                      not_applicable: 1,
                      pending: [
                        {
                          object: "name",
                          concern_key: "type",
                          reason: "旧识别未定位字段",
                        },
                      ],
                      note: "本地处理未声明独立数据字段",
                    },
                  },
                ],
              },
      }) as Response,
  );
  render(<ResultsView project="frozen-recognition" />);
  await screen.findByText(/修订前的冻结结果/);
  fireEvent.click(await screen.findByRole("button", { name: "关注点层" }));
  expect(screen.getByText(/本方法识别状态：已确认/)).toBeTruthy();
  expect(screen.getByText(/旧识别未定位字段/)).toBeTruthy();
  expect(screen.getByText("本地处理未声明独立数据字段")).toBeTruthy();
});

test("an imported version uses its own case detail and metrics in an unrun project", async () => {
  const requests: string[] = [];
  const imported = {
    id: "a".repeat(64),
    case: { id: "G-001", name: "创建商品" },
    scope: "SR",
    imported_at: "2026-11-11T00:00:00Z",
    pending: ["超时阈值待确认"],
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const path = String(url);
    requests.push(path);
    const selected = path.includes("import_id=" + imported.id);
    const index = path.split("?")[0].endsWith("/results");
    const data = index
      ? {
          cases: selected ? [imported.case] : [],
          artifacts: [],
          case_result_imports: [imported],
          imported_result: selected ? imported : undefined,
          supplement_tests: false,
        }
      : {
          interactions: [],
          definitions: {},
          unbound: {},
          case: imported.case,
          metrics: {},
          cases: [],
          history: [],
          recommendations: { enabled: false, Q: [] },
        };
    return { ok: true, json: async () => data } as Response;
  });
  render(<ResultsView project="imported-project" />);
  const source = await screen.findByRole("combobox", { name: "结果来源" });
  fireEvent.change(source, { target: { value: imported.id } });
  await screen.findByRole("option", { name: "G-001 · 创建商品" });
  await waitFor(() => {
    expect(
      requests.some(
        (p) => p.includes("/results/G-001?") && p.includes(imported.id),
      ),
    ).toBe(true);
  });
  fireEvent.change(screen.getByLabelText("当前范围视图"), {
    target: { value: "metrics" },
  });
  await screen.findByRole("heading", { name: /创建商品 · 本用例指标/ });
  expect(
    requests.some(
      (p) => p.includes("/results/G-001/metrics?") && p.includes(imported.id),
    ),
  ).toBe(true);
  fireEvent.change(screen.getByLabelText("结果来源"), {
    target: { value: "" },
  });
  await waitFor(() => {
    expect(
      screen.queryByRole("option", { name: "G-001 · 创建商品" }),
    ).toBeNull();
  });
});
