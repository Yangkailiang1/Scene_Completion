import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SsdResultsView } from "./SsdResultsView";
import { invalidateResults } from "../shared/resultRequests";
import { SsdSourceDialog } from "./SsdSourceDialog";
import { ResultsView } from "../ResultsView";
import { type Bundle } from "./types";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  invalidateResults();
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
test("keeps every case and SSD step in the original comparison navigation", async () => {
  const bundle = fixture();
  bundle.steps.push({
    ...structuredClone(bundle.steps[0]),
    id: "empty-local-step",
    order: 2,
    kind: "action",
    layer: "SR",
    api_id: null,
    operation: { name: "本地校验，没有异常记录", kinds: [] },
    data: [],
  });
  const second = fixture();
  second.case = { id: "C2", name: "创建商品" };
  second.steps[0].operation.name = "创建商品交互";
  second.channels.E.concerns[0].condition = "创建商品的原文异常";
  const multiple = {
    ...index,
    cases: [{ id: "C2", name: "创建商品" }, ...index.cases],
  };
  mockApi((path) =>
    path.endsWith("ssd-results")
      ? multiple
      : path.includes("/results/C2/")
        ? response(second)
        : response(bundle),
  );
  render(<SsdResultsView project="P1" initialIndex={multiple} />);
  await screen.findByLabelText("编辑 E e1");
  expect((screen.getByLabelText("结果用例") as HTMLSelectElement).value).toBe(
    "C1",
  );
  expect(
    within(screen.getByLabelText("结果用例")).getAllByRole("option"),
  ).toHaveLength(2);
  const navigation = screen.getByLabelText("结果交互步骤");
  expect(
    within(navigation).getByRole("button", { name: /查询商品列表/ }),
  ).toBeTruthy();
  fireEvent.click(
    within(navigation).getByRole("button", { name: /本地校验，没有异常记录/ }),
  );
  expect(screen.getByText("当前步骤及筛选下没有关注点记录。")).toBeTruthy();
  expect(screen.queryByLabelText("编辑 E e1")).toBeNull();
  expect(screen.getAllByText("本地校验，没有异常记录")).toHaveLength(2);
  fireEvent.click(
    within(navigation).getByRole("button", { name: /查询商品列表/ }),
  );
  const row = screen.getByLabelText("编辑 E e1").closest("tr")!;
  expect(within(row).getAllByRole("cell")).toHaveLength(5);
  expect(within(row).getByLabelText("编辑 G g1")).toBeTruthy();
  fireEvent.click(
    within(row).getAllByRole("button", { name: /查看原始出处/ })[0],
  );
  expect(await screen.findByRole("heading", { name: "原始需求" })).toBeTruthy();
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "关闭原文",
    }),
  );
  fireEvent.change(screen.getByLabelText("结果用例"), {
    target: { value: "C2" },
  });
  await screen.findByText("创建商品的原文异常");
  expect(
    screen.queryByRole("button", { name: /本地校验，没有异常记录/ }),
  ).toBeNull();
});

