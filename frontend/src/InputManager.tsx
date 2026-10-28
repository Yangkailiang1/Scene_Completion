import { useEffect, useState } from "react";
import { api, projectUrl, fileUrl } from "./api";
import { NodeOutput } from "./NodeOutput";

const labels: Record<string, string> = {
  components: "系统组成",
  "api-map": "API映射",
  "api-parameters": "API参数",
  "rr-ssd": "RR SSD",
  "sr-ssd": "SR SSD",
  "fused-ssd": "融合SSD",
  "object-operations": "对象操作",
};
const statuses: Record<string, string> = {
  candidate: "完整候选，待节点校验",
  accepted: "已确认",
  active: "已采用",
  needs_confirmation: "部分或结构待确认",
  needs_conversion: "等待格式转换",
  conversion_failed: "转换失败",
  converted: "转换完成",
  source_pending: "待确认原始材料",
  source_active: "已登记原始材料",
  unclassified: "待归类",
  rejected: "已拒绝",
};
export function InputManager({
  project,
  reviewOnly = false,
}: {
  project: string;
  reviewOnly?: boolean;
}) {
  const [data, setData] = useState<any>({ items: [] }),
    [watch, setWatch] = useState<any>({}),
    [detail, setDetail] = useState<any>(null),
    [chosen, setChosen] = useState(0),
    [editor, setEditor] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [caseId, setCaseId] = useState(""),
    [cases, setCases] = useState<any[]>([]),
    [recovery, setRecovery] = useState<any>(null),
    [replace, setReplace] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => {
    if (!detail?.id) {
      setEvents([]);
      return;
    }
    let live = true;
    const loadEvents = () =>
      api(
        projectUrl(
          project,
          "events/history?task_key=" +
            encodeURIComponent("imports:" + detail.id) +
            "&limit=1000",
        ),
      )
        .then((v) => live && setEvents(v.events || []))
        .catch(() => {});
    loadEvents();
    const timer = setInterval(loadEvents, 2000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [project, detail?.id]);
  const load = async () => {
    const [a, b, c, d] = await Promise.all([
      api(projectUrl(project, "imports")),
      api(projectUrl(project, "input-scan")),
      api(projectUrl(project, "results")),
      api(projectUrl(project, "recovery")),
    ]);
    setData(a);
    setWatch(b);
    setCases(c.cases || []);
    setRecovery(d);
  };
  useEffect(() => {
    setDetail(null);
    load().catch((e) => setMessage(e.message));
    const id = setInterval(() => load().catch(() => {}), 5000);
    return () => clearInterval(id);
  }, [project]);
  const select = async (id: string) => {
    const row = await api(
      projectUrl(project, "imports?item=" + encodeURIComponent(id)),
    );
    setDetail(row);
    setChosen(0);
    setReplace(false);
    setEditor(JSON.stringify(row.artifacts?.[0]?.payload || {}, null, 2));
  };
  const action = async (fn: () => Promise<any>) => {
    setBusy(true);
    setMessage("");
    try {
      await fn();
      await load();
      setMessage("已保存；运行中变更保留为候选，下一安全执行轮接入。");
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };
  const upload = async (files: FileList | null) =>
    action(async () => {
      const rows = await Promise.all(
        Array.from(files || []).map(async (f) => ({
          name: f.name,
          content_base64: await new Promise<string>((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(String(r.result).split(",")[1]);
            r.onerror = reject;
            r.readAsDataURL(f);
          }),
        })),
      );
      return api(projectUrl(project, "imports"), {
        method: "POST",
        body: JSON.stringify({ files: rows }),
      });
    });
  const artifact = detail?.artifacts?.[chosen];
  const [coverage, setCoverage] = useState("partial");
  useEffect(
    () => setCoverage(artifact?.coverage || "partial"),
    [detail?.id, chosen, artifact?.coverage],
  );
  const decide = (decision: string) =>
    action(async () => {
      await api(projectUrl(project, "imports/" + detail.id), {
        method: "PUT",
        body: JSON.stringify({
          action: decision,
          expected_revision: detail.revision,
          artifact_id: artifact?.id,
          coverage: artifact ? coverage : undefined,
          payload: artifact ? JSON.parse(editor) : undefined,
          case_id: caseId || undefined,
          replace,
        }),
      });
      await select(detail.id);
    });
  return (
    <div className="input-manager">
      <header>
        <div>
          <h2>输入与导入</h2>
          <p>同事产物先转换、校验；完整结果复用，部分结果只补缺项。</p>
        </div>
        <button onClick={() => load().catch((e) => setMessage(e.message))}>
          刷新
        </button>
      </header>
      {message && (
        <p role="status" className="input-message">
          {message}
        </p>
      )}
      {!reviewOnly && (
        <details className="input-controls">
          <summary>文件上传、目录监控与运行范围</summary>
          <div className="input-control-grid">
            <label>
              上传多份文件
              <input
                type="file"
                multiple
                accept=".md,.markdown,.json,.xlsx"
                disabled={busy}
                onChange={(e) => upload(e.target.files)}
              />
            </label>
            <label>
              上传文件夹
              <input
                type="file"
                multiple
                {...{ webkitdirectory: "" }}
                disabled={busy}
                onChange={(e) => upload(e.target.files)}
              />
            </label>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                action(() =>
                  api(projectUrl(project, "input-scan"), {
                    method: "POST",
                    body: JSON.stringify({
                      directory: form.get("directory"),
                      watch: form.get("watch") === "on",
                      expected_revision: watch.revision,
                    }),
                  }),
                );
              }}
            >
              <label>
                服务所在电脑的input目录
                <input
                  name="directory"
                  key={watch.directory}
                  defaultValue={watch.directory || ""}
                  placeholder="C:\\SceneCompletion\\input"
                  required
                />
              </label>
              <label>
                <input
                  type="checkbox"
                  name="watch"
                  defaultChecked={watch.watch ?? true}
                />
                每5秒自动发现，连续两次稳定后接收
              </label>
              <button disabled={busy}>登记并扫描</button>
            </form>
            <div>
              <label>
                运行用例／优先用例
                <select
                  value={caseId}
                  onChange={(e) => setCaseId(e.target.value)}
                >
                  <option value="">全部用例，按目录顺序</option>
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.id} · {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="input-actions">
                <button
                  disabled={busy || !caseId}
                  onClick={() =>
                    action(() =>
                      api(projectUrl(project, "run"), {
                        method: "POST",
                        body: JSON.stringify({ case_ids: [caseId] }),
                      }),
                    )
                  }
                >
                  仅运行此例
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    action(() =>
                      api(projectUrl(project, "run"), {
                        method: "POST",
                        body: JSON.stringify({
                          case_ids: [],
                          priority_cases: caseId ? [caseId] : [],
                        }),
                      }),
                    )
                  }
                >
                  优先此例，继续其余
                </button>
              </div>
              <small>关闭网页不停止执行；结果按用例实时发布。</small>
            </div>
          </div>
        </details>
      )}
      <div className="input-columns">
        <aside aria-label="导入文件列表">
          {data.items.length === 0 ? (
            <p>尚无文件。支持Markdown、JSON和测试XLSX。</p>
          ) : (
            data.items.map((r: any) => (
              <button
                key={r.id}
                className={detail?.id === r.id ? "active" : ""}
                onClick={() => select(r.id).catch((e) => setMessage(e.message))}
              >
                <strong>{r.name}</strong>
                <small>
                  {r.role} · {statuses[r.status] || r.status}
                </small>
              </button>
            ))
          )}
        </aside>
        <section className="input-detail">
          {!detail ? (
            <div className="node-empty">
              <h3>选择文件查看来源与转换结果</h3>
              <p>
                有歧义、部分覆盖或替换成功结果时需要确认。原始测试与正向产物始终分开。
              </p>
            </div>
          ) : (
            <>
              <div className="input-detail-heading">
                <h3>{detail.name}</h3>
                <a
                  href={fileUrl(project, detail.original)}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看原文件
                </a>
                <span>版本 {detail.revision}</span>
              </div>
              {detail.error && <p role="alert">{detail.error}</p>}
              {detail.artifacts?.length ? (
                <>
                  <label>
                    目标产物
                    <select
                      value={chosen}
                      onChange={(e) => {
                        const n = Number(e.target.value);
                        setChosen(n);
                        setEditor(
                          JSON.stringify(detail.artifacts[n].payload, null, 2),
                        );
                      }}
                    >
                      {detail.artifacts.map((a: any, n: number) => (
                        <option key={a.id} value={n}>
                          {labels[a.task]} · {a.case_hint || "项目共享/待绑定"}{" "}
                          · {a.coverage === "complete" ? "完整" : "部分"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    覆盖范围（完整仍须通过节点校验）
                    <select
                      value={coverage}
                      disabled={reviewOnly}
                      onChange={(e) => setCoverage(e.target.value)}
                    >
                      <option value="partial">部分：只补充已声明事实</option>
                      <option value="complete">
                        完整：已覆盖该节点／用例全部范围
                      </option>
                    </select>
                  </label>
                  <p>
                    {statuses[artifact.status] || artifact.status}{" "}
                    {artifact.error && " · " + artifact.error}
                  </p>
                  <label>
                    标准化JSON（可编辑，提交仍需校验）
                    <textarea
                      className="input-json"
                      value={editor}
                      readOnly={reviewOnly}
                      onChange={(e) => setEditor(e.target.value)}
                      spellCheck={false}
                    />
                  </label>
                  {!reviewOnly && (
                    <div className="input-actions">
                      <label>
                        <input
                          type="checkbox"
                          checked={replace}
                          onChange={(e) => setReplace(e.target.checked)}
                        />
                        确认替换已有成功产物
                      </label>
                      <button disabled={busy} onClick={() => decide("accept")}>
                        确认本产物
                      </button>
                      <button disabled={busy} onClick={() => decide("reject")}>
                        拒绝
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <p>
                    {statuses[detail.status] || detail.status}
                    。未知格式可重试转换；RR/SR/测试来源需明确确认用途。
                  </p>
                  {!reviewOnly && (
                    <div className="input-actions">
                      {["RR", "SR", "test"].map((role) => (
                        <button
                          key={role}
                          disabled={busy}
                          onClick={() =>
                            action(async () => {
                              await api(
                                projectUrl(project, "imports/" + detail.id),
                                {
                                  method: "PUT",
                                  body: JSON.stringify({
                                    action: "accept_source",
                                    role,
                                    replace,
                                    expected_revision: detail.revision,
                                  }),
                                },
                              );
                              await select(detail.id);
                            })
                          }
                        >
                          登记为{role}
                        </button>
                      ))}
                      <label>
                        <input
                          type="checkbox"
                          checked={replace}
                          onChange={(e) => setReplace(e.target.checked)}
                        />
                        替换同名来源
                      </label>
                      <button
                        disabled={busy}
                        onClick={() => decide("retry_conversion")}
                      >
                        重试格式转换
                      </button>
                    </div>
                  )}
                </>
              )}
              <details>
                <summary>格式转换实时输出</summary>
                <div className="input-conversion-log">
                  <NodeOutput
                    events={events}
                    loading={false}
                    active={detail.status === "needs_conversion"}
                  />
                </div>
              </details>
              <details>
                <summary>版本与转换记录</summary>
                <p>
                  已采用节点：
                  {detail.usage?.map((u: any) => u.node).join("、") ||
                    "尚未采用"}
                </p>
                <pre>{JSON.stringify(detail.history, null, 2)}</pre>
              </details>
            </>
          )}
        </section>
      </div>
      {recovery && (
        <details className="input-recovery">
          <summary>
            自动恢复策略与记录 · 默认每节点最多2次、每轮20次额外调用
          </summary>
          <p>
            恢复只修复本节点结果或使用预设参数；程序错误保留故障包，未知业务保留待确认。
          </p>
          {!reviewOnly && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                action(() =>
                  api(projectUrl(project, "recovery"), {
                    method: "PUT",
                    body: JSON.stringify({
                      expected_revision: recovery.revision,
                      settings: {
                        ...recovery.settings,
                        enabled: f.get("enabled") === "on",
                        max_output_tokens: f.get("ceiling")
                          ? Number(f.get("ceiling"))
                          : null,
                      },
                    }),
                  }),
                );
              }}
            >
              <label>
                <input
                  name="enabled"
                  type="checkbox"
                  defaultChecked={recovery.settings.enabled}
                />
                启用有界恢复
              </label>
              <label>
                允许恢复时使用的输出上限（留空则不自动调大）
                <input
                  name="ceiling"
                  type="number"
                  min="256"
                  defaultValue={recovery.settings.max_output_tokens || ""}
                />
              </label>
              <button disabled={busy}>保存策略</button>
            </form>
          )}
          <pre>{JSON.stringify(recovery.ledger, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
