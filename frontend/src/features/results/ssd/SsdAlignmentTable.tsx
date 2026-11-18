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
  channelLabels,
  targetLabels,
  type Channel,
  type Observation,
  type Step,
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
            ? "业务实体属性约束"
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
        ].includes(id)
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
  onSplit,
  onRemove,
  onSources,
  onGoToStep,
  onMatch,
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
    anchors?: any[];
    documents?: any[];
    channels?: Record<string, { scenarios: Observation[] }>;
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
  onSplit: (channel: Channel, item: Observation) => void;
  onRemove: (channel: Channel, item: Observation) => void;
  onSources: (item: Observation) => void;
  onGoToStep?: (stepId: string) => void;
  onMatch: (row: any) => void;
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
  function objectName(record: Observation) {
    if (getObjectName) return getObjectName(record);
    if (record.entity_id && record.attribute)
      return `${record.entity_id}.${record.attribute}`;
    const owner = bundle.steps?.find((item) => item.id === record.step_id);
    const field = owner?.data.find((item) => item.id === record.field_id);
    if (record.target === "data")
      return field
        ? [field.location, field.name].filter(Boolean).join(".")
        : record.field_id || "待指定字段";
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
                channels
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
                      {row.cells[channel].length ? (
                        row.cells[channel].map((record: Observation) => (
                          <article
                            className="concern-cell ssd-record"
                            key={record.id}
                          >
                            {channel === "G" &&
                              row.coverage_by_record?.[record.id] && (
                                <small className="ssd-coverage">
                                  {rowDrafts.some(
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
                                            {link.status === "partial"
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
                            <details>
                              <summary>
                                记录详情{readonly ? "" : "与更多操作"}
                              </summary>
                              <small>{record.id}</small>
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
                              清空单元格
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  ))}
                  <td>
                    <strong className={`ssd-status ssd-status-${row.status}`}>
                      {rowDrafts.length > 0 && "已保存："}
                      {ssdStatusNames[row.status] || row.status}
                    </strong>
                    <p>
                      {rowDrafts.length > 0 && "已保存依据："}
                      {row.reason}
                    </p>
                    {rowDrafts.map((d) => (
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
                        查看该关注点的场景 →
                      </button>
                    )}
                    {!readonly && onDeleteRow && (
                      <button onClick={() => onDeleteRow(row)}>删除整行</button>
                    )}
                    {!readonly && layer !== "pending" && (
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
