import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown,
  ChevronDown,
  FileJson,
  Radio,
  Terminal,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { display, failureText } from "./utils";
import type { ExecutionEvent } from "./types";
export interface LogSegment {
  id: number;
  kind: string;
  channel?: string;
  name?: string;
  text: string;
  at: number;
  attempt: number | null;
}
export function segments(events: ExecutionEvent[]): LogSegment[] {
  const rows: LogSegment[] = [];
  for (const e of events) {
    const d = e.data;
    if (e.kind === "stream_delta") {
      const channel = d.channel;
      const name = d.tool_name || "";
      const key = `${e.attempt}:${d.model_call_id || ""}:${channel}:${d.tool_index ?? ""}`;
      const last = rows[rows.length - 1] as LogSegment & { key?: string };
      if (last?.kind === "stream_delta" && last.key === key) {
        last.text += d.text || "";
        last.name = (last.name || "") + name;
      } else
        rows.push({
          ...e,
          kind: e.kind,
          channel,
          name,
          text: d.text || "",
          key,
        } as LogSegment);
    } else if (
      [
        "request_started",
        "request_finished",
        "request_failed",
        "stream_progress",
        "stream_status",
        "endpoint_wait",
        "endpoint_admitted",
        "tool_started",
        "tool_finished",
        "tool_failed",
        "validation_failed",
        "agent_failed",
        "result_validated",
        "artifacts_saved",
        "task_status",
        "rate_limit_wait",
        "guidance_applied",
        "question_asked",
      ].includes(e.kind)
    ) {
      let text = "";
      if (e.kind === "stream_status") text = d.message;
      if (e.kind === "endpoint_wait")
        text = `等待账号并发名额（总上限${d.limit}路，包含其他项目和节点对话）`;
      if (e.kind === "endpoint_admitted")
        text = `已取得模型请求名额，等待${d.wait_seconds}秒`;
      if (e.kind === "rate_limit_wait")
        text = `限流冷却，${new Date(d.retry_at * 1000).toLocaleTimeString()}重试（${d.retry_count}/3）`;
      if (e.kind === "guidance_applied")
        text = `节点指导版本${d.revision}已生效`;
      if (e.kind === "question_asked")
        text = d.question?.text || "等待用户回答";
      if (e.kind === "request_started")
        text =
          `请求 ${d.requested_model}` +
          (d.input_bytes
            ? ` · 输入${(d.input_bytes / 1024).toFixed(1)}KB · 输出上限${d.max_output_tokens} tokens · 生成总时限${d.stream_total_timeout_seconds}秒`
            : "");
      if (e.kind === "stream_progress")
        text = `服务仍在返回增量：已等待${Math.round(d.elapsed_seconds)}秒，已接收${d.output_bytes}字节正文／工具参数`;
      if (e.kind === "request_failed") text = failureText(d.diagnostic);
      if (e.kind === "request_finished")
        text = `实际返回模型：${d.provider_model || "未报告"}`;
      if (e.kind === "tool_started") text = d.arguments || "";
      if (e.kind === "tool_finished") text = d.result || "";
      if (e.kind.endsWith("failed") && e.kind !== "request_failed")
        text = d.error || d.failure?.error || display(d);
      if (e.kind === "artifacts_saved") text = (d.files || []).join("\n");
      if (e.kind === "result_validated") text = "产物已通过结构与来源校验";
      if (e.kind === "task_status")
        text = d.failure?.error || d.failure?.reason || d.status;
      rows.push({
        id: e.id,
        at: e.at,
        kind: e.kind,
        name: d.tool,
        text,
        attempt: e.attempt,
      });
    }
  }
  return rows;
}
const labels: Record<string, string> = {
  request_started: "模型请求",
  request_finished: "请求结束",
  request_failed: "请求未完成",
  stream_progress: "生成进展",
  stream_status: "模型状态",
  endpoint_wait: "并发排队",
  endpoint_admitted: "继续请求",
  tool_started: "调用工具",
  tool_finished: "工具返回",
  tool_failed: "工具失败",
  validation_failed: "校验未通过",
  agent_failed: "执行失败",
  result_validated: "校验通过",
  artifacts_saved: "产物已保存",
  task_status: "任务状态",
  rate_limit_wait: "限流冷却",
  guidance_applied: "指导已生效",
  question_asked: "模型提问",
};
export function NodeOutput({
  events,
  loading,
  active = false,
}: {
  events: ExecutionEvent[];
  loading: boolean;
  active?: boolean;
}) {
  const groups = useMemo(() => segments(events), [events]);
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!active) return;
    setNow(Date.now() / 1000);
    const timer = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, [active]);
  const request = [...events]
    .reverse()
    .find((e) => e.kind === "request_started" && e.data.purpose !== "dialogue");
  const requestEvents = request
    ? events.filter(
        (e) =>
          e.id >= request.id &&
          e.data.model_call_id === request.data.model_call_id,
      )
    : [];
  const waiting =
    active &&
    request &&
    !requestEvents.some((e) =>
      ["request_finished", "request_failed"].includes(e.kind),
    );
  const deltas = requestEvents.filter((e) => e.kind === "stream_delta");
  const received = deltas.reduce((n, e) => n + (e.data.text?.length || 0), 0);
  const pendingTool = deltas.find((e) => e.data.tool_name === "submit_result")
    ? "submit_result"
    : deltas.find((e) => e.data.tool_name)?.data.tool_name;
  const lastDelta = deltas[deltas.length - 1];
  const viewport = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  useEffect(() => {
    if (follow && viewport.current)
      viewport.current.scrollTop = viewport.current.scrollHeight;
  }, [events.length, follow]);
  return (
    <div className="log-container">
      <div className="log-meta">
        <span>
          <Radio size={12} />
          {events.length} 条已保存事件
        </span>
        <span>断线后可续接 · 只显示模型正文与工具输出</span>
      </div>
      {waiting && (
        <div className="live-stream-status" role="status">
          <strong>
            {received === 0
              ? pendingTool === "submit_result"
                ? "正在等待结构化产物正文"
                : "已发送请求，尚未收到可显示正文"
              : "已收到流式内容，等待本次请求完成"}
          </strong>
          <p>
            本次请求已等待 {Math.max(0, Math.floor(now - request.at))} 秒 ·
            已收到 {received.toLocaleString()} 字符
            {lastDelta
              ? ` · 最近增量${Math.max(0, Math.floor(now - lastDelta.at))}秒前`
              : ""}
          </p>
          {received === 0 && (
            <small>
              {pendingTool === "submit_result"
                ? "上游已返回submit_result工具名，但参数正文仍为空；本接口的大JSON可能在生成完成后集中返回。"
                : "尚无正文不代表请求已经失败；这里只展示模型实际返回的文本和工具参数。"}
            </small>
          )}
        </div>
      )}
      <div
        className="log-scroll"
        ref={viewport}
        onScroll={(e) => {
          const n = e.currentTarget;
          setFollow(n.scrollHeight - n.scrollTop - n.clientHeight < 60);
        }}
      >
        {groups.length === 0 ? (
          <div className="node-empty">
            <Terminal size={30} />
            <h3>{loading ? "正在读取历史输出" : "尚无流式输出"}</h3>
            <p>
              节点开始执行后会显示实时内容。历史运行没有记录的输出不会补造。
            </p>
          </div>
        ) : (
          groups.map((g) => {
            const time = new Date(g.at * 1000).toLocaleTimeString("zh-CN", {
              hour12: false,
            });
            if (g.kind === "stream_delta")
              return (
                <section
                  key={g.id}
                  className={`stream-block ${g.channel === "tool_arguments" ? "tool" : "text"}`}
                >
                  <div className="stream-heading">
                    <span>
                      {g.channel === "tool_arguments" ? (
                        <FileJson size={13} />
                      ) : (
                        <Terminal size={13} />
                      )}{" "}
                      {g.channel === "tool_arguments"
                        ? `工具参数 · ${g.name || "生成中"}`
                        : "模型输出"}
                    </span>
                    <small>
                      {time} · 尝试 {g.attempt || 1}
                    </small>
                  </div>
                  {g.channel === "tool_arguments" ? (
                    <details
                      open={g.name === "submit_result" && g.text.length > 0}
                    >
                      <summary>
                        {g.name === "submit_result"
                          ? "查看结构化产物正文"
                          : "查看工具参数增量"}{" "}
                        · {g.text.length.toLocaleString()} 字符
                      </summary>
                      <pre>{g.text || "…"}</pre>
                    </details>
                  ) : (
                    <pre>{g.text || "…"}</pre>
                  )}
                </section>
              );
            const bad = g.kind.endsWith("failed");
            const details = ["tool_started", "tool_finished"].includes(g.kind);
            return (
              <div key={g.id} className={`event-line ${bad ? "error" : ""}`}>
                {bad ? <AlertCircle size={13} /> : <CheckCircle2 size={13} />}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <strong>
                      {labels[g.kind] || g.kind}
                      {g.name ? " · " + g.name : ""}
                    </strong>
                    <time>{time}</time>
                  </div>
                  {details ? (
                    <details>
                      <summary>
                        查看内容 <ChevronDown size={10} />
                      </summary>
                      <pre>{g.text}</pre>
                    </details>
                  ) : (
                    <p>{g.text}</p>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
      {!follow && (
        <Button
          className="follow-button"
          size="sm"
          variant="outline"
          onClick={() => {
            setFollow(true);
            viewport.current?.scrollTo({
              top: viewport.current.scrollHeight,
              behavior: "smooth",
            });
          }}
        >
          <ArrowDown size={13} />
          回到最新输出
        </Button>
      )}
    </div>
  );
}
