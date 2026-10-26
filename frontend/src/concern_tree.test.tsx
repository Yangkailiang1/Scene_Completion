import { render, screen, fireEvent } from "@testing-library/react";
import { test, expect, vi } from "vitest";
import { ConcernTree } from "./ConcernTree";
import { ConcernAlignmentTable } from "./ResultComparison";

test("shared input/output paths edit the same stable ID and search retains ancestors", () => {
  const pick = vi.fn(),
    d = { label: "数据范围", description: "上限下限" };
  const props = {
    definitions: [["range", d]] as [string, any][],
    paths: {
      range: [
        ["Service关注点", "输入数据"],
        ["Service关注点", "输出数据"],
      ],
    },
    project: "tree",
    selected: "range",
    query: "",
    pick,
  };
  const view = render(<ConcernTree {...props} />);
  expect(screen.getAllByRole("button", { name: /数据范围/ })).toHaveLength(2);
  fireEvent.click(screen.getAllByRole("button", { name: /数据范围/ })[1]);
  expect(pick).toHaveBeenCalledWith("range", d);
  view.rerender(<ConcernTree {...props} query="上限" />);
  expect(screen.getByText("Service关注点")).toBeTruthy();
  expect(screen.getAllByRole("button", { name: /数据范围/ })).toHaveLength(2);
});

test("unclassified custom definitions remain editable", () => {
  render(
    <ConcernTree
      definitions={[["custom", { label: "待分类规则" }]]}
      paths={{}}
      project="other"
      selected=""
      query=""
      pick={vi.fn()}
    />,
  );
  expect(screen.getByText("待归类")).toBeTruthy();
  expect(screen.getByRole("button", { name: /待分类规则/ })).toBeTruthy();
});

test("taxonomy group headings never duplicate E/G/GT comparison rows", () => {
  const row = {
    id: "b",
    anchor: { target: "data", object: "page", concern_key: "range" },
    status: "pair",
    reason: "same",
    classification_paths: [
      ["Service关注点", "基础", "输入数据"],
      ["alternate"],
    ],
    cells: { E: [], G: [], GT: [] },
  };
  const { container } = render(
    <ConcernAlignmentTable
      rows={[row]}
      definitions={{ range: { label: "数据范围" } }}
      onlyUnmatched={false}
      onSelect={vi.fn()}
    />,
  );
  expect(container.querySelectorAll("tr.alignment-pair")).toHaveLength(1);
  expect(container.querySelectorAll("tr.concern-group-heading")).toHaveLength(
    1,
  );
});
