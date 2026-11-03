import { useEffect, useRef, useState } from "react";
import { api, fileUrl, primaryJsonArtifact, projectUrl } from "../shared/api";
import type {
  ExecutionEvent,
  Graph,
  Project,
  Review,
  Snapshot,
} from "../shared/types";
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
export function useAppController() {
  const [newTestPreview, setNewTestPreview] = useState<any>(null);
  const [newTestError, setNewTestError] = useState("");
  const [newTestLoading, setNewTestLoading] = useState(false);
  const [newCreating, setNewCreating] = useState(false);
  const [bundleCreate, setBundleCreate] = useState(false);
  const [importPlanOpen, setImportPlanOpen] = useState(false);
  const newTestRequest = useRef(0);
  const [management, setManagement] = useState<
    | "pending"
    | "concerns"
    | "results"
    | "patterns"
    | "recommendations"
    | "handoff"
    | "imports"
    | null
  >(null);
  const jobStatusRef = useRef("ready");
  const [usageOpen, setUsageOpen] = useState(false),
    [usageTask, setUsageTask] = useState<string | null>(null);
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
  const managementRef = useRef(management),
    refreshBusy = useRef(new Set<string>());
  managementRef.current = management;
  currentRef.current = current;
  selectedRef.current = selected;
  const project = current ? projects.find((p) => p.id === current) : null,
    node = graph.nodes.find((n) => n.id === selected),
    running = snapshot?.job.status === "running";
  const error = (e: any) =>
    setNotice(e instanceof Error ? e.message : String(e));
  useEffect(() => {
    if (dialog === "new") {
      newTestRequest.current += 1;
      setNewTestPreview(null);
      setNewTestError("");
      setNewTestLoading(false);
    }
  }, [dialog]);
  async function loadProjects() {
    const list = await api<Project[]>("/api/projects");
    setProjects(list);
    return list;
  }
  async function refresh(id = currentRef.current) {
    if (!id) return;
    if (refreshBusy.current.has(id)) return;
    refreshBusy.current.add(id);
    try {
      const compact = managementRef.current !== null;
      const s = await api<Snapshot & { compact?: boolean }>(
        projectUrl(id) + (compact ? "?compact=true" : ""),
      );
      if (currentRef.current !== id) return;
      jobStatusRef.current = s.job.status;
      setSnapshot((old) =>
        s.compact && old
          ? { ...old, project: s.project, job: s.job, manifest: s.manifest }
          : s,
      );
      if (!compact) {
        const g = await api<Graph>(projectUrl(id, "graph"));
        if (currentRef.current === id) setGraph(g);
      }
    } finally {
      refreshBusy.current.delete(id);
    }
  }
  useEffect(() => {
    if (current) refresh(current).catch(error);
  }, [management]);
  useEffect(() => {
    loadProjects()
      .then((list) => {
        const saved = localStorage.getItem("scene-selected-project");
        if (saved && list.some((p) => p.id === saved)) openProject(saved);
      })
      .catch(error);
  }, []);
  function openProject(id: string) {
    jobStatusRef.current = "ready";
    setManagement(null);
    setUsageOpen(false);
    setUsageTask(null);
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
    api(projectUrl(id, "registry"))
      .then((r) => setDefinitions(r.registry?.definitions || {}))
      .catch(error);
  }
  function selectNode(id: string) {
    setManagement(null);
    setUsageOpen(false);
    selectedRef.current = id;
    setSelected(id);
    const target = graph.nodes.find((n) => n.id === id);
    setTab(
      target && ["passed", "awaiting_review"].includes(target.status)
        ? "artifacts"
        : "stream",
    );
    setGraphMaximized(false);
    dirty.current = false;
    setReview(null);
    setValue(null);
    setEvents([]);
  }
  useEffect(() => {
    if (
      !current ||
      !snapshot ||
      ["complete", "complete_with_questions"].includes(snapshot.job.status)
    )
      return;
    const id = current;
    const cursor = sessionStorage.getItem("scene-cursor-" + id) || "0";
    const source = new EventSource(
      projectUrl(id, "events?after=" + cursor + "&tail=1"),
    );
    source.addEventListener("cursor", (message) => {
      sessionStorage.setItem(
        "scene-cursor-" + id,
        String(JSON.parse((message as MessageEvent).data).id),
      );
    });
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
    const poll = setInterval(() => {
      if (
        !["complete", "complete_with_questions"].includes(
          jobStatusRef.current,
        ) &&
        !document.hidden
      )
        refresh(id).catch(() => {});
    }, 4000);
    return () => {
      source.close();
      clearInterval(flush);
      clearInterval(poll);
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      refreshTimer.current = null;
      buffer.current = [];
      setStreamConnected(false);
    };
  }, [
    current,
    !!snapshot,
    ["complete", "complete_with_questions"].includes(
      snapshot?.job.status || "",
    ),
  ]);
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
        const file = primaryJsonArtifact(artifacts);
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
    const held =
      snapshot?.job.status === "paused" ||
      snapshot?.job.reason === "user_stop" ||
      snapshot?.job.reason === "user_pause" ||
      ["paused", "stopped"].includes(snapshot?.job.control_state || "");
    const response = await api<any>(
      projectUrl(current, held ? "execution-control" : "run"),
      {
        method: "POST",
        body: held ? JSON.stringify({ action: "resume" }) : "{}",
      },
    );
    if (response.project_id && response.project_id !== current) {
      await loadProjects();
      openProject(response.project_id);
      return;
    }
    await refresh();
  }
  async function controlRun(action: "pause" | "stop") {
    if (!current) return;
    const response = await api(projectUrl(current, "execution-control"), {
      method: "POST",
      body: JSON.stringify({ action }),
    });
    setNotice(response.message || "执行控制已保存，成功产物保留");
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
  return {
    emptyGraph,
    mergeEvents,
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
    jobStatusRef,
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
    setProjects,
    current,
    setCurrent,
    snapshot,
    setSnapshot,
    graph,
    setGraph,
    collapsed,
    setCollapsed,
    selected,
    setSelected,
    tab,
    setTab,
    versions,
    setVersions,
    review,
    setReview,
    value,
    setValue,
    editor,
    setEditor,
    comment,
    setComment,
    events,
    setEvents,
    loading,
    setLoading,
    notice,
    setNotice,
    dialog,
    setDialog,
    definitions,
    setDefinitions,
    streamConnected,
    setStreamConnected,
    filter,
    setFilter,
    currentRef,
    selectedRef,
    dirty,
    refreshTimer,
    buffer,
    managementRef,
    refreshBusy,
    project,
    node,
    running,
    error,
    loadProjects,
    refresh,
    openProject,
    selectNode,
    reviewHeader,
    artifacts,
    start,
    controlRun,
    decide,
    formalArtifacts,
    visibleArtifacts,
    docs,
    collect,
    activeNodes,
    failedNodes,
    pendingReviews,
  };
}
