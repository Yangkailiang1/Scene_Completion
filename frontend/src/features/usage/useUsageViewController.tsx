import { useEffect, useState } from "react";
import { api, projectUrl } from "../../shared/api";
const number = (n: number | undefined) => (n || 0).toLocaleString();
const cache = new Map<string, { at: number; data: any }>();
export function useUsageViewController({
  project,
  task,
}: {
  project: string;
  task: string | null;
  onClose: () => void;
  onSelect: (key: string) => void;
}) {
  const [throughputOpen, setThroughputOpen] = useState(false);
  const [session, setSession] = useState(""),
    [account, setAccount] = useState("");
  const [sort, setSort] = useState("tokens");
  const [view, setView] = useState("tasks"),
    [scope, setScope] = useState(task || ""),
    [role, setRole] = useState(""),
    [model, setModel] = useState(""),
    [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0),
    [data, setData] = useState<any>(null),
    [summary, setSummary] = useState<any>(null),
    [context, setContext] = useState<any>(null),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0),
    [round, setRound] = useState("");
  useEffect(() => {
    setScope(task || "");
    setData(null);
    setOffset(0);
    setContext(null);
    setSession("");
  }, [project, task]);
  useEffect(() => {
    setSummary(null);
    const controller = new AbortController();
    api(projectUrl(project, "usage"), { signal: controller.signal })
      .then(setSummary)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [project, reload]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const p = new URLSearchParams({
        view,
        sort,
        offset: String(offset),
        limit: "50",
        search: query,
      });
      if (account) p.set("account", account);
      if (session) p.set("session_id", session);
      if (scope) p.set("task_key", scope);
      if (role) p.set("role", role);
      if (model) p.set("model", model);
      if (round) p.set("after", round);
      const url = projectUrl(project, "usage?" + p.toString()),
        saved = cache.get(url);
      if (saved && Date.now() - saved.at < 5000 && !reload) {
        setData(saved.data);
        return;
      }
      api(url, { signal: controller.signal })
        .then((d) => {
          cache.set(url, { at: Date.now(), data: d });
          setData(d);
          setError("");
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
    }, 180);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    project,
    view,
    sort,
    scope,
    role,
    model,
    query,
    offset,
    reload,
    round,
    session,
    account,
  ]);
  useEffect(() => {
    const timer = setInterval(() => {
      if (!document.hidden) setReload((v) => v + 1);
    }, 15000);
    return () => clearInterval(timer);
  }, [project]);
  const totals = data?.totals || summary?.totals || {};
  function filter(fn: () => void) {
    fn();
    setOffset(0);
    setContext(null);
  }
  return {
    number,
    cache,
    throughputOpen,
    setThroughputOpen,
    session,
    setSession,
    account,
    setAccount,
    sort,
    setSort,
    view,
    setView,
    scope,
    setScope,
    role,
    setRole,
    model,
    setModel,
    query,
    setQuery,
    offset,
    setOffset,
    data,
    setData,
    summary,
    setSummary,
    context,
    setContext,
    error,
    setError,
    reload,
    setReload,
    round,
    setRound,
    totals,
    filter,
  };
}
