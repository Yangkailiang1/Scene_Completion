import { useState } from "react";
import { Workflow, ChevronDown } from "lucide-react";
import type { Graph } from "./types";
import { phaseLabels, phaseColor, roleLabels, duration } from "./utils";

export function ExecutionNavigator({
  graph,
  selected,
  onSelect,
  onOpenGraph,
}: {
  graph: Graph;
  selected: string | null;
  onSelect: (id: string) => void;
  onOpenGraph: () => void;
}) {
  const [filter, setFilter] = useState("all");
  return (
    <aside className="execution-navigator" aria-label="执行任务导航">
      <header>
        <div>
          <Workflow size={18} />
          <strong>执行进度</strong>
        </div>
        <button onClick={onOpenGraph}>打开完整依赖图</button>
      </header>
      <select
        aria-label="筛选执行任务"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      >
        <option value="all">全部任务</option>
        <option value="attention">失败 / 待回答 / 待审核</option>
        <option value="running">正在执行</option>
      </select>
      <div className="navigator-scroll">
        {(["modeler", "checker", "recommender"] as const).map((role) => {
          const all = graph.nodes.filter((n) => n.role === role);
          const nodes = all.filter(
            (n) =>
              filter === "all" ||
              (filter === "running"
                ? n.status === "running"
                : [
                    "failed",
                    "rejected",
                    "awaiting_review",
                    "awaiting_answer",
                    "rate_limited",
                  ].includes(n.status)),
          );
          return (
            <details key={role} open className="navigator-role">
              <summary>
                {roleLabels[role]}
                <span>
                  {role === "recommender" &&
                  all.every((n) => n.status === "disabled")
                    ? "未启用"
                    : `${all.filter((n) => n.status === "passed").length} / ${all.filter((n) => !n.planned).length}`}
                </span>
                <ChevronDown size={13} />
              </summary>
              {nodes.map((n) => (
                <button
                  key={n.id}
                  aria-label={n.label}
                  aria-current={n.id === selected ? "step" : undefined}
                  className={n.id === selected ? "chosen" : ""}
                  onClick={() => onSelect(n.id)}
                >
                  <div>
                    <span className={`status-dot ${phaseColor(n.phase)}`} />
                    <strong>{n.label}</strong>
                  </div>
                  <small>
                    {n.case === "shared" ? "项目共享" : n.case} ·{" "}
                    {phaseLabels[n.phase] || n.phase}{" "}
                    {n.status === "running" ? duration(n.elapsed_seconds) : ""}
                  </small>
                  {n.question && <em>需要您回答</em>}
                </button>
              ))}
              {!nodes.length && <p>当前筛选下没有任务</p>}
            </details>
          );
        })}
      </div>
    </aside>
  );
}
