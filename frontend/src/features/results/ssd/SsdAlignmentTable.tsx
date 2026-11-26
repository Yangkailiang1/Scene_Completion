import {
  draftChanges,
  rowDraftDecisions,
  decisionKey,
  decisionLabel,
} from "../shared/matchDraft";
import { relatedRequirementRefs } from "../shared/provenance";
import { EditableCell } from "../shared/EditableCell";
import { Fragment, useMemo } from "react";
import {
  fieldLabel,
  channelLabels,
  targetLabels,
  type Bundle,
  type Channel,
  type Observation,
  type Step,
  type SourceRef,
} from "./types";

export type SsdRecordKind = "concerns" | "scenarios" | "pending";
export const ssdStatusNames: Record<string, string> = {
  active: "已确认",
  pending: "待确认",
  unbound: "待重新挂载",
  triple: "三方完整对应",
  pair: "两方对应",
  single: "单方独有",
  partial: "覆盖",
  unmatched: "未匹配",
  full: "覆盖",
  none: "不覆盖",
};
const channels: Channel[] = ["E", "G", "GT"];
const base = ["交互级关注点", "Service关注点", "单个Service内部"];

// Display taxonomy follows domain/concern_presentation; it never changes bindings or scores.
function concernPath(
  key: string,
  bundle: { registry?: any },
  step?: Step,
): string {
  const definitions = bundle.registry?.definitions || {};
  const definition = definitions[key] || {};
  const { layer, group } = definition;
  if (key === "service.base.availability")
    return "交互级关注点 › 外部Service调用 › 服务可用性（项目合并计数）";
  if (definition.scope === "business_chain")
    return "业务链路关注点 › 用例与业务实体依赖";
  if (definition.scope === "architecture")
    return "项目架构关注点 › 外部Service关注点";
  if (layer === "human")
    return `交互级关注点 › 人类Actor关注点 › ${key.endsWith("authentication") ? "身份关注点" : "权限关注点"}`;
  if (layer === "relation") return "交互级关注点 › Service之间";
  if (layer === "global") return "全局业务级关注点";
  if (layer === "base") {
    const label =
      key === "service.base.request_data"
        ? "输入数据"
        : key === "service.base.response_contract"
          ? "输出数据"
          : group === "business_attribute"
            ? definition.label || "字段约束"
            : "外部Service调用";
    return [...base, "第一层：基础关注点", label].join(" › ");
  }
  if (layer === "shared") {
    const found = new Set<string>();
    const visit = (id: string, seen: Set<string>) => {
      if (seen.has(id)) return;
      if (
        [
          "service.base.request_data",
          "service.base.response_contract",
        ].includes(id) &&
        definitions[id]?.enabled !== false
      )
        found.add(id);
      (definitions[id]?.parents || []).forEach((parent: string) =>
        visit(parent, new Set([...seen, id])),
      );
    };
    visit(key, new Set());
    const root =
      step?.direction === "return"
        ? "service.base.response_contract"
        : "service.base.request_data";
    if (found.has(root))
      return [
        ...base,
        "第一层：基础关注点",
        step?.direction === "return" ? "输出数据" : "输入数据",
      ].join(" › ");
  }
  const crud: Record<string, string> = {
    query_retrieval: "R：查询检索",
    create: "C：创建",
    update: "U：更新",
    delete: "D：删除",
  };
  const functions: Record<string, string> = {
    display_interaction: "展示交互型",
    analysis_generation: "分析生成型",
    release_activation: "发布生效型",
  };
  if (layer === "functional" && crud[group])
    return [...base, "第二层：功能类型关注点", crud[group]].join(" › ");
  if (layer === "functional" && functions[group])
    return [...base, "第三层：业务关注点", functions[group]].join(" › ");
  if (layer === "technology" && ["database", "llm"].includes(group))
    return [
      ...base,
      "第四层：技术扩展关注点",
      group === "database" ? "数据库" : "LLM",
    ].join(" › ");
  return "待归类";
}

