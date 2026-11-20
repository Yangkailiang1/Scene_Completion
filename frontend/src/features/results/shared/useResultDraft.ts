import { useRef, useState } from "react";
import { copy } from "../ssd/types";
import { draftChanges } from "./matchDraft";

// One controller per case/scope. Synchronous refs prevent rapid edits losing a prior edit.
export function useResultDraft<T>() {
  const [draft, render] = useState<T | null>(null);
  const current = useRef<T | null>(null),
    saved = useRef<T | null>(null),
    history = useRef<T[]>([]);
  function reset(value: T | null) {
    current.current = copy(value);
    saved.current = current.current;
    history.current = [];
    render(current.current);
  }
  function change(update: (value: T) => void) {
    if (!current.current) return false;
    const next = copy(current.current);
    update(next);
    if (draftChanges(current.current, next).total === 0) return false;
    history.current.push(current.current);
    if (history.current.length > 50) history.current.shift();
    current.current = next;
    render(next);
    return true;
  }
  function undo() {
    const previous = history.current.pop();
    if (previous) {
      current.current = previous;
      render(previous);
    }
  }
  const changes = draftChanges(saved.current, draft);
  return {
    draft,
    reset,
    change,
    undo,
    changes,
    dirty: changes.total > 0,
    canUndo: history.current.length > 0,
  };
}
