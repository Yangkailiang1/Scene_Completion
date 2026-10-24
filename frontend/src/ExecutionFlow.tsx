import React, { useMemo, useState, useEffect } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
  Background,
  Controls,
  MiniMap,
  useReactFlow,
  MarkerType,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { LocateFixed, Workflow } from "lucide-react";
import { Button } from "./components/ui/button";
import { phaseColor, phaseLabels, roleLabels, duration } from "./utils";
import type { Graph, GraphNode } from "./types";
import "@xyflow/react/dist/style.css";
type TaskNode = Node<{ task: GraphNode; chosen: boolean }, "task">;
function TaskCard({ data }: NodeProps<TaskNode>) {
  const n = data.task,
    c = phaseColor(n.phase);
  return (
    <div className={`flow-card ${data.chosen ? "chosen" : ""} ${c}`}>
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center justify-between gap-2">
        <span className={`status-dot ${c}`} />
        <span className="text-[10px] text-slate-400">
          {n.case === "shared" ? "项目共享" : n.case}
        </span>
      </div>
      <div className="mt-2 text-[13px] font-semibold">{n.label}</div>
      <div
        className="mt-1 truncate font-mono text-[10px] text-slate-400"
        title={n.expected_files.join("、")}
      >
        {n.expected_files[0]}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <span className={`status-label ${c}`}>
          {phaseLabels[n.phase] || n.phase}
        </span>
        <span className="text-[10px] text-slate-400">
          {duration(n.elapsed_seconds)}
        </span>
      </div>
      {n.failure && (
        <div
          className="mt-2 truncate text-[10px] text-red-500"
          title={n.failure.error || JSON.stringify(n.failure)}
        >
          {n.failure.error || n.failure.reason || "查看错误详情"}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
function RoleLane({
  data,
}: NodeProps<Node<{ role: string; label: string }, "lane">>) {
  return (
    <div className={`role-lane ${data.role}`}>
      <div className="role-lane-label">
        <span className="text-[10px] text-slate-400">
          {data.role.toUpperCase()}
        </span>
        <strong>{data.label}</strong>
      </div>
    </div>
  );
}
const nodeTypes = { task: TaskCard, lane: RoleLane };
function layout(nodes: GraphNode[], selected: string | null) {
  const roles = ["modeler", "checker", "recommender"];
  const positions: Record<string, { x: number; y: number }> = {};
  const counts: Record<string, number> = {};
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const ordered: GraphNode[] = [];
  const visit = (n: GraphNode) => {
    if (ordered.includes(n)) return;
    for (const d of n.deps) {
      const parent = byId.get(d);
      if (parent) visit(parent);
    }
    ordered.push(n);
  };
  nodes.forEach(visit);
  for (const n of ordered) {
    let y = 60;
    for (const dep of n.deps)
      if (positions[dep]) y = Math.max(y, positions[dep].y + 158);
    y = Math.max(y, counts[n.role] || 60);
    positions[n.id] = { x: 18, y };
    counts[n.role] = y + 158;
  }
  const height = Math.max(500, ...Object.values(counts).map((n) => n + 20));
  const result: Node[] = [];
  for (const [idx, role] of roles.entries()) {
    result.push({
      id: "lane-" + role,
      type: "lane",
      position: { x: idx * 292, y: 0 },
      data: { role, label: roleLabels[role] },
      style: { width: 270, height },
      selectable: false,
      draggable: false,
      zIndex: -1,
    });
    for (const n of nodes.filter((n) => n.role === role))
      result.push({
        id: n.id,
        type: "task",
        parentId: "lane-" + role,
        extent: "parent",
        position: positions[n.id],
        data: { task: n, chosen: n.id === selected },
        draggable: false,
        connectable: false,
      });
  }
  return result;
}
function Canvas({
  graph,
  selected,
  onSelect,
}: {
  graph: Graph;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [scope, setScope] = useState("all");
  const flow = useReactFlow();
  const cases = [
    ...new Set(
      graph.nodes.filter((n) => n.case !== "shared").map((n) => n.case),
    ),
  ];
  const visible = graph.nodes.filter(
    (n) => scope === "all" || n.case === "shared" || n.case === scope,
  );
  const nodes = useMemo(
    () => layout(visible, selected),
    [graph, scope, selected],
  );
  const ids = new Set(visible.map((n) => n.id));
  const edges = graph.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => ({
      ...e,
      style: { stroke: "#a8b6cb", strokeWidth: 1.2 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#a8b6cb" },
      animated:
        graph.nodes.find((n) => n.id === e.target)?.status === "running",
    }));
  useEffect(() => {
    if (scope !== "all" && !cases.includes(scope)) setScope("all");
  }, [cases.join("|")]);
  const locate = () => {
    const n =
      visible.find((n) => n.status === "running") ||
      visible.find((n) => n.phase === "awaiting_review") ||
      visible.find((n) => n.status === "failed");
    if (n)
      flow.fitView({
        nodes: [{ id: n.id }],
        padding: 1.2,
        maxZoom: 1,
        duration: 350,
      });
    else flow.fitView({ padding: 0.2, duration: 300 });
  };
  return (
    <>
      <div className="flow-toolbar">
        <select
          aria-label="执行图用例范围"
          value={scope}
          onChange={(e) => setScope(e.target.value)}
        >
          <option value="all">全部已发现用例</option>
          {cases.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <Button
          variant="ghost"
          size="icon"
          title="定位当前节点"
          onClick={locate}
        >
          <LocateFixed size={15} />
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, n) => n.type === "task" && onSelect(n.id)}
          nodesConnectable={false}
          nodesDraggable={false}
          minZoom={0.15}
          maxZoom={1.6}
          defaultViewport={{ x: 15, y: 15, zoom: 0.8 }}
          onlyRenderVisibleElements
        >
          <Background color="#dce4f0" gap={18} size={1} />
          <Controls showInteractive={false} />
          <MiniMap
            pannable
            zoomable
            nodeColor={(n) => (n.type === "lane" ? "transparent" : "#9aafdb")}
            maskColor="rgba(242,245,251,.8)"
          />
        </ReactFlow>
      </div>
    </>
  );
}
export function ExecutionFlow(props: {
  graph: Graph;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="execution-panel">
      <div className="flex h-[58px] items-center justify-between border-b px-5">
        <div className="flex items-center gap-2">
          <Workflow size={16} className="text-primary" />
          <h2 className="text-sm font-semibold">执行编排</h2>
        </div>
        <span className="rounded bg-slate-100 px-2 py-1 text-[10px] text-slate-500">
          实时依赖图
        </span>
      </div>
      <div className="role-summary">
        {["modeler", "checker", "recommender"].map((id) => {
          const r = props.graph.roles.find((r) => r.id === id);
          return (
            <div key={id}>
              <span className={`role-tiny ${id}`} />
              <span>{roleLabels[id]}</span>
              <strong>
                {id === "recommender"
                  ? "未启用"
                  : `${r?.completed || 0} / ${r?.known || 0}`}
              </strong>
            </div>
          );
        })}
      </div>
      {!props.graph.definition_available && props.graph.nodes.length === 0 ? (
        <div className="empty-graph">
          <Workflow size={34} />
          <h3>等待执行计划</h3>
          <p>开始运行后，展示调度器实际生成的节点和依赖。</p>
          {props.graph.nodes.length === 0 && (
            <small>历史运行若没有图定义，可在节点详情查看原状态。</small>
          )}
        </div>
      ) : (
        <ReactFlowProvider>
          <Canvas {...props} />
        </ReactFlowProvider>
      )}
      {!props.graph.definition_available && props.graph.nodes.length > 0 && (
        <div className="flow-footnote">
          历史运行未保存依赖图，仅展示原状态记录；不会补造连线。
        </div>
      )}
      {props.graph.case_expansion_pending &&
        props.graph.definition_available && (
          <div className="flow-footnote">
            用例对应确认后，将展开各用例的建模与检查节点。
          </div>
        )}
    </section>
  );
}
