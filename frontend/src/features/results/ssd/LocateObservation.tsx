import { useState } from "react";
import { putDecision } from "../shared/matchDraft";
import { putTableRecord } from "../shared/tableEditing";
import { Modal, Select, Text } from "./SsdEditors";
import type { SsdRecordKind } from "./SsdAlignmentTable";
import { channelLabels, targetLabels, uid } from "./types";
import { fieldLabel } from "./types";
import type { Bundle, Channel, Observation, Step } from "./types";

type LocationTarget = { channel?: Channel; record: Observation };
type LocationChoice = {
  target: LocationTarget;
  scenario?: Observation;
  status: "full" | "partial";
  condition: string;
  expected: string;
  reason: string;
};

const bindingFields = [
  "step_id",
  "target",
  "key",
  "field_id",
  "entity_id",
  "attribute",
  "unit_id",
  "obligation_scope",
  "operation_unit_id",
  "command_id",
  "call_step_id",
  "validation_step_ids",
  "response_step_ids",
  "related_call_step_ids",
];

function sameBinding(a: Observation, b: Observation) {
  return [
    "step_id",
    "target",
    "key",
    "field_id",
    "entity_id",
    "attribute",
    "obligation_scope",
    "operation_unit_id",
  ].every((key) => {
    if (key === "obligation_scope")
      return (
        JSON.stringify([...(a[key] || [])].sort()) ===
        JSON.stringify([...(b[key] || [])].sort())
      );
    return (a[key] || null) === (b[key] || null);
  });
}

export function locateObservation(
  bundle: Bundle,
  channel: Channel,
  kind: SsdRecordKind,
  item: Observation,
  choice: LocationChoice,
) {
  const { target, scenario, condition, expected, status, reason } = choice;
  const records = bundle.channels[channel];
  const mounted: Observation = {
    ...item,
    condition,
    status: "active",
    origin: "manual",
  };
  for (const key of bindingFields) {
    delete mounted[key];
    if (target.record[key] != null) mounted[key] = target.record[key];
  }
  mounted.label = target.record.label || target.record.key;
  mounted.needs_semantic = false;
  if (mounted.reason && !mounted.identification_reason)
    mounted.identification_reason = mounted.reason;
  delete mounted.binding_issue;
  delete mounted.reason;
  delete mounted.display_row_id;
  delete mounted.aligned_concern_ids;

  mounted.source_record_ids = [
    ...new Set([...(item.source_record_ids || []), item.id]),
  ];
  const existing = records.concerns.find(
    (row) => row.id !== item.id && sameBinding(row, mounted),
  );
  const concern: Observation = existing
    ? {
        ...existing,
        status: "active",
        source_refs: [
          ...new Map(
            [...existing.source_refs, ...mounted.source_refs].map((ref) => [
              JSON.stringify(ref),
              ref,
            ]),
          ).values(),
        ],
      }
    : {
        ...mounted,
        id: kind === "concerns" ? item.id : uid("concern"),
        condition: kind === "concerns" ? condition : mounted.label || condition,
      };
  delete concern.binding_issue;
  delete concern.concern_ids;
  delete concern.expected;
  delete concern.analysis;

  if (kind === "pending")
    records.pending = records.pending.filter((row) => row.id !== item.id);
  if (kind === "concerns" && existing) {
    records.concerns = records.concerns.filter((row) => row.id !== item.id);
    for (const row of records.scenarios)
      if (row.concern_ids?.includes(item.id))
        row.concern_ids = [
          ...new Set(
            row.concern_ids.map((id) => (id === item.id ? concern.id : id)),
          ),
        ];
  }
  putTableRecord(bundle, channel, "concerns", concern);
  if (kind !== "concerns")
    putTableRecord(bundle, channel, "scenarios", {
      ...mounted,
      expected,
      concern_ids: [concern.id],
    });

  bundle.decisions = bundle.decisions.filter((decision) => {
    const movedLevel = kind === "concerns" ? "concern" : "scenario";
    if (kind === "pending" || decision.level !== movedLevel) return true;
    const [left, right] = decision.pair.split("_");
    return !(
      (left === channel && decision.left_id === item.id) ||
      (right === channel && decision.right_id === item.id)
    );
  });
  if (!target.channel) {
    bundle.review_notes = [
      ...(bundle.review_notes || []),
      {
        id: uid("review"),
        channel,
        record_id: item.id,
        decision: "mounted",
        reason: reason.trim() || "人工确认独立挂载",
      },
    ];
    return;
  }
  const order: Channel[] = ["GT", "G", "E"];
  const [left, right] = order.filter(
    (ch) => ch === channel || ch === target.channel,
  );
  function match(level: "concern" | "scenario", own: string, other: string) {
    putDecision(bundle, {
      id: uid("match"),
      level,
      pair: `${left}_${right}`,
      left_id: left === channel ? own : other,
      right_id: right === channel ? own : other,
      status: level === "concern" ? "full" : status,
      reason: reason.trim() || "人工定位并确认对应关系",
      origin: "manual",
    });
  }
  match("concern", concern.id, target.record.id);
  if (scenario && kind !== "concerns") match("scenario", item.id, scenario.id);
}

