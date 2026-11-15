import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useAppController } from "./useAppController";

const projects = [
  { id: "ssd", name: "SSD 已完成项目", review_mode: "auto", sources: {} },
  { id: "history", name: "历史报告项目", review_mode: "auto", sources: {} },
];
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function snapshot(id: string, compact = false) {
  return {
    project: projects.find((project) => project.id === id),
    job: { status: id === "ssd" ? "complete_with_questions" : "complete" },
    manifest: { execution_complete: true, pending_count: id === "ssd" ? 8 : 0 },
    tasks: { tasks: {}, events: [] },
    reviews: [],
    artifacts: [],
    config: {},
    compact,
  };
}
function graph(id: string) {
  return {
    nodes:
      id === "ssd"
        ? Array.from({ length: 15 }, (_, index) => ({
            id: `node-${index}`,
            status: "passed",
          }))
        : [],
    edges: [],
    roles: [],
    definition_available: true,
    case_expansion_pending: false,
  };
}
const response = (value: unknown) => ({ ok: true, json: async () => value });
afterEach(() => vi.unstubAllGlobals());

test("opening a completed project from results loads its graph instead of only a compact snapshot", async () => {
  const requests: string[] = [];
  const held = new Map<string, ReturnType<typeof deferred<unknown>>>();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      requests.push(url);
      if (url === "/api/projects") return response(projects);
      const id = url.includes("/history") ? "history" : "ssd";
      if (url.endsWith("/registry"))
        return response({ registry: { definitions: {} } });
      if (url.endsWith("/graph")) return response(graph(id));
      const pending = held.get(id);
      if (pending) {
        held.delete(id);
        await pending.promise;
      }
      return response(snapshot(id, url.includes("compact=true")));
    }),
  );
  const { result } = renderHook(() => useAppController());
  await waitFor(() => expect(result.current.projects).toHaveLength(2));
  await act(async () => result.current.openProject("ssd"));
  await waitFor(() => expect(result.current.graph.nodes).toHaveLength(15));
  await act(async () => result.current.setManagement("results"));
  await waitFor(() => expect(result.current.refreshBusy.current.size).toBe(0));

  const historyResponse = deferred<unknown>();
  held.set("history", historyResponse);
  await act(async () => result.current.openProject("history"));
  expect(requests).toContain("/api/projects/history");
  expect(requests).not.toContain("/api/projects/history?compact=true");
  await act(async () => historyResponse.resolve(null));
  await waitFor(() =>
    expect(requests).toContain("/api/projects/history/graph"),
  );
  expect(result.current.snapshot?.project.id).toBe("history");
  expect(result.current.graph.nodes).toHaveLength(0);

  await act(async () => result.current.setManagement("results"));
  await waitFor(() => expect(result.current.refreshBusy.current.size).toBe(0));
  const ssdResponse = deferred<unknown>();
  held.set("ssd", ssdResponse);
  await act(async () => result.current.openProject("ssd"));
  await act(async () => ssdResponse.resolve(null));
  await waitFor(() => expect(result.current.graph.nodes).toHaveLength(15));
  expect(result.current.snapshot?.manifest.pending_count).toBe(8);
  expect(
    requests.filter((url) => url === "/api/projects/ssd/graph"),
  ).toHaveLength(2);
});

test("a delayed registry response cannot overwrite the newly selected project's definitions", async () => {
  const oldRegistry = deferred<unknown>();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url === "/api/projects") return response(projects);
      const id = url.includes("/history") ? "history" : "ssd";
      if (url === "/api/projects/ssd/registry")
        return response(await oldRegistry.promise);
      if (url.endsWith("/registry"))
        return response({
          registry: { definitions: { history: { label: "历史项目定义" } } },
        });
      if (url.endsWith("/graph")) return response(graph(id));
      return response(snapshot(id));
    }),
  );
  const { result } = renderHook(() => useAppController());
  await waitFor(() => expect(result.current.projects).toHaveLength(2));
  await act(async () => result.current.openProject("ssd"));
  await waitFor(() => expect(result.current.graph.nodes).toHaveLength(15));
  await act(async () => result.current.openProject("history"));
  await waitFor(() =>
    expect(result.current.definitions).toEqual({
      history: { label: "历史项目定义" },
    }),
  );
  await act(async () =>
    oldRegistry.resolve({
      registry: { definitions: { ssd: { label: "旧项目迟到定义" } } },
    }),
  );
  expect(result.current.current).toBe("history");
  expect(result.current.definitions).toEqual({
    history: { label: "历史项目定义" },
  });
});
