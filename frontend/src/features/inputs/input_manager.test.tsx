import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { InputManager } from "./InputManager";

test("behavior file exposes scoped adoption and keeps fallback instead of a fake completed SSD", async () => {
  const writes: any[] = [];
  const detail = {
    id: "behavior",
    name: "complete_behavior.json",
    revision: 2,
    role: "artifact",
    status: "converted",
    original: "imports/files/behavior/original/complete_behavior.json",
    artifacts: [],
    history: [],
    behavior_enabled: false,
    target_nodes: ["<用例>:fused-ssd"],
    behavior_product: {
      label: "SR完整行为（含分支）",
      kind: "sr_complete",
      layer: "SR",
      case_name: "查看订单详情",
      counts: { interactions: 2, local_actions: 1 },
      pending: [{ object: "query", reason: "缺少明确内部调用" }],
      raw: {
        operation_id: "getOrderDetail",
        flow: { type: "sequence", steps: [] },
      },
      normal_document: { lines: [] },
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: any, init: any) => ({
      ok: true,
      json: async () => {
        if (init?.method === "PUT") {
          writes.push(JSON.parse(init.body));
          return { saved: true };
        }
        const path = String(url);
        if (path.includes("imports?item=")) return detail;
        if (path.endsWith("/imports"))
          return {
            items: [
              {
                id: detail.id,
                name: detail.name,
                role: "artifact",
                status: "converted",
              },
            ],
          };
        if (path.endsWith("/results")) return { cases: [] };
        if (path.endsWith("/recovery")) return null;
        return { revision: 0 };
      },
    })),
  );
  render(<InputManager project="behavior" />);
  fireEvent.click(
    await screen.findByRole("button", { name: /complete_behavior.json/ }),
  );
  expect(await screen.findByText("SR完整行为（含分支）")).toBeTruthy();
  expect(screen.getByText(/用例：查看订单详情/)).toBeTruthy();
  expect(screen.getByText(/本地动作不补造Service调用/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "确认本产物" })).toBeNull();
  expect(screen.queryByText(/请确认本文件角色/)).toBeNull();
  fireEvent.click(screen.getByText("内容预览与待补齐项"));
  expect(screen.getByText(/getOrderDetail/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "采用此行为版本" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({
    action: "enable_behavior",
    expected_revision: 2,
  });
});

test("partial colleague import requires explicit versioned confirmation and keeps raw file link", async () => {
  const artifact = {
    id: "file:0",
    task: "components",
    case_hint: null,
    coverage: "partial",
    status: "needs_confirmation",
    payload: { components: [], relations: [] },
  };
  const detail = {
    id: "file",
    revision: 2,
    name: "colleague.json",
    status: "converted",
    original: "imports/files/file/original/colleague.json",
    artifacts: [artifact],
    history: [],
  };
  const writes: any[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: any, init: any) => ({
      ok: true,
      json: async () => {
        if (init?.method === "PUT") {
          writes.push(JSON.parse(init.body));
          return { saved: true };
        }
        const path = String(url);
        if (path.includes("imports?item=")) return detail;
        if (path.endsWith("/imports"))
          return {
            items: [
              {
                id: "file",
                name: "colleague.json",
                role: "artifact",
                status: "converted",
              },
            ],
          };
        if (path.endsWith("/input-scan")) return { revision: 0 };
        if (path.endsWith("/results")) return { cases: [] };
        if (path.endsWith("/recovery"))
          return {
            revision: 0,
            settings: { enabled: true, max_node_calls: 2, max_run_calls: 20 },
            ledger: { history: [] },
          };
        return { events: [] };
      },
    })),
  );
  render(<InputManager project="p" />);
  fireEvent.click(
    await screen.findByRole("button", { name: /colleague.json/ }),
  );
  expect(
    (await screen.findByRole("link", { name: "查看原文件" })).getAttribute(
      "href",
    ),
  ).toContain("original");
  fireEvent.change(screen.getByLabelText(/覆盖范围/), {
    target: { value: "complete" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认本产物" }));
  await waitFor(() => expect(writes.length).toBe(1));
  expect(writes[0]).toMatchObject({
    expected_revision: 2,
    artifact_id: "file:0",
    coverage: "complete",
    replace: false,
  });
});

test("keeps upload actions compact and advanced controls collapsed by default", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: any) => ({
      ok: true,
      json: async () =>
        String(url).endsWith("/imports")
          ? { items: [] }
          : String(url).endsWith("/results")
            ? { cases: [] }
            : String(url).endsWith("/recovery")
              ? null
              : { revision: 0 },
    })),
  );
  const view = render(<InputManager project="empty-project" />);
  await screen.findByText("还没有文件");
  expect(screen.getByRole("button", { name: "添加文件" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "添加文件夹" })).toBeTruthy();
  expect(
    (view.container.querySelector(".input-controls") as HTMLDetailsElement)
      .open,
  ).toBe(false);
  expect(
    [
      ...view.container.querySelectorAll<HTMLInputElement>(
        'input[type="file"]',
      ),
    ].every((x) => x.hidden),
  ).toBe(true);
  fireEvent.click(screen.getByText(/目录监控与运行范围/));
  expect(screen.getByLabelText("监控本机目录")).toBeTruthy();
});