test("deleting a step retains its observations in the unbound comparison", async () => {
  const bundle = fixture();
  bundle.channels.GT.pending = [];
  let submitted: any;
  mockApi((path, init) => {
    if (path.endsWith("/revisions")) {
      submitted = JSON.parse(String(init?.body));
      return response(submitted.bundle, 2);
    }
    return path.endsWith("ssd-results") ? index : response(bundle);
  });
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findByLabelText("编辑 E e1");
  fireEvent.click(
    screen.getByText("数据属性、接口实体映射、步骤编辑及原文依据"),
  );
  fireEvent.click(screen.getByRole("button", { name: "删除步骤 1" }));
  expect(screen.getByLabelText("编辑 E e1")).toBeTruthy();
  expect(screen.getByLabelText("编辑 G g1")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
  await waitFor(() => expect(submitted).toBeTruthy());
  expect(submitted.bundle.steps).toEqual([]);
  expect(submitted.bundle.channels.E.concerns[0]).toEqual(
    bundle.channels.E.concerns[0],
  );
  expect(submitted.bundle.documents).toEqual(bundle.documents);
});

test("opens existing business review with the selected case and step and protects a draft", async () => {
  mockApi();
  const onReviewRequest = vi.fn();
  render(
    <SsdResultsView
      project="P1"
      initialIndex={index}
      onReviewRequest={onReviewRequest}
    />,
  );
  await screen.findByLabelText("编辑 E e1");
  fireEvent.click(screen.getByRole("button", { name: "展开工具栏" }));
  fireEvent.click(screen.getByRole("button", { name: "交给业务审核" }));
  expect(onReviewRequest).toHaveBeenCalledWith({
    scope: "interaction",
    caseId: "C1",
    stepId: "step1",
    differencesOnly: true,
  });
  expect(screen.queryByText("导出差异审核 HTML")).toBeNull();
  fireEvent.click(screen.getByLabelText("编辑 E e1"));
  fireEvent.change(screen.getByLabelText("条件或描述"), {
    target: { value: "尚未保存的审核修改" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  fireEvent.click(screen.getByRole("button", { name: "交给业务审核" }));
  expect(onReviewRequest).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("alert").textContent).toContain(
    "请先保存或放弃当前草稿",
  );
  expect(screen.getByText("尚未保存的审核修改")).toBeTruthy();
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
  fireEvent.click(screen.getByText("原文抽取操作"));
  fireEvent.click(screen.getAllByRole("button", { name: /^合并所选/ })[0]);
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
  fireEvent.click(
    screen.getByText("数据属性、接口实体映射、步骤编辑及原文依据"),
  );
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
test("Excel provenance opens as a worksheet and precisely highlights the cited cells", () => {
  const name = "原始测试.xlsx#测试用例";
  const content = Array.from({ length: 121 }, (_, i) =>
    i === 119
      ? "| GT-01 | 需要\\|校验<br>第二行 |  | <img src=unsafe> |"
      : i === 0
        ? "| 编号 | 条件 | 预期 | 备注 |"
        : "",
  ).join("\n");
  render(
    <SsdSourceDialog
      documents={[
        {
          id: "json",
          name: "recovered_usecases.json",
          role: "test",
          content: "{}",
        },
        { id: "excel", name, role: "test", content },
      ]}
      refs={[
        {
          document_id: "json",
          start_line: 1,
          end_line: 1,
          quote: "{}",
          kind: "test",
          origin: {
            document: name,
            start_line: 120,
            end_line: 120,
            match: "exact",
            sheet: "测试用例",
            cell_range: "B120:C120",
          },
        },
      ]}
      onClose={() => {}}
    />,
  );
  const table = screen.getByRole("table", { name: "测试用例 工作表" });
  expect(within(table).getByRole("columnheader", { name: "C" })).toBeTruthy();
  expect(within(table).getByRole("rowheader", { name: "120" })).toBeTruthy();
  expect(table.querySelector('[data-cell="B120"]')?.textContent).toBe(
    "需要|校验\n第二行",
  );
  expect(table.querySelector('[data-cell="C120"]')?.textContent).toBe("");
  expect(
    Array.from(
      table.querySelectorAll<HTMLElement>(".source-sheet-highlight"),
      (cell) => cell.dataset.cell,
    ),
  ).toEqual(["B120", "C120"]);
  expect(table.querySelector("img")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "上一段" }));
  expect(screen.getByRole("rowheader", { name: "1" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "返回引用" }));
  expect(screen.getByRole("rowheader", { name: "120" })).toBeTruthy();
});

test("the source dialog jumps to a manually added origin among recorded ones", async () => {
  const manual = {
    document_id: "sr",
    start_line: 2,
    end_line: 2,
    quote: "服务处理原文。",
    kind: "origin",
    origin: "manual",
  };
  render(
    <SsdSourceDialog
      documents={fixture().documents}
      refs={[ref, manual]}
      onClose={() => {}}
    />,
  );
  expect(await screen.findByRole("heading", { name: "原始需求" })).toBeTruthy();
  const positions = screen.getByLabelText<HTMLSelectElement>("来源位置");
  // RR/SR stays first; the manual origin is offered as a one-click jump instead.
  const options = Array.from(positions.options).map((o) => o.textContent);
  expect(options[0]).toContain("系统需求_spec.md");
  expect(options[1]).toContain("（人工补录）");
  fireEvent.click(
    screen.getByRole("button", { name: "跳到人工补录出处（1）" }),
  );
  expect(positions.selectedOptions[0].textContent).toContain(
    "功能设计_spec.md",
  );
  expect(positions.selectedOptions[0].textContent).toContain("第 2–2 行");
  expect(screen.getByRole("heading", { name: "服务设计" })).toBeTruthy();
});
test("original and historical versions are read only and use the version API", async () => {
  const fetch = mockApi();
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findAllByText("数据范围");
  fireEvent.click(screen.getByRole("button", { name: "展开工具栏" }));
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
  await screen.findByText(/历史快照 · 只读/);
  expect(screen.queryByLabelText("编辑 E e1")).toBeNull();
  expect(screen.queryByRole("button", { name: "保存修改并重算" })).toBeNull();
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
  fireEvent.click(
    within(screen.getByLabelText("编辑 E e1").closest("article")!).getByText(
      "记录详情与更多操作",
    ),
  );
  fireEvent.click(screen.getByLabelText("拆分 E e1"));
  fireEvent.change(screen.getByLabelText("条件或描述"), {
    target: { value: "第二个独立条件" },
  });
  fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
  const eChecks = screen.getAllByLabelText(/^选择 E /);
  expect(eChecks).toHaveLength(2);
  eChecks.forEach((c) => fireEvent.click(c));
  fireEvent.click(screen.getByText("原文抽取操作"));
  fireEvent.click(screen.getAllByRole("button", { name: /^合并所选/ })[0]);
  expect(screen.getAllByLabelText(/^选择 E /)).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: /待定位／本轮不计分/ }));
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
test("unbound navigation restores each regular result layer without reloading", async () => {
  const data = fixture();
  data.channels.G.scenarios = [
    { ...data.channels.G.concerns[0], id: "g-scenario", concern_ids: ["g1"] },
  ];
  const fetch = mockApi((path) =>
    path.includes("/editor?") ? response(data) : undefined,
  );
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findByLabelText("编辑 G g1");
  const step = within(screen.getByLabelText("结果交互步骤")).getByRole(
    "button",
    { name: /查询商品列表/ },
  );
  const goUnbound = () =>
    fireEvent.click(screen.getByRole("button", { name: /待定位／本轮不计分/ }));
  goUnbound();
  expect(screen.getByLabelText("编辑 GT t1")).toBeTruthy();
  fireEvent.click(screen.getByLabelText("只看不一致"));
  fireEvent.click(step);
  expect(screen.getByLabelText("编辑 G g1")).toBeTruthy();
  expect(
    (screen.getByLabelText("只看不一致") as HTMLInputElement).checked,
  ).toBe(false);
  fireEvent.click(screen.getByRole("tab", { name: /场景层/ }));
  goUnbound();
  fireEvent.click(step);
  expect(screen.getByLabelText("编辑 G g-scenario")).toBeTruthy();
  expect(
    fetch.mock.calls.filter(([url]) => String(url).includes("/editor")),
  ).toHaveLength(1);
});

test("locating a pending GT record reuses the concern and drafts a cross-step match", async () => {
  const data = fixture();
  data.steps.push({
    ...data.steps[0],
    id: "step2",
    order: 2,
    operation: { name: "校验分页限制", kinds: [] },
  });
  const generated = {
    ...data.channels.G.concerns[0],
    id: "g-range",
    step_id: "step2",
    entity_id: "Product",
    attribute: "pageSize",
    obligation_scope: ["query"],
  };
  data.channels.G.concerns.push(generated);
  data.channels.G.scenarios = [
    {
      ...generated,
      id: "g-range-exceeded",
      concern_ids: [generated.id],
      expected: "拒绝超出范围的查询",
    },
  ];
  data.channels.GT.concerns = [
    { ...generated, id: "gt-range-existing", source_refs: [] },
    { ...generated, id: "gt-other", attribute: "pageNumber" },
  ];
  data.channels.GT.pending[0] = {
    ...data.channels.GT.pending[0],
    condition: "页大小为101时测试失败",
    expected: "HTTP 400",
    failure_step_id: "step1",
    binding_issue: "未定位字段",
    source_refs: [ref],
  };
  let saved: any;
  mockApi((path, init) => {
    if (path.endsWith("/revisions")) {
      saved = JSON.parse(String(init?.body));
      return response(saved.bundle, 2);
    }
    if (path.includes("/editor?")) return response(data);
  });
  render(<SsdResultsView project="P1" initialIndex={index} />);
  const goToPending = () =>
    fireEvent.click(screen.getByRole("button", { name: /待定位／本轮不计分/ }));
  const locate = () =>
    fireEvent.click(screen.getByLabelText("定位并匹配 GT t1"));
  await screen.findByLabelText("编辑 G g1");
  goToPending();
  locate();
  const dialog = within(
    screen.getByRole("dialog", { name: "定位并匹配已有关注点" }),
  );
  expect(
    dialog.getByRole<HTMLButtonElement>("button", { name: "应用到草稿" })
      .disabled,
  ).toBe(true);
  fireEvent.change(dialog.getByLabelText("定位到已有步骤"), {
    target: { value: "step2" },
  });
  expect(
    dialog.getByRole("option", { name: /方法生成.*数据范围.*query.pageSize/ }),
  ).toBeTruthy();
  fireEvent.change(dialog.getByLabelText("匹配已有关注点"), {
    target: { value: "G:g-range" },
  });
  fireEvent.change(dialog.getByLabelText("匹配已有场景（可选）"), {
    target: { value: "g-range-exceeded" },
  });
  fireEvent.change(dialog.getByLabelText("场景匹配判定"), {
    target: { value: "partial" },
  });
  fireEvent.change(dialog.getByLabelText("匹配说明（可选）"), {
    target: { value: "现场验证了上界" },
  });
  fireEvent.click(dialog.getByRole("button", { name: "应用到草稿" }));
  expect(screen.getByText(/已定位并应用到草稿/)).toBeTruthy();
  const moved = screen.getByLabelText("GT t1 条件或描述");
  expect(moved.textContent).toBe("页大小为101时测试失败");
  expect(
    within(moved.closest("tr")!).getByText(/GT_G · 部分匹配/),
  ).toBeTruthy();
  expect(screen.queryByLabelText("定位并匹配 GT t1")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
  await waitFor(() => expect(saved?.base_revision).toBe(1));
  expect(saved.bundle.channels.GT.pending).toEqual([]);
  expect(saved.bundle.channels.GT.concerns).toHaveLength(2);
  expect(saved.bundle.channels.GT.concerns[0].source_refs).toEqual([ref]);
  expect(saved.bundle.channels.GT.scenarios).toEqual([
    expect.objectContaining({
      id: "t1",
      step_id: "step2",
      failure_step_id: "step1",
      field_id: "field1",
      attribute: "pageSize",
      concern_ids: ["gt-range-existing"],
      condition: "页大小为101时测试失败",
      expected: "HTTP 400",
      status: "active",
      source_refs: [ref],
    }),
  ]);
  expect(saved.bundle.channels.GT.scenarios[0].binding_issue).toBeUndefined();
  expect(saved.bundle.decisions).toEqual([
    expect.objectContaining({
      pair: "GT_G",
      level: "concern",
      left_id: "gt-range-existing",
      right_id: "g-range",
      status: "full",
      origin: "manual",
    }),
    expect.objectContaining({
      pair: "GT_G",
      level: "scenario",
      left_id: "t1",
      right_id: "g-range-exceeded",
      status: "partial",
      origin: "manual",
      reason: "现场验证了上界",
    }),
  ]);
});

test("a pending record can be located without asserting scenario coverage, and undone", async () => {
  const data = fixture();
  data.channels.GT.pending[0].expected = "显示错误提示";
  mockApi((path) => (path.includes("/editor?") ? response(data) : undefined));
  render(<SsdResultsView project="P1" initialIndex={index} />);
  const pending = () =>
    fireEvent.click(screen.getByRole("button", { name: /待定位／本轮不计分/ }));
  const locate = () =>
    fireEvent.click(screen.getByLabelText("定位并匹配 GT t1"));
  await screen.findByLabelText("编辑 G g1");
  pending();
  locate();
  fireEvent.click(screen.getByRole("button", { name: "取消编辑" }));
  expect(screen.queryByRole("button", { name: "保存修改并重算" })).toBeNull();
  locate();
  const dialog = within(
    screen.getByRole("dialog", { name: "定位并匹配已有关注点" }),
  );
  fireEvent.change(dialog.getByLabelText("定位到已有步骤"), {
    target: { value: "step1" },
  });
  fireEvent.change(dialog.getByLabelText("匹配已有关注点"), {
    target: { value: "G:g1" },
  });
  expect(dialog.getByLabelText("匹配已有场景（可选）")).toHaveProperty(
    "value",
    "",
  );
  fireEvent.click(dialog.getByRole("button", { name: "应用到草稿" }));
  expect(screen.getByText(/匹配判定修改 1 条/)).toBeTruthy();
  expect(screen.queryByLabelText("定位并匹配 GT t1")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "撤销草稿修改" }));
  pending();
  expect(screen.getByLabelText("定位并匹配 GT t1")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "保存修改并重算" })).toBeNull();
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
    ).toBe(before),
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
  fireEvent.click(
    screen.getByText("数据属性、接口实体映射、步骤编辑及原文依据"),
  );
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
  fireEvent.click(
    screen.getByText("数据属性、接口实体映射、步骤编辑及原文依据"),
  );
  fireEvent.click(screen.getByLabelText("上移步骤 2"));
  fireEvent.click(
    within(screen.getByLabelText("结果交互步骤")).getByRole("button", {
      name: /查询商品列表/,
    }),
  );
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
    await screen.findByText(/当前为部分结果 · 待修正记录 1 项/),
  ).toBeTruthy();
  fireEvent.click(screen.getByText(/当前为部分结果 · 待修正记录 1 项/));
  expect(screen.getByText(/未完成的语义比较不视为已判定不匹配/)).toBeTruthy();
  fireEvent.click(screen.getByText(/尚未完成的语义比较（1 对）/));
  expect(screen.getByText("方法生成：生成条件")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "查看详情" }));
  expect(
    (screen.getByLabelText("方法生成记录") as HTMLSelectElement).value,
  ).toBe("gs1");
  expect(
    (screen.getByLabelText("原文抽取记录") as HTMLSelectElement).value,
  ).toBe("es1");
});

