import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ExecutionNavigator } from "./ExecutionNavigator";
import type { Graph } from "./types";
it("lets readers select tasks and open the optional full dependency canvas", () => {
  const pick = vi.fn(),
    open = vi.fn();
  const graph: Graph = {
    nodes: [
      {
        id: "a",
        label: "系统组成",
        role: "modeler",
        stage: "components",
        case: "shared",
        phase: "awaiting_review",
        status: "awaiting_review",
        deps: [],
        blocked_by: [],
        expected_files: [],
        failure: null,
        attempt: 1,
        elapsed_seconds: 0,
        last_event_at: null,
      },
    ],
    edges: [],
    roles: [],
    definition_available: true,
    case_expansion_pending: false,
  };
  render(
    <ExecutionNavigator
      graph={graph}
      selected="a"
      onSelect={pick}
      onOpenGraph={open}
    />,
  );
  expect(
    screen
      .getByRole("button", { name: "系统组成" })
      .getAttribute("aria-current"),
  ).toBe("step");
  fireEvent.click(screen.getByRole("button", { name: "系统组成" }));
  expect(pick).toHaveBeenCalledWith("a");
  fireEvent.click(screen.getByRole("button", { name: "打开完整依赖图" }));
  expect(open).toHaveBeenCalledOnce();
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "running" },
  });
  expect(screen.queryByRole("button", { name: "系统组成" })).toBeNull();
});
