import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { run } from "./runner.mjs";

const start = {
  system: "only this allowed packet",
  prompt: "submit the test result",
  tools: [
    {
      name: "submit_result",
      description: "submit",
      parameters: {
        type: "object",
        properties: { payload: { type: "object" } },
        required: ["payload"],
      },
    },
  ],
};
const reply = (content) => ({
  role: "assistant",
  content,
  api: "openai-completions",
  provider: "scene-experiment",
  model: "ecnu-max",
  timestamp: Date.now(),
  stopReason: content.some((c) => c.type === "toolCall") ? "toolUse" : "stop",
  usage: {
    input: 1,
    output: 1,
    totalTokens: 2,
    cacheRead: 0,
    cacheWrite: 0,
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
  },
});

test("SDK exposes only supplied tools and stops after verified submission", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "scene-pi-node-"));
  const calls = [];
  try {
    const result = await run(
      start,
      async (event) => {
        calls.push(event.kind);
        if (event.kind === "model")
          return {
            message: reply([
              {
                type: "toolCall",
                id: "submit-1",
                name: "submit_result",
                arguments: { payload: { ok: true } },
              },
            ]),
          };
        assert.equal(event.name, "submit_result");
        return { text: "validated", submitted: true };
      },
      cwd,
    );
    assert.deepEqual(calls, ["model", "tool"]);
    assert.deepEqual(result.tools, ["submit_result"]);
    assert.equal(result.submitted, true);
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("plain assistant completion is not successful delivery", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "scene-pi-node-"));
  try {
    await assert.rejects(
      run(
        start,
        async () => ({ message: reply([{ type: "text", text: "I am done" }]) }),
        cwd,
      ),
      /without submit_result/,
    );
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});