function describeObject(record: Observation, step: Step, bundle: Bundle) {
  const operation = bundle.operation_units?.find(
    (unit) => unit.id === record.operation_unit_id,
  );
  if (operation)
    return [operation.command_id, operation.name].filter(Boolean).join(" · ");
  const field = step.data.find((field) => field.id === record.field_id);
  if (field) return fieldLabel(field);
  if (record.entity_id)
    return [record.entity_id, record.attribute].filter(Boolean).join(".");
  if (record.target === "sender") return step.sender.name;
  if (record.target === "receiver") return step.receiver.name;
  return targetLabels[record.target || ""] || "未指定对象";
}

type MountObject = {
  id: string;
  label: string;
  binding: Partial<Observation>;
};

function mountObjects(bundle: Bundle, step: Step): MountObject[] {
  const anchors = (bundle.field_anchors?.units || []).filter(
    (unit) => unit.step_id === step.id,
  );
  const entities = new Set([
    ...step.entity_ids,
    ...anchors.map((unit) => unit.entity),
  ]);
  return [
    {
      id: "sender",
      label: `发送方 · ${step.sender.name}`,
      binding: { target: "sender" },
    },
    {
      id: "receiver",
      label: `接收方 · ${step.receiver.name}`,
      binding: { target: "receiver" },
    },
    ...[...entities].flatMap((entityId) => {
      const attributes = (
        bundle.entities?.find((entity) => entity.id === entityId)?.attributes ||
        []
      ).filter(
        (attribute) =>
          step.entity_ids.includes(entityId) ||
          anchors.some(
            (anchor) =>
              anchor.entity === entityId && anchor.attribute === attribute.name,
          ),
      );
      return [
        {
          id: JSON.stringify([entityId]),
          label: `实体 · ${entityId}`,
          binding: { target: "data", entity_id: entityId },
        },
        ...attributes.map((attribute) => ({
          id: JSON.stringify([entityId, attribute.name]),
          label: `实体属性 · ${entityId}.${attribute.name}`,
          binding: {
            target: "data",
            entity_id: entityId,
            attribute: attribute.name,
          },
        })),
      ];
    }),
    ...(step.direction === "request" ? step.data : [])
      .filter(
        (field) => field.location !== "response" && !field.conflicts?.length,
      )
      .map((field) => ({
        id: JSON.stringify(["field", field.id]),
        label: `输入字段 · ${fieldLabel(field)}`,
        binding: {
          target: "data",
          field_id: field.id,
          command_id: field.command_id,
          call_step_id: field.call_step_id,
        },
      })),
  ];
}

