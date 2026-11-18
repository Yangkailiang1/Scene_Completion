import { lazy, Suspense, useState } from "react";
import { documentChoices, documentLines } from "../shared/provenance";
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
  type SourceDocument,
  type SourceRef,
  type Step,
} from "./types";
const MarkdownSource = lazy(() =>
  import("../../sources/MarkdownSource").then((module) => ({
    default: module.MarkdownSource,
  })),
);

const list = (s: string) =>
  s
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean);
export function Text({
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
export function Select({
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
export function Modal({
  title,
  children,
  onClose,
  onSave,
  canSave = true,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  onSave: () => void;
  canSave?: boolean;
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
          <button
            className="primary-action"
            disabled={!canSave}
            onClick={onSave}
          >
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
export function SourceRefsEditor({
  documents,
  value,
  onChange,
}: {
  documents: SourceDocument[];
  value: SourceRef[];
  onChange: (refs: SourceRef[]) => void;
}) {
  const choices = documentChoices(documents);
  const [draft, set] = useState({
    document_id: "",
    start_line: "",
    end_line: "",
    quote: "",
  });
  const patch = (v: Partial<typeof draft>) => set({ ...draft, ...v });
  const lines = documentLines(documents, draft.document_id);
  const start = Number(draft.start_line) || 0;
  const end = Number(draft.end_line) || start;
  const position = (n: number) =>
    Number.isInteger(n) && n >= 1 && n <= lines.length
      ? n
      : Math.min(Math.max(1, n || 1), Math.max(1, lines.length));
  const valid =
    !!draft.document_id &&
    !!lines.length &&
    Number.isInteger(start) &&
    start >= 1 &&
    start <= lines.length &&
    Number.isInteger(end) &&
    end >= start &&
    end - start <= 1000;
  const invalidReason = () => {
    if (!draft.document_id) return "请选择来源文件。";
    if (!lines.length) return "该文档没有可引用的行。";
    if (!Number.isInteger(start) || start < 1 || start > lines.length)
      return `起始行需在 1–${lines.length} 之间。`;
    if (!Number.isInteger(end) || end < start) return "结束行不能小于起始行。";
    if (end - start > 1000) return "单条出处最多引用 1001 行，请分段补录。";
    return "";
  };
  const name = (id: string) =>
    choices.find((c) => c.id === id)?.name || id || "未指定文档";
  const add = () => {
    if (!valid) return;
    const quote =
      draft.quote.trim() ||
      lines
        .filter((r) => r.number >= start && r.number <= end)
        .map((r) => r.text)
        .join("\n")
        .trim();
    const next: SourceRef = {
      document_id: draft.document_id,
      start_line: start,
      end_line: end,
      quote,
      kind: "origin",
      origin: "manual",
    };
    onChange([
      ...value.filter(
        (r) => !(r.document_id === next.document_id && r.start_line === start),
      ),
      next,
    ]);
    patch({ start_line: "", end_line: "", quote: "" });
  };
  return (
    <fieldset className="ssd-source-editor">
      <legend>来源（原文出处）</legend>
      {value.length ? (
        <ul className="ssd-source-current">
          {value.map((r, n) => (
            <li key={`${r.document_id}-${r.start_line}-${n}`}>
              <div>
                <code>{name(r.document_id)}</code>
                <span>
                  第 {r.start_line}–{r.end_line} 行
                </span>
                {r.quote && <small>{r.quote}</small>}
                {r.json_pointer && <small>{r.json_pointer}</small>}
              </div>
              <button
                aria-label={`移除出处 ${n + 1}`}
                onClick={() => onChange(value.filter((_, k) => k !== n))}
              >
                移除
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted ssd-source-empty">
          尚未补录出处；保存后该记录的「查看原始出处」为
          0，无法跳转到原文。填写下方文件与行号即可追溯。
        </p>
      )}
      <Select
        label="来源文件"
        value={draft.document_id}
        values={[
          ["", choices.length ? "选择来源文件" : "本用例没有可引用的文档"],
          ...choices.map(
            (d) => [d.id, `${d.roleLabel} · ${d.name}`] as [string, string],
          ),
        ]}
        onChange={(document_id) =>
          patch({ document_id, start_line: "", end_line: "" })
        }
      />
      {draft.document_id && (
        <>
          <div className="ssd-form-columns">
            <Text
              label="起始行"
              value={draft.start_line}
              onChange={(v) => patch({ start_line: v.replace(/[^0-9]/g, "") })}
            />
            <Text
              label="结束行"
              value={draft.end_line}
              onChange={(v) => patch({ end_line: v.replace(/[^0-9]/g, "") })}
            />
          </div>
          <small className="muted ssd-source-hint">
            文档共 {lines.length} 行；留空结束行表示只引用起始行。
          </small>
          {valid && (
            <>
              <p className="ssd-source-location" aria-live="polite">
                预览：{name(draft.document_id)} · 第 {start}–{end} 行
              </p>
              <div className="ssd-source-preview" aria-label="来源预览">
                {/\.(md|markdown)$/i.test(name(draft.document_id)) ? (
                  <Suspense fallback={<p>正在渲染原文预览…</p>}>
                    <MarkdownSource
                      lines={lines}
                      highlightStart={start}
                      highlightEnd={end}
                      jump={{ line: start, revision: 0 }}
                      outlineOpen={false}
                      onOutline={() => undefined}
                      onNavigate={() => undefined}
                    />
                  </Suspense>
                ) : (
                  <div className="ssd-source-code">
                    {lines
                      .slice(
                        Math.max(0, position(start) - 5),
                        Math.min(lines.length, position(end) + 4),
                      )
                      .map((r) => (
                        <div
                          key={r.number}
                          className={
                            r.number >= start && r.number <= end
                              ? "source-line highlighted"
                              : "source-line"
                          }
                        >
                          <span>{r.number}</span>
                          <code>{r.text}</code>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </>
          )}
          <Text
            label="引文（留空则取上方所选行原文）"
            value={draft.quote}
            onChange={(quote) => patch({ quote })}
            multiline
          />
          <button className="ssd-source-add" disabled={!valid} onClick={add}>
            添加出处
          </button>
          {!valid && <small className="muted">{invalidReason()}</small>}
        </>
      )}
      <p className="muted">
        只能引用本用例快照内的文档，行号按该文件自身行号（从 1 开始）计算。
        <code>.md</code>
        按渲染阅读，<code>.json</code> 等按源码行查看。
      </p>
    </fieldset>
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
  bundle: Pick<Bundle, "steps" | "channels" | "documents"> & Partial<Bundle>;
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
  const definitions =
    bundle.registry?.definitions ||
    Object.fromEntries(
      Object.values(bundle.channels)
        .flatMap((data) => [...data.concerns, ...data.scenarios])
        .filter((row) => row.key)
        .map((row) => [
          row.key!,
          { label: row.label || row.key, kind: "check", scope: "interaction" },
        ]),
    );
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
      <Select
        label="关注点标识"
        value={value.key}
        values={[
          ["", "选择框架关注点"],
          ...Object.entries(definitions)
            .filter(
              ([, d]: any) =>
                (d.kind || "check") === "check" &&
                d.enabled !== false &&
                (d.scope || "interaction") === "interaction",
            )
            .map(
              ([key, d]: any) =>
                [key, `${d.label} · ${key}`] as [string, string],
            ),
        ]}
        onChange={(key) =>
          set({
            ...value,
            key,
            label: bundle.registry?.definitions?.[key]?.label || key,
          })
        }
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
      {kind === "scenarios" && (
        <Text
          label="具体场景说明"
          value={value.analysis}
          onChange={(analysis) => set({ ...value, analysis })}
          multiline
        />
      )}
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
      <SourceRefsEditor
        documents={bundle.documents || []}
        value={value.source_refs || []}
        onChange={(source_refs) => set({ ...value, source_refs })}
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
  bundle: Pick<Bundle, "channels">;
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
      canSave={!!value.left_id && !!value.right_id}
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
