import { layout } from "./flow_layout";
import { useMemo, useState, useEffect } from "react";
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
import { LocateFixed, Workflow, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "./components/ui/button";
import {
  phaseColor,
  phaseLabels,
  roleLabels,
  duration,
  failureText,
} from "./utils";
import type { Graph, GraphNode } from "./types";
import "@xyflow/react/dist/style.css";
type TaskNode = Node<{ task: GraphNode; chosen: boolean }, "task">;
function TaskCard({ data }: NodeProps<TaskNode>) {
  const n = data.task,
    c = phaseColor(n.phase);
  const seconds = n.retry_at
    ? Math.max(0, Math.ceil(n.retry_at - Date.now() / 1000))
    : null;
  return (
    <div
      className={`flow-card ${data.chosen ? "chosen" : ""} ${c} ${n.planned ? "planned" : ""}`}
    >
      <Handle type="target" position={Position.Top} />
      <div className="flow-card-kicker">
        <span className={`status-dot ${c}`} />
        <span>
          {n.planned
            ? "流程预告 · 不计进度"
            : n.case === "shared"
              ? "项目级共享"
              : n.case}
        </span>
      </div>
      <h3>{n.label}</h3>
      <p className="flow-input">输入：{n.input_summary || "上游已验证产物"}</p>
      <div className="flow-files">
        <b>产物</b>
        {n.expected_files.length ? (
          n.expected_files.map((f) => (
            <span key={f} title={f}>
              <code>{f}</code>
              <small>
                {n.artifacts?.some((a) => a.name === f)
                  ? n.artifacts?.some(
                      (a) => a.name === f && a.status === "awaiting_review",
                    )
                    ? "已保存 · 待审核"
                    : "已保存"
                  : n.planned
                    ? "待展开"
                    : "待生成"}
              </small>
            </span>
          ))
        ) : (
          <span>当前不生成产物</span>
        )}
      </div>
      <div className="flow-state">
        <span className={`status-label ${c}`}>
          {phaseLabels[n.phase] || n.phase}
        </span>
        <small>{n.planned ? "" : duration(n.elapsed_seconds)}</small>
      </div>
      {n.phase === "rate_limit_wait" && (
        <p className="retry-note">
          {seconds}秒后续试 · {n.retry_count}/3
        </p>
      )}
      {n.failure && (
        <p className="flow-error" title={JSON.stringify(n.failure)}>
          {failureText(n.failure)}
        </p>
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
        <span>{data.role.toUpperCase()}</span>
        <strong>{data.label}</strong>
      </div>
    </div>
  );
}
const nodeTypes = { task: TaskCard, lane: RoleLane };

function Canvas({
  graph,
  selected,
  onSelect,
  hidden,
}: {
  graph: Graph;
  selected: string | null;
  onSelect: (id: string) => void;
  hidden: string[];
}) {
  const [scope, setScope] = useState("all");
  const flow = useReactFlow();
  const cases = [
    ...new Set(
      graph.nodes
        .filter((n) => !n.planned && n.case !== "shared")
        .map((n) => n.case),
    ),
  ];
  const visible = graph.nodes.filter(
    (n) =>
      !hidden.includes(n.role) &&
      (scope === "all" || n.case === "shared" || n.planned || n.case === scope),
  );
  const nodes = useMemo(
    () => layout(visible, selected),
    [graph, scope, selected, hidden.join("|")],
  );
  const ids = new Set(visible.map((n) => n.id));
  const edges = graph.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => ({
      ...e,
      style: { stroke: "#96a9c6", strokeWidth: 1.3 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#96a9c6" },
      animated:
        graph.nodes.find((n) => n.id === e.target)?.status === "running",
    }));
  useEffect(() => {
    if (scope !== "all" && !cases.includes(scope)) setScope("all");
  }, [cases.join("|")]);
  const locate = () => {
    const n =
      visible.find((n) => n.status === "running") ||
      visible.find((n) => n.phase === "awaiting_answer") ||
      visible.find((n) => n.phase === "awaiting_review") ||
      visible.find((n) => n.status === "failed");
    if (n) {
      flow.fitView({
        nodes: [{ id: n.id }],
        padding: 0.5,
        maxZoom: 1,
        duration: 250,
      });
      onSelect(n.id);
    } else flow.fitView({ padding: 0.1, duration: 250 });
  };
  return (
    <>
      <div className="flow-toolbar">
        <select
          aria-label="执行图用例范围"
          value={scope}
          onChange={(e) => setScope(e.target.value)}
        >
          <option value="all">全部用例与项目共享</option>
          {cases.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <Button
          variant="outline"
          size="sm"
          onClick={() => flow.fitView({ padding: 0.08, duration: 250 })}
        >
          适应画布
        </Button>
        <Button
          variant="ghost"
          size="icon"
          title="定位当前节点"
          aria-label="定位当前节点"
          onClick={locate}
        >
          <LocateFixed size={15} />
        </Button>
      </div>
      <div className="graph-scroll-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, n) => n.type === "task" && onSelect(n.id)}
          nodesConnectable={false}
          nodesDraggable={false}
          minZoom={0.08}
          maxZoom={1.7}
          defaultViewport={{ x: 12, y: 12, zoom: 0.65 }}
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
  onMaximize?: () => void;
  maximized?: boolean;
}) {
  const [hidden, setHidden] = useState<string[]>([]);
  return (
    <section className="execution-panel">
      <div className="execution-title">
        <Workflow size={17} />
        <h2>执行编排与产物</h2>
        <select
          aria-label="执行图角色聚焦"
          onChange={(e) =>
            setHidden(
              e.target.value === "all"
                ? []
                : ["modeler", "checker", "recommender"].filter(
                    (r) => r !== e.target.value,
                  ),
            )
          }
        >
          <option value="all">全部角色</option>
          {["modeler", "checker", "recommender"].map((r) => (
            <option key={r} value={r}>
              {roleLabels[r]}
            </option>
          ))}
        </select>
        <button onClick={props.onMaximize}>
          {props.maximized ? "恢复双栏" : "放大执行图"}
        </button>
      </div>
      <div className="role-summary">
        {["modeler", "checker", "recommender"].map((id) => {
          const r = props.graph.roles.find((r) => r.id === id),
            closed = hidden.includes(id);
          return (
            <button
              key={id}
              onClick={() =>
                setHidden((old) =>
                  closed ? old.filter((r) => r !== id) : [...old, id],
                )
              }
              aria-label={(closed ? "展开" : "收起") + roleLabels[id]}
            >
              {closed ? <ChevronRight size={13} /> : <ChevronDown size={13} />}
              <span className={`role-tiny ${id}`} />
              <span>{roleLabels[id]}</span>
              <strong>
                {id === "recommender"
                  ? "未启用"
                  : `${r?.completed || 0} / ${r?.known || 0}`}
              </strong>
            </button>
          );
        })}
      </div>
      <ReactFlowProvider>
        <Canvas {...props} hidden={hidden} />
      </ReactFlowProvider>
      {!props.graph.definition_available && (
        <div className="flow-footnote">
          {props.graph.nodes.some((n) => !n.planned)
            ? "历史记录未保存依赖，不能补造连线。"
            : "当前为流程预告，运行后显示实际节点。"}
        </div>
      )}
      {props.graph.case_expansion_pending && (
        <div className="flow-footnote">
          用例对应后展开具体节点；虚线框为预告，不计进度。可收起角色、缩放或平移查看完整编排。
        </div>
      )}
    </section>
  );
}
