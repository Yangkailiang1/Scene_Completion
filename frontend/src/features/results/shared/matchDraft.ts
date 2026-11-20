import type { Decision } from "../ssd/types";

export const decisionKey = (
  d: Pick<Decision, "level" | "pair" | "left_id" | "right_id">,
) => JSON.stringify([d.level, d.pair, d.left_id, d.right_id]);

export function stable(value: any): string {
  if (Array.isArray(value)) return "[" + value.map(stable).join(",") + "]";
  if (value && typeof value === "object")
    return (
      "{" +
      Object.keys(value)
        .sort()
        .map((k) => JSON.stringify(k) + ":" + stable(value[k]))
        .join(",") +
      "}"
    );
  return JSON.stringify(value);
}
function decisionsByKey(bundle: any) {
  const groups = new Map<string, string[]>();
  for (const d of bundle?.decisions || []) {
    const { id: _id, ...content } = d;
    void _id;
    const key = decisionKey(d);
    groups.set(key, [...(groups.get(key) || []), stable(content)].sort());
  }
  return groups;
}
function otherItems(bundle: any) {
  const items = new Map<string, string>();
  for (const [key, value] of Object.entries(bundle || {})) {
    if (key === "decisions") continue;
    if (key === "channels") {
      for (const [channel, kinds] of Object.entries(value as any))
        for (const [kind, rows] of Object.entries(kinds as any))
          for (const row of rows as any[])
            items.set(
              "channel:" + channel + ":" + row.id,
              stable({ kind, row }),
            );
    } else if (
      Array.isArray(value) &&
      value.every((v) => v && typeof v === "object" && v.id)
    ) {
      for (const row of value) items.set(key + ":" + row.id, stable(row));
    } else items.set(key, stable(value));
  }
  return items;
}
export function draftChanges(saved: any, draft: any) {
  if (saved === draft)
    return { matches: new Set<string>(), other: 0, total: 0 };
  const before = decisionsByKey(saved),
    after = decisionsByKey(draft);
  const keys = new Set([...before.keys(), ...after.keys()]);
  const matches = new Set(
    [...keys].filter(
      (key) => stable(before.get(key) || []) !== stable(after.get(key) || []),
    ),
  );
  const a = otherItems(saved),
    b = otherItems(draft);
  const other = [...new Set([...a.keys(), ...b.keys()])].filter(
    (key) => a.get(key) !== b.get(key),
  ).length;
  return { matches, other, total: matches.size + other };
}
export function findDecision(bundle: any, pair: any): Decision | undefined {
  const rows = (bundle?.decisions || []).filter(
    (d: Decision) => decisionKey(d) === decisionKey(pair),
  );
  return (
    [...rows].reverse().find((d: Decision) => d.origin === "manual") ||
    rows.at(-1)
  );
}
export function putDecision(bundle: any, value: Decision) {
  bundle.decisions = (bundle.decisions || []).filter(
    (d: Decision) => d.id !== value.id && decisionKey(d) !== decisionKey(value),
  );
  bundle.decisions.push(value);
}
export function restoreDecision(bundle: any, saved: any, pair: Decision) {
  const key = decisionKey(pair);
  bundle.decisions = [
    ...(bundle.decisions || []).filter((d: Decision) => decisionKey(d) !== key),
    ...(saved?.decisions || []).filter((d: Decision) => decisionKey(d) === key),
  ];
}
export const decisionLabel = (status?: string) =>
  ({ full: "已匹配", partial: "部分匹配", none: "不匹配" })[status || ""] ||
  "待判定";

export function rowDraftDecisions(
  bundle: any,
  saved: any,
  row: any,
  layer: string,
  changes = draftChanges(saved, bundle).matches,
) {
  const candidates = [
    ...(bundle?.decisions || []),
    ...(saved?.decisions || []),
  ];
  const unique = new Map<string, Decision>();
  for (const d of candidates) {
    const [left, right] = d.pair.split("_");
    if (
      changes.has(decisionKey(d)) &&
      d.level === (layer === "concerns" ? "concern" : "scenario") &&
      (row.cells[left]?.some((r: any) => r.id === d.left_id) ||
        row.cells[right]?.some((r: any) => r.id === d.right_id))
    )
      unique.set(
        decisionKey(d),
        findDecision(bundle, d) || {
          ...d,
          status: "removed",
          reason: "撤销已保存判定",
        },
      );
  }
  return [...unique.values()];
}