function matchingFixture() {
  const bundle = fixture();
  bundle.channels.GT.pending = [];
  for (const ch of ["G", "E"] as const)
    bundle.channels[ch].scenarios = [1, 2].map((n) => ({
      ...bundle.channels[ch].concerns[0],
      id: ch + "s" + n,
      condition: ch + "失败条件" + n,
      expected: "拒绝",
      concern_ids: [ch === "G" ? "g1" : "e1"],
    }));
  bundle.semantic_pending = [1, 2].map((n) => ({
    pair: "G_E",
    left_id: "Gs" + n,
    right_id: "Es" + n,
    step_id: "step1",
  }));
  return bundle;
}
function card(n: number) {
  return screen.getByRole("article", { name: "配对 G_E Gs" + n + " Es" + n });
}
test("two individual quick matches update counts, pending cards and table drafts without opening details", async () => {
  const bundle = matchingFixture();
  const onDirty = vi.fn();
  mockApi(() => response(bundle));
  render(
    <SsdResultsView
      project="P1"
      initialIndex={index}
      onDirtyChange={onDirty}
    />,
  );
  await screen.findByText(/尚未完成的语义比较（2 对）/);
  fireEvent.click(screen.getByText(/尚未完成的语义比较（2 对）/));
  fireEvent.click(within(card(1)).getByRole("button", { name: "确认匹配" }));
  fireEvent.click(within(card(2)).getByRole("button", { name: "确认匹配" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByText(/匹配判定修改 2 条 · 其他修改 0 项/)).toBeTruthy();
  expect(within(card(1)).getByText("已匹配 · 未保存")).toBeTruthy();
  expect(
    screen.getByText(/尚未完成的语义比较（0 对） · 本次已判定 2 对/),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: /^场景层/ }));
  expect(screen.getAllByText(/G_E · 已匹配 · 未保存/).length).toBeGreaterThan(
    0,
  );
  fireEvent.click(
    within(card(1)).getByRole("button", { name: "取消本次匹配" }),
  );
  expect(screen.getByText(/匹配判定修改 1 条/)).toBeTruthy();
  expect(within(card(2)).getByText("已匹配 · 未保存")).toBeTruthy();
  fireEvent.click(
    within(card(2)).getByRole("button", { name: "取消本次匹配" }),
  );
  expect(screen.queryByRole("button", { name: "保存修改并重算" })).toBeNull();
  expect(within(card(1)).getByText("待判定")).toBeTruthy();
  await waitFor(() => expect(onDirty).toHaveBeenLastCalledWith(false));
});
test.each(["full", "partial", "none"])(
  "detail %s applies immediately to the same card and can be undone",
  async (status) => {
    const bundle = matchingFixture();
    mockApi(() => response(bundle));
    render(<SsdResultsView project="P1" initialIndex={index} />);
    await screen.findByText(/尚未完成的语义比较（2 对）/);
    fireEvent.click(screen.getByText(/尚未完成的语义比较（2 对）/));
    fireEvent.click(within(card(1)).getByRole("button", { name: "查看详情" }));
    fireEvent.change(screen.getByLabelText("匹配判定"), {
      target: { value: status },
    });
    fireEvent.change(screen.getByLabelText("匹配说明"), {
      target: { value: "核对后的人工依据" },
    });
    fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(within(card(1)).getByText("核对后的人工依据")).toBeTruthy();
    expect(
      within(card(1)).getByText(
        ({ full: "已匹配", partial: "部分匹配", none: "不匹配" }[status] ||
          "") + " · 未保存",
      ),
    ).toBeTruthy();
    expect(screen.getByText(/匹配判定修改 1 条/)).toBeTruthy();
    fireEvent.click(within(card(1)).getByRole("button", { name: "查看详情" }));
    fireEvent.click(screen.getByRole("button", { name: "应用到草稿" }));
    expect(
      screen.getByText("该条判定与当前内容一致，没有新增修改。"),
    ).toBeTruthy();
    fireEvent.click(within(card(1)).getByRole("button", { name: "查看详情" }));
    fireEvent.click(screen.getByRole("button", { name: "取消编辑" }));
    expect(screen.getByText(/匹配判定修改 1 条/)).toBeTruthy();
    fireEvent.click(
      within(card(1)).getByRole("button", {
        name: status === "none" ? "取消本次判定" : "取消本次匹配",
      }),
    );
    expect(screen.queryByRole("button", { name: "保存修改并重算" })).toBeNull();
  },
);
test.each([409, 500])(
  "save failure %s retains both match drafts; an in-flight save locks edits and successful save resets counts",
  async (status) => {
    const bundle = matchingFixture();
    let savedBundle = bundle;
    let revision = 1;
    let submit: ((value: any) => void) | undefined;
    const fetch = mockApi((path) =>
      path.endsWith("ssd-results") ? index : response(savedBundle, revision),
    );
    fetch.mockImplementation(async (url, init) => {
      if (init?.method === "POST" && String(url).endsWith("revisions"))
        return await new Promise((resolve) => {
          submit = resolve;
        });
      return {
        ok: true,
        json: async () =>
          String(url).endsWith("ssd-results")
            ? index
            : response(savedBundle, revision),
      } as Response;
    });
    render(<SsdResultsView project="P1" initialIndex={index} />);
    await screen.findByText(/尚未完成的语义比较（2 对）/);
    fireEvent.click(screen.getByText(/尚未完成的语义比较（2 对）/));
    for (const n of [1, 2])
      fireEvent.click(
        within(card(n)).getByRole("button", { name: "确认匹配" }),
      );
    fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
    await waitFor(() => expect(submit).toBeTypeOf("function"));
    expect(
      within(card(1))
        .getByRole("button", { name: "取消本次匹配" })
        .closest("fieldset")?.disabled,
    ).toBe(true);
    submit!({
      ok: false,
      status,
      json: async () => ({
        detail: { message: "修订冲突", current_revision: 2 },
      }),
    });
    await screen.findByText(/草稿仍保留/);
    expect(screen.getByText(/匹配判定修改 2 条/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
    await waitFor(() =>
      expect(
        fetch.mock.calls.filter(([, init]) => init?.method === "POST"),
      ).toHaveLength(2),
    );
    const request = fetch.mock.calls
      .filter(([, init]) => init?.method === "POST")
      .at(-1)!;
    savedBundle = JSON.parse(request[1]!.body as string).bundle;
    revision = 2;
    savedBundle.semantic_pending = [];
    expect(savedBundle.decisions).toHaveLength(2);
    submit!({ ok: true, json: async () => response(savedBundle, revision) });
    await screen.findByText(/修订已保存/);
    expect(screen.queryByRole("button", { name: "保存修改并重算" })).toBeNull();
  },
);

test("a manually added record keeps the origin picked from snapshot documents", async () => {
  const bundle = fixture();
  bundle.documents.unshift({
    id: "json",
    name: "api_extraction.json",
    role: "intermediate",
    content: '{\n  "apis": [],\n  "note": "页面大小上限100"\n}',
  });
  let submitted: any;
  mockApi((path, init) => {
    if (path.endsWith("/revisions")) {
      submitted = JSON.parse(String(init?.body));
      return response(submitted.bundle, 2);
    }
    return path.endsWith("ssd-results") ? index : response(bundle);
  });
  render(<SsdResultsView project="P1" initialIndex={index} />);
  await screen.findByLabelText("编辑 E e1");
  // The pending record is where a reviewer adds an abnormal item.
  fireEvent.click(screen.getByRole("button", { name: /待定位／本轮不计分/ }));
  fireEvent.click(screen.getByLabelText("编辑 GT t1"));
  const dialog = await screen.findByRole("dialog", {
    name: "编辑测试逆向待确认项",
  });
  // The editor opens from the currently loaded snapshot; wait until the document
  // list of this case (which includes the JSON artifact) backs it.
  await waitFor(() =>
    expect(
      within(dialog)
        .getByLabelText("来源文件")
        .querySelector('option[value="json"]'),
    ).toBeTruthy(),
  );
  const withinDialog = within(dialog);
  // A new origin starts empty; the editor says so instead of implying a source.
  expect(withinDialog.getByText(/尚无出处/)).toBeTruthy();
  fireEvent.change(withinDialog.getByLabelText("来源文件"), {
    target: { value: "json" },
  });
  expect(
    withinDialog.getByRole<HTMLButtonElement>("button", { name: "添加出处" })
      .disabled,
  ).toBe(true);
  // Out-of-range lines are refused instead of saving an origin that cannot open.
  fireEvent.change(withinDialog.getByLabelText("起始行"), {
    target: { value: "9" },
  });
  expect(withinDialog.getByText(/起始行需在 1–4 之间/)).toBeTruthy();
  fireEvent.change(withinDialog.getByLabelText("起始行"), {
    target: { value: "2" },
  });
  fireEvent.change(withinDialog.getByLabelText("结束行"), {
    target: { value: "3" },
  });
  // The preview names exactly the lines that will be cited.
  expect(
    withinDialog.getByText(/预览：api_extraction\.json · 第 2–3 行/),
  ).toBeTruthy();
  fireEvent.click(withinDialog.getByRole("button", { name: /添加出处/ }));
  expect(withinDialog.getByText(/第 2–3 行/)).toBeTruthy();
  fireEvent.change(withinDialog.getByLabelText("挂载步骤"), {
    target: { value: "step1" },
  });
  fireEvent.change(withinDialog.getByLabelText("挂载对象"), {
    target: { value: "receiver" },
  });
  fireEvent.change(withinDialog.getByLabelText("关注点标识"), {
    target: { value: "api.data.range" },
  });
  fireEvent.change(withinDialog.getByLabelText("条件或描述"), {
    target: { value: "分页上限被绕过" },
  });
  fireEvent.change(withinDialog.getByLabelText("预期结果"), {
    target: { value: "拒绝请求" },
  });
  const quoted = bundle.documents[0].content
    .split("\n")
    .slice(1, 3)
    .join("\n")
    .trim();
  fireEvent.click(withinDialog.getByRole("button", { name: "应用到草稿" }));
  fireEvent.click(screen.getByRole("button", { name: "保存修改并重算" }));
  await waitFor(() => expect(submitted).toBeTruthy());
  const added = submitted.bundle.channels.GT.pending.find(
    (r: any) => r.condition === "分页上限被绕过",
  );
  expect(added.source_refs).toEqual([
    {
      document_id: "json",
      start_line: 2,
      end_line: 3,
      quote: quoted,
      kind: "origin",
      origin: "manual",
    },
  ]);
  // The pinned originals are still untouched by the manual edit.
  expect(submitted.bundle.documents).toEqual(bundle.documents);
});

test("applying a concern draft includes filled provenance and opens it immediately", async () => {
  const bundle = fixture();
  bundle.channels.G.concerns[0].source_refs = [];
  mockApi((path) => (path.includes("/editor?") ? response(bundle) : undefined));
  render(<SsdResultsView project="P1" initialIndex={index} />);
  fireEvent.click(await screen.findByLabelText("编辑 G g1"));
  const editor = within(screen.getByRole("dialog"));
  fireEvent.change(editor.getByLabelText("来源文件"), {
    target: { value: "sr" },
  });
  fireEvent.change(editor.getByLabelText("起始行"), { target: { value: "2" } });
  fireEvent.change(editor.getByLabelText("结束行"), { target: { value: "3" } });
  expect(
    editor.getByRole<HTMLButtonElement>("button", { name: "应用到草稿" })
      .disabled,
  ).toBe(true);
  fireEvent.change(editor.getByLabelText("结束行"), { target: { value: "" } });
  fireEvent.click(editor.getByRole("button", { name: "应用到草稿" }));
  const record = screen
    .getByLabelText("编辑 G g1")
    .closest(".ssd-record")! as HTMLElement;
  fireEvent.click(
    within(record).getByRole("button", { name: /查看原始出处.*1/ }),
  );
  expect(await screen.findByText("服务处理原文。")).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "跳到人工补录出处（1）" }),
  ).toBeTruthy();
});

