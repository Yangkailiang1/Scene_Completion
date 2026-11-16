import { useResultDraft } from "../shared/useResultDraft";
import { MatchPairCard } from "../shared/MatchPairCard";
import {
  decisionKey,
  findDecision,
  putDecision,
  restoreDecision,
} from "../shared/matchDraft";
import {
  clearTableCell,
  putTableRecord,
  groupDisplayRows,
} from "../shared/tableEditing";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import {
  SsdAlignmentTable,
  ssdStatusNames,
  type SsdRecordKind,
} from "../ssd/SsdAlignmentTable";
import { MatchEditor } from "../ssd/SsdEditors";
import { SsdSourceDialog } from "../ssd/SsdSourceDialog";
import {
  copy,
  uid,
  type Channel,
  type Decision,
  type Observation,
  type SourceRef,
} from "../ssd/types";
import type { SsdReviewSelection } from "../../review/SsdReviewHandoff";
import { getProjectEditor, saveProjectRevision } from "./api";
import { AnchorEditor, ProjectObservationEditor } from "./ProjectEditors";
import {
  anchorName,
  scopeNames,
  type Anchor,
  type ProjectBundle,
  type ProjectScope,
} from "./types";
import { ScopeMetrics } from "./ScopeMetrics";
import { DependencyGraph } from "./DependencyGraph";
import "../ssd/ssd-results.css";
import "./project-results.css";
const channels: Channel[] = ["E", "G", "GT"];
const UNBOUND = "__unbound__";
export function ProjectScopeResultsView({
  project,
  scope,
  liveVersion,
  navigation,
  sourceControl,
  requestedAnchorId,
  onDirtyChange,
  onSelectionChange,
  onReviewRequest,
  onUpdated,
  forceReadonly = false,
  onNavigateCase,
}: {
  project: string;
  scope: ProjectScope;
  liveVersion?: string;
  navigation: ReactNode;
  sourceControl?: ReactNode;
  requestedAnchorId?: string;
  onDirtyChange?: (dirty: boolean) => void;
  onSelectionChange?: (selection: SsdReviewSelection) => void;
  onReviewRequest?: (selection: SsdReviewSelection) => void;
  onUpdated?: () => void;
  forceReadonly?: boolean;
  onNavigateCase?: (caseId: string, stepId?: string) => void;
}) {
  const [snapshot, setSnapshot] = useState<any>(null);
  const {
    draft,
    reset: setDraft,
    change: changeDraft,
    undo: undoDraft,
    dirty,
    changes,
    canUndo,
  } = useResultDraft<ProjectBundle>();
  const saving = useRef(false);
  const [version, setVersion] = useState("current"),
    [anchorId, setAnchor] = useState(requestedAnchorId || ""),
    [mode, setMode] = useState("comparison");
  const [layer, setLayer] = useState<SsdRecordKind>("concerns"),
    [differences, setDifferences] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [reason, setReason] = useState("");
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("scene-result-controls-collapsed") !== "false",
  );
  const [anchorEdit, setAnchorEdit] = useState<Anchor | null>(null),
    [sources, setSources] = useState<SourceRef[] | null>(null);
  const [recordEdit, setRecordEdit] = useState<{
      channel: Channel;
      kind: SsdRecordKind;
      item: Observation;
    } | null>(null),
    [matchEdit, setMatchEdit] = useState<Decision | true | null>(null);
  const [selected, setSelected] = useState<Record<Channel, string[]>>({
      E: [],
      G: [],
      GT: [],
    }),
    [focus, setFocus] = useState<Record<Channel, string[]> | null>(null);
  const readonly = forceReadonly || version !== "current";
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  useEffect(() => {
    onSelectionChange?.({
      scope,
      ...(anchorId && anchorId !== UNBOUND ? { anchorId } : {}),
      differencesOnly: differences,
    });
  }, [scope, anchorId, differences, onSelectionChange]);
  useEffect(() => {
    let active = true;
    setSnapshot(null);
    setDraft(null);

    setError("");

    setFocus(null);
    getProjectEditor(project, scope, version)
      .then((value) => {
        if (!active) return;
        setSnapshot(value);
        setDraft(copy(value.bundle));

        setAnchor(
          value.bundle.anchors.some(
            (anchor: Anchor) => anchor.id === requestedAnchorId,
          )
            ? requestedAnchorId!
            : value.bundle.anchors[0]?.id || UNBOUND,
        );
      })
      .catch((error) => {
        if (active) setError(error.message);
      });
    return () => {
      active = false;
    };
  }, [project, scope, version]);
  useEffect(() => {
    if (requestedAnchorId && !dirty) {
      setAnchor(requestedAnchorId);
      setMode("comparison");
    }
  }, [requestedAnchorId]);
  useEffect(() => {
    if (!liveVersion || dirty || !snapshot || readonly) return;
    let active = true;
    getProjectEditor(project, scope)
      .then((value) => {
        if (active && value.revision !== snapshot.revision) {
          setSnapshot(value);
          setDraft(copy(value.bundle));
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [project, scope, liveVersion, dirty]);
  function change(update: (bundle: ProjectBundle) => void) {
    if (readonly || saving.current) return false;
    const updated = changeDraft(update);
    if (updated) {
      setError("");
      setNotice("");
    }
    return updated;
  }
  function toggleMatch(pair: Decision) {
    if (readonly || saving.current || !draft) return;
    const changed = changes.matches.has(decisionKey(pair));
    change((bundle) => {
      if (changed) restoreDecision(bundle, snapshot?.bundle, pair);
      else
        putDecision(bundle, {
          ...pair,
          id: findDecision(bundle, pair)?.id || uid("match"),
          status: "full",
          reason: "人工确认",
          origin: "manual",
        });
    });
    setNotice(
      changed
        ? "已撤回该条匹配草稿，恢复点击前状态。"
        : "该条已确认匹配并加入草稿，保存后重算指标。",
    );
  }
  function openMatchDetails(pair: Decision) {
    if (!readonly && !saving.current)
      setMatchEdit({ ...pair, id: pair.id || uid("match") });
  }
  async function save() {
    if (!draft || !dirty || saving.current) return;
    saving.current = true;
    setBusy(true);
    setError("");
    try {
      const value = await saveProjectRevision(project, scope, {
        base_revision: snapshot.revision,
        bundle: draft,
        reason,
      });
      setSnapshot(value);
      setDraft(copy(value.bundle));

      setReason("");
      setSelected({ E: [], G: [], GT: [] });
      setNotice("修订已保存，当前范围与项目汇总指标已重算。原始版本保留。");
      onUpdated?.();
    } catch (error: any) {
      setError(`${error.message}。草稿仍保留。`);
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }
  async function refresh() {
    setBusy(true);
    try {
      const value = await getProjectEditor(project, scope, version);
      setSnapshot(value);
      setDraft(copy(value.bundle));

      setReason("");
      setError("");
      onUpdated?.();
    } catch (error: any) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  const currentAnchor = draft?.anchors.find((anchor) => anchor.id === anchorId);
  const visible = (record: Observation) =>
    anchorId === UNBOUND
      ? !draft?.anchors.some((anchor) => anchor.id === record.anchor_id)
      : record.anchor_id === anchorId;
  const records = (channel: Channel) => draft?.channels[channel][layer] || [];
  const shownRecord = (record: Observation, channel: Channel) =>
    visible(record) &&
    (layer !== "scenarios" ||
      !focus ||
      record.concern_ids?.some((id) => focus[channel].includes(id)));
  const known = new Set<string>();
  let rows = (layer === "pending" ? [] : snapshot?.comparison?.[layer] || [])
    .map((row: any) => {
      const cells = Object.fromEntries(
        channels.map((channel) => {
          const items = (row.cells[channel] || [])
            .map((item: Observation) =>
              records(channel).find((candidate) => candidate.id === item.id),
            )
            .filter(
              (item: Observation | undefined): item is Observation =>
                !!item && !!shownRecord(item, channel),
            );
          items.forEach((item: Observation) =>
            known.add(`${channel}:${item.id}`),
          );
          return [channel, items];
        }),
      );
      return { ...row, cells };
    })
    .filter(
      (row: any) =>
        channels.some((channel) => row.cells[channel].length) &&
        (!differences || row.status !== "triple"),
    );
  channels.forEach((channel) =>
    records(channel)
      .filter(
        (record) =>
          shownRecord(record, channel) && !known.has(`${channel}:${record.id}`),
      )
      .forEach((record) =>
        rows.push({
          id: `${channel}:${record.id}`,
          anchor_id: record.anchor_id,
          target: record.target,
          key: record.key,
          status: record.status === "active" ? "single" : "pending",
          reason: dirty ? "草稿修改，保存后重算对应关系" : "待确认或尚未对应",
          cells: { E: [], G: [], GT: [], [channel]: [record] },
        }),
      ),
  );
  rows = groupDisplayRows(rows);
  const allRecords = channels.flatMap((channel) =>
    ["concerns", "scenarios", "pending"].flatMap(
      (kind) => draft?.channels[channel][kind as SsdRecordKind] || [],
    ),
  );
  const unbound = allRecords.filter(
    (record) =>
      !draft?.anchors.some((anchor) => anchor.id === record.anchor_id),
  );
  const recordIds = new Set(
    allRecords.filter(visible).map((record) => record.id),
  );
  const decisions = (draft?.decisions || []).filter(
    (decision) =>
      recordIds.has(decision.left_id) || recordIds.has(decision.right_id),
  );
  function selectAnchor(id: string) {
    setAnchor(id);
    setFocus(null);
    setSelected({ E: [], G: [], GT: [] });
  }
  function addAnchor() {
    setAnchorEdit(
      scope === "business_chain"
        ? {
            id: uid("dependency"),
            kind: "dependency",
            from_case_id: "",
            to_case_id: "",
            relation_type: "direct",
            condition: "",
            obligation: "",
            entity_ids: [],
            source_refs: [],
            status: "active",
          }
        : {
            id: uid("service"),
            kind: "external_service",
            name: "",
            description: "",
            external: true,
            api_ids: [],
            case_ids: [],
            source_refs: [],
            status: "active",
          },
    );
  }
  function addRecord(channel: Channel, row?: any) {
    setRecordEdit({
      channel,
      kind: layer,
      item: {
        id: uid(layer === "concerns" ? "concern" : "scenario"),
        anchor_id: row?.anchor_id || (anchorId === UNBOUND ? "" : anchorId),
        target:
          row?.target ||
          (scope === "business_chain" ? "dependency" : "service"),
        key: row?.key || "",
        label: draft?.registry?.definitions?.[row?.key || ""]?.label || "",
        ...(row
          ? {
              field_id: row.field_id || null,
              entity_id: row.entity_id || null,
              display_row_id: row.id,
            }
          : { display_row_id: uid("row") }),
        condition: "",
        expected: "",
        concern_ids: [],
        status: layer === "pending" ? "pending" : "active",
        source_refs: [],
      },
    });
  }
  function merge(channel: Channel) {
    const ids = selected[channel],
      items = records(channel).filter((item) => ids.includes(item.id)),
      first = items[0];
    if (items.length < 2) return;
    if (
      items.some(
        (item) =>
          item.anchor_id !== first.anchor_id ||
          item.key !== first.key ||
          (item.entity_id || null) !== (first.entity_id || null),
      )
    ) {
      setError("合并记录需属于同一对象、实体和关注点，请先修正挂载。");
      return;
    }
    change((bundle) => {
      const merged = {
        ...first,
        condition: [...new Set(items.map((item) => item.condition))].join("；"),
        analysis: [
          ...new Set(items.map((item) => item.analysis).filter(Boolean)),
        ].join("；"),
        expected: [
          ...new Set(items.map((item) => item.expected).filter(Boolean)),
        ].join("；"),
        concern_ids: [
          ...new Set(items.flatMap((item) => item.concern_ids || [])),
        ],
        source_refs: [
          ...new Map(
            items
              .flatMap((item) => item.source_refs || [])
              .map((ref) => [JSON.stringify(ref), ref]),
          ).values(),
        ],
      };
      bundle.channels[channel][layer] = bundle.channels[channel][layer]
        .filter((item) => !ids.includes(item.id) || item.id === first.id)
        .map((item) => (item.id === first.id ? merged : item));
      if (layer === "concerns")
        bundle.channels[channel].scenarios.forEach((item) => {
          item.concern_ids = [
            ...new Set(
              (item.concern_ids || []).map((id) =>
                ids.includes(id) ? first.id : id,
              ),
            ),
          ];
        });
      bundle.decisions = bundle.decisions.filter(
        (item) => !ids.includes(item.left_id) && !ids.includes(item.right_id),
      );
    });
    setSelected({ ...selected, [channel]: [] });
  }
  function removeRecord(channel: Channel, record: Observation) {
    change((bundle) => {
      bundle.channels[channel][layer] = bundle.channels[channel][layer].filter(
        (item) => item.id !== record.id,
      );
      if (layer === "pending")
        bundle.review_notes = [
          ...(bundle.review_notes || []),
          {
            id: uid("review"),
            channel,
            record_id: record.id,
            decision: "not_exception",
            reason: "人工判定不是异常",
          },
        ];
    });
  }
  function matchRow(row: any) {
    const pair =
      row.cells.G.length && row.cells.E.length
        ? "G_E"
        : row.cells.GT.length && row.cells.G.length
          ? "GT_G"
          : row.cells.GT.length && row.cells.E.length
            ? "GT_E"
            : "G_E";
    const [left, right] = pair.split("_");
    setMatchEdit({
      id: uid("match"),
      level: layer === "concerns" ? "concern" : "scenario",
      pair,
      left_id: row.cells[left][0]?.id || "",
      right_id: row.cells[right][0]?.id || "",
      status: "full",
      reason: "人工确认",
      origin: "manual",
    });
  }
  const scopeMeta = snapshot?.completeness && {
    ...snapshot.completeness,
    semantic_pairs: Math.max(
      0,
      (snapshot.completeness.semantic_pairs || 0) -
        (draft?.semantic_pending || []).filter((p: any) =>
          findDecision(draft, { ...p, level: "scenario" }),
        ).length,
    ),
  };
  return (
    <fieldset
      disabled={busy}
      aria-busy={busy}
      className="management-view results-view ssd-results ssd-result-edit-lock"
    >
      {navigation}
      <div className="results-compact-controls">
        {sourceControl}
        <select
          aria-label="当前范围视图"
          value={mode}
          onChange={(event) => setMode(event.target.value)}
        >
          <option value="comparison">三方对照</option>
          {scope !== "shared_services" && (
            <option value="anchors">
              {scope === "business_chain" ? "业务依赖表" : "外部服务清单"}
            </option>
          )}
          {scope === "business_chain" && (
            <option value="diagram">用例依赖图</option>
          )}
          <option value="metrics">本层指标</option>
        </select>
        <span className="results-compact-description">
          {scopeNames[scope]} · {draft?.anchors.length || 0} 个
          {scope === "business_chain" ? "依赖对象" : "外部服务身份"} ·{" "}
          {readonly ? "历史只读" : "当前修订"}
        </span>
        <button
          aria-expanded={!collapsed}
          onClick={() => {
            setCollapsed(!collapsed);
            localStorage.setItem(
              "scene-result-controls-collapsed",
              String(!collapsed),
            );
          }}
        >
          {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          {collapsed ? "展开工具栏" : "收起工具栏"}
        </button>
      </div>
      <div className="results-toolbar" hidden={collapsed}>
        {!readonly && (
          <button
            onClick={() =>
              change((b) => {
                b.coverage_policy = "coverage-any-confirmed-v2";
              })
            }
          >
            采用当前覆盖口径（保存后生效）
          </button>
        )}
        <label>
          <span>结果版本</span>
          <select
            aria-label="结果版本"
            disabled={dirty || busy}
            value={version}
            onChange={(event) => setVersion(event.target.value)}
          >
            <option value="current">当前修订结果</option>
            <option value="original">原始机器结果</option>
            {(snapshot?.history || [])
              .filter((item: any) => item.revision !== "original")
              .map((item: any) => (
                <option key={item.revision} value={String(item.revision)}>
                  修订 {item.revision} · {item.reason || item.created_at}
                </option>
              ))}
          </select>
        </label>
        <button disabled={!draft} onClick={() => setSources([])}>
          阅读原始 RR / SR
        </button>
        {onReviewRequest && (
          <button
            disabled={dirty || !draft || readonly}
            onClick={() =>
              onReviewRequest({
                scope,
                ...(anchorId && anchorId !== UNBOUND ? { anchorId } : {}),
                differencesOnly: true,
              })
            }
          >
            交给业务审核
          </button>
        )}
        <button onClick={undoDraft} disabled={!canUndo || busy}>
          撤销草稿修改
        </button>
        <button disabled={busy || dirty} onClick={() => void refresh()}>
          刷新
        </button>
      </div>
      {error && (
        <p className="management-notice ssd-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="management-notice" role="status">
          {notice}
        </p>
      )}
      {scopeMeta && !scopeMeta.complete && (
        <details className="management-notice ssd-completeness">
          <summary>
            当前为部分结果 · 待确认 {scopeMeta.pending_records || 0} 项 ·
            未完成语义比较 {scopeMeta.semantic_pairs || 0} 对
          </summary>
          <p>
            待处理记录与未挂载对象不作为已确认结果计分；未完成比较不视为已判定不匹配。
          </p>
        </details>
      )}
      {dirty && (
        <div className="ssd-save-bar">
          <span>
            匹配判定修改 {changes.matches.size} 条 · 其他修改 {changes.other}{" "}
            项；指标为保存版本，保存后重算。
          </span>
          <details className="ssd-revision-reason">
            <summary>修订说明</summary>{" "}
            <input
              aria-label="修订说明"
              placeholder="本次修正说明"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </details>
          <button disabled={busy} onClick={() => void save()}>
            保存修改并重算
          </button>
          <button disabled={busy} onClick={() => void refresh()}>
            放弃草稿并刷新
          </button>
        </div>
      )}
      {!draft ? (
        <p className="management-loading">
          {error ? "当前范围尚无可读取结果。" : "正在读取结果…"}
        </p>
      ) : mode === "metrics" ? (
        <section className="result-metrics ssd-metrics-view">
          <h2>{scopeNames[scope]}指标</h2>
          <ScopeMetrics snapshot={snapshot} historical={readonly} />
        </section>
      ) : (
        <div className="results-step-body">
          <aside
            className="results-step-list"
            aria-label={`${scopeNames[scope]}对象列表`}
          >
            {draft.anchors.map((anchor) => (
              <button
                key={anchor.id}
                className={anchorId === anchor.id ? "active" : ""}
                onClick={() => selectAnchor(anchor.id)}
              >
                <small>{anchor.id}</small>
                <strong>{anchorName(anchor)}</strong>
                <span>{anchor.obligation || anchor.description}</span>
                {(["concerns", "scenarios"] as const).map((kind) => (
                  <small key={kind}>
                    {kind === "concerns" ? "关注点" : "场景"}{" "}
                    {channels
                      .map(
                        (channel) =>
                          `${channel} ${draft.channels[channel][kind].filter((record) => record.anchor_id === anchor.id).length}`,
                      )
                      .join(" · ")}
                  </small>
                ))}
              </button>
            ))}
            {(unbound.length > 0 || anchorId === UNBOUND) && (
              <button
                className={`ssd-unbound-nav ${anchorId === UNBOUND ? "active" : ""}`}
                onClick={() => {
                  selectAnchor(UNBOUND);
                  setMode("comparison");
                  setLayer(
                    (
                      ["pending", "concerns", "scenarios"] as SsdRecordKind[]
                    ).find((kind) =>
                      channels.some((channel) =>
                        draft.channels[channel][kind].some((record) =>
                          unbound.some((item) => item.id === record.id),
                        ),
                      ),
                    ) || "pending",
                  );
                }}
              >
                待定位／本轮不计分（{unbound.length}）
              </button>
            )}
            {!readonly && scope !== "shared_services" && (
              <button onClick={addAnchor}>
                新增{scope === "business_chain" ? "业务依赖" : "外部服务"}
              </button>
            )}
            {(draft.pending?.length > 0 ||
              draft.revision_issues?.length > 0) && (
              <details className="ssd-case-issues" open>
                <summary>待处理与修订缺口</summary>
                {[
                  ...(draft.pending || []),
                  ...(draft.revision_issues || []),
                ].map((item: any, index) => (
                  <p key={item.id || index}>
                    {item.condition || item.reason || String(item)}
                    {item.source_refs && (
                      <button onClick={() => setSources(item.source_refs)}>
                        原始出处
                      </button>
                    )}
                  </p>
                ))}
              </details>
            )}
          </aside>
          <section className="results-reading">
            {mode === "anchors" ? (
              <>
                <h3>
                  {scope === "business_chain"
                    ? "业务依赖关系表"
                    : "外部服务身份清单"}
                </h3>
                <div className="result-data-scroll">
                  <table>
                    <thead>
                      <tr>
                        {(scope === "business_chain"
                          ? [
                              "上游用例",
                              "下游用例",
                              "依赖类型",
                              "条件／义务",
                              "关联实体",
                              "原文与修正",
                            ]
                          : [
                              "外部服务",
                              "稳定身份",
                              "职责／技术",
                              "涉及用例／接口",
                              "原文与修正",
                            ]
                        ).map((label) => (
                          <th key={label}>{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {draft.anchors.map((anchor) => (
                        <tr key={anchor.id}>
                          {scope === "business_chain" ? (
                            <>
                              <td>{anchor.from_case_id}</td>
                              <td>{anchor.to_case_id}</td>
                              <td>
                                {anchor.relation_type === "cascade"
                                  ? "级联依赖"
                                  : "直接依赖"}
                              </td>
                              <td>
                                {anchor.condition}
                                <p>{anchor.obligation}</p>
                              </td>
                              <td>{(anchor.entity_ids || []).join("、")}</td>
                            </>
                          ) : (
                            <>
                              <td>{anchor.name}</td>
                              <td>{anchor.id}</td>
                              <td>
                                {anchor.description}
                                <p>{anchor.technology}</p>
                              </td>
                              <td>
                                {(anchor.case_ids || []).join("、")}
                                <p>{(anchor.api_ids || []).join("、")}</p>
                              </td>
                            </>
                          )}
                          <td>
                            <button
                              onClick={() =>
                                setSources(anchor.source_refs || [])
                              }
                            >
                              查看原始出处
                            </button>
                            {!readonly && (
                              <button
                                onClick={() => setAnchorEdit(copy(anchor))}
                              >
                                修正关系／对象
                              </button>
                            )}
                            <button
                              onClick={() => {
                                selectAnchor(anchor.id);
                                setMode("comparison");
                              }}
                            >
                              查看三方结果
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : mode === "diagram" ? (
              <>
                <h3>用例业务依赖图</h3>
                <p className="muted">
                  图与关系表使用同一份已保存关系；点击边查看其条件、出处及修订。同一对用例的不同依赖语义独立保留。
                </p>
                <DependencyGraph
                  anchors={draft.anchors}
                  selected={anchorId}
                  onSelect={(id) => {
                    selectAnchor(id);
                    setMode("comparison");
                  }}
                />
              </>
            ) : (
              <>
                {currentAnchor ? (
                  <>
                    <div className="results-step-meta">
                      <strong>{anchorName(currentAnchor)}</strong>
                      <span>{currentAnchor.id}</span>
                    </div>
                    <details className="ssd-step-context">
                      <summary>
                        对象上下文（展开查看） · {anchorName(currentAnchor)}
                      </summary>
                      <div className="interaction-four">
                        {(scope === "business_chain"
                          ? [
                              ["上游用例", currentAnchor.from_case_id],
                              [
                                "依赖语义",
                                currentAnchor.obligation ||
                                  currentAnchor.condition,
                              ],
                              [
                                "业务实体",
                                (currentAnchor.entity_ids || []).join("、"),
                              ],
                              ["下游用例", currentAnchor.to_case_id],
                            ]
                          : [
                              ["外部服务", currentAnchor.name],
                              ["服务职责", currentAnchor.description],
                              [
                                "关联接口",
                                (currentAnchor.api_ids || []).join("、"),
                              ],
                              [
                                "涉及用例",
                                (currentAnchor.case_ids || []).join("、"),
                              ],
                            ]
                        ).map(([label, value]) => (
                          <div key={label}>
                            <small>{label}</small>
                            <strong>{value || "未记录"}</strong>
                          </div>
                        ))}
                      </div>
                    </details>
                    <details className="result-data">
                      <summary>
                        {scope === "business_chain"
                          ? "依赖条件、实体、原文与关系修正"
                          : "服务身份、原文与对象修正"}
                      </summary>
                      <p>
                        {currentAnchor.condition || currentAnchor.technology}
                      </p>
                      <div className="ssd-inline-actions">
                        <button
                          onClick={() =>
                            setSources(currentAnchor.source_refs || [])
                          }
                        >
                          原始出处
                        </button>
                        {!readonly && scope !== "shared_services" && (
                          <>
                            <button
                              onClick={() => setAnchorEdit(copy(currentAnchor))}
                            >
                              编辑
                              {scope === "business_chain"
                                ? "业务依赖"
                                : "外部服务"}
                            </button>
                            <button
                              onClick={() => {
                                change((bundle) => {
                                  bundle.anchors = bundle.anchors.filter(
                                    (anchor) => anchor.id !== currentAnchor.id,
                                  );
                                });
                                selectAnchor(UNBOUND);
                              }}
                            >
                              删除对象并保留待重绑记录
                            </button>
                          </>
                        )}
                      </div>
                    </details>
                  </>
                ) : (
                  <>
                    <h3>待定位／本轮不计分</h3>
                    <p>保留未挂载记录，可修正为真实依赖或服务对象。</p>
                  </>
                )}
                <div className="comparison-layer-toolbar">
                  <div
                    className="view-segments"
                    role="tablist"
                    aria-label="对照粒度"
                  >
                    {(
                      [
                        ["concerns", "关注点层"],
                        ["scenarios", "场景层"],
                        ["pending", "待确认"],
                      ] as const
                    ).map(([kind, label]) => (
                      <button
                        key={kind}
                        role="tab"
                        aria-selected={layer === kind}
                        className={layer === kind ? "active" : ""}
                        onClick={() => {
                          setLayer(kind);
                          setSelected({ E: [], G: [], GT: [] });
                          if (kind !== "scenarios") setFocus(null);
                        }}
                      >
                        {label}（
                        {channels.reduce(
                          (count, channel) =>
                            count +
                            draft.channels[channel][kind].filter(visible)
                              .length,
                          0,
                        )}
                        ）
                      </button>
                    ))}
                  </div>
                </div>
                <div className="ssd-comparison-controls">
                  <label className="alignment-filter">
                    <input
                      type="checkbox"
                      checked={differences}
                      onChange={(event) => setDifferences(event.target.checked)}
                    />
                    只看不一致
                  </label>
                  {focus && (
                    <button onClick={() => setFocus(null)}>
                      清除关注点筛选
                    </button>
                  )}
                  {!readonly && (
                    <button onClick={() => setMatchEdit(true)}>
                      添加匹配判定
                    </button>
                  )}
                </div>
                {scope === "shared_services" && currentAnchor && (
                  <details className="ssd-step-context">
                    <summary>
                      涉及的用例交互与原文出处（
                      {(currentAnchor.calls || []).length}）
                    </summary>
                    {(currentAnchor.calls || []).map(
                      (call: any, index: number) => (
                        <p key={index}>
                          <strong>
                            {call.case_id} · {call.step_id}
                          </strong>{" "}
                          {call.operation}
                          <button
                            disabled={dirty}
                            onClick={() =>
                              onNavigateCase?.(call.case_id, call.step_id)
                            }
                          >
                            查看对应交互
                          </button>
                          <button
                            onClick={() => setSources(call.source_refs || [])}
                          >
                            查看原文
                          </button>
                        </p>
                      ),
                    )}
                  </details>
                )}
                <SsdAlignmentTable
                  savedBundle={snapshot?.bundle}
                  rows={rows}
                  bundle={draft}
                  layer={layer}
                  readonly={readonly}
                  selected={selected}
                  objectHeading={
                    scope === "business_chain"
                      ? "业务依赖／关注点"
                      : "外部服务／关注点"
                  }
                  emptyLabel="当前对象"
                  getObjectName={(record) =>
                    anchorName(
                      draft.anchors.find(
                        (anchor) => anchor.id === record.anchor_id,
                      ),
                    )
                  }
                  getTargetLabel={() =>
                    scope === "business_chain"
                      ? "业务依赖"
                      : scope === "shared_services"
                        ? "共用外部服务"
                        : "历史架构外部服务"
                  }
                  getGroupPath={(key) =>
                    (
                      draft.presentation?.paths?.[key]?.[0] ||
                      draft.registry?.presentation?.paths?.[key]?.[0] || [
                        scopeNames[scope],
                        draft.registry?.definitions?.[key]?.label || "待归类",
                      ]
                    ).join(" › ")
                  }
                  onSelect={(channel, id, checked) =>
                    setSelected({
                      ...selected,
                      [channel]: checked
                        ? [...selected[channel], id]
                        : selected[channel].filter((value) => value !== id),
                    })
                  }
                  onNew={addRecord}
                  onPatch={(channel, value) =>
                    change((b) => putTableRecord(b, channel, layer, value))
                  }
                  onClearCell={(channel, row) =>
                    change((b) => clearTableCell(b, row, channel, layer))
                  }
                  onDeleteRow={(row) =>
                    change((b) => {
                      for (const channel of ["E", "G", "GT"] as Channel[])
                        clearTableCell(b, row, channel, layer, true);
                    })
                  }
                  onMerge={merge}
                  onEdit={(channel, item) =>
                    setRecordEdit({ channel, kind: layer, item: copy(item) })
                  }
                  onSplit={(channel, item) =>
                    setRecordEdit({
                      channel,
                      kind: layer,
                      item: {
                        ...copy(item),
                        id: uid(layer === "concerns" ? "concern" : "scenario"),
                      },
                    })
                  }
                  onRemove={removeRecord}
                  onSources={(item) => setSources(item.source_refs || [])}
                  onMatch={matchRow}
                  onScenarios={(row) => {
                    setFocus(
                      Object.fromEntries(
                        channels.map((channel) => [
                          channel,
                          row.cells[channel].map(
                            (record: Observation) => record.id,
                          ),
                        ]),
                      ) as Record<Channel, string[]>,
                    );
                    setLayer("scenarios");
                  }}
                />
                <details className="ssd-match-panel">
                  <summary>当前对象匹配判定（{decisions.length}）</summary>
                  {decisions.map((decision) => (
                    <div className="ssd-match" key={decision.id}>
                      <span>
                        {decision.pair} · {ssdStatusNames[decision.status]} ·{" "}
                        {decision.reason}
                      </span>
                      <small>
                        {decision.left_id} ↔ {decision.right_id}
                      </small>
                      {!readonly && (
                        <div className="ssd-inline-actions">
                          <button onClick={() => setMatchEdit(decision)}>
                            修正匹配
                          </button>
                          <button
                            onClick={() =>
                              change((bundle) => {
                                bundle.decisions = bundle.decisions.filter(
                                  (item) => item.id !== decision.id,
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
                </details>
                {!!(draft.semantic_pending || []).filter(
                  (pair: any) =>
                    pair.anchor_id === anchorId ||
                    recordIds.has(pair.left_id) ||
                    recordIds.has(pair.right_id),
                ).length && (
                  <details className="ssd-match-panel">
                    <summary>
                      尚未完成的语义比较（
                      {
                        (draft.semantic_pending || [])
                          .filter(
                            (pair: any) =>
                              pair.anchor_id === anchorId ||
                              recordIds.has(pair.left_id) ||
                              recordIds.has(pair.right_id),
                          )
                          .filter(
                            (p: any) =>
                              !findDecision(draft, { ...p, level: "scenario" }),
                          ).length
                      }{" "}
                      对） · 本次已判定{" "}
                      {
                        (draft.semantic_pending || [])
                          .filter(
                            (pair: any) =>
                              pair.anchor_id === anchorId ||
                              recordIds.has(pair.left_id) ||
                              recordIds.has(pair.right_id),
                          )
                          .filter(
                            (p: any) =>
                              findDecision(draft, {
                                ...p,
                                level: "scenario",
                              }) &&
                              changes.matches.has(
                                decisionKey({ ...p, level: "scenario" }),
                              ),
                          ).length
                      }{" "}
                      对
                    </summary>
                    <p>
                      确认只加入草稿；卡片保留在原位置，可再次点击撤销，保存后重算。
                    </p>
                    {(draft.semantic_pending || [])
                      .filter(
                        (pair: any) =>
                          pair.anchor_id === anchorId ||
                          recordIds.has(pair.left_id) ||
                          recordIds.has(pair.right_id),
                      )
                      .map((pair: any) => {
                        const candidate: Decision = {
                          ...pair,
                          id: "",
                          level: "scenario",
                          status: "full",
                          reason: "人工确认",
                          origin: "manual",
                        };
                        return (
                          <MatchPairCard
                            key={decisionKey(candidate)}
                            pair={candidate}
                            bundle={draft}
                            changed={changes.matches.has(
                              decisionKey(candidate),
                            )}
                            readonly={readonly}
                            onToggle={toggleMatch}
                            onDetails={openMatchDetails}
                          />
                        );
                      })}
                  </details>
                )}
              </>
            )}
          </section>
        </div>
      )}
      {draft && anchorEdit && (
        <AnchorEditor
          anchor={anchorEdit}
          bundle={draft}
          onClose={() => setAnchorEdit(null)}
          onSave={(value) => {
            change((bundle) => {
              const index = bundle.anchors.findIndex(
                (anchor) => anchor.id === value.id,
              );
              if (index < 0) bundle.anchors.push(value);
              else bundle.anchors[index] = value;
            });
            setAnchor(value.id);
            setAnchorEdit(null);
          }}
        />
      )}
      {draft && recordEdit && (
        <ProjectObservationEditor
          {...recordEdit}
          bundle={draft}
          onClose={() => setRecordEdit(null)}
          onSave={(value) => {
            change((bundle) => {
              putTableRecord(
                bundle,
                recordEdit.channel,
                recordEdit.kind,
                value,
              );
            });
            setRecordEdit(null);
          }}
        />
      )}
      {draft && matchEdit && (
        <MatchEditor
          bundle={draft}
          decision={matchEdit === true ? undefined : matchEdit}
          onClose={() => setMatchEdit(null)}
          onSave={(value) => {
            const updated = change((bundle) => putDecision(bundle, value));
            setMatchEdit(null);
            setNotice(
              updated
                ? "该条判定已应用到草稿，保存后重算指标。"
                : "该条判定与当前内容一致，没有新增修改。",
            );
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
    </fieldset>
  );
}
