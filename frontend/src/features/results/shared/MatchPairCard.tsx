import type { Decision } from "../ssd/types";
import { channelLabels } from "../ssd/types";
import { decisionKey, decisionLabel, findDecision } from "./matchDraft";

export function MatchPairCard({
  pair,
  bundle,
  changed,
  title,
  readonly,
  onToggle,
  onDetails,
}: {
  pair: Decision;
  bundle: any;
  changed: boolean;
  title?: string;
  readonly: boolean;
  onToggle: (pair: Decision) => void;
  onDetails: (pair: Decision) => void;
}) {
  const current = findDecision(bundle, pair);
  const [left, right] = pair.pair.split("_") as (keyof typeof channelLabels)[];
  const field = pair.level === "concern" ? "concerns" : "scenarios";
  const a = bundle.channels[left]?.[field].find(
    (r: any) => r.id === pair.left_id,
  );
  const b = bundle.channels[right]?.[field].find(
    (r: any) => r.id === pair.right_id,
  );
  const valid = a?.status === "active" && b?.status === "active";
  return (
    <article
      className={"ssd-match ssd-pair-card" + (changed ? " ssd-pair-draft" : "")}
      data-pair-key={decisionKey(pair)}
      aria-label={
        "配对 " + pair.pair + " " + pair.left_id + " " + pair.right_id
      }
    >
      {title && <strong>{title}</strong>}
      <p>
        {channelLabels[left]}：{a?.condition || pair.left_id}
      </p>
      {a?.expected && <small>预期：{a.expected}</small>}
      <p>
        {channelLabels[right]}：{b?.condition || pair.right_id}
      </p>
      {b?.expected && <small>预期：{b.expected}</small>}
      <p className="ssd-pair-status" role="status">
        {decisionLabel(current?.status)}
        {changed ? " · 未保存" : current ? " · 已保存" : ""}
      </p>
      {current?.reason && <p className="ssd-pair-reason">{current.reason}</p>}
      {!valid && (
        <p className="muted">记录已变更或待重新挂载，请在详情核对。</p>
      )}
      {!readonly && (
        <div className="ssd-inline-actions">
          <button
            disabled={!valid}
            aria-pressed={changed && current?.status !== "none"}
            onClick={() => onToggle(pair)}
          >
            {changed
              ? current?.status === "none"
                ? "取消本次判定"
                : "取消本次匹配"
              : "确认匹配"}
          </button>
          <button onClick={() => onDetails(current || pair)}>查看详情</button>
        </div>
      )}
    </article>
  );
}
