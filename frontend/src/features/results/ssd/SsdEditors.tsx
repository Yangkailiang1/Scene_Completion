import { useState } from "react";
import {
  channelLabels,
  copy,
  targetLabels,
  uid,
  type Bundle,
  type Channel,
  type Decision,
  type Observation,
  type Party,
  type Step,
} from "./types";

const list = (s: string) =>
  s
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean);
function Text({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value?: string | null;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <label>
      {label}
      {multiline ? (
        <textarea
          aria-label={label}
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          aria-label={label}
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </label>
  );
}
function Select({
  label,
  value,
  values,
  onChange,
}: {
  label: string;
  value?: string;
  values: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select
        aria-label={label}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      >
        {values.map(([id, name]) => (
          <option key={id} value={id}>
            {name}
          </option>
        ))}
      </select>
    </label>
  );
}
function Modal({
  title,
  children,
  onClose,
  onSave,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  onSave: () => void;
}) {
  return (
    <div className="ssd-modal-backdrop">
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="ssd-modal"
      >
        <header>
          <h3>{title}</h3>
          <button onClick={onClose}>取消编辑</button>
        </header>
        <div className="ssd-form">{children}</div>
        <footer>
          <button onClick={onClose}>取消</button>
          <button className="primary-action" onClick={onSave}>
            应用到草稿
          </button>
        </footer>
      </section>
    </div>
  );
}
function PartyEditor({
  side,
  value,
  onChange,
  parties,
}: {
  side: string;
  value: Party;
  onChange: (value: Party) => void;
  parties: Party[];
}) {
  return (
    <fieldset>
      <legend>{side}</legend>
      <Select
        label={`${side}已有参与者`}
        value={parties.some((p) => p.id === value.id) ? value.id : ""}
        values={[
          ["", "自定义参与者"],
          ...parties.map((p) => [p.id, p.name] as [string, string]),
        ]}
        onChange={(id) => {
          const party = parties.find((p) => p.id === id);
          onChange(party ? copy(party) : { ...value, id: uid("party") });
        }}
      />
      <Text
        label={`${side}名称`}
        value={value.name}
        onChange={(name) => onChange({ ...value, name })}
      />
      <Select
        label={`${side}类型`}
        value={value.type}
        values={[
          ["human", "人类 Actor"],
          ["service", "服务"],
        ]}
        onChange={(type) => onChange({ ...value, type })}
      />
      <Text
        label={`${side}技术类型`}
        value={value.technology}
        onChange={(technology) => onChange({ ...value, technology })}
      />
      <label className="ssd-check">
        <input
          type="checkbox"
          checked={!!value.external}
          onChange={(e) => onChange({ ...value, external: e.target.checked })}
        />
        {side}为外部服务
      </label>
    </fieldset>
  );
}
export function StepEditor({
  step,
  steps,
  onClose,
  onSave,
}: {
  step: Step;
  steps: Step[];
  onClose: () => void;
  onSave: (value: Step) => void;
}) {
  const [value, set] = useState(copy(step));
  const parties = [
    ...new Map(
      steps.flatMap((s) => [s.sender, s.receiver]).map((p) => [p.id, p]),
    ).values(),
  ];
  const field = (id: string, patch: any) =>
    set({
      ...value,
      data: value.data.map((f) => (f.id === id ? { ...f, ...patch } : f)),
    });
  return (
    <Modal title="编辑 SSD 步骤" onClose={onClose} onSave={() => onSave(value)}>
      <Text
        label="交互操作"
        value={value.operation.name}
        onChange={(name) =>
          set({ ...value, operation: { ...value.operation, name } })
        }
        multiline
      />
      <Select
        label="步骤类型"
        value={value.kind}
        values={[
          ["interaction", "请求或返回"],
          ["action", "本地处理"],
        ]}
        onChange={(kind) =>
          set({
            ...value,
            kind,
            ...(kind === "action"
              ? {
                  receiver: copy(value.sender),
                  direction: "request",
                  parent_id: null,
                  api_id: null,
                }
              : {}),
          })
        }
      />
      <Select
        label="来源层级"
        value={value.layer}
        values={[
          ["RR", "RR"],
          ["SR", "SR"],
        ]}
        onChange={(layer) => set({ ...value, layer })}
      />
      {value.kind !== "action" && (
        <>
          <Select
            label="交互方向"
            value={value.direction}
            values={[
              ["request", "请求"],
              ["return", "返回"],
            ]}
            onChange={(direction) =>
              set({ ...value, direction, parent_id: null })
            }
          />
          {value.direction === "return" && (
            <Select
              label="对应请求"
              value={value.parent_id || ""}
              values={[
                ["", "选择对应请求"],
                ...steps
                  .filter(
                    (s) =>
                      s.id !== value.id &&
                      s.direction === "request" &&
                      s.kind !== "action",
                  )
                  .map(
                    (s) =>
                      [s.id, `${s.order}. ${s.operation.name}`] as [
                        string,
                        string,
                      ],
                  ),
              ]}
              onChange={(parent_id) =>
                set({ ...value, parent_id: parent_id || null })
              }
            />
          )}
        </>
      )}
      <div className="ssd-form-columns">
        <PartyEditor
          side="发送方"
          parties={parties}
          value={value.sender}
          onChange={(sender) =>
            set({
              ...value,
              sender,
              ...(value.kind === "action" ? { receiver: copy(sender) } : {}),
            })
          }
        />
        {value.kind !== "action" && (
          <PartyEditor
            side="接收方"
            parties={parties}
            value={value.receiver}
            onChange={(receiver) => set({ ...value, receiver })}
          />
        )}
      </div>
      {value.kind === "action" && (
        <fieldset>
          <legend>本地检查对应报文</legend>
          {steps
            .filter(
              (s) =>
                s.id !== value.id &&
                s.order < value.order &&
                s.kind !== "action",
            )
            .map((s) => (
              <label className="ssd-check" key={s.id}>
                <input
                  type="checkbox"
                  checked={(value.validates || []).includes(s.id)}
                  onChange={(e) =>
                    set({
                      ...value,
                      validates: e.target.checked
                        ? [...(value.validates || []), s.id]
                        : (value.validates || []).filter(
                            (id: string) => id !== s.id,
                          ),
                    })
                  }
                />
                {s.order}. {s.operation.name}
              </label>
            ))}
        </fieldset>
      )}
      <Text
        label="接口 API"
        value={value.api_id}
        onChange={(api_id) => set({ ...value, api_id: api_id || null })}
      />
      <Text
        label="业务实体（逗号分隔）"
        value={value.entity_ids.join(",")}
        onChange={(v) => set({ ...value, entity_ids: list(v) })}
      />
      <Text
        label="实际操作（read/create/update/delete，逗号分隔）"
        value={value.operation.kinds.join(",")}
        onChange={(v) =>
          set({ ...value, operation: { ...value.operation, kinds: list(v) } })
        }
      />
      <h4>交互数据</h4>
      {value.data.map((f, n) => (
        <fieldset key={f.id}>
          <legend>字段 {n + 1}</legend>
          <div className="ssd-form-columns">
            <Text
              label={`字段 ${n + 1} 名称`}
              value={f.name}
              onChange={(name) => field(f.id, { name })}
            />
            <Select
              label={`字段 ${n + 1} 位置`}
              value={f.location}
              values={[
                "header",
                "path",
                "query",
                "body",
                "response",
                "business",
              ].map((v) => [v, v])}
              onChange={(location) => field(f.id, { location })}
            />
            <Text
              label={`字段 ${n + 1} 类型`}
              value={f.type}
              onChange={(type) => field(f.id, { type })}
            />
            <Select
              label={`字段 ${n + 1} 必填`}
              value={f.required == null ? "unknown" : String(f.required)}
              values={[
                ["unknown", "未定义"],
                ["true", "必填"],
                ["false", "可选"],
              ]}
              onChange={(v) =>
                field(f.id, { required: v === "unknown" ? null : v === "true" })
              }
            />
          </div>
          {(f.constraints || []).map((c, j) => (
            <div className="ssd-form-columns" key={j}>
              <Text
                label={`字段 ${n + 1} 约束 ${j + 1} 类型`}
                value={c.kind}
                onChange={(kind) =>
                  field(f.id, {
                    constraints: f.constraints.map((x, k) =>
                      k === j ? { ...x, kind } : x,
                    ),
                  })
                }
              />
              <Text
                label={`字段 ${n + 1} 约束 ${j + 1} 值`}
                value={
                  typeof c.value === "string"
                    ? c.value
                    : JSON.stringify(c.value)
                }
                onChange={(text) => {
                  let v: any = text;
                  try {
                    v = JSON.parse(text);
                  } catch {
                    /* A plain-text constraint stays text. */
                  }
                  field(f.id, {
                    constraints: f.constraints.map((x, k) =>
                      k === j ? { ...x, value: v } : x,
                    ),
                  });
                }}
              />
              <button
                onClick={() =>
                  field(f.id, {
                    constraints: f.constraints.filter((_, k) => k !== j),
                  })
                }
              >
                删除约束 {j + 1}
              </button>
            </div>
          ))}
          <button
            onClick={() =>
              field(f.id, {
                constraints: [
                  ...(f.constraints || []),
                  { kind: "type", value: "" },
                ],
              })
            }
          >
            添加字段 {n + 1} 约束
          </button>
          <button
            onClick={() =>
              set({ ...value, data: value.data.filter((x) => x.id !== f.id) })
            }
          >
            删除字段 {n + 1}
          </button>
        </fieldset>
      ))}
      <button
        onClick={() =>
          set({
            ...value,
            data: [
              ...value.data,
              {
                id: uid("field"),
                name: "",
                location: value.direction === "return" ? "response" : "body",
                constraints: [],
                source_refs: [],
              },
            ],
          })
        }
      >
        添加数据字段
      </button>
      <p className="muted">
        步骤身份保持不变。删除字段或改变对象后，无法保留的关联将在保存时转为待重新挂载。
      </p>
    </Modal>
  );
}
export function ObservationEditor({
  item,
  channel,
  kind,
  bundle,
  onClose,
  onSave,
}: {
  item: Observation;
  channel: Channel;
  kind: "concerns" | "scenarios" | "pending";
  bundle: Bundle;
  onClose: () => void;
  onSave: (
    value: Observation,
    destination: "concerns" | "scenarios" | "pending",
  ) => void;
}) {
  const [value, set] = useState<Observation>({
    target: "receiver",
    key: "",
    step_id: "",
    ...copy(item),
  });
  const destination = kind;
  const step = bundle.steps.find((s) => s.id === value.step_id);
  const concerns = bundle.channels[channel].concerns;
  return (
    <Modal
      title={`编辑${channelLabels[channel]}${kind === "concerns" ? "关注点" : kind === "pending" ? "待确认项" : "场景"}`}
      onClose={onClose}
      onSave={() => onSave(value, destination)}
    >
      {kind === "pending" && (
        <p className="ssd-notice">
          确认异常时，请填写步骤、对象、关注点、失败条件和预期结果；保存后同时建立关注点与场景。数据类关注点还需选择具体字段。不属于异常的记录可返回表格选择“不是异常”。
        </p>
      )}
      <Select
        label="挂载步骤"
        value={value.step_id || ""}
        values={[
          ["", "待重新挂载"],
          ...bundle.steps.map(
            (s) =>
              [s.id, `${s.order}. ${s.operation.name}`] as [string, string],
          ),
        ]}
        onChange={(step_id) => set({ ...value, step_id, field_id: null })}
      />
      <Select
        label="挂载对象"
        value={value.target || "receiver"}
        values={Object.entries(targetLabels)}
        onChange={(target) => set({ ...value, target, field_id: null })}
      />
      {value.target === "data" && (
        <Select
          label="挂载字段"
          value={value.field_id || ""}
          values={[
            ["", "选择字段"],
            ...(step?.data || []).map(
              (f) => [f.id, `${f.location}.${f.name}`] as [string, string],
            ),
          ]}
          onChange={(field_id) => set({ ...value, field_id: field_id || null })}
        />
      )}
      <Text
        label="关注点标识"
        value={value.key}
        onChange={(key) => set({ ...value, key })}
      />
      <Text
        label="关注点名称"
        value={value.label}
        onChange={(label) => set({ ...value, label })}
      />
      <Text
        label="业务实体"
        value={value.entity_id}
        onChange={(entity_id) =>
          set({ ...value, entity_id: entity_id || null })
        }
      />
      <Text
        label="条件或描述"
        value={value.condition}
        onChange={(condition) => set({ ...value, condition })}
        multiline
      />
      {(destination === "scenarios" || kind === "pending") && (
        <>
          <Text
            label="预期结果"
            value={value.expected}
            onChange={(expected) => set({ ...value, expected })}
            multiline
          />
          {kind !== "pending" && (
            <fieldset>
              <legend>关联关注点</legend>
              {concerns.map((c) => (
                <label className="ssd-check" key={c.id}>
                  <input
                    type="checkbox"
                    checked={value.concern_ids?.includes(c.id) || false}
                    onChange={(e) =>
                      set({
                        ...value,
                        concern_ids: e.target.checked
                          ? [...(value.concern_ids || []), c.id]
                          : (value.concern_ids || []).filter(
                              (id) => id !== c.id,
                            ),
                      })
                    }
                  />
                  {c.label || c.key} · {c.condition}
                </label>
              ))}
              {!concerns.length && <p>先添加本通道的关注点，再关联场景。</p>}
            </fieldset>
          )}
        </>
      )}
      <Select
        label={kind === "pending" ? "异常判定" : "计分状态"}
        value={value.status}
        values={
          kind === "pending"
            ? [
                ["pending", "保留待确认"],
                ["active", "确认异常：同时建立关注点与场景"],
              ]
            : [
                ["active", "已确认，参与计分"],
                ["pending", "待确认，暂不计分"],
                ["unbound", "待重新挂载，暂不计分"],
              ]
        }
        onChange={(status) => set({ ...value, status })}
      />
      <p className="muted">保留原始出处，修订记录在保存后单独留存。</p>
    </Modal>
  );
}
export function MatchEditor({
  bundle,
  decision,
  onClose,
  onSave,
}: {
  bundle: Bundle;
  decision?: Decision;
  onClose: () => void;
  onSave: (value: Decision) => void;
}) {
  const [value, set] = useState<Decision>(
    decision
      ? copy(decision)
      : {
          id: uid("match"),
          level: "scenario",
          pair: "G_E",
          left_id: "",
          right_id: "",
          status: "full",
          reason: "人工确认",
          origin: "manual",
        },
  );
  const [left, right] = value.pair.split("_") as [Channel, Channel];
  const field = value.level === "concern" ? "concerns" : "scenarios";
  const options = (ch: Channel): [string, string][] => [
    ["", "选择记录"],
    ...bundle.channels[ch][field].map(
      (o) => [o.id, `${o.label || o.key} · ${o.condition}`] as [string, string],
    ),
  ];
  return (
    <Modal
      title="修正匹配关系"
      onClose={onClose}
      onSave={() => onSave({ ...value, origin: "manual" })}
    >
      <Select
        label="匹配粒度"
        value={value.level}
        values={[
          ["concern", "关注点"],
          ["scenario", "场景"],
        ]}
        onChange={(level) =>
          set({ ...value, level, left_id: "", right_id: "" })
        }
      />
      <Select
        label="匹配来源"
        value={value.pair}
        values={[
          ["G_E", "方法生成 ↔ 原文抽取"],
          ["GT_G", "测试逆向 ↔ 方法生成"],
          ["GT_E", "测试逆向 ↔ 原文抽取"],
        ]}
        onChange={(pair) => set({ ...value, pair, left_id: "", right_id: "" })}
      />
      <Select
        label={`${channelLabels[left]}记录`}
        value={value.left_id}
        values={options(left)}
        onChange={(left_id) => set({ ...value, left_id })}
      />
      <Select
        label={`${channelLabels[right]}记录`}
        value={value.right_id}
        values={options(right)}
        onChange={(right_id) => set({ ...value, right_id })}
      />
      <Select
        label="匹配判定"
        value={value.status}
        values={[
          ["full", "完整匹配"],
          ["partial", "部分匹配"],
          ["none", "不匹配"],
        ]}
        onChange={(status) => set({ ...value, status })}
      />
      <Text
        label="匹配说明"
        value={value.reason}
        onChange={(reason) => set({ ...value, reason })}
        multiline
      />
    </Modal>
  );
}
