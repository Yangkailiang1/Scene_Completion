import { useEffect, useState } from "react";
import { api, projectUrl } from "./api";
const choices: Record<string, string> = {
  unresolved: "未处理",
  anomaly: "是异常",
  not_anomaly: "不是异常／已跳过",
  needs_info: "待补材料",
  all: "全部",
};
const stageNames: Record<string, string> = {
  "normal-rules": "建模器 · 正向正常规则",
  "concern-match": "建模器 · 关注点匹配",
  "existing-bind": "检查器 · 已有异常绑定",
  "existing-extract": "检查器 · 已有异常细化",
  "test-ground-truth": "独立测试 · GT整理",
  "fused-ssd": "建模器 · SSD",
  "enriched-view": "建模器 · 交互补全",
};
export function PendingView({
  project,
  onSelect,
}: {
  project: string;
  onSelect: (id: string) => void;
}) {
  const [data, setData] = useState<any>(null),
    [defs, setDefs] = useState<Record<string, any>>({}),
    [status, setStatus] = useState("unresolved"),
    [caseId, setCase] = useState(""),
    [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [channel, setChannel] = useState(""),
    [offset, setOffset] = useState(0),
    [selected, setSelected] = useState<any>(null),
    [choice, setChoice] = useState("needs_info"),
    [concern, setConcern] = useState(""),
    [note, setNote] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [reload, setReload] = useState(0);
  useEffect(() => {const timer=setTimeout(()=>{setSearch(query);setOffset(0)},250);return()=>clearTimeout(timer)},[query]);
  useEffect(() => {
    let active = true;
    setData(null);
    api(
      projectUrl(
        project,
        `pending?status=${status}&offset=${offset}&limit=40&search=${encodeURIComponent(search)}${channel ? "&channel="+channel : ""}${caseId ? "&case=" + encodeURIComponent(caseId) : ""}`,
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
  }, [project, status, caseId, offset, reload, search, channel]);
  useEffect(() => {
    api(projectUrl(project, "registry"))
      .then((d) => setDefs(d.registry.definitions))
      .catch((e) => setNotice(e.message));
  }, [project]);
  function pick(item: any) {
    setSelected(item);
    setChoice(item?.decision?.choice || "needs_info");
    setConcern(item?.decision?.concern_key || item?.concern_key || "");
    setNote(item?.decision?.note || "");
  }
  async function save() {
    if (!selected) return;
    setBusy(true);
    try {
      await api(projectUrl(project, "pending/" + selected.id), {
        method: "POST",
        body: JSON.stringify({
          choice,
          concern_key: concern,
          note,
          revision: selected.decision?.revision || 0,
        }),
      });
      setNotice(
        "审核已保存；不会自动调用模型，也不会改写已有报告。指导仅供来源节点后续重算使用。",
      );
      setReload((x) => x + 1);
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="management-view pending-review-view">
      <header className="management-heading">
        <div>
          <span className="eyebrow">业务审核</span>
          <h2>待确认项</h2>
          <p>
            区分建模、已有异常和测试来源，逐项判断，不把不确定项强行算作异常。
          </p>
        </div>
        <button onClick={() => setReload((x) => x + 1)}>刷新</button>
      </header>
      {notice && (
        <div role="status" className="management-notice">
          {notice}
        </div>
      )}
      <div className="management-filters">
        <div className="view-segments">
          {Object.entries(choices).map(([k, v]) => (
            <button
              key={k}
              className={status === k ? "active" : ""}
              onClick={() => {
                setStatus(k);
                setOffset(0);
              }}
            >
              {v}
              {k !== "all" && data?.counts?.[k] != null
                ? " " + data.counts[k]
                : ""}
            </button>
          ))}
        </div>
        <select
          aria-label="待确认用例"
          value={caseId}
          onChange={(e) => {
            setCase(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">全部用例</option>
          {data?.cases?.map((c: string) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select aria-label="待确认来源通道" value={channel} onChange={e=>{setChannel(e.target.value);setOffset(0)}}><option value="">全部来源</option><option value="positive">正向建模</option><option value="existing_e">原文已有异常</option><option value="test_gt">独立测试GT</option></select>
        <input aria-label="搜索待确认项" placeholder="搜索原因、对象或字段" value={query} onChange={e=>setQuery(e.target.value)}/>
      </div>
      {!data ? (
        <p className="management-loading">正在整理待确认项…</p>
      ) : (
        <div className="management-body">
          <aside className="management-list" aria-label="待确认列表">
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
                  {stageNames[
                    r.origins[0]?.split(":").pop()?.split("--part-")[0]
                  ] || r.category}
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
          </aside>
          <section className="management-detail">
            {selected ? (
              <>
                <div className="detail-kicker">
                  {selected.case} / {selected.interaction_id} ·{" "}
                  {{
                    positive: "正向建模通道",
                    existing_e: "原文已有异常通道",
                    test_gt: "独立测试GT通道",
                  }[selected.source_channel as string] || selected.category}
                </div>
                <h3>{selected.reason}</h3>
                {selected.object && (
                  <p className="muted">
                    对象／字段：{selected.object} ·{" "}
                    {defs[selected.concern_key]?.label || selected.concern_key}
                  </p>
                )}
                <div className="origin-actions">
                  {selected.origins.map((k: string) => (
                    <button key={k} onClick={() => onSelect(k)}>
                      查看来源节点 ·{" "}
                      {stageNames[
                        k.split(":").pop()?.split("--part-")[0] || ""
                      ] || k}
                    </button>
                  ))}
                </div>
                <h4>原文依据</h4>
                {selected.source_refs.length ? (
                  selected.source_refs.map((r: any, i: number) => (
                    <blockquote key={i}>
                      <small>
                        {r.source_id} · 第{r.line_start}–{r.line_end}行
                      </small>
                      <p>{r.quote}</p>
                    </blockquote>
                  ))
                ) : (
                  <p className="muted">暂无明确原文依据，应先补充材料。</p>
                )}
                {selected.question || selected.technical ? (
                  <div className="management-notice">
                    这是
                    {selected.question ? "模型的阻断提问" : "执行或配置问题"}
                    。请通过上方来源节点处理，不将其直接计作异常场景。
                  </div>
                ) : (
                  <div className="decision-form">
                    <h4>业务判定</h4>
                    <label>
                      这是否属于异常场景？
                      <select
                        aria-label="是否为异常场景"
                        value={choice}
                        onChange={(e) => setChoice(e.target.value)}
                      >
                        <option value="needs_info">信息不足，待补材料</option>
                        <option value="not_anomaly">不是异常场景，跳过</option>
                        <option value="anomaly">是异常场景</option>
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
                        {concern && <small>{defs[concern]?.description}</small>}
                      </label>
                    )}
                    <label>
                      判定依据或补充意见
                      <textarea
                        aria-label="待确认审核说明"
                        rows={4}
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="记录判断原因，或说明还需要哪些材料"
                      />
                    </label>
                    <button
                      className="primary-action"
                      disabled={busy || (choice === "anomaly" && !concern)}
                      onClick={save}
                    >
                      {busy ? "保存中…" : "保存判定"}
                    </button>
                    <p className="muted">
                      不会把检查器或测试答案传播给建模器。已有报告保持原样，可在来源节点查看指导及重新执行。
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="management-empty">
                选择左侧条目查看依据和判定。
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