function applicable(
  definition: any,
  key: string,
  step: Step,
  object: MountObject,
) {
  const { target, field_id, attribute, entity_id } = object.binding;
  if (
    definition.enabled === false ||
    definition.guard === "storage_field" ||
    (definition.kind || "check") !== "check" ||
    ((definition.scope || "interaction") !== "interaction" &&
      key !== "service.base.availability")
  )
    return false;
  if (target === "data")
    return (
      ((field_id || attribute) && key.startsWith("api.data.")) ||
      (!!entity_id && key === "service.business_attribute_constraint")
    );
  const call =
    step.direction === "request" &&
    step.kind !== "action" &&
    step.sender.id !== step.receiver.id &&
    step.receiver.type === "service";
  if (key.startsWith("human."))
    return call && target === "sender" && step.sender.type === "human";
  const party = target === "sender" ? step.sender : step.receiver;
  if (
    party.type === "service" &&
    party.external &&
    party.technology === "database" &&
    (target !== "sender" || step.sender.id !== step.receiver.id) &&
    ["service.base.availability", "database.special_characters"].includes(key)
  )
    return true;
  if (target !== "receiver" || step.receiver.type !== "service") return false;
  if (key.startsWith("service_relation."))
    return call && step.sender.type === "service";
  if (key === "service.base.availability")
    return call && !!step.receiver.external;
  if (
    definition.technology &&
    step.receiver.technology !== definition.technology
  )
    return false;
  if (
    definition.group === "business" ||
    [
      "display_interaction",
      "analysis_generation",
      "release_activation",
    ].includes(definition.group)
  )
    return false;
  return (
    !key.startsWith("api.data.") &&
    key !== "service.business_attribute_constraint" &&
    (!definition.operation_kinds?.length ||
      definition.operation_kinds.some((operation: string) =>
        step.operation.kinds.includes(operation),
      ))
  );
}

