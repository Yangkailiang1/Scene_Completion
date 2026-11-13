import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SsdResultsView } from "./SsdResultsView";
import { SsdSourceDialog } from "./SsdSourceDialog";
import { ResultsView } from "../ResultsView";
import { type Bundle } from "./types";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
const ref = {
  document_id: "rr",
  start_line: 2,
  end_line: 2,
  quote: "页面大小最多100。",
  kind: "origin",
};
function fixture(): Bundle {
  const c = (id: string) => ({
    id,
    step_id: "step1",
    target: "data",
    key: "api.data.range",
    label: "数据范围",
    field_id: "field1",
    condition: "页面大小超过100",
    status: "active",
    source_refs: [ref],
  });
  return {
    version: "ssd-case-v1",
    case: { id: "C1", name: "查询商品" },
    steps: [
      {
        id: "step1",
        order: 1,
        kind: "interaction",
        layer: "RR",
        direction: "request",
        sender: { id: "u", name: "商家", type: "human" },
        receiver: { id: "s", name: "商城", type: "service" },
        operation: { name: "查询商品列表", kinds: ["read"] },
        api_id: "API-RR-02",
        entity_ids: ["Product"],
        data: [
          {
            id: "field1",
            name: "pageSize",
            location: "query",
            type: "integer",
            constraints: [{ kind: "maximum", value: 100 }],
            source_refs: [ref],
          },
        ],
        source_refs: [ref],
      },
    ],
    channels: {
      E: { concerns: [c("e1")], scenarios: [], pending: [] },
      G: { concerns: [c("g1")], scenarios: [], pending: [] },
      GT: {
        concerns: [],
        scenarios: [],
        pending: [
          {
            id: "t1",
            condition: "未确认是否异常",
            status: "pending",
            source_refs: [],
          },
        ],
      },
    },
    documents: [
      {
        id: "rr",
        name: "系统需求_spec.md",
        role: "RR",
        content:
          "# 原始需求\n页面大小最多100。\n\n| 字段 | 说明 |\n| --- | --- |\n| pageSize | 分页大小 |",
      },
      {
        id: "sr",
        name: "功能设计_spec.md",
        role: "SR",
        content: "# 服务设计\n服务处理原文。",
      },
    ],
    decisions: [],
    pending: [],
  };
}
const metrics = {
  missing_exception_miss_rate: {
    value: 0,
    numerator: 0,
    denominator: 1,
    status: "适用",
  },
  generation_validity: {
    value: 100,
    numerator: 1,
    denominator: 1,
    status: "适用",
  },
};
const index = {
  version: "ssd-case-v1",
  cases: [{ id: "C1", name: "查询商品", revision: 1, pending_count: 1 }],
  metrics,
};
function response(bundle = fixture(), revision = 1) {
  return {
    bundle,
    revision,
    comparison: {
      concerns: [
        {
          id: "row1",
          step_id: "step1",
          target: "data",
          key: "api.data.range",
          status: "pair",
          reason: "同一对象",
          cells: {
            E: bundle.channels.E.concerns,
            G: bundle.channels.G.concerns,
            GT: [],
          },
        },
      ],
      scenarios: [],
    },
    metrics,
    original_metrics: metrics,
    history: [{ revision: 1, reason: "初始校正", metrics }],
  };
}
function mockApi(handler?: (path: string, init?: RequestInit) => any) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const path = String(url);
    const body =
      handler?.(path, init) ??
      (path.endsWith("ssd-results") ? index : response());
    return { ok: true, json: async () => body } as Response;
  });
}
test("exports the current step across all three record kinds or all cases explicitly", async () => {
  const bundle = fixture();
  bundle.steps.push({ ...bundle.steps[0], id: "step2", order: 2 });
  bundle.channels.E.concerns.push({
    ...bundle.channels.E.concerns[0],
    id: "e2",
    step_id: "step2",
  });
  bundle.channels.G.scenarios.push({
    ...bundle.channels.G.concerns[0],
    id: "gs1",
    concern_ids: ["g1"],
    expected: "拒绝请求",
  });
  bundle.channels.GT.pending[0].step_id = "step1";
  const exported: any[] = [];
  mockApi((path, init) => {
    if (path.endsWith("ssd-review/export")) {
      exported.push(JSON.parse(String(init?.body)));
      return {};
    }
    return path.endsWith("ssd-results") ? index : response(bundle);
  });
  // The export endpoint returns a file rather than the JSON used by mockApi.
  const fetchMock = vi.mocked(globalThis.fetch);
  const baseFetch = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (url, init) => {
    const result = await baseFetch(url, init);
    if (String(url).endsWith("ssd-review/export"))
      return { ...result, blob: async () => new Blob(["review"]) } as Response;
    return result;
  });
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:review"),
    revokeObjectURL: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findAllByText("数据范围");
  fireEvent.change(screen.getByLabelText("交互步骤"), {
    target: { value: "step1" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "导出当前步骤差异 HTML" }),
  );
  await screen.findByText(/已导出可离线编辑/);
  expect(exported[0]).toEqual({
    case_ids: ["C1"],
    record_ids: ["e1", "g1", "gs1", "t1"],
  });
  fireEvent.change(screen.getByLabelText("交互步骤"), {
    target: { value: "" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "导出当前用例差异 HTML" }),
  );
  await waitFor(() => expect(exported).toHaveLength(2));
  expect(exported[1]).toEqual({ case_ids: ["C1"] });
  fireEvent.change(screen.getByLabelText("交互步骤"), {
    target: { value: "step1" },
  });
  fireEvent.click(screen.getByLabelText("导出全部用例（忽略步骤筛选）"));
  await waitFor(() =>
    expect(
      (
        screen.getByRole("button", {
          name: "导出全部用例差异 HTML",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "导出全部用例差异 HTML" }),
  );
  await waitFor(() => expect(exported).toHaveLength(3));
  expect(exported[2]).toEqual({});
});
test("refuses to merge records attached to different entities", async () => {
  const bundle = fixture();
  bundle.channels.E.concerns[0].entity_id = "Product";
  bundle.channels.E.concerns.push({
    ...bundle.channels.E.concerns[0],
    id: "e2",
    entity_id: "Category",
  });
  mockApi(() => response(bundle));
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findAllByText("数据范围");
  screen.getAllByLabelText(/^选择 E /).forEach((el) => fireEvent.click(el));
  fireEvent.click(screen.getAllByRole("button", { name: "合并所选" })[0]);
  expect(screen.getByRole("alert").textContent).toContain(
    "同一步骤、对象、实体和关注点",
  );
  expect(screen.getAllByLabelText(/^选择 E /)).toHaveLength(2);
});
test("edits an SSD step and observation, preserves stable IDs and saves one version", async () => {
  let submitted: any;
  mockApi((path, init) => {
    if (path.endsWith("/revisions")) {
      submitted = JSON.parse(String(init?.body));
      return response(submitted.bundle, 2);
    }
  });
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findAllByText("数据范围");
  fireEvent.click(screen.getByText("SSD 步骤与接口实体映射（1）"));
  fireEvent.click(screen.getByRole("button", { name: "编辑步骤 1" }));
  const stepDialog = screen.getByRole("dialog", { name: "编辑 SSD 步骤" });
  fireEvent.change(within(stepDialog).getByLabelText("交互操作"), {
    target: { value: "修正查询操作" },
  });
  fireEvent.change(within(stepDialog).getByLabelText("接口 API"), {
    target: { value: "API-NEW" },
  });
  fireEvent.change(within(stepDialog).getByLabelText("业务实体（逗号分隔）"), {
    target: { value: "Product,Category" },
  });
  fireEvent.click(
    within(stepDialog).getByRole("button", { name: "应用到草稿" }),
  );
  fireEvent.click(screen.getByLabelText("编辑 E e1"));
  fireEvent.change(screen.getByLabelText("条件或描述"), {
    target: { value: "页面大小大于100" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
  await waitFor(() =>
    expect(submitted?.bundle.steps[0].operation.name).toBe("修正查询操作"),
  );
  expect(submitted.base_revision).toBe(1);
  expect(submitted.bundle.steps[0].id).toBe("step1");
  expect(submitted.bundle.steps[0].api_id).toBe("API-NEW");
  expect(submitted.bundle.steps[0].entity_ids).toEqual(["Product", "Category"]);
  expect(submitted.bundle.channels.E.concerns[0].condition).toBe(
    "页面大小大于100",
  );
  expect(submitted.bundle.documents).toEqual(fixture().documents);
  await screen.findByText(/修订已保存/);
});
test("opens original Markdown and can switch between original RR and SR", async () => {
  render(
    <SsdSourceDialog
      documents={fixture().documents}
      refs={[ref]}
      onClose={() => {}}
    />,
  );
  expect(await screen.findByRole("heading", { name: "原始需求" })).toBeTruthy();
  expect(screen.getByRole("table")).toBeTruthy();
  expect(screen.getByText("页面大小最多100。").className).toContain(
    "source-block-highlighted",
  );
  fireEvent.change(screen.getByLabelText("原文文档"), {
    target: { value: "sr" },
  });
  expect(screen.getByRole("heading", { name: "服务设计" })).toBeTruthy();
});
test("original and historical versions are read only and use the version API", async () => {
  const fetch = mockApi();
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findAllByText("数据范围");
  fireEvent.change(screen.getByLabelText("结果版本"), {
    target: { value: "original" },
  });
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([url]) =>
        String(url).includes("?revision=original"),
      ),
    ).toBe(true),
  );
  await screen.findByText(/正在查看历史快照/);
  expect(screen.queryByLabelText("编辑 E e1")).toBeNull();
  expect(
    (
      screen.getByRole("button", {
        name: "保存修改并重算",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});
test("split and merge preserve origins and pending test records can be corrected", async () => {
  let saved: any;
  mockApi((path, init) => {
    if (path.endsWith("/revisions")) {
      saved = JSON.parse(String(init?.body));
      return response(saved.bundle, 2);
    }
  });
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findAllByText("数据范围");
  fireEvent.click(screen.getByLabelText("拆分 E e1"));
  fireEvent.change(screen.getByLabelText("条件或描述"), {
    target: { value: "第二个独立条件" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  const eChecks = screen.getAllByLabelText(/^选择 E /);
  expect(eChecks).toHaveLength(2);
  eChecks.forEach((c) => fireEvent.click(c));
  fireEvent.click(screen.getAllByRole("button", { name: "合并所选" })[0]);
  expect(screen.getAllByLabelText(/^选择 E /)).toHaveLength(1);
  fireEvent.click(screen.getByRole("tab", { name: "待确认" }));
  fireEvent.click(screen.getByLabelText("编辑 GT t1"));
  fireEvent.change(screen.getByLabelText("异常判定"), {
    target: { value: "active" },
  });
  fireEvent.change(screen.getByLabelText("挂载步骤"), {
    target: { value: "step1" },
  });
  fireEvent.change(screen.getByLabelText("关注点标识"), {
    target: { value: "api.data.range" },
  });
  fireEvent.change(screen.getByLabelText("挂载对象"), {
    target: { value: "data" },
  });
  fireEvent.change(screen.getByLabelText("挂载字段"), {
    target: { value: "field1" },
  });
  fireEvent.change(screen.getByLabelText("预期结果"), {
    target: { value: "返回参数错误" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
  await waitFor(() => expect(saved).toBeTruthy());
  expect(saved.bundle.channels.E.concerns).toHaveLength(1);
  expect(saved.bundle.channels.E.concerns[0].source_refs).toEqual([ref]);
  expect(saved.bundle.channels.GT.pending).toHaveLength(1);
  expect(saved.bundle.channels.GT.pending[0]).toMatchObject({
    id: "t1",
    status: "active",
    step_id: "step1",
    target: "data",
    field_id: "field1",
    key: "api.data.range",
    expected: "返回参数错误",
  });
  expect(saved.bundle.channels.GT.concerns).toHaveLength(0);
});
test("409 keeps the draft instead of discarding a business correction", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (url) =>
      ({
        ok: !String(url).endsWith("/revisions"),
        status: 409,
        json: async () =>
          String(url).endsWith("/revisions")
            ? { detail: { message: "版本已变化", current_revision: 2 } }
            : response(),
      }) as Response,
  );
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findAllByText("数据范围");
  fireEvent.click(screen.getByLabelText("编辑 E e1"));
  fireEvent.change(screen.getByLabelText("条件或描述"), {
    target: { value: "保留我的修订" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("版本已变化"),
  );
  expect(screen.getByText("保留我的修订")).toBeTruthy();
});
test("feedback is previewed before applying selected nonconflicting cases", async () => {
  let applied: any;
  mockApi((path, init) => {
    if (path.endsWith("/preview"))
      return {
        cases: [
          {
            case_id: "C1",
            name: "查询商品",
            status: "ready",
            changes: [
              { path: "steps/step1/operation", before: "旧", after: "新" },
            ],
            conflicts: [],
          },
          {
            case_id: "C2",
            name: "创建商品",
            status: "conflict",
            changes: [],
            conflicts: ["版本已变化"],
          },
        ],
      };
    if (path.endsWith("/apply")) {
      applied = JSON.parse(String(init?.body));
      return {
        cases: [
          { case_id: "C1", name: "查询商品", status: "applied", changes: [] },
        ],
      };
    }
  });
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findAllByText("数据范围");
  fireEvent.click(screen.getByText("回收业务审核修改"));
  const file = new File(["feedback"], "review.html", { type: "text/html" });
  Object.defineProperty(file, "text", { value: async () => "feedback" });
  fireEvent.change(screen.getByLabelText("导入业务审核文件"), {
    target: { files: [file] },
  });
  await screen.findByLabelText("应用 查询商品");
  expect(applied).toBeUndefined();
  expect(
    (screen.getByLabelText("应用 创建商品") as HTMLInputElement).disabled,
  ).toBe(true);
  fireEvent.click(
    screen.getByRole("button", { name: "应用选定用例修改并重算" }),
  );
  await waitFor(() => expect(applied.case_ids).toEqual(["C1"]));
  expect(applied.content).toBe("feedback");
});

test("live progress updates keep unsaved edits in the modern result page", async () => {
  const fetch = mockApi((path) => {
    if (path.includes("/results?")) return { cases: [], artifacts: [] };
  });
  const view = render(<ResultsView project="P1" liveVersion="1" />);
  await screen.findByLabelText("编辑 E e1");
  fireEvent.click(screen.getByLabelText("编辑 E e1"));
  fireEvent.change(screen.getByLabelText("条件或描述"), {
    target: { value: "未保存但必须保留的修改" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  const before = fetch.mock.calls.filter(([url]) =>
    String(url).endsWith("ssd-results"),
  ).length;
  view.rerender(<ResultsView project="P1" liveVersion="2" />);
  await waitFor(() =>
    expect(
      fetch.mock.calls.filter(([url]) => String(url).endsWith("ssd-results"))
        .length,
    ).toBeGreaterThan(before),
  );
  expect(screen.getByText("未保存但必须保留的修改")).toBeTruthy();
  expect(screen.getByText(/有尚未保存的修改/)).toBeTruthy();
});

test("adds and reorders steps and submits a manual matching decision", async () => {
  let submitted: any;
  mockApi((path, init) => {
    if (path.endsWith("/revisions")) {
      submitted = JSON.parse(String(init?.body));
      return response(submitted.bundle, 2);
    }
  });
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findByLabelText("编辑 E e1");
  fireEvent.click(screen.getByText("SSD 步骤与接口实体映射（1）"));
  fireEvent.click(screen.getByRole("button", { name: "新增 SSD 步骤" }));
  fireEvent.change(screen.getByLabelText("交互操作"), {
    target: { value: "补充查询步骤" },
  });
  fireEvent.change(screen.getByLabelText("发送方已有参与者"), {
    target: { value: "u" },
  });
  fireEvent.change(screen.getByLabelText("接收方已有参与者"), {
    target: { value: "s" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  fireEvent.click(screen.getByLabelText("上移步骤 2"));
  fireEvent.click(screen.getByText("匹配判定（0）"));
  fireEvent.click(screen.getByRole("button", { name: "添加匹配判定" }));
  fireEvent.change(screen.getByLabelText("匹配粒度"), {
    target: { value: "concern" },
  });
  fireEvent.change(screen.getByLabelText("方法生成记录"), {
    target: { value: "g1" },
  });
  fireEvent.change(screen.getByLabelText("原文抽取记录"), {
    target: { value: "e1" },
  });
  fireEvent.change(screen.getByLabelText("匹配判定"), {
    target: { value: "partial" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
  await waitFor(() => expect(submitted).toBeTruthy());
  expect(submitted.bundle.steps[0].operation.name).toBe("补充查询步骤");
  expect(submitted.bundle.steps[0].order).toBe(1);
  expect(submitted.bundle.steps[1].id).toBe("step1");
  expect(submitted.bundle.decisions[0]).toMatchObject({
    level: "concern",
    pair: "G_E",
    left_id: "g1",
    right_id: "e1",
    status: "partial",
    origin: "manual",
  });
});

test("incomplete semantic comparisons are visible and can be manually adjudicated", async () => {
  const bundle = fixture();
  bundle.channels.G.scenarios = [
    {
      ...bundle.channels.G.concerns[0],
      id: "gs1",
      condition: "生成条件",
      expected: "",
      concern_ids: ["g1"],
    },
  ];
  bundle.channels.E.scenarios = [
    {
      ...bundle.channels.E.concerns[0],
      id: "es1",
      condition: "原文条件",
      expected: "拒绝请求",
      concern_ids: ["e1"],
    },
  ];
  bundle.semantic_pending = [
    { pair: "G_E", left_id: "gs1", right_id: "es1", step_id: "step1" },
  ];
  mockApi(() => ({
    ...response(bundle),
    completeness: {
      complete: false,
      pending_records: 1,
      pending_case_items: 0,
      revision_issues: 0,
      semantic_pairs: 1,
    },
  }));
  render(<SsdResultsView project="P1" initialIndex={index} />);
  expect(
    await screen.findByText("当前为部分结果，尚有内容待确认。"),
  ).toBeTruthy();
  expect(screen.getByText(/未完成的语义比较不视为已判定不匹配/)).toBeTruthy();
  fireEvent.click(screen.getByText("尚未完成的语义比较（1 对）"));
  expect(screen.getByText("方法生成：生成条件")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "人工判定此对" }));
  expect(
    (screen.getByLabelText("方法生成记录") as HTMLSelectElement).value,
  ).toBe("gs1");
  expect(
    (screen.getByLabelText("原文抽取记录") as HTMLSelectElement).value,
  ).toBe("es1");
});
