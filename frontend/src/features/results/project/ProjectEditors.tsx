import { useState } from "react";
import { Modal, Select, Text } from "../ssd/SsdEditors";
import {
  channelLabels,
  copy,
  type Channel,
  type Observation,
} from "../ssd/types";
import { anchorName, type Anchor, type ProjectBundle } from "./types";
const list = (value: string) =>
  value
    .split(/[,，]/)
    .map((part) => part.trim())
    .filter(Boolean);
export function AnchorEditor({
  anchor,
  bundle,
  onClose,
  onSave,
}: {
  anchor: Anchor;
  bundle: ProjectBundle;
  onClose: () => void;
  onSave: (anchor: Anchor) => void;
}) {
  const [value, set] = useState(copy(anchor));
  const dependency = value.kind === "dependency";
  return (
    <Modal
      title={dependency ? "编辑业务依赖关系" : "编辑架构外部服务"}
      onClose={onClose}
      onSave={() => onSave(value)}
    >
      <p className="muted">
        稳定标识：{value.id}。已有出处保留；修改后保存修订并重新计算相关结果。
      </p>
      {dependency ? (
        <>
          {(["from_case_id", "to_case_id"] as const).map((field) =>
            bundle.cases?.length ? (
              <Select
                key={field}
                label={field === "from_case_id" ? "上游用例" : "下游用例"}
                value={value[field]}
                values={[
                  ["", "选择用例"],
                  ...bundle.cases.map(
                    (item) =>
                      [item.id, `${item.id} · ${item.name || item.id}`] as [
                        string,
                        string,
                      ],
                  ),
                ]}
                onChange={(id) => set({ ...value, [field]: id })}
              />
            ) : (
              <Text
                key={field}
                label={field === "from_case_id" ? "上游用例" : "下游用例"}
                value={value[field]}
                onChange={(id) => set({ ...value, [field]: id })}
              />
            ),
          )}
          <Select
            label="依赖类型"
            value={value.relation_type}
            values={[
              ["direct", "直接依赖"],
              ["cascade", "级联依赖"],
            ]}
            onChange={(relation_type) =>
              set({
                ...value,
                relation_type: relation_type as Anchor["relation_type"],
              })
            }
          />
          <Text
            label="关系成立条件"
            value={value.condition}
            multiline
            onChange={(condition) => set({ ...value, condition })}
          />
          <Text
            label="依赖义务与业务语义"
            value={value.obligation}
            multiline
            onChange={(obligation) => set({ ...value, obligation })}
          />
          <Text
            label="相关实体（逗号分隔）"
            value={(value.entity_ids || []).join(",")}
            onChange={(ids) => set({ ...value, entity_ids: list(ids) })}
          />
        </>
      ) : (
        <>
          <Text
            label="外部服务名称"
            value={value.name}
            onChange={(name) => set({ ...value, name })}
          />
          <Text
            label="服务职责与身份说明"
            value={value.description}
            multiline
            onChange={(description) => set({ ...value, description })}
          />
          <Text
            label="技术类型"
            value={value.technology}
            onChange={(technology) => set({ ...value, technology })}
          />
          <Text
            label="关联 API（逗号分隔）"
            value={(value.api_ids || []).join(",")}
            onChange={(ids) => set({ ...value, api_ids: list(ids) })}
          />
          <Text
            label="涉及用例（逗号分隔）"
            value={(value.case_ids || []).join(",")}
            onChange={(ids) => set({ ...value, case_ids: list(ids) })}
          />
          <p>
            同一外部服务按稳定身份统计一次，调用次数与调用步骤保留为上下文。
          </p>
        </>
      )}
      <Select
        label="对象确认状态"
        value={value.status || "active"}
        values={[
          ["active", "已确认"],
          ["pending", "待确认"],
        ]}
        onChange={(status) => set({ ...value, status })}
      />
    </Modal>
  );
}
export function ProjectObservationEditor({
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
  bundle: ProjectBundle;
  onClose: () => void;
  onSave: (item: Observation) => void;
}) {
  const [value, set] = useState(copy(item));
  const definitions = bundle.registry?.definitions || {};
  return (
    <Modal
      title={`编辑${channelLabels[channel]}${kind === "concerns" ? "关注点" : kind === "scenarios" ? "场景" : "待确认项"}`}
      onClose={onClose}
      onSave={() => onSave(value)}
    >
      <Select
        label="挂载对象"
        value={value.anchor_id || ""}
        values={[
          ["", "待重新挂载"],
          ...bundle.anchors.map(
            (anchor) => [anchor.id, anchorName(anchor)] as [string, string],
          ),
        ]}
        onChange={(anchor_id) =>
          set({
            ...value,
            anchor_id,
            target:
              bundle.scope.id === "business_chain" ? "dependency" : "service",
          })
        }
      />
      <Select
        label="关注点"
        value={value.key}
        values={[
          ["", "选择关注点"],
          ...Object.entries(definitions)
            .filter(
              ([, definition]: any) =>
                !definition.scope || definition.scope === bundle.scope.id,
            )
            .map(
              ([key, definition]: any) =>
                [key, `${definition.label} · ${key}`] as [string, string],
            ),
        ]}
        onChange={(key) =>
          set({ ...value, key, label: definitions[key]?.label || key })
        }
      />
      <Text
        label="记录名称"
        value={value.label}
        onChange={(label) => set({ ...value, label })}
      />
      <Text
        label="失败条件"
        value={value.condition}
        multiline
        onChange={(condition) => set({ ...value, condition })}
      />
      {kind !== "concerns" && (
        <>
          <Text
            label="具体场景说明"
            value={value.analysis}
            multiline
            onChange={(analysis) => set({ ...value, analysis })}
          />
          <Text
            label="预期结果"
            value={value.expected}
            multiline
            onChange={(expected) => set({ ...value, expected })}
          />
        </>
      )}
      <Text
        label="业务实体"
        value={value.entity_id}
        onChange={(entity_id) =>
          set({ ...value, entity_id: entity_id || null })
        }
      />
      <Select
        label="记录状态"
        value={value.status}
        values={[
          ["active", kind === "pending" ? "确认异常" : "已确认"],
          ["pending", "待确认"],
          ["unbound", "待重新挂载"],
        ]}
        onChange={(status) => set({ ...value, status })}
      />
      {kind === "scenarios" && (
        <fieldset>
          <legend>关联关注点</legend>
          {bundle.channels[channel].concerns
            .filter((concern) => concern.anchor_id === value.anchor_id)
            .map((concern) => (
              <label className="ssd-check" key={concern.id}>
                <input
                  type="checkbox"
                  checked={(value.concern_ids || []).includes(concern.id)}
                  onChange={(event) =>
                    set({
                      ...value,
                      concern_ids: event.target.checked
                        ? [...(value.concern_ids || []), concern.id]
                        : (value.concern_ids || []).filter(
                            (id) => id !== concern.id,
                          ),
                    })
                  }
                />
                {concern.label || concern.key} · {concern.condition}
              </label>
            ))}
        </fieldset>
      )}
      {kind === "pending" && (
        <p>
          确认异常时请填写挂载对象、关注点、失败条件和预期结果；保存后重新计分。不是异常可在列表中移除。
        </p>
      )}
    </Modal>
  );
}
