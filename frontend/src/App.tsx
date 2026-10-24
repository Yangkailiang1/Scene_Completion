import { useEffect, useRef, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import {
  Layers3,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Play,
  Settings2,
  Download,
  FolderOpen,
  ChevronRight,
  ChevronLeft,
  Activity,
  Files,
  ClipboardCheck,
  BookOpen,
  Workflow,
  AlertCircle,
  RefreshCw,
  X,
  ExternalLink,
  GripVertical,
  FileText,
  Search,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { ExecutionFlow } from "./ExecutionFlow";
import { NodeConversation } from "./NodeConversation";
import { NodeOutput } from "./NodeOutput";
import { ArtifactView } from "./ArtifactView";
import { api, projectUrl, fileUrl } from "./api";
import {
  cn,
  phaseColor,
  phaseLabels,
  roleLabels,
  duration,
  failureText,
} from "./utils";
import type {
  Project,
  Snapshot,
  Graph,
  Review,
  ExecutionEvent,
  GraphNode,
} from "./types";
const emptyGraph: Graph = {
  nodes: [],
  edges: [],
  roles: [],
  definition_available: false,
  case_expansion_pending: true,
};
function mergeEvents(a: ExecutionEvent[], b: ExecutionEvent[]) {
  return [...new Map([...a, ...b].map((e) => [e.id, e])).values()].sort(
    (a, b) => a.id - b.id,
  );
}
export default function App() {
  const [maximized, setMaximized] = useState(false),
    [graphMaximized, setGraphMaximized] = useState(false),
    [panelVersion, setPanelVersion] = useState(0);
  const [projects, setProjects] = useState<Project[]>([]),
    [current, setCurrent] = useState<string | null>(null),
    [snapshot, setSnapshot] = useState<Snapshot | null>(null),
    [graph, setGraph] = useState<Graph>(emptyGraph),
    [collapsed, setCollapsed] = useState(
      () => localStorage.getItem("scene-sidebar-collapsed") === "true",
    ),
    [selected, setSelected] = useState<string | null>(null),
    [tab, setTab] = useState("stream"),
    [versions, setVersions] = useState<any[]>([]),
    [review, setReview] = useState<Review | null>(null),
    [value, setValue] = useState<any>(null),
    [editor, setEditor] = useState(""),
    [comment, setComment] = useState(""),
    [events, setEvents] = useState<ExecutionEvent[]>([]),
    [loading, setLoading] = useState(false),
    [notice, setNotice] = useState(""),
    [dialog, setDialog] = useState<"new" | "settings" | null>(null),
    [definitions, setDefinitions] = useState<Record<string, any>>({}),
    [streamConnected, setStreamConnected] = useState(false),
    [filter, setFilter] = useState("");
  const currentRef = useRef(current),
    selectedRef = useRef(selected),
    dirty = useRef(false),
    refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null),
    buffer = useRef<ExecutionEvent[]>([]);
  currentRef.current = current;
  selectedRef.current = selected;
  const project = current ? projects.find((p) => p.id === current) : null,
    node = graph.nodes.find((n) => n.id === selected),
    running = snapshot?.job.status === "running";
  const error = (e: any) =>
    setNotice(e instanceof Error ? e.message : String(e));
  async function loadProjects() {
    const list = await api<Project[]>("/api/projects");
    setProjects(list);
    return list;
  }
  async function refresh(id = currentRef.current) {
    if (!id) return;
    const [s, g] = await Promise.all([
      api<Snapshot>(projectUrl(id)),
      api<Graph>(projectUrl(id, "graph")),
    ]);
    if (currentRef.current !== id) return;
    setSnapshot(s);
    setGraph(g);
  }
  useEffect(() => {
    loadProjects()
      .then((list) => {
        const saved = localStorage.getItem("scene-selected-project");
        if (saved && list.some((p) => p.id === saved)) openProject(saved);
      })
      .catch(error);
    api("/api/registry")
      .then((r) => setDefinitions(r.definitions))
      .catch(error);
  }, []);
  function openProject(id: string) {
    currentRef.current = id;
    selectedRef.current = null;
    setCurrent(id);
    setSelected(null);
    setReview(null);
    setEvents([]);
    setSnapshot(null);
    setGraph(emptyGraph);
    setValue(null);
    dirty.current = false;
    setNotice("");
    localStorage.setItem("scene-selected-project", id);
    refresh(id).catch(error);
  }
  function selectNode(id: string) {
    selectedRef.current = id;
    setSelected(id);
    setTab("stream");
    dirty.current = false;
    setReview(null);
    setValue(null);
    setEvents([]);
  }
  useEffect(() => {
    if (!current) return;
    const id = current;
    const cursor = sessionStorage.getItem("scene-cursor-" + id) || "0";
    const source = new EventSource(projectUrl(id, "events?after=" + cursor));
    source.onopen = () => setStreamConnected(true);
    source.onerror = () => setStreamConnected(false);
    source.addEventListener("execution", (message) => {
      const e = JSON.parse((message as MessageEvent).data) as ExecutionEvent;
      sessionStorage.setItem("scene-cursor-" + id, String(e.id));
      if (e.task_key === selectedRef.current) buffer.current.push(e);
      if (!refreshTimer.current)
        refreshTimer.current = setTimeout(() => {
          refreshTimer.current = null;
          refresh(id).catch(error);
        }, 700);
    });
    const flush = setInterval(() => {
      if (buffer.current.length) {
        const rows = buffer.current.splice(0);
        setEvents((old) =>
          mergeEvents(
            old,
            rows.filter((e) => e.task_key === selectedRef.current),
          ),
        );
      }
    }, 100);
    const poll = setInterval(() => refresh(id).catch(() => {}), 4000);
    return () => {
      source.close();
      clearInterval(flush);
      clearInterval(poll);
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      refreshTimer.current = null;
      buffer.current = [];
      setStreamConnected(false);
    };
  }, [current]);
  useEffect(() => {
    if (!current || !selected || selected.startsWith("planned:")) return;
    let active = true;
    setLoading(true);
    setEvents([]);
    (async () => {
      let cursor = 0;
      while (active) {
        const r = await api<{ events: ExecutionEvent[] }>(
          projectUrl(
            current,
            "events/history?task_key=" +
              encodeURIComponent(selected) +
              "&after=" +
              cursor +
              "&limit=500",
          ),
        );
        if (!active) break;
        setEvents((old) => mergeEvents(old, r.events));
        if (!r.events.length || r.events.length < 500) break;
        cursor = r.events[r.events.length - 1].id;
      }
    })()
      .catch(error)
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [current, selected]);
  const reviewHeader = snapshot?.reviews.find((r) => r.key === selected);
  const artifacts =
    snapshot?.artifacts.filter((a) => a.task_key === selected) || [];
  useEffect(() => {
    if (!current || !selected || !snapshot || selected.startsWith("planned:"))
      return;
    let active = true;
    const id = current,
      key = selected;
    (async () => {
      let v: any = null,
        r: Review | null = null;
      if (reviewHeader) {
        r = await api<Review>(
          projectUrl(id, "reviews/" + encodeURIComponent(key)),
        );
        v = r.payload;
      } else {
        const file = artifacts.find(
          (a) => a.name.endsWith(".json") && !a.name.endsWith(".metadata.json"),
        );
        if (file) {
          const raw = await api(fileUrl(id, file.path));
          v = raw.payload || raw;
        }
      }
      const h = await api<{ versions: any[] }>(
        projectUrl(id, "review-history?task_key=" + encodeURIComponent(key)),
      );
      if (!active) return;
      setVersions(h.versions);
      setReview(r);
      setValue(v);
      if (!dirty.current) {
        setEditor(JSON.stringify(v || {}, null, 2));
        setComment(r?.comment || "");
      }
    })().catch(error);
    return () => {
      active = false;
    };
  }, [
    current,
    selected,
    reviewHeader?.revision,
    reviewHeader?.status,
    artifacts.map((a) => a.path).join("|"),
  ]);
  async function start() {
    if (!current) return;
    setNotice("");
    const response = await api<any>(projectUrl(current, "run"), {
      method: "POST",
      body: "{}",
    });
    if (response.project_id && response.project_id !== current) {
      await loadProjects();
      openProject(response.project_id);
      return;
    }
    await refresh();
  }
  async function decide(action: string) {
    if (!current || !review) return;
    const body: any = {
      key: review.key,
      action,
      revision: review.revision,
      input_hash: review.input_hash,
      comment,
    };
    if (action === "approve") body.payload = JSON.parse(editor);
    await api(projectUrl(current, "decision"), {
      method: "POST",
      body: JSON.stringify(body),
    });
    dirty.current = false;
    await refresh();
    setNotice(
      action === "approve"
        ? "结果已保存并通过；点击“继续运行”推进后续节点。"
        : "审核决定已保存。",
    );
  }
  const formalArtifacts = artifacts.filter((a) =>
    a.path.startsWith("run/artifacts/"),
  );
  const visibleArtifacts =
    (review && ["draft", "rejected"].includes(review.status)) ||
    !formalArtifacts.length
      ? artifacts.filter((a) => a.path.includes("/reviews/previews/"))
      : formalArtifacts;
  const docs: Record<string, any> = {};
  function collect(v: any) {
    if (v && typeof v === "object") {
      if (v.source_id && Array.isArray(v.lines)) docs[v.source_id] = v;
      else Object.values(v).forEach(collect);
    }
  }
  if (review) collect(review.inputs);
  const activeNodes = graph.nodes.filter(
      (n) => n.status === "running" || n.status === "awaiting_answer",
    ),
    failedNodes = graph.nodes.filter(
      (n) =>
        n.phase === "transport_timeout" ||
        n.phase === "connection_failed" ||
        [
          "failed",
          "rejected",
          "budget_exhausted",
          "awaiting_configuration",
          "rate_limited",
        ].includes(n.status),
    ),
    pendingReviews =
      snapshot?.reviews.filter(
        (r) => r.status === "draft" || r.status === "rejected",
      ).length || 0;
  return (
    <div className="app-shell">
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
              localStorage.setItem(
                "scene-sidebar-collapsed",
                String(!collapsed),
              );
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
      <div className="workspace-shell">
        <header className="topbar">
          <div className="min-w-0">
            <div className="breadcrumb">
              <Layers3 size={12} /> 场景工作台 <ChevronRight size={12} />
              {project?.name || "项目概览"}
            </div>
            <h1>{project?.name || "需求场景审核工作台"}</h1>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn("connection", streamConnected && "online")}>
              <span />
              {streamConnected ? "事件已连接" : "本地工作台"}
            </span>
            <Button
              variant="ghost"
              size="icon"
              title="模型配置"
              aria-label="模型配置"
              onClick={() =>
                current
                  ? setDialog("settings")
                  : setNotice("请先选择或新建项目。")
              }
            >
              <Settings2 size={17} />
            </Button>
            {current && (
              <Button variant="outline" size="sm" asChild>
                <a href={projectUrl(current, "export")}>
                  <Download size={13} />
                  导出
                </a>
              </Button>
            )}
            <Button
              size="sm"
              onClick={() => start().catch(error)}
              disabled={!current || running}
            >
              <Play size={13} />
              {running
                ? "运行中"
                : graph.nodes.length
                  ? "继续运行"
                  : "开始运行"}
            </Button>
          </div>
        </header>
        {notice && (
          <div className="notice">
            <AlertCircle size={14} />
            <span>{notice}</span>
            <button onClick={() => setNotice("")} aria-label="关闭提示">
              <X size={14} />
            </button>
          </div>
        )}
        {!current ? (
          <div className="welcome">
            <div className="welcome-icon">
              <Workflow size={38} />
            </div>
            <span className="eyebrow">从文档到可审核的场景</span>
            <h2>让每一次检查，都有据可循</h2>
            <p>
              导入 RR / SR 文档，建立分层交互模型。
              <br />
              逐节点查看模型输出、关注点和异常缺失。
            </p>
            <Button onClick={() => setDialog("new")}>
              <Plus size={15} />
              新建审核项目
            </Button>
            <div className="welcome-steps">
              <span>01 文档与建模</span>
              <ChevronRight size={14} />
              <span>02 关注点与异常</span>
              <ChevronRight size={14} />
              <span>03 业务确认</span>
            </div>
          </div>
        ) : (
          <>
            {snapshot?.project.protocol &&
              snapshot.project.protocol !== "scene-workflow-v3" && (
                <div className="upgrade-banner">
                  当前是旧版运行记录。继续运行会创建融合交互新版项目；原项目与失败记录保留。
                </div>
              )}
            <div className="project-statusbar">
              <span
                className={`status-dot ${running ? "blue" : snapshot?.job.status === "complete" ? "green" : failedNodes.length ? "red" : "gray"}`}
              />
              <strong>
                {running
                  ? "正在执行"
                  : snapshot?.job.status === "complete"
                    ? "执行完成"
                    : failedNodes.length
                      ? "存在失败节点"
                      : snapshot?.job.status === "waiting"
                        ? "等待确认 / 补充"
                        : "待运行"}
              </strong>
              <span className="status-divider" />
              <span>
                已完成{" "}
                <b>{graph.nodes.filter((n) => n.status === "passed").length}</b>{" "}
                /{" "}
                {
                  graph.nodes.filter(
                    (n) => !n.planned && n.status !== "disabled",
                  ).length
                }{" "}
                个已发现节点
              </span>
              <span>
                待审核 <b>{pendingReviews}</b>
              </span>
              <div className="ml-auto flex items-center gap-2">
                <span className="text-[11px] text-slate-400">执行模式</span>
                <select
                  aria-label="执行模式"
                  disabled={running}
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
              </div>
            </div>
            <PanelGroup
              direction="horizontal"
              key={panelVersion}
              autoSaveId="scene-workspace-panels-v3"
              className={cn(
                "main-panels",
                maximized && "workspace-maximized",
                graphMaximized && "graph-maximized",
              )}
            >
              <Panel defaultSize={60} minSize={30}>
                <section className="center-workspace">
                  {!selected ? (
                    <div className="overview">
                      <div className="overview-title">
                        <span className="eyebrow">PROJECT OVERVIEW</span>
                        <h2>执行概览</h2>
                        <p>在右侧选择节点，查看实时输出与生成文件。</p>
                      </div>
                      <div className="overview-metrics">
                        <div>
                          <Workflow size={17} />
                          <strong>
                            {
                              graph.nodes.filter(
                                (n) => !n.planned && n.status !== "disabled",
                              ).length
                            }
                          </strong>
                          <span>已发现任务</span>
                        </div>
                        <div>
                          <ClipboardCheck size={17} />
                          <strong>{pendingReviews}</strong>
                          <span>待确认产物</span>
                        </div>
                        <div>
                          <Files size={17} />
                          <strong>
                            {snapshot?.artifacts.filter(
                              (a) => !a.path.includes("/reviews/"),
                            ).length || 0}
                          </strong>
                          <span>正式产物文件</span>
                        </div>
                      </div>
                      <h3 className="section-label">当前节点</h3>
                      {[...activeNodes, ...failedNodes].length === 0 ? (
                        <div className="info-card">
                          {pendingReviews
                            ? "有产物等待审核。点击右侧黄色节点，查看结果并确认。"
                            : "点击“开始运行”建立任务计划。用例对应确认后展开各用例流程。"}
                        </div>
                      ) : (
                        [...activeNodes, ...failedNodes]
                          .slice(0, 5)
                          .map((n) => (
                            <button
                              key={n.id}
                              className="active-task-card"
                              onClick={() => selectNode(n.id)}
                            >
                              <span
                                className={`status-dot ${phaseColor(n.phase)}`}
                              />
                              <span>
                                <strong>
                                  {roleLabels[n.role]} · {n.label}
                                </strong>
                                <small>
                                  {n.expected_files[0]} ·{" "}
                                  {n.case === "shared" ? "项目级共享" : n.case}
                                </small>
                              </span>
                              <span
                                className={`status-label ${phaseColor(n.phase)}`}
                              >
                                {phaseLabels[n.phase] || n.phase}
                              </span>
                              <ChevronRight size={15} />
                            </button>
                          ))
                      )}
                      <h3 className="section-label">输入文档</h3>
                      <div className="source-list">
                        {snapshot &&
                          Object.entries(snapshot.project.sources).flatMap(
                            ([role, files]) =>
                              files.map((f) => (
                                <a
                                  key={f.path}
                                  href={fileUrl(current, f.path)}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  <div className="source-icon">
                                    <FileText size={19} />
                                  </div>
                                  <span>
                                    <strong>{f.name}</strong>
                                    <small>
                                      {role === "test"
                                        ? "测试操作 / 独立真值"
                                        : role === "RR"
                                          ? "RR · 系统需求"
                                          : "SR · 功能设计"}
                                    </small>
                                  </span>
                                  <ExternalLink size={13} />
                                </a>
                              )),
                          )}
                      </div>
                      <div className="scope-note">
                        {snapshot?.project.case_ids?.length
                          ? "当前分析范围：" +
                            snapshot.project.case_ids.join("、")
                          : "分析所有已确认的用例对应组"}
                        <br />
                        共享图表为项目级；推荐器当前未启用。
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="node-heading">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="返回项目概览"
                          title="返回概览"
                          onClick={() => setSelected(null)}
                        >
                          <ChevronLeft size={17} />
                        </Button>
                        <div className="min-w-0 flex-1">
                          <div className="text-[10px] text-slate-400">
                            {roleLabels[node?.role || "modeler"]} /{" "}
                            {node?.case === "shared" ? "项目共享" : node?.case}
                          </div>
                          <h2>{node?.label || selected}</h2>
                        </div>
                        <span
                          className={`status-label ${phaseColor(node?.phase || "pending")}`}
                        >
                          {phaseLabels[node?.phase || "pending"] || node?.phase}
                        </span>
                      </div>
                      <div className="workspace-tools">
                        <button onClick={() => setMaximized(!maximized)}>
                          {maximized ? "恢复执行图" : "最大化工作区"}
                        </button>
                        <button
                          onClick={() => {
                            localStorage.removeItem(
                              "react-resizable-panels:scene-workspace-panels-v3",
                            );
                            setPanelVersion((v) => v + 1);
                          }}
                        >
                          恢复60 / 40布局
                        </button>
                      </div>
                      <div className="node-meta">
                        <span>
                          目标文件{" "}
                          <code>{node?.expected_files.join(" · ")}</code>
                        </span>
                        <span>
                          第 {node?.attempt || 1} 次尝试 ·{" "}
                          {duration(node?.elapsed_seconds ?? null)}
                        </span>
                      </div>
                      {node?.failure && (
                        <div className="failure-card">
                          <AlertCircle size={14} />
                          <div>
                            <strong>当前执行未完成</strong>
                            <p>{failureText(node.failure)}</p>
                          </div>
                        </div>
                      )}
                      {node?.blocked_by?.length ? (
                        <div className="dependency-note">
                          等待上游：
                          {node.blocked_by.map((k) => (
                            <button key={k} onClick={() => selectNode(k)}>
                              {graph.nodes.find((n) => n.id === k)?.label || k}
                              <ChevronRight size={11} />
                            </button>
                          ))}
                        </div>
                      ) : null}
                      <Tabs
                        value={tab}
                        onValueChange={setTab}
                        className="node-tabs"
                      >
                        <div className="tab-row">
                          <TabsList>
                            <TabsTrigger value="stream">
                              <Activity size={13} />
                              节点对话与实时输出
                            </TabsTrigger>
                            <TabsTrigger value="artifacts">
                              <Files size={13} />
                              产物{" "}
                              {visibleArtifacts.length > 0 && (
                                <small>{visibleArtifacts.length}</small>
                              )}
                            </TabsTrigger>
                            <TabsTrigger value="evidence">
                              <BookOpen size={13} />
                              原文依据
                            </TabsTrigger>
                            <TabsTrigger value="review">
                              <ClipboardCheck size={13} />
                              审核
                            </TabsTrigger>
                          </TabsList>
                        </div>
                        <TabsContent value="stream" className="stream-panel">
                          <NodeOutput
                            key={selected}
                            events={events}
                            loading={loading}
                            active={node?.status === "running"}
                          />
                          <NodeConversation
                            key={"conversation-" + selected}
                            projectId={current}
                            taskKey={selected}
                            planned={node?.planned}
                            onChanged={() => refresh().catch(error)}
                          />
                        </TabsContent>
                        <TabsContent value="artifacts" className="panel-scroll">
                          <ArtifactView
                            projectId={current}
                            artifacts={visibleArtifacts}
                            value={value}
                            definitions={definitions}
                          />
                        </TabsContent>
                        <TabsContent value="evidence" className="panel-scroll">
                          <div className="evidence-content">
                            {Object.values(docs).map((d: any) => (
                              <details key={d.source_id} open>
                                <summary>
                                  {d.name}
                                  <span>
                                    {d.channel === "normal"
                                      ? "正向材料"
                                      : d.channel === "test"
                                        ? "独立测试"
                                        : "原文异常通道"}
                                  </span>
                                </summary>
                                <pre>
                                  {d.lines
                                    .map(
                                      (line: any) =>
                                        `${String(line.number).padStart(4, " ")}  ${line.text}`,
                                    )
                                    .join("\n")}
                                </pre>
                              </details>
                            ))}
                            {Object.keys(docs).length === 0 && (
                              <p className="text-sm text-slate-400">
                                该节点的来源见结构化结果中的
                                source_refs，以及上游产物。
                              </p>
                            )}
                          </div>
                        </TabsContent>
                        <TabsContent value="review" className="panel-scroll">
                          <div className="review-content">
                            {!review ? (
                              <div className="node-empty">
                                <ClipboardCheck size={30} />
                                <h3>此节点暂无可审核结果</h3>
                                <p>
                                  模型产物完成校验后可在此查看、编辑和确认。
                                </p>
                              </div>
                            ) : (
                              <>
                                <div className="review-intro">
                                  <strong>
                                    {review.status === "approved"
                                      ? "业务已确认"
                                      : review.status === "auto"
                                        ? "自动运行结果，可继续审核"
                                        : "待业务确认"}
                                  </strong>
                                  <span>
                                    版本 {review.revision} ·
                                    修改后重新校验来源与字段
                                  </span>
                                </div>
                                <label>
                                  结构化产物
                                  <textarea
                                    aria-label="编辑结构化产物"
                                    spellCheck={false}
                                    value={editor}
                                    onChange={(e) => {
                                      dirty.current = true;
                                      setEditor(e.target.value);
                                    }}
                                  />
                                </label>
                                <label>
                                  审核备注
                                  <input
                                    value={comment}
                                    onChange={(e) => setComment(e.target.value)}
                                    placeholder="补充本次判断或修改依据"
                                  />
                                </label>
                                <div className="review-buttons">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={running}
                                    onClick={() =>
                                      decide("reject").catch(error)
                                    }
                                  >
                                    驳回
                                  </Button>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={running}
                                    onClick={() =>
                                      decide("regenerate").catch(error)
                                    }
                                  >
                                    <RefreshCw size={12} />
                                    重新生成
                                  </Button>
                                  <Button
                                    size="sm"
                                    disabled={running}
                                    onClick={() =>
                                      decide("approve").catch(error)
                                    }
                                  >
                                    保存并通过
                                  </Button>
                                </div>
                                <div className="review-history">
                                  <h3 className="section-label">
                                    审核版本记录
                                  </h3>
                                  {versions.map((v, i) => (
                                    <details key={i}>
                                      <summary>
                                        版本 {v.revision} · {v.status}
                                        <time>
                                          {new Date(
                                            v.updated_at,
                                          ).toLocaleString("zh-CN")}
                                        </time>
                                      </summary>
                                      {v.comment && <p>{v.comment}</p>}
                                      <pre>
                                        {JSON.stringify(v.payload, null, 2)}
                                      </pre>
                                    </details>
                                  ))}
                                </div>
                              </>
                            )}
                          </div>
                        </TabsContent>
                      </Tabs>
                    </>
                  )}
                </section>
              </Panel>
              <PanelResizeHandle className="panel-handle">
                <GripVertical size={13} />
              </PanelResizeHandle>
              <Panel defaultSize={40} minSize={28}>
                <ExecutionFlow
                  maximized={graphMaximized}
                  onMaximize={() => {
                    setMaximized(false);
                    setGraphMaximized((v) => !v);
                  }}
                  graph={graph}
                  selected={selected}
                  onSelect={selectNode}
                />
              </Panel>
            </PanelGroup>
          </>
        )}
      </div>
      {dialog && (
        <div
          className="modal-backdrop"
          onMouseDown={(e) => e.target === e.currentTarget && setDialog(null)}
        >
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={dialog === "new" ? "新建项目" : "模型配置"}
          >
            <button
              className="modal-close"
              onClick={() => setDialog(null)}
              aria-label="关闭对话框"
            >
              <X size={18} />
            </button>
            {dialog === "new" ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = e.currentTarget;
                  const form = new FormData(f);
                  (async () => {
                    const sources: Record<string, any[]> = {};
                    for (const role of ["RR", "SR", "test"])
                      sources[role] = await Promise.all(
                        (form.getAll(role) as File[])
                          .filter((v) => v.name)
                          .map(async (v) => ({
                            name: v.name,
                            content: await v.text(),
                          })),
                      );
                    const p = await api<Project>("/api/projects", {
                      method: "POST",
                      body: JSON.stringify({
                        name: form.get("name"),
                        review_mode: form.get("review_mode"),
                        case_ids: String(form.get("case_ids") || "")
                          .split(/[,，\s]+/)
                          .filter(Boolean),
                        sources,
                      }),
                    });
                    await loadProjects();
                    openProject(p.id);
                    setDialog(null);
                  })().catch(error);
                }}
              >
                <span className="eyebrow">NEW PROJECT</span>
                <h2>新建审核项目</h2>
                <p>文档与模型结果保存在本地，逐节点检查有据可循。</p>
                <label>
                  项目名称
                  <input
                    name="name"
                    required
                    placeholder="例如：商城需求审核"
                  />
                </label>
                {[
                  ["RR", "RR 系统需求文档"],
                  ["SR", "SR 功能设计文档"],
                  ["test", "测试文档（可选）"],
                ].map(([name, label]) => (
                  <label key={name}>
                    {label}
                    <input
                      type="file"
                      name={name}
                      accept=".md,.markdown"
                      multiple
                      required={name !== "test"}
                    />
                  </label>
                ))}
                <div className="form-grid">
                  <label>
                    执行模式
                    <select name="review_mode">
                      <option value="manual">中间产物手动确认</option>
                      <option value="auto">自动运行完整流程</option>
                    </select>
                  </label>
                  <label>
                    用例范围（可选）
                    <input name="case_ids" placeholder="留空分析所有用例" />
                  </label>
                </div>
                <Button className="mt-5 w-full" type="submit">
                  创建项目
                </Button>
              </form>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!current) return;
                  const raw = Object.fromEntries(new FormData(e.currentTarget));
                  const body = {
                    ...raw,
                    max_concurrency: Number(raw.max_concurrency),
                    max_tokens: Number(raw.max_tokens),
                    timeout_seconds: Number(raw.timeout_seconds),
                    stream_idle_timeout_seconds: Number(
                      raw.stream_idle_timeout_seconds,
                    ),
                    stream_total_timeout_seconds: Number(
                      raw.stream_total_timeout_seconds,
                    ),
                  };
                  api(projectUrl(current, "config"), {
                    method: "PUT",
                    body: JSON.stringify(body),
                  })
                    .then(() => {
                      setDialog(null);
                      refresh();
                      setNotice("模型配置已保存。");
                    })
                    .catch(error);
                }}
              >
                <span className="eyebrow">MODEL CONNECTION</span>
                <h2>模型配置</h2>
                <p>
                  优先使用项目配置，未覆盖项读取服务端
                  .env。密钥不会返回浏览器。
                </p>
                {snapshot?.config.credential_configured && (
                  <div className="credential-note">
                    ✓ 服务端已配置凭证，可直接运行
                  </div>
                )}
                <label>
                  OpenAI 兼容 Base URL
                  <input
                    name="base_url"
                    required
                    defaultValue={snapshot?.config.base_url || ""}
                    placeholder="https://服务地址/v1"
                  />
                </label>
                <label>
                  请求模型
                  <input
                    name="agent_model"
                    defaultValue={snapshot?.config.agent_model || "ecnu-plus"}
                    required
                  />
                </label>
                <label>
                  API Key
                  <input
                    type="password"
                    name="api_key"
                    autoComplete="off"
                    placeholder="留空继续使用服务端已配置密钥"
                  />
                </label>
                <div className="form-grid">
                  <label>
                    并发任务数
                    <input
                      type="number"
                      name="max_concurrency"
                      min="1"
                      max="8"
                      defaultValue={snapshot?.config.max_concurrency || 2}
                    />
                  </label>
                  <label>
                    输出 Token 上限
                    <input
                      type="number"
                      name="max_tokens"
                      min="256"
                      max="64000"
                      defaultValue={snapshot?.config.max_tokens || 12000}
                    />
                  </label>
                </div>
                <div className="form-grid mt-3">
                  <label>
                    连接／首响应等待（秒）
                    <input
                      name="timeout_seconds"
                      type="number"
                      min="10"
                      max="1800"
                      defaultValue={snapshot?.config.timeout_seconds || 120}
                    />
                  </label>
                  <label>
                    流中无数据等待（秒）
                    <input
                      name="stream_idle_timeout_seconds"
                      type="number"
                      min="10"
                      max="1800"
                      defaultValue={
                        snapshot?.config.stream_idle_timeout_seconds || 300
                      }
                    />
                  </label>
                  <label>
                    整次生成时限（秒）
                    <input
                      name="stream_total_timeout_seconds"
                      type="number"
                      min="30"
                      max="3600"
                      defaultValue={
                        snapshot?.config.stream_total_timeout_seconds || 900
                      }
                    />
                  </label>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  输出上限不是保证输出长度。大制品会耗时更久；连接、无数据等待和总生成时限分别生效，超时不会自动重发。
                </p>
                <Button type="submit" className="mt-6 w-full">
                  保存配置
                </Button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