test("structured RR import shows actual skip scope and can disable its version", async () => {
  const writes: any[] = [];
  const detail = {
    id: "rr",
    name: "structure_model.json",
    revision: 0,
    role: "artifact",
    status: "converted",
    original: "imports/files/rr/original/structure_model.json",
    artifacts: [],
    target_nodes: ["rr-use-cases"],
    structure_enabled: true,
    structure_model: {
      layer: "RR",
      counts: {
        use_cases: 1,
        main_success: 1,
        exceptions: 2,
        non_exception: 1,
      },
      catalogue: { cases: [{ id: "UC-1", name: "查询列表", actors: [] }] },
    },
    history: [],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: any, init: any) => ({
      ok: true,
      json: async () => {
        if (init?.method === "PUT") {
          writes.push(JSON.parse(init.body));
          return { saved: true };
        }
        const path = String(url);
        if (path.includes("imports?item=")) return detail;
        if (path.endsWith("/imports"))
          return {
            items: [
              {
                id: "rr",
                name: detail.name,
                role: "artifact",
                status: "converted",
              },
            ],
          };
        if (path.endsWith("/results")) return { cases: [] };
        if (path.endsWith("/recovery")) return null;
        return { events: [] };
      },
    })),
  );
  render(<InputManager project="structured" />);
  fireEvent.click(
    await screen.findByRole("button", { name: /structure_model.json/ }),
  );
  expect(await screen.findByText("RR 结构化需求")).toBeTruthy();
  expect(screen.getByText("查询列表")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /确认.*原始/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "停用此结构版本" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({
    action: "disable_structure",
    expected_revision: 0,
  });
});

test("supplied SSD preflight starts only the validated cases", async () => {
  const runs: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => ({
      ok: true,
      json: async () => {
        if (url.endsWith("/supplied-cases")) {
          return {
            accepted: ["G-001"],
            cases: [
              {
                file_id: "ok",
                file: "Product/create/SysOperation.json",
                name: "创建商品",
                case_id: "G-001",
                target: "G-001:fused-ssd",
                status: "ready",
                reason: "校验通过",
              },
              {
                file_id: "bad",
                file: "Product/update/SysOperation.json",
                name: "更新商品",
                case_id: "G-002",
                target: "G-002:fused-ssd",
                status: "excluded",
                reason: "返回缺少请求",
              },
            ],
          };
        }
        if (url.endsWith("/run")) {
          runs.push(JSON.parse(String(init?.body)));
          return { status: "running" };
        }
        if (url.endsWith("/imports")) return { items: [] };
        if (url.endsWith("/input-scan")) return {};
        if (url.endsWith("/results")) return { cases: [] };
        return null;
      },
    })),
  );
  render(<InputManager project="validated" />);
  fireEvent.click(screen.getByRole("button", { name: "预检已有 SSD" }));
  expect(await screen.findByText("未纳入 · 返回缺少请求")).toBeTruthy();
  expect(await screen.findByText("已有 SSD 预检完成。")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "仅运行已校验的用例" }));
  await waitFor(() =>
    expect(runs).toEqual([{ supplied_only: true, case_ids: ["G-001"] }]),
  );
});
