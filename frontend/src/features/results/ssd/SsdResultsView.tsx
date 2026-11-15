import { invalidateResults } from "../shared/resultRequests";
import { EditableCell } from "../shared/EditableCell";
import {
  clearTableCell,
  putTableRecord,
  groupDisplayRows,
} from "../shared/tableEditing";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import type { SsdReviewSelection } from "../../review/SsdReviewHandoff";
import {
  SsdAlignmentTable,
  ssdStatusNames as statusNames,
} from "./SsdAlignmentTable";
import { getSsdEditor, getSsdResultIndex, saveSsdRevision } from "./api";
import { MatchEditor, ObservationEditor, StepEditor } from "./SsdEditors";
import { SsdSourceDialog } from "./SsdSourceDialog";
import {
  channelLabels,
  copy,
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
const UNBOUND = "__unbound__";
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
export function SsdResultsView({
  project,
  initialIndex,
  liveVersion,
  onReviewRequest,
  onDirtyChange,
  onSelectionChange,
  requestedCaseId,
  requestedStepId,
  resultSourceControl,
  scopeNavigation,
}: {
  project: string;
  initialIndex: any;
  liveVersion?: string;
  onReviewRequest?: (selection: SsdReviewSelection) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSelectionChange?: (selection: SsdReviewSelection) => void;
  requestedCaseId?: string;
  requestedStepId?: string;
  resultSourceControl?: ReactNode;
  scopeNavigation?: ReactNode;
}) {
  const [index, setIndex] = useState(initialIndex);
  const [caseId, setCase] = useState(
    requestedCaseId ||
      [...initialIndex.cases].sort((a, b) =>
        String(a.id).localeCompare(String(b.id), "zh-CN", { numeric: true }),
      )[0]?.id ||
      "",
  );
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
  const [resultArea, setResultArea] = useState<"case" | "global" | "project">(
    "case",
  );
  const [caseMode, setCaseMode] = useState("steps");
  const [controlsCollapsed, setControlsCollapsed] = useState(
    () => localStorage.getItem("scene-result-controls-collapsed") !== "false",
  );
  const [concernFocus, setConcernFocus] = useState<Record<
    Channel,
    string[]
  > | null>(null);
  const [concernFocusLabel, setConcernFocusLabel] = useState("");
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  useEffect(() => {
    if (requestedCaseId && !dirty) {
      setCase(requestedCaseId);
      setVersion("current");
      setResultArea("case");
      setCaseMode("steps");
      if (requestedStepId) setStep(requestedStepId);
    }
  }, [requestedCaseId, requestedStepId]);
  useEffect(() => {
    onSelectionChange?.({
      scope: "interaction",
      caseId,
      ...(stepId && stepId !== UNBOUND ? { stepId } : {}),
      differencesOnly: differences,
    });
  }, [caseId, stepId, differences, onSelectionChange]);
  const readonly = version !== "current";
  useEffect(() => {
    setIndex(initialIndex);
  }, [initialIndex]);
  useEffect(() => {
    let live = true;
    setSnapshot(null);
    setDraft(null);
    undoStack.current = [];
    setError("");
    setDirty(false);
    setStep("");
    setConcernFocus(null);
    setSelected({ E: [], G: [], GT: [] });
    getSsdEditor(project, caseId, version)
      .then((v) => {
        if (live) {
          setSnapshot(v);
          setDraft(copy(v.bundle));
          undoStack.current = [];
          setStep(
            requestedCaseId === caseId &&
              v.bundle.steps.some((s: Step) => s.id === requestedStepId)
              ? requestedStepId!
              : v.bundle.steps[0]?.id || UNBOUND,
          );
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
            undoStack.current = [];
          }
        }
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [project, liveVersion, dirty]);
  const undoStack = useRef<any[]>([]);
  function undoDraft() {
    const previous = undoStack.current.pop();
    if (previous) {
      setDraft(previous);
      setDirty(true);
    }
  }
  function change(fn: (b: Bundle) => void) {
    if (!draft || readonly) return;
    undoStack.current.push(copy(draft));
    if (undoStack.current.length > 50) undoStack.current.shift();
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
      undoStack.current = [];
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
    invalidateResults(project);
    setBusy(true);
    try {
      const value = await getSsdEditor(project, caseId);
      setSnapshot(value);
      setDraft(copy(value.bundle));
      undoStack.current = [];
      setDirty(false);
      setError("");
      setReason("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function newRecord(channel: Channel, row?: any) {
    setRecordEdit({
      channel,
      kind: layer,
      item: {
        id: uid(layer === "concerns" ? "concern" : "scenario"),
        step_id:
          row?.step_id ||
          (stepId === UNBOUND ? "" : stepId || draft?.steps[0]?.id || ""),
        target: row?.target || "receiver",
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
  function editRecord(value: Observation, destination: Kind) {
    if (!recordEdit) return;
    const { channel, kind, item } = recordEdit;
    change((b) => {
      if (kind !== destination)
        b.channels[channel][kind] = b.channels[channel][kind].filter(
          (x) => x.id !== item.id,
        );
      putTableRecord(b, channel, destination, value);
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
  const records = (channel: Channel) => draft?.channels[channel][layer] || [];
  const comparison =
    layer === "pending" ? [] : snapshot?.comparison?.[layer] || [];
  const activeStep = draft?.steps.find((step) => step.id === stepId);
  const visible = (record: Observation) =>
    stepId === UNBOUND
      ? !draft?.steps.some((step) => step.id === record.step_id)
      : record.step_id === stepId;
  const inConcernFocus = (record: Observation, channel: Channel) =>
    layer !== "scenarios" ||
    !concernFocus ||
    record.concern_ids?.some((id) => concernFocus[channel].includes(id));
  const known = new Set<string>();
  let rows = comparison
    .map((r: any) => {
      const cells: Record<string, Observation[]> = {};
      channels.forEach((ch) => {
        cells[ch] = (r.cells[ch] || [])
          .map((x: Observation) => records(ch).find((y) => y.id === x.id))
          .filter(
            (x: Observation | undefined): x is Observation =>
              !!x && visible(x) && !!inConcernFocus(x, ch),
          );
        cells[ch].forEach((x) => known.add(`${ch}:${x.id}`));
      });
      const current = channels.flatMap((ch) => cells[ch])[0];
      return {
        ...r,
        ...(current
          ? {
              step_id: current.step_id,
              target: current.target,
              key: current.key,
              field_id: current.field_id,
            }
          : {}),
        cells,
      };
    })
    .filter(
      (r: any) =>
        channels.some((ch) => r.cells[ch].length) &&
        (!differences || r.status !== "triple"),
    );
  channels.forEach((ch) =>
    records(ch)
      .filter(
        (r) =>
          visible(r) && inConcernFocus(r, ch) && !known.has(`${ch}:${r.id}`),
      )
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
  rows = groupDisplayRows(rows);
  const stepName = (id?: string) =>
    draft?.steps.find((s) => s.id === id)?.operation.name || "待重新挂载";
  const orderedCases = [...index.cases].sort((a, b) =>
    String(a.id).localeCompare(String(b.id), "zh-CN", { numeric: true }),
  );
  const allRecords = channels.flatMap((channel) =>
    ["concerns", "scenarios", "pending"].flatMap(
      (kind) => draft?.channels[channel][kind as Kind] || [],
    ),
  );
  const unboundCount = allRecords.filter(
    (record) => !draft?.steps.some((step) => step.id === record.step_id),
  ).length;
  const stepRecordIds = new Set(
    allRecords.filter(visible).map((record) => record.id),
  );
  const decisions = (draft?.decisions || []).filter(
    (decision) =>
      stepRecordIds.has(decision.left_id) ||
      stepRecordIds.has(decision.right_id),
  );
  const semanticPending = (draft?.semantic_pending || []).filter(
    (pair: any) =>
      visible(pair) ||
      stepRecordIds.has(pair.left_id) ||
      stepRecordIds.has(pair.right_id),
  );
  const matchBundle = draft && {
    ...draft,
    channels: Object.fromEntries(
      channels.map((channel) => [
        channel,
        Object.fromEntries(
          ["concerns", "scenarios", "pending"].map((kind) => [
            kind,
            draft.channels[channel][kind as Kind].filter(
              (record) =>
                visible(record) ||
                (matchEdit &&
                  matchEdit !== true &&
                  [matchEdit.left_id, matchEdit.right_id].includes(record.id)),
            ),
          ]),
        ),
      ]),
    ) as Bundle["channels"],
  };
  function selectStep(id: string) {
    setStep(id);
    setConcernFocus(null);
    setSelected({ E: [], G: [], GT: [] });
  }
  function chooseCase(id: string) {
    if (dirty) {
      setError("请先保存或放弃当前草稿，再切换用例。");
      return;
    }
    setCase(id);
    setVersion("current");
    setResultArea("case");
    setCaseMode("steps");
  }
  function toggleControls() {
    setControlsCollapsed((old) => {
      localStorage.setItem("scene-result-controls-collapsed", String(!old));
      return !old;
    });
  }
  function review() {
    if (dirty) {
      setError("请先保存或放弃当前草稿，再进入业务审核交接。");
      return;
    }
    onReviewRequest?.({
      scope: "interaction",
      caseId,
      ...(stepId && stepId !== UNBOUND ? { stepId } : {}),
      differencesOnly: true,
    });
  }
  function addStep() {
    if (!draft) return;
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
    const [left, right] = pair.split("_") as Channel[];
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
  const completeness = snapshot?.completeness;
  return (
    <div className="management-view results-view ssd-results">
      {scopeNavigation || (
        <div
          className="results-area-nav view-segments"
          role="tablist"
          aria-label="结果统计范围"
        >
          {(
            [
              ["case", "用例结果"],
              ["global", "全局业务分析"],
              ["project", "项目指标"],
            ] as const
          ).map(([area, label]) => (
            <button
              key={area}
              role="tab"
              aria-selected={resultArea === area}
              className={resultArea === area ? "active" : ""}
              onClick={() => setResultArea(area)}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="results-compact-controls" aria-label="结果快捷控制">
        {resultSourceControl}
        {resultArea === "case" && (
          <select
            aria-label="结果用例"
            disabled={dirty || busy}
            value={caseId}
            onChange={(event) => chooseCase(event.target.value)}
          >
            {orderedCases.map((item) => (
              <option key={item.id} value={item.id}>
                {item.id} · {item.name}
                {item.pending_count ? ` · ${item.pending_count} 项待确认` : ""}
              </option>
            ))}
          </select>
        )}
        {resultArea !== "global" && (
          <select
            aria-label="当前范围视图"
            value={resultArea === "project" ? "project" : caseMode}
            onChange={(event) => setCaseMode(event.target.value)}
          >
            {resultArea === "project" ? (
              <option value="project">项目总指标</option>
            ) : (
              <>
                <option value="steps">交互对照</option>
                <option value="metrics">本用例指标</option>
              </>
            )}
          </select>
        )}
        <span className="results-compact-description">
          {readonly
            ? "历史快照 · 只读"
            : dirty
              ? "当前修订 · 有未保存修改"
              : "当前修订结果"}{" "}
          · {index.cases.length} 个用例
          {completeness && !completeness.complete ? " · 部分内容待确认" : ""}
        </span>
        <button
          onClick={toggleControls}
          aria-expanded={!controlsCollapsed}
          aria-controls="results-main-controls"
        >
          {controlsCollapsed ? (
            <ChevronDown size={14} />
          ) : (
            <ChevronUp size={14} />
          )}
          {controlsCollapsed ? "展开工具栏" : "收起工具栏"}
        </button>
      </div>
      <div
        id="results-main-controls"
        className="results-toolbar"
        hidden={controlsCollapsed}
      >
        {resultArea === "case" && (
          <>
            <div
              className="view-segments results-view-tabs"
              role="navigation"
              aria-label="当前范围结果视图"
            >
              <button
                className={caseMode === "steps" ? "active" : ""}
                onClick={() => setCaseMode("steps")}
              >
                交互对照
              </button>
              <button
                className={caseMode === "metrics" ? "active" : ""}
                onClick={() => setCaseMode("metrics")}
              >
                本用例指标
              </button>
            </div>
            <label>
              <span>结果版本</span>
              <select
                aria-label="结果版本"
                value={version}
                disabled={dirty || busy}
                onChange={(event) => setVersion(event.target.value)}
              >
                <option value="current">当前修订结果</option>
                <option value="original">原始机器结果</option>
                {(snapshot?.history || [])
                  .filter((item: any) => item.revision !== "original")
                  .map((item: any) => (
                    <option key={item.revision} value={String(item.revision)}>
                      修订 {item.revision} ·{" "}
                      {item.reason || item.created_at || "历史保存"}
                    </option>
                  ))}
              </select>
            </label>
            <button disabled={!draft} onClick={() => setSources([])}>
              阅读原始 RR / SR
            </button>
            {onReviewRequest && (
              <button disabled={!draft || busy || readonly} onClick={review}>
                交给业务审核
              </button>
            )}
          </>
        )}
        <button
          className="results-refresh"
          disabled={busy || dirty}
          onClick={() => {
            void refreshIndex();
            if (version === "current") void discard();
          }}
        >
          <RefreshCw size={14} />
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
      {resultArea === "case" &&
        caseMode === "steps" &&
        completeness &&
        !completeness.complete && (
          <details className="management-notice ssd-completeness">
            <summary>
              当前为部分结果 · 待修正记录 {completeness.pending_records || 0} 项
              · 尚未完成语义比较 {completeness.semantic_pairs || 0} 对
            </summary>
            <p>
              用例待处理 {completeness.pending_case_items || 0} 项 ·
              人工修订待定位 {completeness.revision_issues || 0}{" "}
              项。指标基于当前已确认记录；未完成的语义比较不视为已判定不匹配。
            </p>
          </details>
        )}
      {dirty && (
        <div className="ssd-save-bar" role="status">
          <span>有尚未保存的修改；指标与匹配仍为上次保存版本。</span>
          <details className="ssd-revision-reason">
            <summary>修订说明</summary>{" "}
            <input
              aria-label="修订说明"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="本次修订说明"
            />
          </details>
          <button
            disabled={busy}
            className="primary-action"
            onClick={() => void save()}
          >
            保存修改并重算
          </button>
          <button disabled={busy} onClick={() => void discard()}>
            放弃草稿并刷新
          </button>
        </div>
      )}
      {resultArea === "global" ? (
        <section
          className="result-metrics ssd-metrics-view"
          aria-label="全局业务分析"
        >
          <h2>全局业务分析</h2>
          <p>当前 SSD 流程尚未计算全局业务分析与全局指标。</p>
          <p>
            如需查看已有全局报告，请在上方“结果视图”切换到“历史工作流 / Code
            Agent 报告（只读）”。
          </p>
        </section>
      ) : resultArea === "project" ? (
        <section
          className="result-metrics ssd-metrics-view"
          aria-label="项目指标"
        >
          <h2>项目总指标</h2>
          <p>
            当前修订结果 · 全部用例、RR 与 SR
            全部步骤。待定位或待确认记录不进入确定集合。
          </p>
          <Metrics values={index.metrics} />
          <table>
            <thead>
              <tr>
                <th>用例</th>
                <th>关注点漏报率</th>
                <th>生成有效率</th>
                <th>待确认</th>
                <th>查看</th>
              </tr>
            </thead>
            <tbody>
              {orderedCases.map((item) => (
                <tr key={item.id}>
                  <td>
                    {item.id} · {item.name}
                  </td>
                  {["missing_exception_miss_rate", "generation_validity"].map(
                    (key) => (
                      <td key={key}>
                        {item.metrics?.[key]?.value == null
                          ? item.metrics?.[key]?.status || "尚未评测"
                          : `${Number(item.metrics[key].value).toFixed(2)}%`}
                        <small>
                          {item.metrics?.[key] &&
                            `${item.metrics[key].numerator} / ${item.metrics[key].denominator}`}
                        </small>
                      </td>
                    ),
                  )}
                  <td>{item.pending_count || 0}</td>
                  <td>
                    <button
                      disabled={dirty}
                      onClick={() => chooseCase(item.id)}
                    >
                      查看用例
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : !draft ? (
        <p className="management-loading">正在读取本用例…</p>
      ) : caseMode === "metrics" ? (
        <section
          className="result-metrics ssd-metrics-view"
          aria-label="本用例指标"
        >
          <h2>
            {draft.case.name} ·{" "}
            {version === "original"
              ? "原始机器"
              : readonly
                ? `修订 ${version}`
                : "当前修订"}
            指标
          </h2>
          <p>按本用例 RR 与 SR 全部步骤计分。原始版本和每次修订分别保存。</p>
          <div className="ssd-metric-groups">
            <section>
              <h3>
                {version === "original" ? "原始机器指标" : "所选修订指标"}
              </h3>
              <Metrics
                values={
                  snapshot?.metrics_by_level?.concern || snapshot?.metrics
                }
              />
            </section>
            {version !== "original" && snapshot?.original_metrics && (
              <section>
                <h3>原始机器指标（对照）</h3>
                <Metrics
                  values={
                    snapshot.original_metrics_by_level?.concern ||
                    snapshot.original_metrics
                  }
                />
              </section>
            )}
          </div>
          {completeness && !completeness.complete && (
            <p className="management-notice">
              当前为部分结果：待修正记录 {completeness.pending_records || 0}{" "}
              项、用例待处理 {completeness.pending_case_items || 0}{" "}
              项、人工修订待定位 {completeness.revision_issues || 0}{" "}
              项、尚未完成语义比较 {completeness.semantic_pairs || 0}{" "}
              对。未完成语义比较不视为已判定不匹配。
            </p>
          )}
          {snapshot?.scenario_diagnostic && (
            <details className="ssd-step-panel">
              <summary>场景层指标（独立于关注点计数）</summary>
              <Metrics
                values={
                  snapshot.metrics_by_level?.scenario ||
                  snapshot.scenario_diagnostic
                }
                scenario
              />
              {snapshot.original_metrics_by_level?.scenario && (
                <>
                  <h4>原始场景指标对照</h4>
                  <Metrics
                    values={snapshot.original_metrics_by_level.scenario}
                    scenario
                  />
                </>
              )}
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
        </section>
      ) : (
        <div className="results-step-body">
          <aside className="results-step-list" aria-label="结果交互步骤">
            {draft.steps.map((step) => (
              <button
                key={step.id}
                className={stepId === step.id ? "active" : ""}
                aria-current={stepId === step.id ? "step" : undefined}
                onClick={() => selectStep(step.id)}
              >
                <small>
                  步骤{step.order} · {step.id} · {step.layer} ·{" "}
                  {step.kind === "action"
                    ? "本地处理"
                    : step.direction === "return"
                      ? "返回"
                      : "请求"}
                </small>
                <strong>{step.operation.name}</strong>
                <span>
                  {step.sender.name} → {step.receiver.name}
                </span>
                <small>
                  关注点{" "}
                  {channels
                    .map(
                      (channel) =>
                        `${channel} ${draft.channels[channel].concerns.filter((record) => record.step_id === step.id).length}`,
                    )
                    .join(" · ")}
                </small>
                <small>
                  场景{" "}
                  {channels
                    .map(
                      (channel) =>
                        `${channel} ${draft.channels[channel].scenarios.filter((record) => record.step_id === step.id).length}`,
                    )
                    .join(" · ")}
                </small>
                {allRecords.some(
                  (record) =>
                    record.step_id === step.id && record.status !== "active",
                ) && <small className="ssd-step-pending">含待确认记录</small>}
                {!!draft.semantic_pending?.filter(
                  (pair: any) => pair.step_id === step.id,
                ).length && (
                  <small className="ssd-step-pending">
                    尚未完成语义比较{" "}
                    {
                      draft.semantic_pending.filter(
                        (pair: any) => pair.step_id === step.id,
                      ).length
                    }{" "}
                    对
                  </small>
                )}
              </button>
            ))}
            {(unboundCount > 0 || stepId === UNBOUND) && (
              <button
                className={`ssd-unbound-nav ${stepId === UNBOUND ? "active" : ""}`}
                onClick={() => {
                  selectStep(UNBOUND);
                  setLayer(
                    (["pending", "concerns", "scenarios"] as Kind[]).find(
                      (kind) =>
                        channels.some((channel) =>
                          draft.channels[channel][kind].some(
                            (record) =>
                              !draft.steps.some(
                                (step) => step.id === record.step_id,
                              ),
                          ),
                        ),
                    ) || "pending",
                  );
                }}
              >
                <strong>待定位／本轮不计分（{unboundCount}）</strong>
                <span>未挂载到有效步骤的记录，可修正对象与关注点。</span>
              </button>
            )}
            {!readonly && (
              <button className="ssd-add-step" onClick={addStep}>
                新增 SSD 步骤
              </button>
            )}
            {(draft.pending?.length > 0 ||
              draft.revision_issues?.length > 0) && (
              <details className="ssd-case-issues" open>
                <summary>
                  用例待处理与修订缺口（
                  {(draft.pending?.length || 0) +
                    (draft.revision_issues?.length || 0)}
                  ）
                </summary>
                {(draft.pending || []).map((item: any, n: number) => (
                  <p key={item.id || n}>
                    {item.condition || item.reason || String(item)}
                    {item.source_refs && (
                      <button onClick={() => setSources(item.source_refs)}>
                        原始出处
                      </button>
                    )}
                  </p>
                ))}
                {(draft.revision_issues || []).map((item: any, n: number) => (
                  <p key={item.id || n}>
                    {item.reason}
                    <small>{item.id}</small>
                  </p>
                ))}
              </details>
            )}
          </aside>
          <section className="results-reading">
            {activeStep ? (
              <>
                <div className="results-step-meta">
                  <strong>
                    步骤{activeStep.order} · {activeStep.id}
                  </strong>
                  <span>
                    {activeStep.layer} ·{" "}
                    {activeStep.kind === "action"
                      ? "本地处理"
                      : activeStep.direction === "return"
                        ? "返回"
                        : "请求"}
                    {activeStep.parent_id
                      ? " · 展开自 " + activeStep.parent_id
                      : ""}
                  </span>
                </div>
                <details className="ssd-step-context">
                  <summary title={activeStep.operation.name}>
                    交互四元组（展开查看／编辑） · {activeStep.sender.name} →{" "}
                    {activeStep.receiver.name} ·{" "}
                    {activeStep.operation.kinds.join("/") || "CRUD待确定"}
                  </summary>
                  <div className="interaction-four">
                    <div>
                      <small>发送方</small>
                      <strong>
                        <EditableCell
                          label="四元组sender名称"
                          readonly={readonly}
                          value={activeStep.sender.name}
                          onChange={(name) =>
                            change((b) => {
                              b.steps.find(
                                (s) => s.id === activeStep.id,
                              )!.sender.name = name;
                            })
                          }
                        />
                      </strong>
                      <p>
                        {activeStep.sender.type === "human"
                          ? "人类 Actor"
                          : activeStep.sender.type}
                        {activeStep.sender.technology
                          ? ` · ${activeStep.sender.technology}`
                          : ""}
                      </p>
                    </div>
                    <div>
                      <small>操作</small>
                      <strong>
                        <EditableCell
                          label="四元组操作"
                          readonly={readonly}
                          value={activeStep.operation.name}
                          onChange={(name) =>
                            change((b) => {
                              b.steps.find(
                                (s) => s.id === activeStep.id,
                              )!.operation.name = name;
                            })
                          }
                        />
                      </strong>
                      <p>
                        <EditableCell
                          label="四元组CRUD"
                          readonly={readonly}
                          value={activeStep.operation.kinds.join(",")}
                          onChange={(value) =>
                            change((b) => {
                              b.steps.find(
                                (s) => s.id === activeStep.id,
                              )!.operation.kinds = value
                                .split(/[,，\s]+/)
                                .filter(Boolean);
                            })
                          }
                        />
                      </p>
                    </div>
                    <div>
                      <small>数据</small>
                      <strong>
                        {readonly ? (
                          activeStep.data
                            .map((field) => field.name)
                            .join("、") || "未记录数据字段"
                        ) : (
                          <button
                            className="ssd-editable-cell"
                            aria-label="四元组数据与API"
                            onClick={() => setStepEdit(copy(activeStep))}
                          >
                            {activeStep.data
                              .map((field) => field.name)
                              .join("、") || "点击填写数据字段"}
                          </button>
                        )}
                      </strong>
                      <p>
                        {activeStep.api_id
                          ? "接口 " + activeStep.api_id
                          : "未关联具体接口"}
                      </p>
                    </div>
                    <div>
                      <small>接收方</small>
                      <strong>
                        <EditableCell
                          label="四元组receiver名称"
                          readonly={readonly}
                          value={activeStep.receiver.name}
                          onChange={(name) =>
                            change((b) => {
                              b.steps.find(
                                (s) => s.id === activeStep.id,
                              )!.receiver.name = name;
                            })
                          }
                        />
                      </strong>
                      <p>
                        {activeStep.receiver.type}
                        {activeStep.receiver.technology
                          ? ` · ${activeStep.receiver.technology}`
                          : ""}
                      </p>
                    </div>
                  </div>
                </details>
                {activeStep.binding_issue && (
                  <p className="management-notice">
                    {activeStep.binding_issue}
                  </p>
                )}
                <details className="result-data">
                  <summary>数据属性、接口实体映射、步骤编辑及原文依据</summary>
                  <p>
                    接口：{activeStep.api_id || "未关联"} · 业务实体：
                    {activeStep.entity_ids.join("、") || "未关联"}
                  </p>
                  <div className="ssd-inline-actions">
                    <button
                      onClick={() => setSources(activeStep.source_refs || [])}
                    >
                      原始出处
                    </button>
                    {!readonly && (
                      <>
                        <button onClick={() => setStepEdit(copy(activeStep))}>
                          编辑步骤 {activeStep.order}
                        </button>
                        <button
                          aria-label={`上移步骤 ${activeStep.order}`}
                          disabled={draft.steps[0]?.id === activeStep.id}
                          onClick={() => moveStep(activeStep.id, -1)}
                        >
                          ↑ 上移
                        </button>
                        <button
                          aria-label={`下移步骤 ${activeStep.order}`}
                          disabled={
                            draft.steps[draft.steps.length - 1]?.id ===
                            activeStep.id
                          }
                          onClick={() => moveStep(activeStep.id, 1)}
                        >
                          ↓ 下移
                        </button>
                        <button
                          onClick={() => {
                            change((bundle) => {
                              bundle.steps = bundle.steps.filter(
                                (item) => item.id !== activeStep.id,
                              );
                              bundle.steps.forEach((item, index) => {
                                item.order = index + 1;
                              });
                            });
                            selectStep(UNBOUND);
                          }}
                        >
                          删除步骤 {activeStep.order}
                        </button>
                      </>
                    )}
                  </div>
                  <div className="result-data-scroll">
                    <table>
                      <thead>
                        <tr>
                          {[
                            "数据",
                            "位置",
                            "类型",
                            "必填／可选",
                            "约束",
                            "原文依据",
                          ].map((label) => (
                            <th key={label}>{label}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {activeStep.data.map((field) => (
                          <tr key={field.id}>
                            <td>
                              <EditableCell
                                label={`字段 ${field.id} 名称`}
                                readonly={readonly}
                                value={field.name}
                                onChange={(name) =>
                                  change((b) => {
                                    b.steps
                                      .find((s) => s.id === activeStep.id)!
                                      .data.find(
                                        (f) => f.id === field.id,
                                      )!.name = name;
                                  })
                                }
                              />
                            </td>
                            <td>{field.location}</td>
                            <td>
                              <EditableCell
                                label={`字段 ${field.id} 类型`}
                                readonly={readonly}
                                value={field.type || ""}
                                onChange={(type) =>
                                  change((b) => {
                                    b.steps
                                      .find((s) => s.id === activeStep.id)!
                                      .data.find(
                                        (f) => f.id === field.id,
                                      )!.type = type;
                                  })
                                }
                              />
                            </td>
                            <td>
                              {field.required == null
                                ? "未记录"
                                : field.required
                                  ? "必填"
                                  : "可选"}
                            </td>
                            <td>
                              {field.constraints
                                .map(
                                  (constraint) =>
                                    `${constraint.kind}: ${typeof constraint.value === "string" ? constraint.value : JSON.stringify(constraint.value)}`,
                                )
                                .join("；") || "未记录"}
                            </td>
                            <td>
                              <button
                                onClick={() =>
                                  setSources(field.source_refs || [])
                                }
                              >
                                查看出处
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </>
            ) : (
              <div className="ssd-unbound-heading">
                <h3>待定位／本轮不计分</h3>
                <p>
                  这些记录尚未挂载到有效 SSD
                  步骤。保留原始出处，可编辑后重新挂载；不属于异常的待确认项可标记移除。
                </p>
              </div>
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
                    role="tab"
                    key={kind}
                    aria-selected={layer === kind}
                    className={layer === kind ? "active" : ""}
                    onClick={() => {
                      setLayer(kind);
                      if (kind !== "scenarios") setConcernFocus(null);
                      setSelected({ E: [], G: [], GT: [] });
                    }}
                  >
                    {label}
                    {`（${channels.reduce((sum, channel) => sum + draft.channels[channel][kind].filter(visible).length, 0)}）`}
                  </button>
                ))}
              </div>
              <p>
                {layer === "concerns"
                  ? "按关注点层级核对 E / G / GT"
                  : layer === "scenarios"
                    ? "在对应关注点下比较具体失败条件"
                    : "修正挂载与异常判定后保存"}
              </p>
            </div>
            <div className="ssd-comparison-controls">
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
              <button onClick={undoDraft} disabled={!dirty}>
                撤销草稿修改
              </button>
              <label className="alignment-filter">
                <input
                  type="checkbox"
                  checked={differences}
                  onChange={(event) => setDifferences(event.target.checked)}
                />
                只看不一致
              </label>
              {concernFocus && (
                <button onClick={() => setConcernFocus(null)}>
                  清除关注点筛选：{concernFocusLabel}
                </button>
              )}
              {!readonly && (
                <button onClick={() => setMatchEdit(true)}>添加匹配判定</button>
              )}
            </div>
            <SsdAlignmentTable
              rows={rows}
              bundle={draft}
              step={activeStep}
              layer={layer}
              readonly={readonly}
              selected={selected}
              onSelect={(channel, id, checked) =>
                setSelected({
                  ...selected,
                  [channel]: checked
                    ? [...selected[channel], id]
                    : selected[channel].filter((item) => item !== id),
                })
              }
              onNew={newRecord}
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
              onRemove={(channel, item) =>
                removeRecord(channel, layer, item.id)
              }
              onSources={(item) => setSources(item.source_refs || [])}
              onMatch={matchRow}
              onScenarios={(row) => {
                setConcernFocus(
                  Object.fromEntries(
                    channels.map((channel) => [
                      channel,
                      row.cells[channel].map((item: Observation) => item.id),
                    ]),
                  ) as Record<Channel, string[]>,
                );
                setConcernFocusLabel(
                  draft.registry?.definitions?.[row.key]?.label ||
                    row.key ||
                    "所选关注点",
                );
                setLayer("scenarios");
                setSelected({ E: [], G: [], GT: [] });
              }}
            />
            <details className="ssd-match-panel">
              <summary>当前步骤匹配判定（{decisions.length}）</summary>
              {decisions.map((decision) => (
                <div className="ssd-match" key={decision.id}>
                  <span>
                    {decision.level === "concern" ? "关注点" : "场景"} ·{" "}
                    {decision.pair} · {statusNames[decision.status]} ·{" "}
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
            {!!semanticPending.length && (
              <details className="ssd-match-panel">
                <summary>
                  尚未完成的语义比较（{semanticPending.length} 对）
                </summary>
                <p>这些记录尚未判断具体失败是否相同，可查看出处后人工判定。</p>
                {semanticPending.map((pair: any, n: number) => {
                  const [left, right] = String(pair.pair).split(
                    "_",
                  ) as Channel[];
                  const a = draft.channels[left]?.scenarios.find(
                    (item) => item.id === pair.left_id,
                  );
                  const b = draft.channels[right]?.scenarios.find(
                    (item) => item.id === pair.right_id,
                  );
                  return (
                    <div
                      className="ssd-match"
                      key={`${pair.pair}-${pair.left_id}-${pair.right_id}-${n}`}
                    >
                      <strong>{stepName(pair.step_id)}</strong>
                      <p>
                        {channelLabels[left] || left}：
                        {a?.condition || pair.left_id}
                      </p>
                      <p>
                        {channelLabels[right] || right}：
                        {b?.condition || pair.right_id}
                      </p>
                      {!readonly && (
                        <button
                          onClick={() =>
                            setMatchEdit({
                              id: uid("match"),
                              level: "scenario",
                              pair: pair.pair,
                              left_id: pair.left_id,
                              right_id: pair.right_id,
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
          </section>
        </div>
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
            setStep(value.id);
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
          bundle={matchBundle || draft}
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
