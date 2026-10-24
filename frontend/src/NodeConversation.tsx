import { useState, useEffect } from "react";
import { Send, MessageCircle, RotateCcw } from "lucide-react";
import { api, projectUrl } from "./api";
import { Button } from "./components/ui/button";
export function NodeConversation({
  projectId,
  taskKey,
  planned,
  onChanged,
}: {
  projectId: string;
  taskKey: string;
  planned?: boolean;
  onChanged: () => void;
}) {
  const [data, setData] = useState<any>({ messages: [], question: null }),
    [text, setText] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function refresh() {
    if (planned) return;
    const r = await api(
      projectUrl(
        projectId,
        "conversation?task_key=" + encodeURIComponent(taskKey),
      ),
    );
    setData({ messages: r.messages || [], question: r.question || null });
  }
  useEffect(() => {
    let active = true;
    if (!planned) {
      api(
        projectUrl(
          projectId,
          "conversation?task_key=" + encodeURIComponent(taskKey),
        ),
      )
        .then(
          (r) =>
            active &&
            setData({
              messages: r.messages || [],
              question: r.question || null,
            }),
        )
        .catch(() => {});
      const t = setInterval(() => refresh().catch(() => {}), 1800);
      return () => {
        active = false;
        clearInterval(t);
      };
    }
    setData({ messages: [], question: null });
  }, [projectId, taskKey, planned]);
  async function send() {
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api(
        projectUrl(projectId, data.question ? "answer" : "conversation"),
        {
          method: "POST",
          body: JSON.stringify({
            task_key: taskKey,
            text,
            question_id: data.question?.detail.question_id,
          }),
        },
      );
      setText("");
      await refresh();
      onChanged();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="node-conversation">
      <details className="conversation-history" open={!!data.question}>
        <summary>
          <MessageCircle size={14} /> 节点对话 · {data.messages.length} 条记录{" "}
          <span>仅本节点生效</span>
        </summary>
        <div className="chat-messages">
          {data.messages.map((m: any) => (
            <article key={m.id} className={"chat-message " + m.kind}>
              <strong>
                {{
                  guidance: "我的指导",
                  answer: "我的回答",
                  assistant: "模型回复",
                  question: "模型提问",
                  system: "系统",
                }[m.kind as string] || m.kind}
                <small>
                  {m.kind === "guidance" || m.kind === "answer"
                    ? m.applied
                      ? "已生效"
                      : "已接收 · 待模型调用"
                    : new Date(m.at * 1000).toLocaleTimeString()}
                </small>
              </strong>
              <p>{m.text}</p>
              {m.kind === "question" && (
                <p className="question-basis">
                  依据：{m.detail.basis}
                  <br />
                  需要决定：{m.detail.decision}
                </p>
              )}
            </article>
          ))}
        </div>
      </details>
      {data.question && (
        <div className="question-alert">
          <b>此节点等待回答：</b>
          {data.question.text}
          <small>其他独立节点继续执行，回答后自动恢复。</small>
        </div>
      )}
      <div className="composer-row">
        <textarea
          aria-label="节点指导或回答"
          disabled={planned || busy}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            planned
              ? "流程预告节点尚未创建，展开后可对话"
              : data.question
                ? "请输入回答，解除本节点阻塞"
                : "对这个节点提出意见或问题；指导在下一次模型调用生效"
          }
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              send();
            }
          }}
        />
        <Button
          aria-label={data.question ? "回答并继续" : "发送指导"}
          disabled={planned || busy || !text.trim()}
          onClick={send}
        >
          <Send size={15} />
          {data.question ? "回答" : "发送"}
        </Button>
      </div>
      <div className="composer-hint">
        <span>Ctrl / ⌘ + Enter发送 · 不会中断当前HTTP输出</span>
        <button
          disabled={planned || busy}
          onClick={async () => {
            setBusy(true);
            try {
              await api(projectUrl(projectId, "rerun-node"), {
                method: "POST",
                body: JSON.stringify({ task_key: taskKey }),
              });
              onChanged();
            } catch (e) {
              setError(String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <RotateCcw size={12} />
          按指导重做
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
