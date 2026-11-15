// Pi owns the loop and tool execution. Python owns model access and business
// validation. This process receives neither credentials nor a general filesystem tool.
import { createInterface } from "node:readline";
import {
  createAgentSession,
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";

const write = (v) => process.stdout.write(JSON.stringify(v) + "\n");

export async function run(start, broker, cwd = process.cwd()) {
  let submitted = false;
  const settingsManager = SettingsManager.inMemory({
    retry: { enabled: false, maxRetries: 0 },
    compaction: { enabled: false },
    cacheWarming: { mode: "off" },
    defaultTools: [],
  });
  const runtime = await ModelRuntime.create({
    authPath: `${cwd}/pi-home/auth.json`,
    modelsPath: null,
    modelsStorePath: `${cwd}/pi-home/catalog.json`,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });
  // This dummy credential only satisfies the SDK's local availability check.
  // It is never sent anywhere; streamFunction below has no network provider.
  runtime.registerProvider("scene-experiment", {
    baseUrl: "http://127.0.0.1:1",
    api: "openai-completions",
    apiKey: "broker-only",
    models: [
      {
        id: "ecnu-max",
        name: "Python metered transport",
        reasoning: false,
        input: ["text"],
        contextWindow: 1000000,
        maxTokens: 12000,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      },
    ],
  });
  const loader = new DefaultResourceLoader({
    cwd,
    agentDir: `${cwd}/pi-home`,
    settingsManager,
    noExtensions: true,
    noSkills: true,
    noPromptTemplates: true,
    noThemes: true,
    noContextFiles: true,
    systemPrompt: start.system,
  });
  await loader.reload();
  const customTools = start.tools.map((tool) => ({
    name: tool.name,
    label: tool.name,
    description: tool.description || "",
    parameters: tool.parameters,
    execute: async (_id, args) => {
      const reply = await broker({ kind: "tool", name: tool.name, args });
      submitted ||= reply.submitted === true;
      return {
        content: [{ type: "text", text: reply.text }],
        details: {},
        ...(reply.submitted ? { terminate: true } : {}),
      };
    },
  }));
  const { session } = await createAgentSession({
    cwd,
    agentDir: `${cwd}/pi-home`,
    modelRuntime: runtime,
    model: runtime.getModel("scene-experiment", "ecnu-max"),
    thinkingLevel: "off",
    settingsManager,
    sessionManager: SessionManager.inMemory(cwd),
    resourceLoader: loader,
    noTools: "builtin",
    tools: start.tools.map((t) => t.name),
    customTools,
  });
  session.agent.streamFunction = (_model, context) => {
    const stream = new AssistantMessageEventStream();
    (async () => {
      try {
        const reply = await broker({
          kind: "model",
          messages: context.messages,
        });
        stream.push({ type: "start", partial: reply.message });
        stream.push({
          type: "done",
          reason: reply.message.stopReason,
          message: reply.message,
        });
      } catch (error) {
        stream.end({
          role: "assistant",
          content: [],
          api: "openai-completions",
          provider: "scene-experiment",
          model: "ecnu-max",
          usage: {
            input: 0,
            output: 0,
            cacheRead: 0,
            cacheWrite: 0,
            totalTokens: 0,
            cost: {
              input: 0,
              output: 0,
              cacheRead: 0,
              cacheWrite: 0,
              total: 0,
            },
          },
          timestamp: Date.now(),
          stopReason: "error",
          errorMessage: String(error),
        });
      }
    })();
    return stream;
  };
  session.agent.toolExecution = "sequential";
  try {
    await session.prompt(start.prompt);
    if (!submitted) throw new Error("Pi finished without submit_result");
    return { kind: "done", submitted, tools: session.getActiveToolNames() };
  } finally {
    session.dispose();
  }
}

if (
  process.argv[1] &&
  import.meta.url === new URL(`file://${process.argv[1]}`).href
) {
  const input = createInterface({ input: process.stdin, terminal: false });
  const iterator = input[Symbol.asyncIterator]();
  const read = async () => {
    const row = await iterator.next();
    if (row.done) throw new Error("Python broker disconnected");
    return JSON.parse(row.value);
  };
  const rpc = async (v) => {
    write(v);
    return await read();
  };
  try {
    write(await run(await read(), rpc));
  } catch (error) {
    write({ kind: "error", error: String(error) });
    process.exitCode = 2;
  } finally {
    input.close();
  }
}
