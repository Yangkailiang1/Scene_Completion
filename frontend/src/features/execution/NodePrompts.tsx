import { useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { api, projectUrl } from "../../shared/api";

type Budget = {
  estimated_input_tokens_upper_bound?: number;
  output_reserve?: number;
  max_context_tokens?: number;
  estimate_method?: string;
};
type RequestMeta = {
  id: string;
  at: number;
  model: string;
  attempt: number | null;
  status: string;
  budget: Budget;
};
type PromptRecord = RequestMeta & {
  note?: string;
  request: {
    messages?: Array<{
      role?: string;
      content?: unknown;
      [key: string]: unknown;
    }>;
    tools?: unknown[];
    response_format?: unknown;
    [key: string]: unknown;
  };
};

export function NodePrompts({
  projectId,
  taskKey,
}: {
  projectId: string;
  taskKey: string;
}) {
  const [requests, setRequests] = useState<RequestMeta[]>([]);
  const [record, setRecord] = useState<PromptRecord | null>(null);
  const [selected, setSelected] = useState("");
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("messages");
  const [legacy, setLegacy] = useState<unknown>(null);
  const base = projectUrl(
    projectId,
    "prompts?task_key=" + encodeURIComponent(taskKey),
  );
  useEffect(() => {
    const abort = new AbortController();
    setLoading(true);
    setError("");
    setRecord(null);
    setLegacy(null);
    api<{ requests: RequestMeta[]; latest: string | null }>(base, {
      signal: abort.signal,
    })
      .then((r) => {
        setRequests(r.requests);
        setSelected(r.latest || "");
      })
      .catch((e: Error) => {
        if (!abort.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [base, version]);
  useEffect(() => {
    if (!selected) return;
    const abort = new AbortController();
    setRecord(null);
    setError("");
    api<PromptRecord>(base + "&request_id=" + encodeURIComponent(selected), {
      signal: abort.signal,
    })
      .then(setRecord)
      .catch((e: Error) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [base, selected, version]);
  const budget = record?.budget;
  return (
    <div className="space-y-4 p-5 text-sm text-slate-700">
      <div className="flex flex-wrap items-center gap-3">
        <strong className="mr-auto">节点完整请求与提示词</strong>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setVersion((v) => v + 1)}
        >
          刷新请求
        </Button>
        {record && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              const url = URL.createObjectURL(
                new Blob([JSON.stringify(record, null, 2)], {
                  type: "application/json",
                }),
              );
              const link = document.createElement("a");
              link.href = url;
              link.download =
                "node-request-" + record.id.slice(0, 12) + ".json";
              link.click();
              URL.revokeObjectURL(url);
            }}
          >
            下载请求JSON
          </Button>
        )}
      </div>
      <p className="text-xs text-slate-500">
        展示最终组装的系统提示、Skill、材料、工具Schema及修复/对话正文历史；凭证已移除，临时推理回传值以redacted标记。预算超限而未发送的请求也会保存。
      </p>
      {loading && <p>正在读取请求目录…</p>}
      {error && (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      )}
      {!loading && requests.length === 0 && (
        <div className="space-y-3">
          <p>
            此节点暂无完整请求记录。尚未执行、纯工具节点或旧版本日志都可能没有记录；旧的输入材料不等于实际发送的完整提示词。
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              api(
                projectUrl(
                  projectId,
                  "context?task_key=" + encodeURIComponent(taskKey),
                ),
              )
                .then(setLegacy)
                .catch((e: Error) => setError(e.message))
            }
          >
            查看旧版保存的输入材料
          </Button>
          {legacy !== null && (
            <>
              <p className="text-xs text-amber-700">
                以下为旧版保存的输入材料／Schema，不是完整HTTP请求，不能据此还原当时的系统提示和历史。
              </p>
              <pre className="whitespace-pre-wrap break-words rounded-lg border p-4 font-mono text-sm">
                {JSON.stringify(legacy, null, 2)}
              </pre>
            </>
          )}
        </div>
      )}
      {requests.length > 0 && (
        <select
          aria-label="选择模型请求"
          className="w-full rounded-lg border bg-white p-3"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {requests.map((r) => (
            <option key={r.id} value={r.id}>
              {new Date(r.at * 1000).toLocaleString()} · {r.model} · 第
              {r.attempt ?? "—"}次尝试 ·{" "}
              {r.status === "context_blocked"
                ? "上下文超限，未发送"
                : "已组装请求"}
            </option>
          ))}
        </select>
      )}
      {record && (
        <>
          <div className="rounded-lg border bg-slate-50 p-3 leading-6">
            <p>
              保守输入上界{" "}
              {budget?.estimated_input_tokens_upper_bound?.toLocaleString() ??
                "未知"}{" "}
              ＋ 输出预留 {budget?.output_reserve?.toLocaleString() ?? "未知"}{" "}
              ／ 上下文上限{" "}
              {budget?.max_context_tokens?.toLocaleString() ?? "未知"}
            </p>
            <p className="text-xs text-slate-500">
              按UTF-8字节及消息封装保守估算，并非供应商真实Token数。
              {record.status === "context_blocked" &&
                "此请求在HTTP发送前被阻止，不应原样重试。"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              ["messages", "系统与用户消息"],
              ["tools", "工具与输出Schema"],
              ["json", "完整请求JSON"],
            ].map(([key, label]) => (
              <Button
                key={key}
                variant={view === key ? "default" : "outline"}
                size="sm"
                onClick={() => setView(key)}
              >
                {label}
              </Button>
            ))}
          </div>
          {view === "messages" &&
            record.request.messages?.map((message, index) => (
              <section key={index} className="min-w-0 rounded-lg border">
                <h3 className="border-b bg-slate-50 px-3 py-2 font-medium">
                  消息 {index + 1} · {message.role || "unknown"}
                </h3>
                <pre className="whitespace-pre-wrap break-words p-4 font-mono text-sm leading-6">
                  {typeof message.content === "string"
                    ? message.content
                    : JSON.stringify(message.content, null, 2)}
                </pre>
                {Object.keys(message).some(
                  (k) => !["role", "content"].includes(k),
                ) && (
                  <details className="border-t p-3">
                    <summary>工具调用及其他消息字段</summary>
                    <pre className="whitespace-pre-wrap break-words">
                      {JSON.stringify(
                        Object.fromEntries(
                          Object.entries(message).filter(
                            ([k]) => !["role", "content"].includes(k),
                          ),
                        ),
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                )}
              </section>
            ))}
          {view === "tools" && (
            <pre className="whitespace-pre-wrap break-words rounded-lg border p-4 font-mono text-sm">
              {JSON.stringify(
                {
                  tools: record.request.tools,
                  response_format: record.request.response_format,
                },
                null,
                2,
              )}
            </pre>
          )}
          {view === "json" && (
            <pre className="whitespace-pre-wrap break-words rounded-lg border p-4 font-mono text-sm">
              {JSON.stringify(record.request, null, 2)}
            </pre>
          )}
        </>
      )}
    </div>
  );
}