test("groups cross-step evidence under each G row and unlinks one match independently", async () => {
  const bundle = fixture();
  bundle.coverage_policy = "coverage-g-obligation-v3";
  bundle.analysis_profile = "command-interaction-v3";
  bundle.steps.push({
    ...bundle.steps[0],
    id: "step2",
    order: 2,
    operation: { name: "实际参数校验步骤", kinds: [] },
  });
  const broad = {
    ...bundle.channels.E.concerns[0],
    id: "e-broad",
    condition: "参数校验失败",
    validation_summary: "request_validation",
    step_id: "step2",
  };
  const explicit = {
    ...broad,
    id: "e-explicit",
    condition: "pageSize > 100",
    validation_summary: undefined,
  };
  const first = bundle.channels.G.concerns[0];
  const second = { ...first, id: "g2", condition: "页面大小缺失" };
  bundle.channels.E.concerns = [broad, explicit];
  bundle.channels.G.concerns = [first, second];
  bundle.decisions = [
    [first, broad],
    [first, explicit],
    [second, broad],
  ].map(([g, e], i) => ({
    id: `d${i}`,
    level: "concern",
    pair: "G_E",
    left_id: g.id,
    right_id: e.id,
    status: "full",
    origin: "auto",
    reason: "同一请求校验义务",
  }));
  const view = response(bundle);
  view.comparison.concerns = [first, second].map((g, i) => ({
    id: `row-${g.id}`,
    generated_id: g.id,
    step_id: "step1",
    target: "data",
    key: "api.data.range",
    status: "pair",
    reason: "按 G 义务归组",
    cells: { E: i === 0 ? [explicit, broad] : [broad], G: [g], GT: [] },
  }));
  mockApi((path) => (path.endsWith("ssd-results") ? index : view));
  render(<SsdResultsView project="P1" initialIndex={index} />);

  const firstRow = (await screen.findByLabelText("编辑 G g1")).closest("tr")!;
  const secondRow = screen.getByLabelText("编辑 G g2").closest("tr")!;
  const firstEvidence = within(firstRow.cells[1]);
  const secondEvidence = within(secondRow.cells[1]);
  expect(firstEvidence.getByText("查看来源记录与判定（2）")).toBeTruthy();
  expect(
    firstEvidence.getByRole("button", { name: "查看原始出处（1）" }),
  ).toBeTruthy();
  fireEvent.click(firstEvidence.getByText("查看来源记录与判定（2）"));
  fireEvent.click(
    firstEvidence.getAllByRole("button", { name: "修正此项匹配" })[1],
  );
  const editor = within(screen.getByRole("dialog", { name: "修正匹配关系" }));
  const select = editor.getByLabelText<HTMLSelectElement>("匹配判定");
  expect([...select.options].map((option) => option.text)).toEqual([
    "匹配",
    "不匹配",
  ]);
  fireEvent.change(select, { target: { value: "none" } });
  fireEvent.click(editor.getByRole("button", { name: "应用到草稿" }));

  expect(firstEvidence.getByText("查看来源记录与判定（1）")).toBeTruthy();
  expect(firstEvidence.queryByText("参数校验失败")).toBeNull();
  expect(secondEvidence.getByText("参数校验失败")).toBeTruthy();
  expect(within(firstRow).getByText(/G_E · 不匹配 · 未保存/)).toBeTruthy();
});

test("shows the SR command and field name when transport location is absent", async () => {
  const bundle = fixture();
  bundle.analysis_profile = "command-interaction-v3";
  bundle.interface_field_policy = "sr-input-by-name-v1";
  const field = bundle.steps[0].data[0];
  delete field.location;
  field.command_id = "CATALOG-GET";
  field.rule_texts = ["pageSize <= 100"];
  mockApi((path) => (path.endsWith("ssd-results") ? index : response(bundle)));
  render(<SsdResultsView project="P1" initialIndex={index} />);

  const table = await screen.findByRole("table", { name: "SR 接口字段" });
  expect(
    within(table).getByRole("columnheader", { name: "SR 接口" }),
  ).toBeTruthy();
  expect(
    within(table).queryByRole("columnheader", { name: "位置" }),
  ).toBeNull();
  expect(within(table).getByText("CATALOG-GET")).toBeTruthy();
  expect(within(table).getByText("pageSize")).toBeTruthy();
  expect(within(table).getByText(/pageSize <= 100/)).toBeTruthy();
});
