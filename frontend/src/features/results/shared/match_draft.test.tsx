import { act, renderHook } from "@testing-library/react";
import { expect, test } from "vitest";
import { useResultDraft } from "./useResultDraft";
import {
  decisionKey,
  draftChanges,
  putDecision,
  restoreDecision,
} from "./matchDraft";
import type { Decision } from "../ssd/types";
const pair = (n: number): Decision => ({
  id: "d" + n,
  level: "scenario",
  pair: "GT_G",
  left_id: "t" + n,
  right_id: "g" + n,
  status: "full",
  origin: "manual",
  reason: "人工确认",
});
test("rapid edits use distinct pair identities and undo reaches a clean baseline", () => {
  const { result } = renderHook(() => useResultDraft<any>());
  const saved = {
    decisions: [],
    channels: { G: { scenarios: [{ id: "g1", condition: "原条件" }] } },
  };
  act(() => result.current.reset(saved));
  act(() => {
    result.current.change((b) => putDecision(b, pair(1)));
    result.current.change((b) => putDecision(b, pair(2)));
  });
  expect(result.current.changes.matches.size).toBe(2);
  expect(result.current.draft.decisions).toHaveLength(2);
  act(() => {
    expect(result.current.change((b) => putDecision(b, pair(1)))).toBe(false);
  });
  act(() =>
    result.current.change((b) =>
      putDecision(b, { ...pair(1), status: "partial", id: "new-id" }),
    ),
  );
  expect(result.current.changes.matches.size).toBe(2);
  act(() => result.current.change((b) => restoreDecision(b, saved, pair(1))));
  expect(result.current.changes.matches.size).toBe(1);
  act(() => result.current.change((b) => restoreDecision(b, saved, pair(2))));
  expect(result.current.dirty).toBe(false);
  act(() => result.current.undo());
  expect(result.current.changes.matches.size).toBe(1);
  act(() => result.current.reset(saved));
  act(() =>
    result.current.change(
      (b) => (b.channels.G.scenarios[0].condition = "新条件"),
    ),
  );
  expect(result.current.changes.other).toBe(1);
  act(() => result.current.undo());
  expect(result.current.dirty).toBe(false);
});
test("cancelling a draft restores its saved model decision and leaves another pair intact", () => {
  const original = {
    ...pair(1),
    origin: "model",
    status: "none",
    reason: "原模型依据",
  };
  const saved = { decisions: [original], steps: [{ id: "step", order: 1 }] };
  const draft = structuredClone(saved);
  putDecision(draft, pair(1));
  putDecision(draft, pair(2));
  restoreDecision(draft, saved, pair(1));
  expect(draft.decisions).toContainEqual(original);
  expect(draftChanges(saved, draft).matches).toEqual(
    new Set([decisionKey(pair(2))]),
  );
});
