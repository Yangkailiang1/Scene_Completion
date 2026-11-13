import { useEffect, useState } from "react";
import {
  applySsdReview,
  exportSsdReview,
  getSsdEditor,
  getSsdResultIndex,
  previewSsdReview,
  saveSsdRevision,
} from "./api";
import { MatchEditor, ObservationEditor, StepEditor } from "./SsdEditors";
import { SsdSourceDialog } from "./SsdSourceDialog";
import {
  channelLabels,
  copy,
  targetLabels,
  uid,
  type Bundle,
  type Channel,
  type Decision,
  type Observation,
  type SourceRef,
  type Step,
} from "./types";
import "./ssd-results.css";

type Kind = "concerns" | "scenarios" | "pending";
const channels: Channel[] = ["E", "G", "GT"];
const statusNames: Record<string, string> = {
  active: "已确认",
  pending: "待确认",
  unbound: "待重新挂载",
  triple: "三方对应",
  pair: "两方对应",
  single: "单方独有",
  partial: "部分对应",
  unmatched: "未匹配",
  full: "完整匹配",
  none: "不匹配",
};
function Metrics({
  values,
  scenario = false,
}: {
  values: any;
  scenario?: boolean;
}) {
  return (
    <div className="ssd-metrics">
      {Object.entries({
        missing_exception_miss_rate: scenario ? "场景漏报率" : "关注点漏报率",
        generation_validity: scenario ? "场景生成有效率" : "生成有效率",
      }).map(([key, label]) => {
        const v =
          values?.[key] ||
          values?.concern?.[key] ||
          values?.concern_level?.[key];
        return (
          <div key={key}>
            <span>{label}</span>
            <strong>
              {v?.value == null
                ? v?.status || "尚未评测"
                : `${Number(v.value).toFixed(2)}%`}
            </strong>
            {v && (
              <small>
                {v.numerator} / {v.denominator}
              </small>
            )}
          </div>
        );
      })}
    </div>
  );
}
function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
export function SsdResultsView({
  project,
  initialIndex,
  liveVersion,
}: {
  project: string;
  initialIndex: any;
  liveVersion?: string;
}) {
  const [index, setIndex] = useState(initialIndex);
  const [caseId, setCase] = useState(initialIndex.cases[0]?.id || "");
  const [snapshot, setSnapshot] = useState<any>(null);
  const [draft, setDraft] = useState<Bundle | null>(null);
  const [version, setVersion] = useState("current");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState("");
  const [layer, setLayer] = useState<Kind>("concerns");
  const [stepId, setStep] = useState("");
  const [differences, setDifferences] = useState(false);
  const [selected, setSelected] = useState<Record<Channel, string[]>>({
    E: [],
    G: [],
    GT: [],
  });
  const [stepEdit, setStepEdit] = useState<Step | null>(null);
  const [recordEdit, setRecordEdit] = useState<{
    channel: Channel;
    kind: Kind;
    item: Observation;
  } | null>(null);
  const [matchEdit, setMatchEdit] = useState<Decision | true | null>(null);
  const [sources, setSources] = useState<SourceRef[] | null>(null);
  const [feedback, setFeedback] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [applyCases, setApplyCases] = useState<string[]>([]);
  const [exportAll, setExportAll] = useState(false);
  const readonly = version !== "current";
  useEffect(() => {
    setIndex(initialIndex);
  }, [initialIndex]);
  useEffect(() => {
    let live = true;
    setSnapshot(null);
    setDraft(null);
    setError("");
    setDirty(false);
    setStep("");
    getSsdEditor(project, caseId, version)
      .then((v) => {
        if (live) {
          setSnapshot(v);
          setDraft(copy(v.bundle));
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [project, caseId, version]);
  useEffect(() => {
    if (dirty || !liveVersion) return;
    let live = true;
    getSsdResultIndex(project)
      .then(async (v) => {
        if (!live) return;
        setIndex(v);
        const selectedCase = v.cases.find((c: any) => c.id === caseId);
        if (
          version === "current" &&
          selectedCase &&
          snapshot &&
          selectedCase.revision !== snapshot.revision
        ) {
          const updated = await getSsdEditor(project, caseId);
          if (live) {
            setSnapshot(updated);
            setDraft(copy(updated.bundle));
          }
        }
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [project, liveVersion, dirty]);
  function change(fn: (b: Bundle) => void) {
    if (!draft || readonly) return;
    const next = copy(draft);
    fn(next);
    setDraft(next);
    setDirty(true);
    setNotice("");
    setError("");
  }
  async function refreshIndex() {
    setIndex(await getSsdResultIndex(project));
  }
  async function save() {
    if (!draft || !snapshot) return;
    setBusy(true);
    setError("");
    try {
      const result = await saveSsdRevision(project, caseId, {
        base_revision: snapshot.revision,
        bundle: draft,
        reason,
      });
      setSnapshot(result);
      setDraft(copy(result.bundle));
      setDirty(false);
      setReason("");
      setSelected({ E: [], G: [], GT: [] });
      setNotice("修订已保存，当前用例与项目指标已重算。原始结果保留。");
      await refreshIndex();
    } catch (e: any) {
      setError(`${e.message}。草稿仍保留，可核对后再次保存。`);
    } finally {
      setBusy(false);
    }
  }
  async function discard() {
    setBusy(true);
    try {
      const value = await getSsdEditor(project, caseId);
      setSnapshot(value);
      setDraft(copy(value.bundle));
      setDirty(false);
      setError("");
      setReason("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function newRecord(channel: Channel) {
    setRecordEdit({
      channel,
      kind: layer,
      item: {
        id: uid(layer === "concerns" ? "concern" : "scenario"),
        step_id: stepId || draft?.steps[0]?.id || "",
        target: "receiver",
        key: "",
        label: "",
        condition: "",
        expected: "",
        concern_ids: [],
        status: layer === "pending" ? "pending" : "active",
        source_refs: [],
      },
    });
  }
  function editRecord(value: Observation, destination: Kind) {
    if (!recordEdit) return;
    const { channel, kind, item } = recordEdit;
    change((b) => {
      if (kind !== destination)
        b.channels[channel][kind] = b.channels[channel][kind].filter(
          (x) => x.id !== item.id,
        );
      const rows = b.channels[channel][destination];
      const pos = rows.findIndex((x) => x.id === value.id);
      if (pos < 0) rows.push(value);
      else rows[pos] = value;
    });
    setRecordEdit(null);
  }
  function merge(channel: Channel) {
    const ids = selected[channel];
    const items = draft!.channels[channel][layer].filter((r) =>
      ids.includes(r.id),
    );
    if (items.length < 2) return;
    const first = items[0];
    if (
      items.some(
        (r) =>
          r.step_id !== first.step_id ||
          r.target !== first.target ||
          r.field_id !== first.field_id ||
          (r.entity_id || null) !== (first.entity_id || null) ||
          r.key !== first.key,
      )
    ) {
      setError(
        "合并记录需要属于同一步骤、对象、实体和关注点；请先修正挂载或分类。",
      );
      return;
    }
    change((b) => {
      const merged = {
        ...first,
        condition: [...new Set(items.map((x) => x.condition))].join("；"),
        source_refs: [
          ...new Map(
            items
              .flatMap((x) => x.source_refs || [])
              .map((r) => [JSON.stringify(r), r]),
          ).values(),
        ],
        ...(layer === "scenarios"
          ? {
              concern_ids: [
                ...new Set(items.flatMap((x) => x.concern_ids || [])),
              ],
              expected: [
                ...new Set(items.map((x) => x.expected || "").filter(Boolean)),
              ].join("；"),
            }
          : {}),
      };
      b.channels[channel][layer] = b.channels[channel][layer]
        .filter((r) => !ids.includes(r.id) || r.id === first.id)
        .map((r) => (r.id === first.id ? merged : r));
      if (layer === "concerns")
        b.channels[channel].scenarios.forEach((s) => {
          s.concern_ids = [
            ...new Set(
              (s.concern_ids || []).map((id) =>
                ids.includes(id) ? first.id : id,
              ),
            ),
          ];
        });
      b.decisions = b.decisions.filter(
        (d) => !ids.includes(d.left_id) && !ids.includes(d.right_id),
      );
    });
    setSelected({ ...selected, [channel]: [] });
  }
  function removeRecord(channel: Channel, kind: Kind, id: string) {
    change((b) => {
      b.channels[channel][kind] = b.channels[channel][kind].filter(
        (x) => x.id !== id,
      );
      if (kind === "pending") {
        const notes = Array.isArray(b.review_notes) ? b.review_notes : [];
        b.review_notes = [
          ...notes,
          {
            id: uid("review"),
            channel,
            record_id: id,
            decision: "not_exception",
            reason: "人工判定不是异常，从待确认中移除",
          },
        ];
      }
    });
  }
  function moveStep(id: string, by: number) {
    change((b) => {
      const i = b.steps.findIndex((s) => s.id === id);
      const next = i + by;
      if (next < 0 || next >= b.steps.length) return;
      [b.steps[i], b.steps[next]] = [b.steps[next], b.steps[i]];
      b.steps.forEach((s, n) => {
        s.order = n + 1;
      });
    });
  }
  async function exportReview() {
    setBusy(true);
    setError("");
    try {
      const blob = await exportSsdReview(
        project,
        exportAll
          ? {}
          : {
              case_ids: [caseId],
              ...(stepId && draft
                ? {
                    record_ids: channels.flatMap((channel) =>
                      ["concerns", "scenarios", "pending"].flatMap((kind) =>
                        draft.channels[channel][kind as Kind]
                          .filter((record) => record.step_id === stepId)
                          .map((record) => record.id),
                      ),
                    ),
                  }
                : {}),
            },
      );
      download(
        blob,
        `${exportAll ? "全部用例" : draft?.case.name || caseId}-差异审核.html`,
      );
      setNotice(
        "已导出可离线编辑的 HTML；业务保存修改后，可在此导入审核文件。",
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function previewFile(file: File) {
    setError("");
    setPreview(null);
    setBusy(true);
    try {
      const content = await file.text();
      const result = await previewSsdReview(project, content);
      setFeedback(content);
      setPreview(result);
      setApplyCases(
        result.cases
          .filter((c: any) => c.status === "ready")
          .map((c: any) => c.case_id),
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function applyFeedback() {
    setBusy(true);
    setError("");
    try {
      const result = await applySsdReview(project, feedback, applyCases);
      setPreview(result);
      setApplyCases([]);
      await refreshIndex();
      const value = await getSsdEditor(project, caseId, version);
      setSnapshot(value);
      setDraft(copy(value.bundle));
      setNotice("选定业务修改已回收，结果与指标已更新。");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const records = (channel: Channel) => draft?.channels[channel][layer] || [];
  const comparison =
    layer === "pending" ? [] : snapshot?.comparison?.[layer] || [];
  const visible = (r: Observation) => !stepId || r.step_id === stepId;
  const known = new Set<string>();
  const rows = comparison
    .map((r: any) => {
      const cells: Record<string, Observation[]> = {};
      channels.forEach((ch) => {
        cells[ch] = (r.cells[ch] || [])
          .map((x: Observation) => records(ch).find((y) => y.id === x.id))
          .filter(
            (x: Observation | undefined): x is Observation => !!x && visible(x),
          );
        cells[ch].forEach((x) => known.add(`${ch}:${x.id}`));
      });
      return { ...r, cells };
    })
    .filter(
      (r: any) =>
        channels.some((ch) => r.cells[ch].length) &&
        (!differences || r.status !== "triple"),
    );
  channels.forEach((ch) =>
    records(ch)
      .filter((r) => visible(r) && !known.has(`${ch}:${r.id}`))
      .forEach((r) =>
        rows.push({
          id: `${ch}:${r.id}`,
          status: r.status === "active" ? "single" : "pending",
          step_id: r.step_id,
          target: r.target,
          key: r.key,
          reason: dirty ? "草稿修改，保存后重算对应关系" : "待确认或尚未对应",
          cells: { E: [], G: [], GT: [], [ch]: [r] },
        }),
      ),
  );
  const stepName = (id?: string) =>
    draft?.steps.find((s) => s.id === id)?.operation.name || "待重新挂载";
  return (
    <div className="ssd-results management-view">
      <header className="ssd-heading">
        <div>
          <h2>三方结果对照</h2>
          <p>按 SSD 步骤核对原文、方法和测试；修改保存后重算。</p>
        </div>
        <span>{index.cases.length} 个用例</span>
      </header>
      <div className="ssd-toolbar">
        <label>
          用例
          <select
            aria-label="结果用例"
            disabled={dirty || busy}
            value={caseId}
            onChange={(e) => {
              setCase(e.target.value);
              setVersion("current");
            }}
          >
            {index.cases.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.pending_count ? ` · ${c.pending_count} 项待确认` : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          结果版本
          <select
            aria-label="结果版本"
            value={version}
            disabled={dirty || busy}
            onChange={(e) => setVersion(e.target.value)}
          >
            <option value="current">当前修订结果</option>
            <option value="original">原始机器结果</option>
            {(snapshot?.history || [])
              .filter((h: any) => h.revision !== "original")
              .map((h: any) => (
                <option key={h.revision} value={String(h.revision)}>
                  修订 {h.revision} · {h.reason || h.created_at || "历史保存"}
                </option>
              ))}
          </select>
        </label>
        <button
          disabled={busy || readonly || !dirty}
          onClick={() => void save()}
        >
          保存修改并重算
        </button>
        <button disabled={busy || readonly} onClick={() => void discard()}>
          放弃草稿并刷新
        </button>
        <button
          disabled={busy || dirty || !draft || readonly}
          onClick={() => void exportReview()}
          title="包含所选范围内三方关注点与场景的全部差异，不限当前对照粒度"
        >
          {exportAll
            ? "导出全部用例差异 HTML"
            : stepId
              ? "导出当前步骤差异 HTML"
              : "导出当前用例差异 HTML"}
        </button>
        <label className="ssd-check">
          <input
            type="checkbox"
            checked={exportAll}
            onChange={(e) => setExportAll(e.target.checked)}
          />
          导出全部用例（忽略步骤筛选）
        </label>
      </div>
      {error && (
        <p className="ssd-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="ssd-notice" role="status">
          {notice}
        </p>
      )}
      {dirty && (
        <p className="ssd-notice">
          有尚未保存的修改。表格展示草稿，指标与对应状态仍为上次保存版本。
        </p>
      )}
      {readonly && (
        <p className="ssd-notice">
          正在查看历史快照；切回当前修订结果可以编辑。
        </p>
      )}
      {snapshot?.completeness && !snapshot.completeness.complete && (
        <div className="ssd-notice" role="status">
          <strong>当前为部分结果，尚有内容待确认。</strong>
          <p>
            待修正记录 {snapshot.completeness.pending_records || 0} 项 ·
            用例待处理 {snapshot.completeness.pending_case_items || 0} 项 ·
            人工修订待定位 {snapshot.completeness.revision_issues || 0} 项 ·
            尚未完成语义比较 {snapshot.completeness.semantic_pairs || 0} 对。
          </p>
          <p>
            下方指标基于当前已确认记录；未完成的语义比较不视为已判定不匹配。
          </p>
        </div>
      )}
      {!!draft?.revision_issues?.length && (
        <details className="ssd-notice" open>
          <summary>
            部分人工修订需要重新定位（{draft.revision_issues.length}）
          </summary>
          <p>原锚点已变化，请结合历史版本重新挂载对应记录。</p>
          {draft.revision_issues.map((issue: any, n: number) => (
            <p key={issue.id || n}>
              {issue.reason} <small>{issue.id}</small>
            </p>
          ))}
        </details>
      )}
      <div className="ssd-metric-groups">
        <section>
          <h3>{version === "original" ? "原始" : "当前版本"}用例指标</h3>
          <Metrics values={snapshot?.metrics} />
        </section>
        <section>
          <h3>项目当前汇总</h3>
          <Metrics values={index.metrics} />
        </section>
      </div>
      {snapshot?.scenario_diagnostic && (
        <details className="ssd-step-panel">
          <summary>场景诊断（独立于关注点指标）</summary>
          <Metrics values={snapshot.scenario_diagnostic} scenario />
          <p>
            原文 {snapshot.scenario_diagnostic.counts?.E ?? "—"} 条 · 方法{" "}
            {snapshot.scenario_diagnostic.counts?.G ?? "—"} 条 · 测试{" "}
            {snapshot.scenario_diagnostic.counts?.GT ?? "—"} 条
          </p>
          {!!snapshot.scenario_diagnostic.missing_truth_ids?.length && (
            <p>
              尚未覆盖的测试场景：
              {snapshot.scenario_diagnostic.missing_truth_ids.join("、")}
            </p>
          )}
        </details>
      )}
      {!draft ? (
        <p>正在读取用例结果…</p>
      ) : (
        <>
          {!readonly && (
            <label className="ssd-reason">
              修订说明
              <input
                aria-label="修订说明"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="记录本次修正的原因"
              />
            </label>
          )}
          <details className="ssd-step-panel">
            <summary>SSD 步骤与接口实体映射（{draft.steps.length}）</summary>
            <ol>
              {draft.steps.map((s, n) => (
                <li key={s.id}>
                  <div>
                    <strong>
                      {s.order}. {s.sender.name} → {s.receiver.name}
                    </strong>
                    <p>{s.operation.name}</p>
                    <small>
                      {s.layer} ·{" "}
                      {s.kind === "action"
                        ? "本地处理"
                        : s.direction === "return"
                          ? "返回"
                          : "请求"}{" "}
                      · {s.api_id || "未关联接口"} ·{" "}
                      {s.entity_ids.join("、") || "未关联实体"} ·{" "}
                      {s.operation.kinds.join("/")}
                    </small>
                    {s.binding_issue && (
                      <p className="ssd-notice">{s.binding_issue}</p>
                    )}
                  </div>
                  <div className="ssd-inline-actions">
                    <button onClick={() => setStep(s.id)}>查看此步骤</button>
                    <button onClick={() => setSources(s.source_refs || [])}>
                      原始出处
                    </button>
                    {!readonly && (
                      <>
                        <button onClick={() => setStepEdit(copy(s))}>
                          编辑步骤 {n + 1}
                        </button>
                        <button
                          aria-label={`上移步骤 ${n + 1}`}
                          disabled={n === 0}
                          onClick={() => moveStep(s.id, -1)}
                        >
                          ↑
                        </button>
                        <button
                          aria-label={`下移步骤 ${n + 1}`}
                          disabled={n === draft.steps.length - 1}
                          onClick={() => moveStep(s.id, 1)}
                        >
                          ↓
                        </button>
                        <button
                          onClick={() =>
                            change((b) => {
                              b.steps = b.steps.filter((x) => x.id !== s.id);
                              b.steps.forEach((x, j) => {
                                x.order = j + 1;
                              });
                            })
                          }
                        >
                          删除步骤 {n + 1}
                        </button>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ol>
            {!readonly && (
              <button
                onClick={() =>
                  setStepEdit({
                    id: uid("step"),
                    order: draft.steps.length + 1,
                    kind: "interaction",
                    layer: "SR",
                    direction: "request",
                    sender: { id: uid("party"), name: "", type: "service" },
                    receiver: { id: uid("party"), name: "", type: "service" },
                    operation: { name: "", kinds: ["read"] },
                    data: [],
                    api_id: null,
                    entity_ids: [],
                    source_refs: [],
                    parent_id: null,
                  })
                }
              >
                新增 SSD 步骤
              </button>
            )}
          </details>
          <div className="ssd-toolbar">
            <label>
              交互步骤
              <select
                aria-label="交互步骤"
                value={stepId}
                onChange={(e) => setStep(e.target.value)}
              >
                <option value="">全部步骤</option>
                {draft.steps.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.order}. {s.operation.name}
                  </option>
                ))}
              </select>
            </label>
            <div role="tablist" aria-label="对照粒度">
              {(
                [
                  ["concerns", "关注点"],
                  ["scenarios", "场景"],
                  ["pending", "待确认"],
                ] as const
              ).map(([k, name]) => (
                <button
                  role="tab"
                  key={k}
                  aria-selected={layer === k}
                  className={layer === k ? "active" : ""}
                  onClick={() => {
                    setLayer(k);
                    setSelected({ E: [], G: [], GT: [] });
                  }}
                >
                  {name}
                </button>
              ))}
            </div>
            <label className="ssd-check">
              <input
                type="checkbox"
                checked={differences}
                onChange={(e) => setDifferences(e.target.checked)}
              />
              只看不一致
            </label>
            <button onClick={() => setSources([])}>阅读原始 RR / SR</button>
          </div>
          <div className="ssd-table-scroll">
            <table className="ssd-comparison">
              <thead>
                <tr>
                  <th>SSD 对象与对应状态</th>
                  {channels.map((ch) => (
                    <th key={ch}>
                      {channelLabels[ch]}
                      {!readonly && (
                        <div className="ssd-inline-actions">
                          <button onClick={() => newRecord(ch)}>
                            新增{channelLabels[ch]}
                            {layer === "concerns"
                              ? "关注点"
                              : layer === "scenarios"
                                ? "场景"
                                : "待确认项"}
                          </button>
                          <button
                            disabled={selected[ch].length < 2}
                            onClick={() => merge(ch)}
                          >
                            合并所选
                          </button>
                        </div>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{stepName(row.step_id)}</strong>
                      <p>
                        {targetLabels[row.target] || "待定位"} · {row.key}
                      </p>
                      <span className={`ssd-status ssd-status-${row.status}`}>
                        {statusNames[row.status] || row.status}
                      </span>
                      <small>{row.reason}</small>
                    </td>
                    {channels.map((ch) => (
                      <td key={ch}>
                        {row.cells[ch].map((r: Observation) => (
                          <article className="ssd-record" key={r.id}>
                            {!readonly && (
                              <label className="ssd-check">
                                <input
                                  aria-label={`选择 ${ch} ${r.id}`}
                                  type="checkbox"
                                  checked={selected[ch].includes(r.id)}
                                  onChange={(e) =>
                                    setSelected({
                                      ...selected,
                                      [ch]: e.target.checked
                                        ? [...selected[ch], r.id]
                                        : selected[ch].filter(
                                            (id) => id !== r.id,
                                          ),
                                    })
                                  }
                                />
                                选择合并
                              </label>
                            )}
                            <strong>{r.label || r.key || "待确认记录"}</strong>
                            <p>{r.condition}</p>
                            {(r.binding_issue || r.reason) && (
                              <p className="ssd-notice">
                                {r.binding_issue || r.reason}
                              </p>
                            )}
                            {r.expected && <p>预期：{r.expected}</p>}
                            <small>
                              {statusNames[r.status] || r.status}
                              {r.rule_id ? ` · 规则 ${r.rule_id}` : ""}
                            </small>
                            <div className="ssd-inline-actions">
                              <button
                                onClick={() => setSources(r.source_refs || [])}
                              >
                                查看原始出处
                              </button>
                              {!readonly && (
                                <>
                                  <button
                                    aria-label={`编辑 ${ch} ${r.id}`}
                                    onClick={() =>
                                      setRecordEdit({
                                        channel: ch,
                                        kind: layer,
                                        item: copy(r),
                                      })
                                    }
                                  >
                                    编辑
                                  </button>
                                  <button
                                    aria-label={`拆分 ${ch} ${r.id}`}
                                    onClick={() =>
                                      setRecordEdit({
                                        channel: ch,
                                        kind: layer,
                                        item: {
                                          ...copy(r),
                                          id: uid(
                                            layer === "concerns"
                                              ? "concern"
                                              : "scenario",
                                          ),
                                        },
                                      })
                                    }
                                  >
                                    拆分为新增记录
                                  </button>
                                  <button
                                    aria-label={`删除 ${ch} ${r.id}`}
                                    onClick={() =>
                                      removeRecord(ch, layer, r.id)
                                    }
                                  >
                                    {layer === "pending"
                                      ? "不是异常（移除）"
                                      : "删除"}
                                  </button>
                                </>
                              )}
                            </div>
                          </article>
                        ))}
                        {!row.cells[ch].length && (
                          <span className="muted">无对应项</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length && <p className="ssd-empty">当前筛选下没有记录。</p>}
          </div>
          <details className="ssd-match-panel">
            <summary>匹配判定（{draft.decisions.length}）</summary>
            {draft.decisions.map((d) => (
              <div className="ssd-match" key={d.id}>
                <span>
                  {d.level === "concern" ? "关注点" : "场景"} · {d.pair} ·{" "}
                  {statusNames[d.status]} · {d.reason}
                </span>
                <small>
                  {d.left_id} ↔ {d.right_id}
                </small>
                {!readonly && (
                  <div>
                    <button onClick={() => setMatchEdit(d)}>修正匹配</button>
                    <button
                      onClick={() =>
                        change((b) => {
                          b.decisions = b.decisions.filter(
                            (x) => x.id !== d.id,
                          );
                        })
                      }
                    >
                      取消此判定
                    </button>
                  </div>
                )}
              </div>
            ))}
            {!readonly && (
              <button onClick={() => setMatchEdit(true)}>添加匹配判定</button>
            )}
          </details>
          {!!draft.semantic_pending?.length && (
            <details className="ssd-match-panel">
              <summary>
                尚未完成的语义比较（{draft.semantic_pending.length} 对）
              </summary>
              <p>这些记录尚未判断具体失败是否相同，可查看出处后人工判定。</p>
              {draft.semantic_pending.map((p: any, n: number) => {
                const [left, right] = String(p.pair).split("_") as [
                  Channel,
                  Channel,
                ];
                const a = draft.channels[left]?.scenarios.find(
                  (s) => s.id === p.left_id,
                );
                const b = draft.channels[right]?.scenarios.find(
                  (s) => s.id === p.right_id,
                );
                return (
                  <div
                    className="ssd-match"
                    key={`${p.pair}-${p.left_id}-${p.right_id}-${n}`}
                  >
                    <strong>{stepName(p.step_id)}</strong>
                    <p>
                      {channelLabels[left] || left}：{a?.condition || p.left_id}
                    </p>
                    <p>
                      {channelLabels[right] || right}：
                      {b?.condition || p.right_id}
                    </p>
                    {!readonly && (
                      <button
                        onClick={() =>
                          setMatchEdit({
                            id: uid("match"),
                            level: "scenario",
                            pair: p.pair,
                            left_id: p.left_id,
                            right_id: p.right_id,
                            status: "full",
                            reason: "人工确认",
                            origin: "manual",
                          })
                        }
                      >
                        人工判定此对
                      </button>
                    )}
                  </div>
                );
              })}
            </details>
          )}
          {!!draft.pending?.length && (
            <details>
              <summary>用例待处理记录（{draft.pending.length}）</summary>
              {draft.pending.map((p: any, n: number) => (
                <p key={p.id || n}>
                  {p.condition || p.reason || String(p)}
                  {p.source_refs && (
                    <button onClick={() => setSources(p.source_refs)}>
                      原始出处
                    </button>
                  )}
                </p>
              ))}
            </details>
          )}
          <details className="ssd-feedback">
            <summary>回收业务审核修改</summary>
            <p>选择业务保存的 HTML 或 JSON，预览后应用选定用例的修改。</p>
            <input
              aria-label="导入业务审核文件"
              type="file"
              accept=".html,.htm,.json"
              disabled={busy || dirty}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void previewFile(file);
                e.target.value = "";
              }}
            />
            {preview?.cases?.map((c: any) => (
              <article key={c.case_id}>
                <label className="ssd-check">
                  <input
                    aria-label={`应用 ${c.name || c.case_id}`}
                    type="checkbox"
                    disabled={c.status !== "ready"}
                    checked={applyCases.includes(c.case_id)}
                    onChange={(e) =>
                      setApplyCases(
                        e.target.checked
                          ? [...applyCases, c.case_id]
                          : applyCases.filter((id) => id !== c.case_id),
                      )
                    }
                  />
                  {c.name || c.case_id} ·{" "}
                  {(
                    {
                      ready: "可应用",
                      unchanged: "无变化",
                      conflict: "存在版本冲突",
                      applied: "已应用",
                    } as Record<string, string>
                  )[c.status] || c.status}{" "}
                  · {c.changes?.length || 0} 处修改
                </label>
                {c.conflicts?.map((c: any, i: number) => (
                  <p className="ssd-error" key={i}>
                    {typeof c === "string" ? c : c.reason || JSON.stringify(c)}
                  </p>
                ))}
                <details>
                  <summary>修改明细</summary>
                  {c.changes?.map((x: any, i: number) => (
                    <div className="ssd-feedback-change" key={i}>
                      <strong>{x.path}</strong>
                      <pre>{JSON.stringify(x.before, null, 2)}</pre>
                      <span>→</span>
                      <pre>{JSON.stringify(x.after, null, 2)}</pre>
                    </div>
                  ))}
                </details>
              </article>
            ))}
            {preview && (
              <button
                disabled={busy || dirty || !applyCases.length}
                onClick={() => void applyFeedback()}
              >
                应用选定用例修改并重算
              </button>
            )}
          </details>
        </>
      )}
      {draft && stepEdit && (
        <StepEditor
          step={stepEdit}
          steps={draft.steps}
          onClose={() => setStepEdit(null)}
          onSave={(value) => {
            change((b) => {
              const i = b.steps.findIndex((s) => s.id === value.id);
              if (i >= 0) b.steps[i] = value;
              else b.steps.push(value);
            });
            setStepEdit(null);
          }}
        />
      )}
      {draft && recordEdit && (
        <ObservationEditor
          {...recordEdit}
          bundle={draft}
          onClose={() => setRecordEdit(null)}
          onSave={editRecord}
        />
      )}
      {draft && matchEdit && (
        <MatchEditor
          bundle={draft}
          decision={matchEdit === true ? undefined : matchEdit}
          onClose={() => setMatchEdit(null)}
          onSave={(value) => {
            change((b) => {
              b.decisions = b.decisions.filter(
                (d) =>
                  d.id !== value.id &&
                  !(
                    d.level === value.level &&
                    d.pair === value.pair &&
                    d.left_id === value.left_id &&
                    d.right_id === value.right_id
                  ),
              );
              b.decisions.push(value);
            });
            setMatchEdit(null);
          }}
        />
      )}
      {draft && sources && (
        <SsdSourceDialog
          documents={draft.documents}
          refs={sources}
          onClose={() => setSources(null)}
        />
      )}
    </div>
  );
}
