import {
  ChevronRight,
  Layers3,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
} from "lucide-react";
import { Button } from "../../components/ui/button";
import { cn } from "../../shared/utils";
import type { AppController } from "../types";
export function ProjectSidebar({
  collapsed,
  snapshot,
  setDialog,
  setCollapsed,
  filter,
  setFilter,
  projects,
  current,
  openProject,
}: Pick<
  AppController,
  | "collapsed"
  | "snapshot"
  | "setDialog"
  | "setCollapsed"
  | "value"
  | "filter"
  | "setFilter"
  | "projects"
  | "current"
  | "openProject"
>) {
  return (
    <aside className={cn("project-sidebar", collapsed && "collapsed")}>
      <div className="sidebar-brand">
        <div className="brand-mark">
          <Layers3 size={22} />
        </div>
        {!collapsed && (
          <div>
            <strong>Scene Completion</strong>
            <span>场景完整性审核</span>
          </div>
        )}
      </div>
      <div className="sidebar-controls">
        <Button
          variant="secondary"
          className="new-project"
          disabled={snapshot?.review_only}
          onClick={() => setDialog("new")}
          aria-label="新建项目"
        >
          <Plus size={16} />
          {!collapsed && "新建项目"}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            setCollapsed(!collapsed);
            localStorage.setItem("scene-sidebar-collapsed", String(!collapsed));
          }}
          aria-label={collapsed ? "展开项目栏" : "收起项目栏"}
          title={collapsed ? "展开项目栏" : "收起项目栏"}
        >
          {collapsed ? (
            <PanelLeftOpen size={16} />
          ) : (
            <PanelLeftClose size={16} />
          )}
        </Button>
      </div>
      {!collapsed && (
        <div className="project-search">
          <Search size={13} />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="查找项目"
          />
        </div>
      )}
      <div className="sidebar-section-label">{!collapsed && "工作项目"}</div>
      <nav>
        {projects
          .filter((p) => p.name.includes(filter))
          .map((p) => (
            <button
              key={p.id}
              className={cn("project-item", current === p.id && "active")}
              onClick={() => openProject(p.id)}
              title={p.name}
            >
              <span className="project-avatar">{p.name.slice(0, 1)}</span>
              {!collapsed && (
                <>
                  <span>
                    {p.name}
                    <small>
                      {p.review_mode === "manual" ? "人工确认" : "自动运行"}
                    </small>
                  </span>
                  <ChevronRight size={13} />
                </>
              )}
            </button>
          ))}
      </nav>
      <div className="sidebar-bottom">
        <span className="local-dot" />
        {!collapsed && <span>本地保存 · 内网模型</span>}
      </div>
    </aside>
  );
}
