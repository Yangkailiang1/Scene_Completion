import { useEffect, useState } from "react";
import { Bot, Maximize2, Minimize2, X, Send, ChevronDown } from "lucide-react";
import { api, projectUrl } from "./api";
import { ManagerModelProfile } from "./ManagerModelProfile";
import { ThroughputView } from "./ThroughputView";
import { NodeOutput } from "./NodeOutput";
export function ManagerPanel({
  project,
  reviewOnly = false,
}: {
  project: string;
  reviewOnly?: boolean;
}) {
  const [open, setOpen] = useState(false),
    [large, setLarge] = useState(false),
    [tab, setTab] = useState("chat"),
    [data, setData] = useState<any>(null),
    [text, setText] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [events, setEvents] = useState<any[]>([]),
    [older, setOlder] = useState<any[]>([]);
  async function load() {
    const v = await api(projectUrl(project, "manager"));
    setData(v);
  }
  useEffect(() => {
    setData(null);
    setEvents([]);
    setOpen(false);
  }, [project]);
  useEffect(() => {
    if (!open) return;
    let live = true;
    const update = async () => {
      try {
        const v = await api(projectUrl(project, "manager"));
        if (live) setData(v);
        if (tab === "chat") {
          const e = await api(
            projectUrl(
              project,
              "events/history?task_key=__manager__&limit=200",
            ),
          );
          if (live) setEvents(e.events || []);
        }
      } catch (e: any) {
        if (live) setMessage(e.message);
      }
    };
    update();
    const id = setInterval(update, 2500);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [project, open, tab]);
  async function action(path: string, body: any, method = "POST") {
    setBusy(true);
    try {
      await api(projectUrl(project, "manager/" + path), {
        method,
        body: JSON.stringify(body),
      });
      await load();
      setMessage("");
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  }
  const config = data?.configuration;
  useEffect(() => setOlder([]), [project, data?.session?.id]);
  const messages = [...new Map([...older, ...(data?.messages || [])].map(m => [m.id, m])).values()].sort((a,b) => a.id-b.id);
  async function loadOlder() {
    try {
      const v = await api(projectUrl(project, "manager/messages?limit=100&before=" + (messages[0]?.id || 0)));
      setOlder(p => [...v.messages, ...p]);
      if (!v.messages.length) setMessage("已到当前会话开头；记忆和历史操作独立保存。");
    } catch (e:any) {setMessage(e.message);}
  }
  return (
    <>
      {!open ? (
        <button
          className="manager-fab"
          onClick={() => setOpen(true)}
          aria-label="打开项目管理Agent"
        >
          <Bot size={21} />
          <span>项目管理Agent</span>
        </button>
      ) : (
        <section
          className={"manager-floating " + (large ? "maximized" : "")}
          aria-label="项目管理Agent"
        >
          <header>
            <Bot size={23} />
            <div>
              <strong>项目管理Agent</strong>
              <small>
                {data?.runtime?.status || "正在读取"} · 会话与操作持续保存
              </small>
            </div>
            <button
              aria-label={large ? "还原管理窗口" : "最大化管理窗口"}
              onClick={() => setLarge(!large)}
            >
              {large ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
            </button>
            <button aria-label="收起管理Agent" onClick={() => setOpen(false)}>
              <X size={18} />
            </button>
          </header>
          <div className="manager-mode-bar">
            <label>
              托管模式
              <select
                disabled={reviewOnly || busy || !config}
                value={config?.settings.mode || "collaborative"}
                onChange={(e) =>
                  action(
                    "config",
                    {
                      expected_revision: config.revision,
                      settings: { mode: e.target.value },
                    },
                    "PUT",
                  )
                }
              >
                <option value="collaborative">协作 · 可询问与确认</option>
                <option value="auto">Auto · 自动推进与修复</option>
              </select>
            </label>
            <button
              disabled={reviewOnly || busy || !config}
              className={config?.settings.enabled ? "active" : ""}
              onClick={() =>
                action(
                  "config",
                  {
                    expected_revision: config.revision,
                    settings: { enabled: !config.settings.enabled },
                  },
                  "PUT",
                )
              }
            >
              {config?.settings.enabled ? "暂停托管" : "启用托管"}
            </button>
          </div>
          <nav className="manager-tabs">
            {[
              ["chat", "对话"],
              ["plan", "计划与阻塞"],
              ["actions", "操作与补丁"],
              ["memory", "记忆"],
              ["throughput", "吞吐监视"],
              ["model", "模型"],
            ].map(([id, label]) => (
              <button
                key={id}
                className={tab === id ? "active" : ""}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>
          {message && (
            <p role="alert" className="manager-notice">
              {message}
            </p>
          )}
          <div className="manager-content">
            {tab === "chat" && (
              <>
                <div className="manager-messages">
                  {!!messages.length && <button onClick={loadOlder}>查看更早的会话</button>}
                  {!data?.messages?.length && (
                    <div className="manager-welcome">
                      <h3>让管理Agent协助推进项目</h3>
                      <p>
                        可以询问阻塞原因、检查导入结果，或让它诊断和修复失败节点。Auto会持续托管；协作模式会询问需要你决定的事项。
                      </p>
                    </div>
                  )}
                  {messages.map((m: any) => (
                    <article key={m.id} className={"manager-message " + m.kind}>
                      <small>
                        {(
                          {
                            user: "你",
                            assistant: "管理Agent",
                            question: "需要确认",
                            system: "运行记录",
                          } as any
                        )[m.kind] || m.kind}{" "}
                        · {new Date(m.at * 1000).toLocaleTimeString()}
                      </small>
                      <div>{m.content}</div>
                    </article>
                  ))}
                </div>
                <details className="manager-live">
                  <summary>本轮实时输出与工具事件</summary>
                  <NodeOutput
                    events={events}
                    loading={false}
                    active={data?.runtime?.status === "running"}
                  />
                </details>
                {data?.runtime?.reason && (
                  <p className="manager-runtime-reason">
                    {data.runtime.reason}
                  </p>
                )}
              </>
            )}
            {tab === "plan" && (
              <>
                <h3>当前执行计划</h3>
                {data?.plan?.items?.map((item: any, i: number) => (
                  <article className="manager-plan" key={i}>
                    <strong>{item.task}</strong>
                    <span>{item.status}</span>
                    <p>{item.reason || item.node}</p>
                  </article>
                ))}
                {!data?.plan?.items?.length && (
                  <p>发送“检查当前进展并制定计划”，Agent将读取真实DAG。</p>
                )}
                <button
                  disabled={reviewOnly || busy}
                  onClick={() => action("run", {})}
                >
                  检查并推进
                </button>
                <h4>独立试跑</h4>
                {data?.trials?.map((t: any) => (
                  <p key={t.id}>
                    {t.assumption} · 项目 {t.project_id} · 不合并正式指标
                  </p>
                ))}
              </>
            )}
            {tab === "actions" && (
              <>
                <h3>补丁与回退点</h3>
                {data?.patches?.map((p: any) => (
                  <article className="manager-plan" key={p.id}>
                    <strong>{p.reason}</strong>
                    <span>{p.status}</span>
                    <pre>{p.test?.summary}</pre>
                    <button
                      disabled={busy || reviewOnly}
                      onClick={() =>
                        action("actions", {
                          action:
                            p.status === "applied"
                              ? "rollback_patch"
                              : "apply_patch",
                          arguments: { id: p.id },
                          confirmed: true,
                        })
                      }
                    >
                      {p.status === "applied"
                        ? "回退补丁"
                        : "确认应用已验证补丁"}
                    </button>
                  </article>
                ))}
                <h3>操作记录</h3>
                {data?.operations?.map((o: any) => (
                  <article className="manager-plan" key={o.id}>
                    <strong>{o.action}</strong>
                    <span>{o.status}</span>
                    <p>{o.error || o.result}</p>
                  </article>
                ))}
              </>
            )}
            {tab === "memory" && (
              <>
                <h3>项目记忆</h3>
                <p>
                  用户决定、计划、故障和推理假设分别保存。停用记忆不会删除历史。
                </p>
                {data?.memory?.map((m: any) => (
                  <article className="manager-plan" key={m.id}>
                    <small>
                      {m.category} · {m.source} · v{m.revision}
                    </small>
                    <textarea
                      aria-label="记忆内容"
                      defaultValue={m.text}
                      id={"memory-" + m.id}
                    />
                    <button
                      disabled={busy || reviewOnly}
                      onClick={() =>
                        action(
                          "memory",
                          {
                            id: m.id,
                            expected_revision: m.revision,
                            category: m.category,
                            text: (
                              document.getElementById(
                                "memory-" + m.id,
                              ) as HTMLTextAreaElement
                            ).value,
                            active: m.active,
                            source: m.source,
                            scope: m.scope,
                          },
                          "PUT",
                        )
                      }
                    >
                      保存修改
                    </button>
                    <button
                      disabled={busy || reviewOnly}
                      onClick={() =>
                        action(
                          "memory",
                          {
                            id: m.id,
                            expected_revision: m.revision,
                            category: m.category,
                            text: m.text,
                            active: !m.active,
                            source: m.source,
                            scope: m.scope,
                          },
                          "PUT",
                        )
                      }
                    >
                      {m.active ? "停用" : "启用"}
                    </button>
                  </article>
                ))}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    action(
                      "memory",
                      {
                        category: f.get("category"),
                        text: f.get("text"),
                        expected_revision: 0,
                      },
                      "PUT",
                    );
                    e.currentTarget.reset();
                  }}
                >
                  <select name="category">
                    <option value="decision">用户决定</option>
                    <option value="plan">执行计划</option>
                    <option value="fault">故障经验</option>
                    <option value="assumption">试跑假设</option>
                  </select>
                  <textarea
                    name="text"
                    placeholder="记录本项目的决定或经验"
                    required
                  />
                  <button disabled={busy || reviewOnly}>添加记忆</button>
                </form>
                <button
                  disabled={busy || reviewOnly}
                  onClick={() =>
                    action("run", {
                      new_session: true,
                      text: "新会话，请先查看已有记忆和项目状态。",
                    })
                  }
                >
                  新建会话，保留记忆
                </button>
              </>
            )}
            {tab === "throughput" && <ThroughputView project={project} />}{" "}
            {tab === "model" && <ManagerModelProfile project={project} />}
          </div>
          {tab === "chat" && (
            <form
              className="manager-composer"
              onSubmit={(e) => {
                e.preventDefault();
                if (!text.trim()) return;
                action("messages", { text });
                setText("");
              }}
            >
              <textarea
                aria-label="发送给管理Agent"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="例如：哪个节点卡住了？请检查同事文件并继续首个用例。"
                disabled={reviewOnly}
              />
              <button disabled={busy || reviewOnly || !text.trim()}>
                <Send size={17} />
                发送
              </button>
            </form>
          )}
        </section>
      )}
    </>
  );
}
