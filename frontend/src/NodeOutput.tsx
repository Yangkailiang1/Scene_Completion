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
import { display } from "./utils";
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
        "tool_started",
        "tool_finished",
        "tool_failed",
        "validation_failed",
        "agent_failed",
        "result_validated",
        "artifacts_saved",
        "task_status",
      ].includes(e.kind)
    ) {
      let text = "";
      if (e.kind === "request_started") text = `请求 ${d.requested_model}`;
      if (e.kind === "request_finished")
        text = `实际返回模型：${d.provider_model || "未报告"}`;
      if (e.kind === "tool_started") text = d.arguments || "";
      if (e.kind === "tool_finished") text = d.result || "";
      if (e.kind.endsWith("failed"))
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
  tool_started: "调用工具",
  tool_finished: "工具返回",
  tool_failed: "工具失败",
  validation_failed: "校验未通过",
  agent_failed: "执行失败",
  result_validated: "校验通过",
  artifacts_saved: "产物已保存",
  task_status: "任务状态",
};
export function NodeOutput({
  events,
  loading,
}: {
  events: ExecutionEvent[];
  loading: boolean;
}) {
  const groups = useMemo(() => segments(events), [events]);
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
                  <pre>{g.text || "…"}</pre>
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
