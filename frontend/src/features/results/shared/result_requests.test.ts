import { afterEach, expect, test, vi } from "vitest";
import { invalidateResults, resultGet, setResultEpoch } from "./resultRequests";

afterEach(() => {
  invalidateResults();
  vi.restoreAllMocks();
});
const json = (v: unknown) => ({ ok: true, json: async () => v }) as Response;
test("concurrent result reads coalesce, project epochs invalidate, failures can be retried", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(json({ revision: 1 }));
  const a = resultGet("A", "ssd-results"),
    b = resultGet("A", "ssd-results");
  expect(a).toBe(b);
  await a;
  expect(fetcher).toHaveBeenCalledTimes(1);
  await resultGet("B", "ssd-results");
  expect(fetcher).toHaveBeenCalledTimes(2);
  setResultEpoch("A", "new-revision");
  await resultGet("A", "ssd-results");
  expect(fetcher).toHaveBeenCalledTimes(3);
  await resultGet("B", "ssd-results");
  expect(fetcher).toHaveBeenCalledTimes(3);
  invalidateResults("A");
  fetcher.mockRejectedValueOnce(new Error("offline"));
  await expect(resultGet("A", "ssd-results")).rejects.toThrow("offline");
  await resultGet("A", "ssd-results");
  expect(fetcher).toHaveBeenCalledTimes(5);
});
