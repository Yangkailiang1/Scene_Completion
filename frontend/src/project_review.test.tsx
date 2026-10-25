import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { test, expect, vi, afterEach } from "vitest";
import { PendingView } from "./PendingView";
import { ConcernManager } from "./ConcernManager";
afterEach(() => vi.restoreAllMocks());
const definition = {
  key: "custom.check",
  label: "项目自定义规则",
  description: "仅按本项目明确规则判断",
  layer: "functional",
  group: "query_retrieval",
  kind: "check",
  guard: "business",
  parents: [],
  operation_kinds: ["read"],
  technology: null,
  failure_family: "custom.check",
  enabled: true,
};
const registry = { hash: "v1", definitions: { "custom.check": definition } };
test("business can skip an uncertainty without starting a model or rewriting artifacts", async () => {
  const item = {
    id: "item1",
    case: "C",
    interaction_id: "i",
    reason: "过期阈值不明确",
    origins: ["C:normal-rules--part-x"],
    source_refs: [
      { source_id: "RR", line_start: 8, line_end: 8, quote: "过期后刷新" },
    ],
  };
  let saved = false;
  const writes: any[] = [];
  const mock = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (url, init) => {
      const u = String(url);
      if (init?.method === "POST") {
        writes.push(JSON.parse(String(init.body)));
        saved = true;
        return {
          ok: true,
          json: async () => ({ choice: "not_anomaly" }),
        } as Response;
      }
      return {
        ok: true,
        json: async () =>
          u.endsWith("/registry")
            ? { registry }
            : {
                items: saved ? [] : [item],
                count: saved ? 0 : 1,
                counts: { unresolved: saved ? 0 : 1 },
                cases: ["C"],
              },
      } as Response;
    });
  render(<PendingView project="p" onSelect={vi.fn()} />);
  await screen.findByRole("heading", { name: "过期阈值不明确" });
  expect(screen.getByText("过期后刷新")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("是否为异常场景"), {
    target: { value: "not_anomaly" },
  });
  fireEvent.change(screen.getByLabelText("待确认审核说明"), {
    target: { value: "业务确认不算异常" },
  });
  fireEvent.click(screen.getByText("保存判定"));
  await waitFor(() => expect(writes[0]?.choice).toBe("not_anomaly"));
  expect(mock.mock.calls.some(([u]) => String(u).endsWith("/run"))).toBe(false);
  await screen.findByText(/审核已保存/);
});
test("confirmed anomalies require a current concern, and edits publish a project version", async () => {
  const requests: any[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    if (init?.method === "PUT") {
      const body = JSON.parse(String(init.body));
      requests.push(body);
      return {
        ok: true,
        json: async () => ({
          registry: { ...body.registry, hash: "v2" },
          current_hash: "v2",
          revision: 1,
          versions: [],
          read_only: false,
        }),
      } as Response;
    }
    return {
      ok: true,
      json: async () => ({
        registry,
        current_hash: "v1",
        revision: 0,
        versions: [],
        read_only: false,
      }),
    } as Response;
  });
  render(<ConcernManager project="p" />);
  fireEvent.click(
    await screen.findByRole("button", { name: /项目自定义规则/ }),
  );
  fireEvent.change(screen.getByLabelText("关注点定义"), {
    target: { value: "修改后的项目定义" },
  });
  fireEvent.click(screen.getByText("保存为新版本"));
  await waitFor(() => expect(requests[0]?.expected_hash).toBe("v1"));
  expect(requests[0].registry.definitions["custom.check"].description).toBe(
    "修改后的项目定义",
  );
  await screen.findByText(/已发布项目新版本/);
  fireEvent.click(screen.getByText("删除关注点"));
  await waitFor(() => expect(requests.length).toBe(2));
  expect(requests[1].registry.definitions["custom.check"].enabled).toBe(false);
});
