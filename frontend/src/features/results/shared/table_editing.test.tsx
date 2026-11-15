import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { EditableCell } from "./EditableCell";
import {
  clearTableCell,
  putTableRecord,
  groupDisplayRows,
} from "./tableEditing";

test("cell editing commits on blur and Escape cancels", () => {
  const change = vi.fn();
  render(<EditableCell label="G失败条件" value="原条件" onChange={change} />);
  fireEvent.click(screen.getByRole("button", { name: "G失败条件" }));
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "新条件" },
  });
  fireEvent.blur(screen.getByRole("textbox"));
  expect(change).toHaveBeenCalledWith("新条件");
  fireEvent.click(screen.getByRole("button", { name: "G失败条件" }));
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "取消内容" },
  });
  fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" });
  expect(change).toHaveBeenCalledTimes(1);
});

test("clearing a cell preserves other channels and orphans children; deleting a row cascades", () => {
  const concern = {
    id: "c",
    step_id: "s",
    key: "human.authentication",
    target: "sender",
    status: "active",
    condition: "认证",
    source_refs: [],
  };
  const bundle: any = {
    channels: Object.fromEntries(
      ["G", "E", "GT"].map((ch) => [
        ch,
        {
          concerns: [{ ...concern }],
          scenarios: [{ ...concern, id: "x", concern_ids: ["c"] }],
          pending: [],
        },
      ]),
    ),
    decisions: [],
  };
  const row = { cells: { G: [concern], E: [concern], GT: [concern] } };
  clearTableCell(bundle, row, "G", "concerns");
  expect(bundle.channels.E.concerns).toHaveLength(1);
  expect(bundle.channels.G.scenarios[0].status).toBe("unbound");
  clearTableCell(bundle, row, "E", "concerns", true);
  expect(bundle.channels.E.scenarios).toHaveLength(0);
  putTableRecord(bundle, "G", "scenarios", {
    ...concern,
    id: "new",
    condition: "无凭证",
    concern_ids: [],
  });
  expect(bundle.channels.G.concerns).toHaveLength(1);
  expect(
    bundle.channels.G.scenarios.find((r: any) => r.id === "new").concern_ids,
  ).toHaveLength(1);
});

test("new cells keep the same display row before saving without creating a match", () => {
  const row = (ch: string, id: string) => ({
    id: ch + id,
    cells: {
      E: [],
      G: [],
      GT: [],
      [ch]: [{ id, display_row_id: "manual-row" }],
    },
    coverage_by_record: { [id]: { covered: false, complete: true } },
  });
  const grouped = groupDisplayRows([row("E", "e"), row("G", "g")]);
  expect(grouped).toHaveLength(1);
  expect(grouped[0].id).toBe("manual-row");
  expect(grouped[0].cells.E[0].id).toBe("e");
  expect(grouped[0].cells.G[0].id).toBe("g");
  expect(grouped[0].coverage_by_record.g.covered).toBe(false);
  expect(grouped[0].decisions).toBeUndefined();
});

test("GT links normal field requirements separately from test origins", async () => {
  const { relatedRequirementRefs } = await import("./provenance");
  const rr = {
    document_id: "rr",
    start_line: 2,
    end_line: 2,
    quote: "字段要求",
    kind: "origin",
  };
  const test = {
    document_id: "test",
    start_line: 3,
    end_line: 3,
    quote: "测试原文",
    kind: "test",
  };
  const bundle = {
    documents: [
      { id: "rr", role: "RR" },
      { id: "test", role: "test" },
    ],
    steps: [
      {
        id: "step",
        data: [{ id: "f", source_refs: [rr] }],
        source_refs: [test, rr],
      },
    ],
  };
  const record: any = {
    id: "GT",
    step_id: "step",
    field_id: "f",
    source_refs: [test],
  };
  expect(relatedRequirementRefs(bundle, record)).toEqual([rr]);
  expect(record.source_refs).toEqual([test]);
  expect(
    relatedRequirementRefs(bundle, { ...record, step_id: "missing" }),
  ).toEqual([]);
});
