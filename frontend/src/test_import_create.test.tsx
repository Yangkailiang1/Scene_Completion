import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, test, expect } from "vitest";
import App from "./App";
import { api } from "./api";

vi.mock("./ExecutionFlow", () => ({ ExecutionFlow: () => null }));

test("new-project preview shows file and line errors, keeps files, and blocks invalid submission", async () => {
  let invalid = true;
  const fetcher = vi.fn(async (url: any, init: any) => ({
    ok: true,
    json: async () => String(url).includes("test-sources/preview")
      ? { valid: !invalid, counts: { exception: invalid ? 0 : 14, normal: 11, optional: 0, pending: 10 }, issues: invalid ? [{ source: "recovered.md", row: 18, id: "SC@TC-DUP", reason: "重复测试ID" }] : [] }
      : String(url) === "/api/projects" ? [] : { definitions: {} },
  }));
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "新建项目" }));
  const file = new File(["text"], "recovered.md");
  Object.defineProperty(file, "text", { value: async () => "text" });
  const input = screen.getByLabelText("测试文档（可选）");
  fireEvent.change(input, { target: { files: [file] } });
  await screen.findByText("recovered.md 第18行 SC@TC-DUP：重复测试ID");
  expect((screen.getByRole("button", { name: "创建项目" }) as HTMLButtonElement).disabled).toBe(true);
  expect((input as HTMLInputElement).files?.[0].name).toBe("recovered.md");
  expect(fetcher.mock.calls.some(([url, init]) => url === "/api/projects" && init?.method === "POST")).toBe(false);
  invalid = false;
  fireEvent.change(input, { target: { files: [file] } });
  await waitFor(() => expect((screen.getByRole("button", { name: "创建项目" }) as HTMLButtonElement).disabled).toBe(false));
  expect(screen.getByText(/测试导入预览：异常 14/)).toBeTruthy();
});

test("API import errors preserve actionable preview for the creation dialog", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 400, json: async () => ({ detail: "test.md 第2行：重复测试ID", import_preview: { valid: false, issues: [] } }) })));
  try { await api("/api/projects", { method: "POST" }); throw new Error("expected rejection"); }
  catch (e: any) { expect(e.message).toContain("第2行"); expect(e.importPreview.valid).toBe(false); }
});
