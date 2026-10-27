import { useEffect, useRef, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { api, projectUrl } from "./api";
import { SourceEvidence } from "./SourceEvidence";
const choices: Record<string, string> = {
  unresolved: "未处理",
  answered: "已回答",
  anomaly: "已确认异常",
  not_anomaly: "无需纳入／已跳过",
  needs_info: "待补材料",
  historical: "历史问题",
  all: "全部",
};
const stages: Record<string, string> = {
  "normal-rules": "建模器 · 正向正常规则",
  "concern-match": "建模器 · 关注点识别",
  "existing-bind": "检查器 · 已有异常绑定",
  "existing-extract": "检查器 · 已有异常细化",
  "test-ground-truth": "独立测试 · GT整理",
  "fused-ssd": "建模器 · SSD",
  "enriched-view": "建模器 · 交互补全",
};
export function PendingView({
  project,
  onSelect,
  onEvidenceOpen,
}: {
  project: string;
  onSelect: (id: string) => void;
  onEvidenceOpen?: () => void;
}) {
  const [data, setData] = useState<any>(null),
    [defs, setDefs] = useState<Record<string, any>>({});
  const [status, setStatus] = useState("unresolved"),
    [queue, setQueue] = useState("business"),
    [cid, setCase] = useState(""),
    [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [channel, setChannel] = useState(""),
    [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<any>(null),
    [choice, setChoice] = useState("needs_info"),
    [concern, setConcern] = useState(""),
    [note, setNote] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [reload, setReload] = useState(0);
  const [reviewer, setReviewer] = useState(
    () => localStorage.getItem("scene-reviewer") || "",
  );
  const [evidence, setEvidence] = useState<any>(null),
    [collapsed, setCollapsed] = useState(false),
    [history, setHistory] = useState<any[] | null>(null);
  const drafts = useRef<Record<string, any>>({});
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query);
      setOffset(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    let active = true;
    setData(null);
    api(
      projectUrl(
        project,
        `pending?queue=${queue}&status=${status}&offset=${offset}&limit=40&search=${encodeURIComponent(search)}${channel ? "&channel=" + channel : ""}${cid ? "&case=" + encodeURIComponent(cid) : ""}`,
      ),
    )
      .then((d) => {
        if (active) {
          setData(d);
          pick(d.items[0] || null);
        }
      })
      .catch((e) => active && setNotice(e.message));
    return () => {
      active = false;
    };
  }, [project, queue, status, offset, search, channel, cid, reload]);
  useEffect(() => {
    api(projectUrl(project, "registry"))
      .then((d) => setDefs(d.registry.definitions))
      .catch((e) => setNotice(e.message));
  }, [project]);
  useEffect(() => {
    if (selected) drafts.current[selected.id] = { choice, concern, note };
  }, [choice, concern, note, selected]);
  function pick(item: any) {
    const d = drafts.current[item?.id];
    setSelected(item);
    setChoice(d?.choice || item?.decision?.choice || "needs_info");
    setConcern(
      d?.concern || item?.decision?.concern_key || item?.concern_key || "",
    );
    setNote(d?.note || item?.decision?.answer || item?.decision?.note || "");
    setHistory(null);
    if (evidence) setEvidence(item?.source_refs?.[0] || null);
  }
  async function save(action = choice) {
    if (!selected) return;
    setBusy(true);
    try {
      await api(projectUrl(project, "pending/" + selected.id), {
        method: "POST",
        body: JSON.stringify({
          choice: action,
          concern_key: concern,
          note,
          revision: selected.decision?.revision || 0,
          ...(selected.question_type
            ? {
                answer: note,
                reviewer,
                expected_origin_bindings: selected.origin_bindings,
              }
            : {}),
        }),
      });
      delete drafts.current[selected.id];
      localStorage.setItem("scene-reviewer", reviewer);
      setNotice(
        "审核已保存；不会自动调用模型或重跑。反馈交回研发后，按来源节点及下游定向重算。",
      );
      setReload((x) => x + 1);
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }
  function openEvidence(r: any) {
    setEvidence(r);
    setCollapsed(true);
    onEvidenceOpen?.();
  }
  const typed = !!selected?.question_type;
  const options = selected?.answer_spec?.choices || {
    needs_info: "信息不足，待补材料",
    not_anomaly: "不是异常场景，跳过",
    anomaly: "是异常场景",
  };
  return (
    <div className="management-view pending-review-view">
      {notice && (
        <div role="status" className="management-notice">
          {notice}
        </div>
      )}
      <div className="management-filters">
        <select
          aria-label="待确认类型"
          value={queue}
          onChange={(e) => {
            setQueue(e.target.value);
            setOffset(0);
          }}
        >
          <option value="business">业务确认问题</option>
          <option value="structure">结构与归属核查</option>
          <option value="rules">未明确的规则</option>
          <option value="technical">执行问题（研发）</option>
          <option value="all">全部问题</option>
        </select>
        <div className="segmented">
          {Object.entries(choices).map(([v, n]) => (
            <button
              className={status === v ? "active" : ""}
              key={v}
              onClick={() => {
                setStatus(v);
                setOffset(0);
              }}
            >
              {n}
              {data?.counts?.[v] != null ? ` ${data.counts[v]}` : ""}
            </button>
          ))}
        </div>
        <select
          aria-label="筛选用例"
          value={cid}
          onChange={(e) => {
            setCase(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">全部用例</option>
          {data?.cases.map((c: string) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="筛选问题来源"
          value={channel}
          onChange={(e) => {
            setChannel(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">全部来源</option>
          <option value="positive">正向建模</option>
          <option value="existing_e">原文已有异常E</option>
          <option value="test_gt">独立测试GT</option>
        </select>
        <input
          aria-label="搜索问题"
          placeholder="搜索问题、对象或字段"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button onClick={() => setReload((x) => x + 1)}>刷新</button>
      </div>
      <div className="pending-count-note">
        业务疑问不等同于异常。回答只保存，不在业务端启动模型。
        {data?.queue_counts &&
          ` 业务 ${data.queue_counts.business.total} · 结构 ${data.queue_counts.structure.total} · 规则 ${data.queue_counts.rules.total}`}
      </div>
      {!data ? (
        <p>正在整理待确认项…</p>
      ) : (
        <div
          className={`management-body review-columns ${collapsed ? "list-collapsed" : ""} ${evidence ? "evidence-open" : ""}`}
        >
          <aside className="management-list" aria-label="待确认列表">
            <button
              className="review-list-toggle"
              onClick={() => setCollapsed((v) => !v)}
            >
              {collapsed ? "展开" : "收起问题列表"}
            </button>
            {!collapsed && (
              <>
                {!data.items.length && <p>当前筛选下没有待确认项。</p>}
                {data.items.map((r: any) => (
                  <button
                    key={r.id}
                    className={selected?.id === r.id ? "active" : ""}
                    onClick={() => pick(r)}
                  >
                    <small>
                      {r.case} · {r.interaction_id}
                    </small>
                    <strong>{r.reason}</strong>
                    <span>
                      {r.answer_spec?.label ||
                        stages[
                          r.origins[0]?.split(":").pop()?.split("--part-")[0]
                        ] ||
                        r.category}
                    </span>
                  </button>
                ))}
                <div className="management-pagination">
                  <button
                    disabled={!offset}
                    onClick={() => setOffset((x) => Math.max(0, x - 40))}
                  >
                    上一页
                  </button>
                  <span>
                    {data.count ? offset + 1 : 0}–
                    {Math.min(offset + 40, data.count)} / {data.count}
                  </span>
                  <button
                    disabled={offset + 40 >= data.count}
                    onClick={() => setOffset((x) => x + 40)}
                  >
                    下一页
                  </button>
                </div>
              </>
            )}
          </aside>
          <PanelGroup direction="horizontal" className="review-answer-panels">
            <Panel defaultSize={50} minSize={30}>
              <section className="management-detail review-answer-pane">
                {selected ? (
                  <>
                    <div className="detail-kicker">
                      {selected.case} / {selected.interaction_id} ·{" "}
                      {selected.source_channel} ·{" "}
                      {selected.answer_spec?.label || "业务确认"}
                    </div>
                    <h3>{selected.reason}</h3>
                    {selected.historical && (
                      <p className="management-notice">
                        历史问题：当前产物已不再提出此问题。旧回答和依据仍可追溯；修订或撤回后须由研发预览并重算。
                      </p>
                    )}
                    {selected.required_answer && (
                      <div className="question-intent">
                        <strong>需要您确认什么</strong>
                        <p>{selected.required_answer}</p>
                      </div>
                    )}
                    {selected.known_facts && (
                      <p>已知信息：{selected.known_facts}</p>
                    )}
                    {selected.object && (
                      <p>
                        对象／字段：{selected.object} ·{" "}
                        {defs[selected.concern_key]?.label ||
                          selected.concern_key}
                      </p>
                    )}
                    <div className="origin-actions">
                      {selected.origins.map((k: string) => (
                        <button key={k} onClick={() => onSelect(k)}>
                          查看来源节点 ·{" "}
                          {stages[
                            k.split(":").pop()?.split("--part-")[0] || ""
                          ] || k}
                        </button>
                      ))}
                    </div>
                    <h4>原文依据</h4>
                    {selected.source_refs?.length ? (
                      selected.source_refs.map((r: any, i: number) => (
                        <button
                          className="evidence-link-card"
                          key={i}
                          onClick={() => openEvidence(r)}
                        >
                          <small>
                            {r.source_id} · 第{r.line_start}–{r.line_end}行 ·
                            点击以查看文档
                          </small>
                          <p>{r.quote}</p>
                        </button>
                      ))
                    ) : (
                      <p className="muted">
                        此问题未给出精确引文，请先核对来源节点。
                      </p>
                    )}
                    {selected.technical ? (
                      <div className="management-notice">
                        这是执行或配置错误，请交回研发修复，不直接判作业务异常。
                      </div>
                    ) : (
                      <div className="decision-form">
                        <h4>
                          {typed
                            ? selected.answer_spec?.label || "业务回答"
                            : "业务判定"}
                        </h4>
                        {typed && (
                          <label>
                            审核人
                            <input
                              aria-label="审核人"
                              value={reviewer}
                              onChange={(e) => setReviewer(e.target.value)}
                              placeholder="姓名或业务标识"
                            />
                          </label>
                        )}
                        <label>
                          {typed ? "请选择回答方式" : "这是否属于异常场景？"}
                          <select
                            aria-label={
                              typed ? "业务回答方式" : "是否为异常场景"
                            }
                            value={choice}
                            onChange={(e) => setChoice(e.target.value)}
                          >
                            {Object.entries(options).map(([v, n]) => (
                              <option key={v} value={v}>
                                {String(n)}
                              </option>
                            ))}
                          </select>
                        </label>
                        {choice === "anomaly" && (
                          <label>
                            应归入哪一个关注点？
                            <select
                              aria-label="异常关注点分类"
                              value={concern}
                              onChange={(e) => setConcern(e.target.value)}
                            >
                              <option value="">请选择具体关注点</option>
                              {Object.entries(defs)
                                .filter(
                                  ([, d]) =>
                                    d.enabled !== false && d.kind === "check",
                                )
                                .map(([k, d]) => (
                                  <option key={k} value={k}>
                                    {d.label} · {d.group}（{k}）
                                  </option>
                                ))}
                            </select>
                          </label>
                        )}
                        <label>
                          {selected.question_type === "rule_completion"
                            ? "实际校验规则及执行位置"
                            : "判定依据或补充意见"}
                          <textarea
                            aria-label="待确认审核说明"
                            rows={6}
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            placeholder={
                              selected.question_type === "rule_completion"
                                ? "填写实际要求，例如是否校验存在、启用状态或归属，以及由哪个对象执行；不确定的内容可继续保留。"
                                : "填写具体判断、触发条件或修正对应关系；未知信息不必猜测"
                            }
                          />
                        </label>
                        <div className="review-form-actions">
                          <button
                            className="primary-action"
                            disabled={
                              busy ||
                              (choice === "anomaly" && !concern) ||
                              (typed && !reviewer.trim())
                            }
                            onClick={() => save()}
                          >
                            {busy ? "保存中…" : typed ? "保存回答" : "保存判定"}
                          </button>
                          {typed && selected.decision && (
                            <button
                              disabled={busy || !reviewer.trim()}
                              onClick={() => save("withdraw")}
                            >
                              撤回本次回答
                            </button>
                          )}
                          <button
                            onClick={() =>
                              api(
                                projectUrl(
                                  project,
                                  `pending/${selected.id}/history`,
                                ),
                              )
                                .then((v) => setHistory(v.items))
                                .catch((e) => setNotice(e.message))
                            }
                          >
                            查看回答历史
                          </button>
                        </div>
                        <p className="muted">
                          保存后不重跑。确认材料只作用于其来源节点；研发导入后预览真实影响范围，再手动执行。
                        </p>
                      </div>
                    )}
                    {history && (
                      <section className="review-history">
                        <h4>回答历史</h4>
                        {history.length ? (
                          history.map((h: any, i: number) => (
                            <article key={i}>
                              <b>
                                版本{h.revision} · {h.reviewer || "历史用户"} ·{" "}
                                {h.choice}
                              </b>
                              <p>{h.answer || h.note}</p>
                              <small>
                                {new Date(h.at * 1000).toLocaleString()} ·{" "}
                                {h.via || "历史记录"}
                              </small>
                            </article>
                          ))
                        ) : (
                          <p>尚无回答记录</p>
                        )}
                      </section>
                    )}
                  </>
                ) : (
                  <p>选择左侧问题查看依据并回答。</p>
                )}
              </section>
            </Panel>
            {evidence && (
              <>
                <PanelResizeHandle className="review-resize-handle" />
                <Panel defaultSize={50} minSize={30}>
                  <SourceEvidence
                    project={project}
                    evidence={evidence}
                    onClose={() => setEvidence(null)}
                  />
                </Panel>
              </>
            )}
          </PanelGroup>
        </div>
      )}
    </div>
  );
}
