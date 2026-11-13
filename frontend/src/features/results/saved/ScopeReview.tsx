import { useState } from "react";
import { getScopeCatalogue, saveScopeRecord } from "./api";
import type { ScopeCatalogue, ScopeUnit } from "./types";
export function ScopeReview({ project }: { project: string }) {
  const [data, setData] = useState<ScopeCatalogue | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState("");
  async function load() {
    try {
      const d = await getScopeCatalogue(project);
      setData(d);
    } catch (e) {
      setError(String(e));
    }
  }
  const record = data?.records.find((r) => r.task_key === selected);
  function edit(index: number, patch: Partial<ScopeUnit>) {
    if (!record || !data) return;
    setData({
      ...data,
      records: data.records.map((r) =>
        r === record
          ? {
              ...r,
              value: {
                units: r.value.units.map((u, i) =>
                  i === index ? { ...u, ...patch } : u,
                ),
              },
            }
          : r,
      ),
    });
  }
  async function save() {
    if (!record) return;
    try {
      const result = await saveScopeRecord(project, record);
      setMessage(
        `已保存；${result.affected_nodes.length} 个节点受影响，未自动调用模型。请预览影响后定向重跑。`,
      );
      await load();
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <details
      className="management-notice"
      onToggle={(e) => {
        if (e.currentTarget.open && !data) void load();
      }}
    >
      <summary>审核异常的交互／全局归属（保存后手动重跑）</summary>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <select
        aria-label="来源及用例"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        <option value="">选择来源与用例</option>
        {data?.records.map((r) => (
          <option key={r.task_key} value={r.task_key}>
            {r.task_key}
            {r.pending_rerun ? " · 待重跑" : ""}
          </option>
        ))}
      </select>
      {record?.value.units.map((u, i) => (
        <fieldset key={`${u.source_id}-${i}`}>
          <legend>{u.source_id}</legend>
          <p>{u.trigger}</p>
          <label>
            分析粒度{" "}
            <select
              value={u.scope}
              onChange={(e) =>
                edit(i, {
                  scope: e.target.value,
                  global_kind:
                    e.target.value === "global" ? "idempotency" : null,
                })
              }
            >
              <option value="interaction">交互级</option>
              <option value="global">全局级</option>
              <option value="pending">待确认</option>
            </select>
          </label>
          {u.scope === "global" && (
            <>
              <label>
                全局类别{" "}
                <select
                  value={u.global_kind || ""}
                  onChange={(e) => edit(i, { global_kind: e.target.value })}
                >
                  {[
                    ["idempotency", "幂等性"],
                    ["sequence", "调用顺序"],
                    ["dependency_consistency", "依赖一致性"],
                    ["cascade", "级联操作"],
                  ].map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                业务实体（依赖角色顺序）{" "}
                <input
                  value={u.entity_ids.join(",")}
                  list="scope-entities"
                  onChange={(e) =>
                    edit(i, {
                      entity_ids: e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </label>
              <label>
                关联用例（前置→后续顺序）{" "}
                <input
                  value={u.related_cases.join(",")}
                  list="scope-cases"
                  onChange={(e) =>
                    edit(i, {
                      related_cases: e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </label>
            </>
          )}
          <label>
            审核依据{" "}
            <textarea
              value={u.reason}
              onChange={(e) => edit(i, { reason: e.target.value })}
            />
          </label>
        </fieldset>
      ))}
      <datalist id="scope-entities">
        {data?.entities.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name}
          </option>
        ))}
      </datalist>
      <datalist id="scope-cases">
        {data?.cases.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </datalist>
      {record && <button onClick={() => void save()}>保存归属判定</button>}
    </details>
  );
}
