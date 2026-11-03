import { ChevronRight, Layers3, Pause, Play, Square } from "lucide-react";
import { Button } from "../../components/ui/button";
import { api, projectUrl } from "../../shared/api";
import { cn } from "../../shared/utils";
import type { AppController } from "../types";
export function ProjectHeader({
  project,
  streamConnected,
  setGraphMaximized,
  setMaximized,
  maximized,
  setPanelVersion,
  snapshot,
  current,
  setDialog,
  setNotice,
  running,
  refresh,
  loadProjects,
  error,
  start,
  graph,
  controlRun,
}: Pick<
  AppController,
  | "project"
  | "streamConnected"
  | "setGraphMaximized"
  | "setMaximized"
  | "maximized"
  | "setPanelVersion"
  | "snapshot"
  | "current"
  | "setDialog"
  | "setNotice"
  | "running"
  | "value"
  | "refresh"
  | "loadProjects"
  | "error"
  | "start"
  | "graph"
  | "controlRun"
>) {
  return (
    <header className="topbar">
      <div className="min-w-0">
        <div className="breadcrumb">
          <Layers3 size={12} /> 场景工作台 <ChevronRight size={12} />
          {project?.name || "项目概览"}
        </div>
        <h1>{project?.name || "需求场景审核工作台"}</h1>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={cn("connection", streamConnected && "online")}
          title={streamConnected ? "实时事件已连接" : "本地工作台"}
        >
          <span />
        </span>
        <details className="workspace-menu">
          <summary aria-label="更多项目操作">更多操作</summary>
          <div className="workspace-menu-content">
            <button
              onClick={() => {
                setGraphMaximized(false);
                setMaximized((v) => !v);
              }}
            >
              {maximized ? "显示任务导航" : "专注阅读"}
            </button>
            <button
              onClick={() => {
                localStorage.removeItem(
                  "react-resizable-panels:scene-workspace-panels-v5",
                );
                setPanelVersion((v) => v + 1);
                setMaximized(false);
                setGraphMaximized(false);
              }}
            >
              复位布局
            </button>
            <button
              disabled={snapshot?.review_only}
              onClick={() =>
                current ? setDialog("settings") : setNotice("请先选择项目")
              }
            >
              模型配置
            </button>
            {current && (
              <a href={projectUrl(current, "export")}>导出项目与产物</a>
            )}
            <label>
              执行模式
              <select
                aria-label="执行模式"
                disabled={running || snapshot?.review_only}
                value={snapshot?.project.review_mode || "manual"}
                onChange={(e) =>
                  current &&
                  api(projectUrl(current, "mode"), {
                    method: "PUT",
                    body: JSON.stringify({ review_mode: e.target.value }),
                  })
                    .then(() => Promise.all([refresh(), loadProjects()]))
                    .catch(error)
                }
              >
                <option value="manual">中间产物手动确认</option>
                <option value="auto">自动运行完整流程</option>
              </select>
            </label>
          </div>
        </details>
        <Button
          size="sm"
          onClick={() => start().catch(error)}
          disabled={!current || running || snapshot?.review_only}
        >
          <Play size={13} />
          {snapshot?.review_only
            ? "业务审核模式"
            : running
              ? "运行中"
              : graph.nodes.some((n) => !n.planned)
                ? "继续运行"
                : "开始运行"}
        </Button>
        {(running ||
          ["waiting", "paused", "error"].includes(
            snapshot?.job.status || "",
          )) &&
          !snapshot?.review_only && (
            <>
              {running && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!!snapshot?.job.control_state}
                  onClick={() => controlRun("pause").catch(error)}
                >
                  <Pause size={13} />
                  {snapshot?.job.control_state === "pausing"
                    ? "暂停中…"
                    : "暂停任务"}
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                disabled={snapshot?.job.control_state === "stopping"}
                onClick={() => controlRun("stop").catch(error)}
              >
                <Square size={13} />
                {snapshot?.job.control_state === "stopping"
                  ? "停止中…"
                  : "停止任务"}
              </Button>
            </>
          )}
      </div>
    </header>
  );
}