export function LocateObservation({
  bundle,
  channel,
  kind,
  item,
  excludedIds,
  onClose,
  onSave,
}: {
  bundle: Bundle;
  channel: Channel;
  kind: SsdRecordKind;
  item: Observation;
  excludedIds: ReadonlySet<string>;
  onClose: () => void;
  onSave: (choice: LocationChoice) => void;
}) {
  const [mode, setMode] = useState("mount");
  const [stepId, setStepId] = useState("");
  const [objectId, setObject] = useState("");
  const [concernKey, setConcern] = useState("");
  const [selected, select] = useState("");
  const [scenarioId, setScenario] = useState("");
  const [status, setStatus] = useState<"full" | "partial">("full");
  const [condition, setCondition] = useState(item.condition || "");
  const [expected, setExpected] = useState(
    item.expected || item.original?.expected || "",
  );
  const [reason, setReason] = useState("");
  const steps = new Map(
    bundle.steps.filter((s) => !s.binding_issue).map((s) => [s.id, s]),
  );
  const step = steps.get(stepId);
  const available = (row: Observation) =>
    row.status === "active" && !excludedIds.has(row.id);
  const candidates = (["G", "E", "GT"] as const)
    .filter((ch) => ch !== channel)
    .flatMap((ch) =>
      bundle.channels[ch].concerns
        .filter((r) => {
          const owner = steps.get(r.step_id || "");
          return (
            owner &&
            available(r) &&
            r.target &&
            r.key &&
            (!r.field_id || owner.data.some((f) => f.id === r.field_id))
          );
        })
        .map((record) => ({ channel: ch, record })),
    )
    .sort(
      (a, b) =>
        Number(b.record.key === item.key) - Number(a.record.key === item.key),
    );
  const stepIds = new Set(candidates.map(({ record }) => record.step_id));
  const targets = candidates.filter(({ record }) => record.step_id === stepId);
  const identity = ({ channel, record }: LocationTarget) =>
    `${channel}:${record.id}`;
  const objects = step ? mountObjects(bundle, step) : [];
  const object = objects.find((entry) => entry.id === objectId);
  const definitions =
    step && object
      ? Object.entries(bundle.registry?.definitions || {}).filter(
          ([key, definition]) => applicable(definition, key, step, object),
        )
      : [];
  const definition = definitions.find(([key]) => key === concernKey)?.[1] as
    | { label?: string }
    | undefined;
  const target: LocationTarget | undefined =
    mode === "match"
      ? targets.find((entry) => identity(entry) === selected)
      : object && definition
        ? {
            record: {
              id: item.id,
              condition,
              status: "active",
              source_refs: item.source_refs,
              ...object.binding,
              step_id: stepId,
              key: concernKey,
              label: definition.label || concernKey,
            },
          }
        : undefined;
  const scenarios =
    target?.channel && kind !== "concerns"
      ? bundle.channels[target.channel].scenarios.filter(
          (row) =>
            available(row) &&
            row.step_id === stepId &&
            row.concern_ids?.includes(target.record.id),
        )
      : [];
  const scenario = scenarios.find((record) => record.id === scenarioId);
  const valid =
    !!target &&
    !!condition.trim() &&
    (kind === "concerns" || !!expected.trim());
  return (
    <Modal
      title="定位与挂载"
      onClose={onClose}
      canSave={valid}
      onSave={() => {
        if (valid)
          onSave({ target, scenario, status, condition, expected, reason });
      }}
    >
      <p className="ssd-notice">
        {channelLabels[channel]} · {item.condition || "待补充失败条件"}
        。应用后会跳到对应步骤，原出处随记录保留。
      </p>
      <Select
        label="挂载方式"
        value={mode}
        values={[
          ["mount", "独立挂载"],
          ["match", "匹配已有"],
        ]}
        onChange={(value) => {
          setMode(value);
          setStepId("");
          select("");
          setScenario("");
          setObject("");
          setConcern("");
        }}
      />
      <Select
        label="挂载步骤"
        value={stepId}
        values={[
          ["", "选择步骤"],
          ...bundle.steps
            .filter((s) =>
              mode === "match" ? stepIds.has(s.id) : steps.has(s.id),
            )
            .map((s): [string, string] => [
              s.id,
              `${s.order}. ${s.operation.name}`,
            ]),
        ]}
        onChange={(id) => {
          setStepId(id);
          select("");
          setScenario("");
          setObject("");
          setConcern("");
        }}
      />
      {step && mode === "mount" && (
        <>
          <Select
            label="挂载对象"
            value={objectId}
            values={[
              ["", "选择对象"],
              ...objects.map((entry): [string, string] => [
                entry.id,
                entry.label,
              ]),
            ]}
            onChange={(id) => {
              setObject(id);
              setConcern("");
            }}
          />
          {object && (
            <Select
              label="框架关注点"
              value={concernKey}
              values={[
                ["", "选择关注点"],
                ...definitions.map(([key, value]): [string, string] => [
                  key,
                  (value as { label?: string }).label || key,
                ]),
              ]}
              onChange={setConcern}
            />
          )}
          {object && !definitions.length && (
            <p className="muted">此对象暂无适用的已启用关注点。</p>
          )}
        </>
      )}
      {step && mode === "match" && (
        <Select
          label="匹配已有关注点"
          value={selected}
          values={[
            ["", "选择关注点"],
            ...targets.map((entry): [string, string] => [
              identity(entry),
              `${channelLabels[entry.channel]} · ${entry.record.label || entry.record.key} · ${describeObject(entry.record, step, bundle)} · ${entry.record.condition}`,
            ]),
          ]}
          onChange={(id) => {
            select(id);
            setScenario("");
          }}
        />
      )}
      {mode === "match" && !stepIds.size && (
        <p className="muted">
          当前用例没有其他来源已定位的关注点，可切换为独立挂载。
        </p>
      )}
      <Text
        label="失败条件"
        value={condition}
        onChange={setCondition}
        multiline
      />
      {kind !== "concerns" && (
        <>
          <Text
            label="处理预期"
            value={expected}
            onChange={setExpected}
            multiline
          />
          {target?.channel && (
            <Select
              label="匹配已有场景（可选）"
              value={scenarioId}
              values={[
                ["", "仅确认关注点对应"],
                ...scenarios.map((row): [string, string] => [
                  row.id,
                  `${row.condition} → ${row.expected || "未记录预期"}`,
                ]),
              ]}
              onChange={setScenario}
            />
          )}
          {scenario &&
            bundle.coverage_policy !== "coverage-g-obligation-v3" && (
              <Select
                label="场景匹配判定"
                value={status}
                values={[
                  ["full", "完整匹配"],
                  ["partial", "部分匹配"],
                ]}
                onChange={(value) =>
                  setStatus(value === "partial" ? "partial" : "full")
                }
              />
            )}
        </>
      )}
      <Text
        label={mode === "match" ? "匹配说明（可选）" : "挂载说明（可选）"}
        value={reason}
        onChange={setReason}
        multiline
      />
    </Modal>
  );
}
