import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
});
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.assign(globalThis, { ResizeObserver });
function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (k: string) => values.get(k) ?? null,
    setItem: (k: string, v: string) => {
      values.set(k, String(v));
    },
    removeItem: (k: string) => values.delete(k),
    clear: () => values.clear(),
    get length() {
      return values.size;
    },
    key: (i: number) => [...values.keys()][i] ?? null,
  };
}
Object.defineProperty(globalThis, "localStorage", {
  value: memoryStorage(),
  configurable: true,
});
Object.defineProperty(globalThis, "sessionStorage", {
  value: memoryStorage(),
  configurable: true,
});
