import {
  Activity,
  AlertCircle,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  ExternalLink,
  Files,
  FileText,
  GripVertical,
  Plus,
  RefreshCw,
  Workflow,
  X,
} from "lucide-react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Button } from "../components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { ConcernManager } from "../features/concerns/ConcernManager";
import { ExecutionFlow } from "../features/execution/ExecutionFlow";
import { ExecutionNavigator } from "../features/execution/ExecutionNavigator";
import { NodeConversation } from "../features/execution/NodeConversation";
import { NodeOutput } from "../features/execution/NodeOutput";
import { WorkspaceMonitor } from "../features/execution/WorkspaceMonitor";
import { ImportDependencyPlan } from "../features/inputs/ImportDependencyPlan";
import { InputBundlePicker } from "../features/inputs/InputBundlePicker";
import { InputManager } from "../features/inputs/InputManager";
import { ManagerPanel } from "../features/manager/ManagerPanel";
import { PatternManager } from "../features/patterns/PatternManager";
import { ArtifactView } from "../features/results/ArtifactView";
import { ResultsView } from "../features/results/ResultsView";
import { BusinessRecommendations } from "../features/review/BusinessRecommendations";
import { PendingView } from "../features/review/PendingView";
import { ReviewHandoff } from "../features/review/ReviewHandoff";
import { UsageView } from "../features/usage/UsageView";
import { api, fileUrl, projectUrl } from "../shared/api";
import {
  cn,
  duration,
  failureText,
  phaseColor,
  phaseLabels,
  roleLabels,
} from "../shared/utils";
import { ProjectDialog } from "./components/ProjectDialog";
import { ProjectHeader } from "./components/ProjectHeader";
import { ProjectSidebar } from "./components/ProjectSidebar";
import { useAppController } from "./useAppController";
export default function App() {
  const {
    newTestPreview,
    setNewTestPreview,
    newTestError,
    setNewTestError,
    newTestLoading,
    setNewTestLoading,
    newCreating,
    setNewCreating,
    bundleCreate,
    setBundleCreate,
    importPlanOpen,
    setImportPlanOpen,
    newTestRequest,
    management,
    setManagement,
    usageOpen,
    setUsageOpen,
    usageTask,
    setUsageTask,
    maximized,
    setMaximized,
    graphMaximized,
    setGraphMaximized,
    panelVersion,
    setPanelVersion,
    projects,
    current,
    snapshot,
    graph,
    collapsed,
    setCollapsed,
    selected,
    setSelected,
    tab,
    setTab,
    versions,
    review,
    value,
    editor,
    setEditor,
    comment,
    setComment,
    events,
    loading,
    notice,
    setNotice,
    dialog,
    setDialog,
    definitions,
    setDefinitions,
    streamConnected,
    filter,
    setFilter,
    dirty,
    project,
    node,
    running,
    error,
    loadProjects,
    refresh,
    openProject,
    selectNode,
    reviewHeader,
    start,
    controlRun,
    decide,
    visibleArtifacts,
    docs,
    activeNodes,
    failedNodes,
    pendingReviews,
  } = useAppController();
  return (
    <div className="app-shell">
      <ProjectSidebar
        {...{
          collapsed,
          snapshot,
          setDialog,
          setCollapsed,
          value,
          filter,
          setFilter,
          projects,
          current,
          openProject,
        }}
      />
      <div className="workspace-shell">
        <ProjectHeader
          {...{
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
            value,
            refresh,
            loadProjects,
            error,
            start,
            graph,
            controlRun,
          }}
        />
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
              snapshot.project.protocol !== "scene-workflow-v5" && (
                <div className="upgrade-banner">
                  当前是旧版运行记录。继续运行会创建关注点与场景两层新版项目；原项目与失败记录保留。
                </div>
              )}
            <div className="project-statusbar">
              <span
                className={`status-dot ${running ? "blue" : ["complete", "complete_with_questions"].includes(snapshot?.job.status || "") ? "green" : failedNodes.length ? "red" : "gray"}`}
              />
              <strong>
                {snapshot?.review_only
                  ? "业务审核 · 不运行模型"
                  : snapshot?.job.status === "paused"
                    ? "已暂停"
                    : snapshot?.job.reason === "user_stop"
                      ? "已停止"
                      : running
                        ? "正在执行"
                        : ["complete", "complete_with_questions"].includes(
                              snapshot?.job.status || "",
                            )
                          ? snapshot?.review_summary?.unresolved
                            ? `执行完成 · ${snapshot.review_summary.unresolved} 项待确认`
                            : "执行完成"
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
              <nav className="workspace-views" aria-label="工作区视图">
                <button
                  className={management === "imports" ? "active" : ""}
                  onClick={() => {
                    setManagement("imports");
                    setUsageOpen(false);
                  }}
                >
                  输入与导入
                </button>
                <button
                  className={!management && !usageOpen ? "active" : ""}
                  onClick={() => {
                    setManagement(null);
                    setUsageOpen(false);
                  }}
                >
                  工作区
                </button>
                <button
                  className={management === "results" ? "active" : ""}
                  onClick={() => {
                    setManagement("results");
                    setUsageOpen(false);
                  }}
                >
                  最终结果
                </button>
                <button
                  className={management === "pending" ? "active" : ""}
                  onClick={() => {
                    setManagement("pending");
                    setUsageOpen(false);
                  }}
                >
                  待确认项
                </button>
                <button
                  className={management === "concerns" ? "active" : ""}
                  onClick={() => {
                    setManagement("concerns");
                    setUsageOpen(false);
                  }}
                >
                  关注点设置
                </button>
                <button
                  className={management === "recommendations" ? "active" : ""}
                  onClick={() => {
                    setManagement("recommendations");
                    setUsageOpen(false);
                  }}
                >
                  推荐审核
                </button>
                <button
                  className={management === "handoff" ? "active" : ""}
                  onClick={() => {
                    setManagement("handoff");
                    setUsageOpen(false);
                  }}
                >
                  审核交接
                </button>
                <button
                  className={management === "patterns" ? "active" : ""}
                  onClick={() => {
                    setManagement("patterns");
                    setUsageOpen(false);
                  }}
                >
                  模式与风险
                </button>
                <button
                  className={usageOpen ? "active" : ""}
                  onClick={() => {
                    setManagement(null);
                    setUsageTask(null);
                    setUsageOpen(true);
                  }}
                >
                  用量与费用
                </button>
              </nav>
            </div>
            {current && !management && !usageOpen && (
              <WorkspaceMonitor
                project={current}
                reviewOnly={snapshot?.review_only}
                onSettings={() => setDialog("settings")}
                onSelect={selectNode}
              />
            )}
            <PanelGroup
              direction="horizontal"
              key={panelVersion}
              autoSaveId="scene-workspace-panels-v5"
              className={cn(
                "main-panels",
                (maximized || management || usageOpen) && "workspace-maximized",
                graphMaximized && "graph-maximized",
              )}
            >
              <Panel defaultSize={84} minSize={55}>
                <section className="center-workspace">
                  {management === "imports" && current ? (
                    <InputManager
                      project={current}
                      reviewOnly={snapshot?.review_only}
                      onOpenPlan={() => setImportPlanOpen(true)}
                    />
                  ) : management === "handoff" && current ? (
                    <ReviewHandoff
                      project={current}
                      reviewOnly={snapshot?.review_only}
                    />
                  ) : management === "recommendations" && current ? (
                    <BusinessRecommendations
                      project={current}
                      onEvidenceOpen={() => setCollapsed(true)}
                    />
                  ) : management === "results" && current ? (
                    <ResultsView
                      project={current}
                      liveVersion={JSON.stringify(
                        snapshot?.manifest?.live_cases || {},
                      )}
                    />
                  ) : management === "patterns" && current ? (
                    <PatternManager project={current} />
                  ) : management === "pending" && current ? (
                    <PendingView
                      project={current}
                      onSelect={selectNode}
                      onEvidenceOpen={() => setCollapsed(true)}
                    />
                  ) : management === "concerns" && current ? (
                    <ConcernManager
                      project={current}
                      onUpdated={() =>
                        api(projectUrl(current, "registry"))
                          .then((r) => setDefinitions(r.registry.definitions))
                          .catch(error)
                      }
                    />
                  ) : usageOpen && current ? (
                    <UsageView
                      project={current}
                      task={usageTask}
                      onClose={() => setUsageOpen(false)}
                      onSelect={selectNode}
                    />
                  ) : !selected ? (
                    <div className="overview">
                      <div className="overview-title">
                        <span className="eyebrow">PROJECT OVERVIEW</span>
                        <h2>执行概览</h2>
                        <p>
                          {snapshot?.manifest?.complete
                            ? "本轮执行已完成，可按用例、交互查看三方异常对照及全部已保存图表。"
                            : "从右侧任务导航选择结果；完整依赖图按需展开。"}
                        </p>
                        {snapshot?.manifest?.complete && (
                          <Button
                            onClick={() => {
                              setManagement("results");
                              setUsageOpen(false);
                            }}
                          >
                            查看最终结果与图表
                          </Button>
                        )}
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
                      {graph.preview_only && (
                        <div className="info-card">
                          <p>
                            输入已识别。可先查看文件映射、可跳过的抽取和完整依赖计划，无需启动模型。
                          </p>
                          <Button onClick={() => setImportPlanOpen(true)}>
                            查看文件映射与完整依赖图
                          </Button>
                        </div>
                      )}
                      {[...activeNodes, ...failedNodes].length === 0 ? (
                        <div className="info-card">
                          {pendingReviews
                            ? "有产物等待审核。点击右侧黄色节点，查看结果并确认。"
                            : snapshot?.manifest?.complete
                              ? "本轮没有正在执行或失败的节点。"
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
                        共享图表为项目级；推荐按当前运行版本及缺失M就绪情况执行。
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
                      {reviewHeader?.status === "draft" && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="node-review-shortcut"
                          onClick={() => setTab("review")}
                        >
                          结果已保存，点击审核后继续
                        </Button>
                      )}
                      <div className="node-meta">
                        <span>
                          目标文件{" "}
                          <code>{node?.expected_files.join(" · ")}</code>
                        </span>
                        <span>
                          第 {node?.attempt || 1} 次尝试 ·{" "}
                          {duration(node?.elapsed_seconds ?? null)}
                          {current && (
                            <button
                              className="ml-2 text-blue-700"
                              onClick={() => {
                                setManagement(null);
                                setUsageTask(selected);
                                setUsageOpen(true);
                              }}
                            >
                              token / 耗时明细
                            </button>
                          )}
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
                            taskKey={selected || undefined}
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
              <Panel defaultSize={16} minSize={14} maxSize={45}>
                {graphMaximized ? (
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
                ) : (
                  <ExecutionNavigator
                    graph={graph}
                    selected={selected}
                    onSelect={selectNode}
                    onOpenGraph={() => {
                      setMaximized(false);
                      setGraphMaximized(true);
                    }}
                  />
                )}
              </Panel>
            </PanelGroup>
          </>
        )}
      </div>
      <ManagerPanel
        project={current || ""}
        projectName={project?.name}
        reviewOnly={snapshot?.review_only}
      />
      {bundleCreate && (
        <InputBundlePicker
          project=""
          onClose={() => setBundleCreate(false)}
          onImported={(p) => {
            loadProjects().then(() => {
              openProject(p.id);
              setImportPlanOpen(true);
            });
          }}
        />
      )}
      {importPlanOpen && current && (
        <ImportDependencyPlan
          project={current}
          onClose={() => setImportPlanOpen(false)}
        />
      )}
      {dialog && (
        <ProjectDialog
          {...{
            setDialog,
            dialog,
            setNewCreating,
            setNewTestError,
            filter,
            setNewTestPreview,
            loadProjects,
            openProject,
            setBundleCreate,
            newTestRequest,
            current,
            setNewTestLoading,
            newTestError,
            newTestLoading,
            newTestPreview,
            value,
            newCreating,
            project,
            snapshot,
            refresh,
            setNotice,
          }}
        />
      )}
    </div>
  );
}
