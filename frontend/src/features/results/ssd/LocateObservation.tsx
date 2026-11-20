import { useState } from "react";
import { putDecision } from "../shared/matchDraft";
import { putTableRecord } from "../shared/tableEditing";
import { Modal, Select, Text } from "./SsdEditors";
import type { SsdRecordKind } from "./SsdAlignmentTable";
import { channelLabels, targetLabels, uid } from "./types";
import type { Bundle, Channel, Observation, Step } from "./types";

type LocationTarget = { channel: Channel; record: Observation };
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
  if (field) return [field.location, field.name].filter(Boolean).join(".");
  if (record.entity_id)
    return [record.entity_id, record.attribute].filter(Boolean).join(".");
  if (record.target === "sender") return step.sender.name;
  if (record.target === "receiver") return step.receiver.name;
  return targetLabels[record.target || ""] || "未指定对象";
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
  const [stepId, setStepId] = useState("");
  const [selected, select] = useState("");
  const [scenarioId, setScenario] = useState("");
  const [status, setStatus] = useState<"full" | "partial">("full");
  const [condition, setCondition] = useState(item.condition || "");
  const [expected, setExpected] = useState(item.expected || "");
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
  const target = targets.find((entry) => identity(entry) === selected);
  const scenarios =
    target && kind !== "concerns"
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
      title="定位并匹配已有关注点"
      onClose={onClose}
      canSave={valid}
      onSave={() => {
        if (valid)
          onSave({ target, scenario, status, condition, expected, reason });
      }}
    >
      <p className="ssd-notice">
        {channelLabels[channel]} · {item.condition || "待补充失败条件"}
        。选择当前用例的已有关注点，应用后会跳到对应步骤，原出处随记录保留。
      </p>
      <Select
        label="定位到已有步骤"
        value={stepId}
        values={[
          ["", "选择步骤"],
          ...bundle.steps
            .filter((s) => stepIds.has(s.id))
            .map((s): [string, string] => [
              s.id,
              `${s.order}. ${s.operation.name}`,
            ]),
        ]}
        onChange={(id) => {
          setStepId(id);
          select("");
          setScenario("");
        }}
      />
      {step && (
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
      {!stepIds.size && (
        <p className="muted">
          当前用例没有其他来源已定位的关注点，可用原编辑入口指定挂载步骤和对象。
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
          {target && (
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
          {scenario && (
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
        label="匹配说明（可选）"
        value={reason}
        onChange={setReason}
        multiline
      />
    </Modal>
  );
}
