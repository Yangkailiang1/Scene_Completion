import { useMemo } from "react";
import { Background, Controls, MarkerType, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Anchor } from "./types";
export function DependencyGraph({
  anchors,
  selected,
  onSelect,
}: {
  anchors: Anchor[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const ids = [
      ...new Set(
        anchors
          .flatMap((anchor) => [anchor.from_case_id, anchor.to_case_id])
          .filter((id): id is string => !!id),
      ),
    ];
    return {
      nodes: ids.map((id, index) => ({
        id,
        position: { x: (index % 3) * 250, y: Math.floor(index / 3) * 180 },
        data: { label: id },
      })),
      edges: anchors
        .filter((anchor) => anchor.from_case_id && anchor.to_case_id)
        .map((anchor, index) => ({
          id: anchor.id,
          source: anchor.from_case_id!,
          target: anchor.to_case_id!,
          type: "smoothstep",
          label: `${anchor.relation_type === "cascade" ? "级联" : "直接"} · ${(anchor.obligation || anchor.condition || anchor.id).slice(0, 35)}`,
          markerEnd: { type: MarkerType.ArrowClosed },
          selected: selected === anchor.id,
          style: {
            stroke: selected === anchor.id ? "#315bd9" : "#8a9bb5",
            strokeWidth: selected === anchor.id ? 3 : 1.5,
          },
          pathOptions: { offset: 20 + (index % 4) * 12 },
        })),
    };
  }, [anchors, selected]);
  return (
    <div className="project-dependency-graph" aria-label="用例业务依赖图">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        onEdgeClick={(_, edge) => onSelect(edge.id)}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