export function SsdAlignmentTable({
  rows,
  bundle,
  savedBundle,
  step,
  layer,
  readonly,
  selected,
  onSelect,
  onNew,
  onPatch,
  onClearCell,
  onDeleteRow,
  onMerge,
  onEdit,
  onLocate,
  onSplit,
  onRemove,
  onSources,
  onGoToStep,
  onMatch,
  onMatchEvidence,
  onScenarios,
  getObjectName,
  getGroupPath,
  getTargetLabel,
  objectHeading,
  emptyLabel = "当前步骤",
}: {
  rows: any[];
  bundle: {
    registry?: any;
    steps?: Step[];
    operation_units?: Bundle["operation_units"];
    anchors?: any[];
    documents?: any[];
    channels?: Record<
      string,
      { scenarios: Observation[]; concerns?: Observation[] }
    >;
    decisions?: Bundle["decisions"];
  };
  savedBundle?: any;
  step?: Step;
  layer: SsdRecordKind;
  readonly: boolean;
  selected: Record<Channel, string[]>;
  onSelect: (channel: Channel, id: string, selected: boolean) => void;
  onNew: (channel: Channel, row?: any) => void;
  onPatch?: (channel: Channel, record: Observation) => void;
  onClearCell?: (channel: Channel, row: any) => void;
  onDeleteRow?: (row: any) => void;
  onMerge: (channel: Channel) => void;
  onEdit: (channel: Channel, item: Observation) => void;
  onLocate?: (channel: Channel, item: Observation) => void;
  onSplit: (channel: Channel, item: Observation) => void;
  onRemove: (channel: Channel, item: Observation) => void;
  onSources: (item: Observation) => void;
  onGoToStep?: (stepId: string) => void;
  onMatch: (row: any) => void;
  onMatchEvidence?: (
    row: any,
    channel: "E" | "GT",
    record?: Observation,
  ) => void;
  onScenarios: (row: any) => void;
  getObjectName?: (record: Observation) => string;
  getGroupPath?: (key: string) => string;
  getTargetLabel?: (record: Observation) => string;
  objectHeading?: string;
  emptyLabel?: string;
}) {
  const changedMatches = useMemo(
    () => draftChanges(savedBundle, bundle).matches,
    [savedBundle, bundle],
  );
  const definitions = bundle.registry?.definitions || {};
  const group = (row: any) =>
    getGroupPath?.(row.key || "") || concernPath(row.key || "", bundle, step);
  const groupOrder = (row: any) => {
    const path = group(row);
    return path.includes("人类Actor")
      ? 0
      : path.includes("第一层")
        ? 1
        : path.includes("第二层")
          ? 2
          : path.includes("第三层")
            ? 3
            : path.includes("第四层")
              ? 4
              : path.includes("Service之间")
                ? 5
                : 6;
  };
  const shown = [...rows].sort(
    (a, b) =>
      groupOrder(a) - groupOrder(b) ||
      group(a).localeCompare(group(b), "zh-CN") ||
      String(a.key).localeCompare(String(b.key)),
  );
  const noun =
    layer === "concerns"
      ? "关注点"
      : layer === "scenarios"
        ? "场景"
        : "待确认项";
  const groundedLinks = new Map<
    string,
    {
      target: Observation;
      channel: "G" | "E";
      decision: Bundle["decisions"][number];
    }[]
  >();
  if (layer !== "pending") {
    const generated = new Map(
      (bundle.channels?.G?.[layer] || []).map((record) => [record.id, record]),
    );
    const originals = new Map(
      (bundle.channels?.E?.[layer] || []).map((record) => [record.id, record]),
    );
    for (const decision of bundle.decisions || []) {
      if (
        decision.level !== (layer === "concerns" ? "concern" : "scenario") ||
        !["full", "partial"].includes(decision.status)
      )
        continue;
      const source =
        decision.pair === "G_E"
          ? `E:${decision.right_id}`
          : decision.pair === "GT_G"
            ? `GT:${decision.left_id}`
            : null;
      const target = generated.get(
        decision.pair === "G_E" ? decision.left_id : decision.right_id,
      );
      if (!source || !target) continue;
      const links = groundedLinks.get(source) || [];
      links.push({ target, channel: "G", decision });
      groundedLinks.set(source, links);
      const original =
        decision.pair === "G_E" && originals.get(decision.right_id);
      if (original) {
        const reciprocal = groundedLinks.get(`G:${target.id}`) || [];
        reciprocal.push({ target: original, channel: "E", decision });
        groundedLinks.set(`G:${target.id}`, reciprocal);
      }
    }
  }
  const childCounts = useMemo(() => {
    const counts = new Map<string, number>();
    if (layer === "concerns") {
      for (const channel of channels) {
        for (const scene of bundle.channels?.[channel]?.scenarios || []) {
          if (scene.status !== "active") continue;
          for (const id of scene.concern_ids || [])
            counts.set(id, (counts.get(id) || 0) + 1);
        }
      }
    }
    return counts;
  }, [bundle.channels, layer]);
  function objectName(record: Observation) {
    if (getObjectName) return getObjectName(record);
    if (record.input_group) return "本交互输入";
    const unit = bundle.operation_units?.find(
      (item) => item.id === record.operation_unit_id,
    );
    if (record.path_input) {
      const { command_id, parameter } = record.path_input;
      return `${command_id} · 路径参数${parameter ? ` {${parameter}}` : ""}`;
    }
    if (record.resource_reference) {
      const reference = record.resource_reference;
      const roles = {
        target: "操作目标",
        parent: "父对象",
        ancestor: "祖先对象",
        dependency: "依赖对象",
        unknown: "引用对象",
      };
      return [
        reference.command_id,
        unit?.name,
        `${roles[reference.role]} ${reference.parameter_name}`,
      ]
        .filter(Boolean)
        .join(" · ");
    }
    if (unit) return [unit.command_id, unit.name].filter(Boolean).join(" · ");
    if (record.entity_id && record.attribute)
      return `${record.entity_id}.${record.attribute}`;
    const owner = bundle.steps?.find((item) => item.id === record.step_id);
    const field = owner?.data.find((item) => item.id === record.field_id);
    if (record.target === "data")
      return field ? fieldLabel(field) : record.field_id || "待指定字段";
    if (record.target === "sender") return owner?.sender.name || "待定位发送方";
    if (record.target === "receiver")
      return owner?.receiver.name || "待定位接收方";
    return "待定位对象";
  }
  return (
    <div className="alignment-scroll ssd-alignment-scroll">
      <table
        className={`alignment-table ${layer === "concerns" ? "concern-alignment-table" : ""}`}
      >
        <thead>
          <tr>
            <th>
              {objectHeading ||
                (layer === "scenarios"
                  ? "具体异常／关联关注点"
                  : "四要素对象／关注点")}
            </th>
            {channels.map((channel) => (
              <th key={channel}>
                {channel === "E"
                  ? "需求文档已有"
                  : channel === "G"
                    ? "本方法生成"
                    : "独立测试"}{" "}
                {channel}
                {layer === "concerns" ? "_c" : ""}
                {!readonly && (
                  <details className="ssd-column-actions">
                    <summary>{channelLabels[channel]}操作</summary>
                    <div className="ssd-column-menu">
                      <button onClick={() => onNew(channel)}>
                        新增{channelLabels[channel]}
                        {noun}
                      </button>
                      <button
                        disabled={selected[channel].length < 2}
                        onClick={() => onMerge(channel)}
                      >
                        合并所选（{selected[channel].length}）
                      </button>
                    </div>
                  </details>
                )}
              </th>
            ))}
            <th>对应状态与依据</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((row, index) => {
            const first = channels.flatMap(
              (channel) => row.cells[channel],
            )[0] as Observation;
            const label =
              definitions[row.key]?.label ||
              first?.label ||
              row.key ||
              "待归类关注点";
            const bindings = [
              ...new Map<string, Observation>(
                (row.generated_id ? ["G"] : channels)
                  .flatMap((channel) => row.cells[channel])
                  .map((record: Observation) => [
                    [
                      record.target,
                      record.field_id,
                      record.entity_id,
                      objectName(record),
                    ].join(":"),
                    record,
                  ]),
              ).values(),
            ];
            const rowDrafts = savedBundle
              ? rowDraftDecisions(
                  bundle,
                  savedBundle,
                  row,
                  layer,
                  changedMatches,
                )
              : [];
            const single = (channel: Channel) =>
              row.generated_id && channel !== "G" ? [] : row.cells[channel];
            const scopedDrafts = row.generated_id
              ? rowDrafts.filter(
                  (d) =>
                    (d.pair === "G_E" && d.left_id === row.generated_id) ||
                    (d.pair === "GT_G" && d.right_id === row.generated_id),
                )
              : rowDrafts;
            return (
              <Fragment key={row.id}>
                {(index === 0 || group(shown[index - 1]) !== group(row)) && (
                  <tr className="concern-group-heading">
                    <td colSpan={5}>{group(row)}</td>
                  </tr>
                )}
                <tr className={`alignment-${row.status}`}>
                  <td>
                    {bindings.map((record, index) => (
                      <div className="ssd-binding" key={index}>
                        <small className="concern-path">
                          {getTargetLabel?.(record) ||
                            (record.entity_id && record.attribute
                              ? "实体属性"
                              : null) ||
                            targetLabels[record.target || ""] ||
                            "待定位"}
                        </small>
                        <strong>{objectName(record)}</strong>
                        {record.entity_id && (
                          <small>实体：{record.entity_id}</small>
                        )}
                      </div>
                    ))}
                    <p>{label}</p>
                    {layer === "scenarios" && first?.condition && (
                      <p>{first.condition}</p>
                    )}
                  </td>
                  {channels.map((channel) => (
                    <td key={channel}>
                      {row.generated_id &&
                        channel !== "G" &&
                        row.cells[channel].length > 0 && (
                          <EvidenceCell
                            records={row.cells[channel]}
                            channel={channel}
                            onSources={onSources}
                            onGoToStep={onGoToStep}
                            onEdit={readonly ? undefined : onEdit}
                            onMatch={
                              readonly || !onMatchEvidence
                                ? undefined
                                : (record) =>
                                    onMatchEvidence(row, channel, record)
                            }
                            generated={row.cells.G[0]}
                            decisions={bundle.decisions}
                            level={
                              layer === "concerns" ? "concern" : "scenario"
                            }
                          />
                        )}
                      {row.cells[channel].length ? (
                        single(channel).map((record: Observation) => (
                          <article
                            className="concern-cell ssd-record"
                            key={record.id}
                          >
                            {channel === "G" &&
                              row.coverage_by_record?.[record.id] && (
                                <small className="ssd-coverage">
                                  {scopedDrafts.some(
                                    (d) =>
                                      d.pair === "GT_G" &&
                                      d.right_id === record.id,
                                  )
                                    ? "GT覆盖存在判定草稿，保存后重算"
                                    : row.coverage_by_record[record.id].complete
                                      ? row.coverage_by_record[record.id]
                                          .covered
                                        ? "GT覆盖"
                                        : "GT不覆盖"
                                      : "匹配未完成"}
                                </small>
                              )}
                            {channel === "G" &&
                              layer === "scenarios" &&
                              row.coverage_by_record?.[record.id]?.links
                                ?.length > 0 && (
                                <details className="ssd-coverage-links">
                                  <summary>
                                    关联GT与覆盖依据（
                                    {
                                      row.coverage_by_record[record.id].links
                                        .length
                                    }
                                    ）
                                  </summary>
                                  {row.coverage_by_record[record.id].links.map(
                                    (link: any) => {
                                      const gt =
                                        bundle.channels?.GT.scenarios.find(
                                          (item: Observation) =>
                                            item.id === link.id,
                                        );
                                      return (
                                        <div key={link.id}>
                                          <strong>
                                            {row.generated_id
                                              ? "匹配"
                                              : link.status === "partial"
                                                ? "部分覆盖"
                                                : "完整覆盖"}
                                          </strong>
                                          <p>{link.condition}</p>
                                          <p>{link.reason}</p>
                                          {!row.cells.GT.some(
                                            (item: Observation) =>
                                              item.id === link.id,
                                          ) && (
                                            <small>关联GT位于其他表格行</small>
                                          )}
                                          {gt && (
                                            <button
                                              onClick={() => onSources(gt)}
                                            >
                                              查看关联GT出处
                                            </button>
                                          )}
                                        </div>
                                      );
                                    },
                                  )}
                                </details>
                              )}
                            {channel === "G" &&
                              layer === "scenarios" &&
                              row.coverage_by_record?.[record.id]?.label && (
                                <small className="ssd-review-eligibility">
                                  审核导出：
                                  {row.coverage_by_record[record.id].label}
                                </small>
                              )}
                            {!!groundedLinks.get(`${channel}:${record.id}`)
                              ?.length && (
                              <details className="ssd-coverage-links">
                                <summary>
                                  关联 {channel === "G" ? "E" : "G"} 与判定依据
                                </summary>
                                {groundedLinks
                                  .get(`${channel}:${record.id}`)!
                                  .map(
                                    ({
                                      target,
                                      channel: targetChannel,
                                      decision,
                                    }) => (
                                      <div key={decision.id}>
                                        <p>
                                          {row.generated_id
                                            ? "匹配"
                                            : decision.status === "partial"
                                              ? "部分覆盖"
                                              : "完整覆盖"}{" "}
                                          · {target.condition}
                                        </p>
                                        <p>{decision.reason}</p>
                                        {onGoToStep &&
                                          target.step_id &&
                                          target.step_id !== record.step_id && (
                                            <button
                                              onClick={() =>
                                                onGoToStep(target.step_id!)
                                              }
                                            >
                                              查看 {targetChannel} 步骤{" "}
                                              {target.step_id}
                                            </button>
                                          )}
                                        <button
                                          onClick={() => onSources(target)}
                                        >
                                          查看关联 {targetChannel} 出处
                                        </button>
                                      </div>
                                    ),
                                  )}
                              </details>
                            )}
                            <div className="ssd-record-title">
                              {!readonly && (
                                <input
                                  aria-label={`选择 ${channel} ${record.id}`}
                                  title="选择合并"
                                  type="checkbox"
                                  checked={selected[channel].includes(
                                    record.id,
                                  )}
                                  onChange={(event) =>
                                    onSelect(
                                      channel,
                                      record.id,
                                      event.target.checked,
                                    )
                                  }
                                />
                              )}
                              <button
                                className="ssd-record-link"
                                aria-label={`${readonly ? "查看" : "编辑"} ${channel} ${record.id}`}
                                onClick={() =>
                                  readonly
                                    ? onSources(record)
                                    : onEdit(channel, record)
                                }
                              >
                                {record.label ||
                                  definitions[record.key || ""]?.label ||
                                  record.key ||
                                  "待确认记录"}
                              </button>
                            </div>
                            {(record.applicable_operations?.length || 0) >
                              1 && (
                              <small>
                                适用操作{" "}
                                {record
                                  .applicable_operations!.map((key) =>
                                    key[0].toUpperCase(),
                                  )
                                  .join("／")}
                              </small>
                            )}
                            {onPatch && !readonly ? (
                              <div className="ssd-cell-fields">
                                {[
                                  ...(layer === "concerns"
                                    ? [["label", "关注点名称"]]
                                    : []),
                                  ["condition", "条件或描述"],
                                  ...(layer === "scenarios"
                                    ? [
                                        ["analysis", "具体场景说明"],
                                        ["expected", "预期结果"],
                                      ]
                                    : []),
                                ].map(([field, label]) => (
                                  <EditableCell
                                    key={field}
                                    label={`${channel} ${record.id} ${label}`}
                                    value={record[field]}
                                    onChange={(value) =>
                                      onPatch(channel, {
                                        ...record,
                                        display_row_id:
                                          record.display_row_id || row.id,
                                        [field]: value,
                                      })
                                    }
                                  />
                                ))}
                              </div>
                            ) : (
                              <p>{record.condition}</p>
                            )}
                            {(!onPatch || readonly) && record.analysis && (
                              <p className="scenario-analysis">
                                {record.analysis}
                              </p>
                            )}
                            {(!onPatch || readonly) && record.expected && (
                              <p>预期：{record.expected}</p>
                            )}
                            {record.failure_step_pending && (
                              <p className="ssd-record-issue">
                                实际失败步骤待定位
                              </p>
                            )}
                            {(record.binding_issue || record.reason) && (
                              <p className="ssd-record-issue">
                                {record.binding_issue || record.reason}
                              </p>
                            )}
                            {record.status !== "active" && (
                              <small className="ssd-status">
                                {ssdStatusNames[record.status] || record.status}
                              </small>
                            )}
                            {record.source_kind && (
                              <small>
                                {record.source_kind}
                                {record.review_comment
                                  ? ` · ${record.review_comment}`
                                  : ""}
                              </small>
                            )}
                            {(channel === "GT" ||
                              record.requirement_refs?.length > 0) && (
                              <button
                                onClick={() =>
                                  onSources({
                                    ...record,
                                    source_refs: relatedRequirementRefs(
                                      bundle,
                                      record,
                                    ),
                                  })
                                }
                              >
                                {relatedRequirementRefs(bundle, record).length
                                  ? "查看关联需求／设计（非测试出处）"
                                  : "浏览需求／设计（尚无精确定位）"}
                              </button>
                            )}
                            <button
                              className="ssd-source-link"
                              onClick={() => onSources(record)}
                            >
                              {channel === "GT"
                                ? "查看测试逆向出处"
                                : "查看原始出处"}
                              （{record.source_refs?.length || 0}）
                            </button>
                            {(record.source_refs || []).some(
                              (r: any) => r.origin === "manual",
                            ) && (
                              <small className="ssd-manual-source">
                                含人工补录出处
                              </small>
                            )}
                            {!readonly &&
                              onLocate &&
                              (!step ||
                                layer === "pending" ||
                                record.status === "unbound") && (
                                <button
                                  className="ssd-match-link"
                                  aria-label={`定位与挂载 ${channel} ${record.id}`}
                                  onClick={() => onLocate(channel, record)}
                                >
                                  定位与挂载
                                </button>
                              )}
                            <details>
                              <summary>
                                记录详情{readonly ? "" : "与更多操作"}
                              </summary>
                              <small>{record.id}</small>
                              {record.failure_variants && (
                                <p>
                                  失败类型明细 ·{" "}
                                  {Object.values(record.failure_variants).join(
                                    "、",
                                  )}
                                </p>
                              )}
                              <p>
                                挂载：
                                {getTargetLabel?.(record) ||
                                  (record.entity_id && record.attribute
                                    ? "实体属性"
                                    : null) ||
                                  targetLabels[record.target || ""] ||
                                  "待定位"}{" "}
                                · {objectName(record)}
                              </p>
                              {record.entity_id && (
                                <p>
                                  实体：{record.entity_id}
                                  {record.attribute
                                    ? "." + record.attribute
                                    : ""}
                                </p>
                              )}
                              {(
                                [
                                  [
                                    "实际失败步骤",
                                    record.failure_step_ids ||
                                      (record.failure_step_id
                                        ? [record.failure_step_id]
                                        : []),
                                  ],
                                  [
                                    "校验步骤",
                                    record.validation_step_ids || [],
                                  ],
                                  ["响应步骤", record.response_step_ids || []],
                                  [
                                    "关联调用",
                                    record.related_call_step_ids || [],
                                  ],
                                ] as [string, string[]][]
                              ).map(
                                ([label, ids]) =>
                                  ids.length > 0 && (
                                    <p key={label}>
                                      {label}：
                                      {onGoToStep
                                        ? ids.map((id) => (
                                            <button
                                              className="ssd-source-link"
                                              key={id}
                                              onClick={() => onGoToStep(id)}
                                            >
                                              {id}
                                            </button>
                                          ))
                                        : ids.join("、")}
                                    </p>
                                  ),
                              )}
                              {record.failure_step_reason && (
                                <p>
                                  失败定位依据：{record.failure_step_reason}
                                </p>
                              )}
                              {record.identification_reason && (
                                <p>识别依据：{record.identification_reason}</p>
                              )}
                              {record.rule_id && <p>规则：{record.rule_id}</p>}
                              {(record.generation_origin ||
                                record.template_id) && (
                                <p>
                                  生成依据：
                                  {record.generation_origin ===
                                  "reference_template"
                                    ? "参考模板"
                                    : record.generation_origin ===
                                        "deterministic_constraint"
                                      ? "确定性约束"
                                      : /model|llm/.test(
                                            record.generation_origin || "",
                                          )
                                        ? "模型补充"
                                        : record.generation_origin ||
                                          "参考模板"}
                                  {record.template_id
                                    ? ` · ${record.template_id}`
                                    : ""}
                                  {record.variant_id
                                    ? ` / ${record.variant_id}`
                                    : ""}
                                  {record.template_version
                                    ? ` · ${record.template_version}`
                                    : ""}
                                </p>
                              )}
                              {!!record.members?.length && (
                                <details className="ssd-member-details">
                                  <summary>
                                    合并成员与各调用处理预期（
                                    {record.members.length}）
                                  </summary>
                                  {record.members.map((m: any, i: number) => (
                                    <div key={i}>
                                      <strong>
                                        {m.case_id || "历史架构结果"} ·{" "}
                                        {m.step_id || "服务级"}
                                      </strong>
                                      <p>{m.condition}</p>
                                      <p>预期：{m.expected}</p>
                                      <p>{m.analysis}</p>
                                      <button
                                        onClick={() =>
                                          onSources({
                                            ...record,
                                            source_refs: m.source_refs || [],
                                            requirement_refs:
                                              m.requirement_refs || [],
                                          })
                                        }
                                      >
                                        查看成员出处
                                      </button>
                                    </div>
                                  ))}
                                </details>
                              )}
                              {!readonly && (
                                <div className="ssd-inline-actions">
                                  <button
                                    aria-label={`拆分 ${channel} ${record.id}`}
                                    onClick={() => onSplit(channel, record)}
                                  >
                                    拆分为新增记录
                                  </button>
                                  <button
                                    aria-label={`删除 ${channel} ${record.id}`}
                                    onClick={() => onRemove(channel, record)}
                                  >
                                    {layer === "pending"
                                      ? "不是异常（移除）"
                                      : "删除"}
                                  </button>
                                </div>
                              )}
                            </details>
                          </article>
                        ))
                      ) : readonly ? (
                        <span className="alignment-empty">
                          未识别到对应{noun}
                        </span>
                      ) : (
                        <button
                          className="ssd-empty-cell"
                          onClick={() => onNew(channel, row)}
                        >
                          点击补录{noun}
                        </button>
                      )}
                      {!readonly && (
                        <div className="ssd-cell-actions">
                          <button onClick={() => onNew(channel, row)}>
                            ＋ 添加记录
                          </button>
                          {onClearCell && row.cells[channel].length > 0 && (
                            <button onClick={() => onClearCell(channel, row)}>
                              {row.generated_id && channel !== "G"
                                ? "解除本格匹配"
                                : "清空单元格"}
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  ))}
                  <td>
                    <strong className={`ssd-status ssd-status-${row.status}`}>
                      {scopedDrafts.length > 0 && "已保存："}
                      {ssdStatusNames[row.status] || row.status}
                    </strong>
                    <p>
                      {scopedDrafts.length > 0 && "已保存依据："}
                      {row.reason}
                    </p>
                    {scopedDrafts.map((d) => (
                      <p
                        role="status"
                        className="ssd-table-draft-status"
                        key={decisionKey(d)}
                      >
                        {d.pair} ·{" "}
                        {d.status === "removed"
                          ? "已撤销判定"
                          : decisionLabel(d.status)}{" "}
                        · 未保存
                        <br />
                        {d.reason}
                      </p>
                    ))}
                    {layer === "concerns" && (
                      <button
                        className="concern-drilldown"
                        onClick={() => onScenarios(row)}
                      >
                        {bindings.some((record) => record.input_group)
                          ? `查看场景（${channels
                              .filter(
                                (channel) => row.cells[channel].length > 0,
                              )
                              .map(
                                (channel) =>
                                  `${channel} ${row.cells[channel].reduce(
                                    (count: number, record: Observation) =>
                                      count + (childCounts.get(record.id) || 0),
                                    0,
                                  )}`,
                              )
                              .join(" · ")}） →`
                          : "查看该关注点的场景 →"}
                      </button>
                    )}
                    {!readonly && onDeleteRow && !row.generated_id && (
                      <button onClick={() => onDeleteRow(row)}>删除整行</button>
                    )}
                    {!readonly && row.generated_id && onMatchEvidence
                      ? (["E", "GT"] as const).map((channel) => (
                          <button
                            className="ssd-match-link"
                            key={channel}
                            onClick={() => onMatchEvidence(row, channel)}
                          >
                            匹配 {channel} 记录
                          </button>
                        ))
                      : !readonly &&
                        layer !== "pending" && (
                          <button
                            className="ssd-match-link"
                            onClick={() => onMatch(row)}
                          >
                            修正匹配
                          </button>
                        )}
                  </td>
                </tr>
              </Fragment>
            );
          })}
        </tbody>
        {!readonly && (
          <tfoot>
            <tr>
              <td colSpan={5}>
                <button onClick={() => onNew("G")}>
                  ＋ 在末尾新增行（选择框架关注点）
                </button>
              </td>
            </tr>
          </tfoot>
        )}
      </table>
      {!shown.length && (
        <p className="muted ssd-empty">
          {emptyLabel}及筛选下没有{noun}记录。
        </p>
      )}
    </div>
  );
}

function citationKey(ref: SourceRef) {
  const origin = typeof ref.origin === "object" ? ref.origin : undefined;
  if (
    origin?.document &&
    ["exact", "located"].includes(origin.match) &&
    (origin.cell_range || origin.start_line)
  )
    return JSON.stringify([
      origin.document,
      origin.sheet,
      origin.cell_range,
      origin.start_line,
      origin.end_line,
    ]);
  return JSON.stringify([
    ref.document_id,
    ref.start_line,
    ref.end_line,
    ref.json_pointer,
  ]);
}

function EvidenceCell({
  records,
  channel,
  generated,
  decisions,
  level,
  onSources,
  onGoToStep,
  onEdit,
  onMatch,
}: {
  records: Observation[];
  channel: "E" | "GT";
  generated: Observation;
  decisions?: Bundle["decisions"];
  level: string;
  onSources: (record: Observation) => void;
  onGoToStep?: (id: string) => void;
  onEdit?: (channel: Channel, record: Observation) => void;
  onMatch?: (record: Observation) => void;
}) {
  const refs = [
    ...new Map(
      records.flatMap((record) =>
        (record.source_refs || []).map(
          (ref) => [citationKey(ref), ref] as const,
        ),
      ),
    ).values(),
  ];
  const preferred = records[0];
  const getDecision = (record: Observation) =>
    decisions?.find(
      (decision) =>
        decision.level === level &&
        (channel === "E"
          ? decision.pair === "G_E" &&
            decision.left_id === generated.id &&
            decision.right_id === record.id
          : decision.pair === "GT_G" &&
            decision.left_id === record.id &&
            decision.right_id === generated.id),
    );
  return (
    <article className="concern-cell ssd-record ssd-evidence-cell">
      <strong>
        {preferred.validation_summary
          ? "概括性来源已匹配"
          : preferred.condition}
      </strong>
      {!preferred.validation_summary && preferred.expected && (
        <p>预期：{preferred.expected}</p>
      )}
      <button
        className="ssd-source-link"
        onClick={() =>
          onSources({
            ...preferred,
            source_refs: refs,
          })
        }
      >
        {channel === "GT" ? "查看测试逆向出处" : "查看原始出处"}（{refs.length}
        ）
      </button>
      <details>
        <summary>查看来源记录与判定（{records.length}）</summary>
        {records.map((record) => (
          <div className="ssd-evidence-member" key={record.id}>
            <p>{record.condition}</p>
            {record.expected && <p>预期：{record.expected}</p>}
            {(record.failure_step_id || record.step_id) && (
              <p>实际步骤：{record.failure_step_id || record.step_id}</p>
            )}
            {getDecision(record)?.reason && (
              <p>{getDecision(record)?.reason}</p>
            )}
            <div className="ssd-inline-actions">
              <button onClick={() => onSources(record)}>查看本条出处</button>
              {onGoToStep &&
                (record.failure_step_id || record.step_id) &&
                (record.failure_step_id || record.step_id) !==
                  generated.step_id && (
                  <button
                    onClick={() =>
                      onGoToStep((record.failure_step_id || record.step_id)!)
                    }
                  >
                    跳到实际步骤
                  </button>
                )}
              {onEdit && (
                <button onClick={() => onEdit(channel, record)}>
                  编辑来源记录
                </button>
              )}
              {onMatch && (
                <button onClick={() => onMatch(record)}>修正此项匹配</button>
              )}
            </div>
          </div>
        ))}
      </details>
    </article>
  );
}
