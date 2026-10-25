import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { vi, test, expect } from "vitest";
import { TestSources, sourceFile } from "./TestSources";
test("test source preview and versioned save stay embedded and expose exact counts", async () => {
  const record = {
    id: "TEST-X-1",
    source_id: "s",
    row: 2,
    name: "a.xlsx#异常",
    类型: "异常",
    测试名称: "负库存",
    触发条件: "stock<0",
  };
  const current = {
    version: "v1",
    versions: [{ id: "v1" }],
    preview: {
      counts: { exception: 1, normal: 1, optional: 1, pending: 0 },
      records: [record],
    },
  };
  const fetcher = vi.fn(async (_url: any, init: any) => ({
    ok: true,
    json: async () =>
      init?.method === "POST"
        ? {
            valid: true,
            counts: { exception: 1, normal: 0, optional: 0, pending: 0 },
            issues: [],
            records: [record],
          }
        : current,
  }));
  vi.stubGlobal("fetch", fetcher);
  render(<TestSources project="p" />);
  await screen.findByText("TEST-X-1");
  expect(screen.getByText(/异常 1 \/ 正常 1 \/ 可选 1/)).toBeTruthy();
  expect(
    screen.getByRole("link", { name: /Excel示例/ }).getAttribute("href"),
  ).toBe("/api/test-sources/template");
  const file = new File(["data"], "test.md");
  Object.defineProperty(file, "text", { value: async () => "test" });
  fireEvent.change(screen.getByLabelText("上传测试文件"), {
    target: { files: [file] },
  });
  await screen.findByText("导入预览");
  fireEvent.click(screen.getByRole("button", { name: "保存为当前测试版本" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(
        ([url, init]) =>
          String(url).includes("test-sources") && init?.method === "PUT",
      ),
    ).toBe(true),
  );
  const call = fetcher.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(call![1].body).expected_version).toBe("v1");
});
test("xlsx upload preserves bytes rather than reading workbook as text", async () => {
  const file = new File([], "sample.xlsx");
  Object.defineProperty(file, "arrayBuffer", {
    value: async () => new Uint8Array([80, 75, 3, 4]).buffer,
  });
  expect(await sourceFile(file)).toEqual({
    name: "sample.xlsx",
    content_base64: "UEsDBA==",
  });
});
