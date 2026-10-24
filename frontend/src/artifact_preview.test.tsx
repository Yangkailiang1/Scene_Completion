import React from "react";
import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ArtifactView, PayloadView } from "./ArtifactView";
import { primaryJsonArtifact } from "./api";
it("selects the model data instead of drawing layout metadata", () => {
  const files = [
    "components.layout.json",
    "components.metadata.json",
    "components.json",
  ].map((name) => ({ name, path: name, bytes: 1 }));
  expect(primaryJsonArtifact(files)?.name).toBe("components.json");
});

it("renders an interface index without pretending it contains parameters", () => {
  render(
    <PayloadView
      definitions={{}}
      value={{
        apis: [
          {
            id: "API-M-IF2",
            name: "查询记忆库列表",
            source_ranges: [{ source_id: "SR", start: 10, end: 20 }],
            source_refs: [],
          },
        ],
      }}
    />,
  );
  expect(screen.getByText("接口目录（内部拆分依据）")).toBeTruthy();
  expect(screen.getByText("API-M-IF2")).toBeTruthy();
  expect(screen.getByText("原文范围")).toBeTruthy();
  expect(screen.queryByText("数据类型")).toBeNull();
});
it("shows an empty interface result instead of an invisible page", () => {
  render(<PayloadView definitions={{}} value={{ apis: [] }} />);
  expect(screen.getByText("当前接口集合为空。")).toBeTruthy();
});
it("contains a malformed artifact failure and retains its file download", () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  render(
    <ArtifactView
      projectId="p"
      definitions={{}}
      value={{ services: [{}] }}
      artifacts={[
        { name: "result.json", path: "run/artifacts/result.json", bytes: 10 },
      ]}
    />,
  );
  expect(screen.getByRole("alert").textContent).toContain(
    "完整数据和文件仍可查看",
  );
  expect(screen.getByRole("link")).toBeTruthy();
  vi.restoreAllMocks();
});
it("opens the combined table for mappings and can switch back to the node result", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        complete: false,
        rows: [
          {
            service: "MemoryService",
            api_name: "List",
            name: "memoryType",
            mapping_status: "待审核",
            parameter_status: "已完成",
          },
        ],
      }),
    })),
  );
  render(
    <ArtifactView
      projectId="p"
      taskKey="api-map"
      definitions={{}}
      value={{ services: [] }}
      artifacts={[]}
    />,
  );
  expect(await screen.findByText("MemoryService")).toBeTruthy();
  expect(screen.getByText(/中间结果：/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "下载总表 JSON" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "本节点产物" }));
  expect(screen.getByText("对应接口列表")).toBeTruthy();
  vi.unstubAllGlobals();
});

it("shows readable rules without expanding source JSON inside parameter cells", () => {
  render(
    <PayloadView
      definitions={{}}
      value={{
        apis: [
          {
            id: "A",
            name: "API",
            address: "/a",
            parameters: [
              {
                name: "page",
                required: false,
                constraints: [
                  {
                    kind: "minimum",
                    status: "explicit",
                    value: 1,
                    source_refs: [{ quote: "原文" }],
                  },
                  {
                    kind: "format",
                    status: "pending",
                    value: "格式合法",
                    source_refs: [],
                  },
                ],
              },
            ],
          },
        ],
      }}
    />,
  );
  const cells = screen.getAllByRole("cell");
  expect(cells.some((c) => c.textContent === "可选")).toBe(true);
  const rules = cells.find((c) => c.textContent?.includes("最小值：1"))!;
  expect(rules.textContent).toContain("格式：待确认具体约束");
  expect(rules.textContent).not.toContain("source_refs");
});
