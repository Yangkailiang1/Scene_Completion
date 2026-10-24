import type { Node } from "@xyflow/react";
import type { GraphNode } from "./types";
import { roleLabels } from "./utils";
export function layout(nodes: GraphNode[], selected: string | null) {
  const roles = ["modeler", "checker", "recommender"];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const depths: Record<string, number> = {};
  const visiting = new Set<string>();
  function depth(n: GraphNode): number {
    if (depths[n.id] != null) return depths[n.id];
    if (visiting.has(n.id)) return 0;
    visiting.add(n.id);
    const d = n.deps
      .filter((k) => byId.has(k))
      .map((k) => depth(byId.get(k)!) + 1);
    visiting.delete(n.id);
    return (depths[n.id] = Math.max(0, ...d));
  }
  nodes.filter((n) => !n.planned).forEach(depth);
  const max = Math.max(0, ...Object.values(depths));
  let p = 0;
  for (const n of nodes.filter((n) => n.planned)) depths[n.id] = max + 1 + p++;
  const widths: Record<string, number> = {},
    tops: Record<number, number> = {};
  let y = 66;
  for (const rank of [...new Set(Object.values(depths))].sort(
    (a, b) => a - b,
  )) {
    tops[rank] = y;
    const maxRows = Math.max(
      1,
      ...roles.map((r) =>
        Math.ceil(
          nodes.filter((n) => n.role === r && depths[n.id] === rank).length / 3,
        ),
      ),
    );
    y += maxRows * 246 + 40;
  }
  let x = 0;
  const result: Node[] = [];
  for (const role of roles) {
    const group = nodes.filter((n) => n.role === role);
    const cols = Math.max(
      1,
      ...[...new Set(group.map((n) => depths[n.id]))].map((rank) =>
        Math.min(3, group.filter((n) => depths[n.id] === rank).length),
      ),
    );
    widths[role] = cols * 264 + 32;
    result.push({
      id: "lane-" + role,
      type: "lane",
      position: { x, y: 0 },
      data: { role, label: roleLabels[role] },
      style: { width: widths[role], height: Math.max(480, y) },
      selectable: false,
      draggable: false,
      zIndex: -1,
    });
    const indexes: Record<number, number> = {};
    for (const n of group) {
      const rank = depths[n.id],
        index = indexes[rank] || 0;
      indexes[rank] = index + 1;
      result.push({
        id: n.id,
        type: "task",
        parentId: "lane-" + role,
        extent: "parent",
        position: {
          x: 16 + (index % 3) * 264,
          y: tops[rank] + Math.floor(index / 3) * 246,
        },
        data: { task: n, chosen: n.id === selected },
        draggable: false,
        connectable: false,
      });
    }
    x += widths[role] + 26;
  }
  return result;
}
