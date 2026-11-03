import { useEffect, useRef, useState } from "react";
import { api, projectUrl } from "../../shared/api";
import { loadPatternSettings, savePatternSettings } from "./api";
import type {
  ConcernDefinition,
  PatternDefinition,
  PatternSettings,
  PatternSettingsView,
} from "./types";
const risks: Record<string, string> = {
  low: "低",
  normal: "普通",
  high: "高",
  critical: "关键",
};
const feedbacks: Record<string, string> = {
  adopt: "采纳",
  not_needed: "明确无需纳入",
  already_covered: "已经覆盖",
  defer: "暂缓",
  not_applicable: "不适用",
};
export function usePatternManagerController({ project }: { project: string }) {
  const [view, setView] = useState<PatternSettingsView | null>(null),
    [selected, setSelected] = useState(""),
    [riskFilter, setRiskFilter] = useState(""),
    [search, setSearch] = useState(""),
    [msg, setMsg] = useState(""),
    [hist, setHist] = useState<any>(null),
    [text, setText] = useState(""),
    [definitions, setDefinitions] = useState<Record<string, ConcernDefinition>>(
      {},
    ),
    [dirty, setDirty] = useState(false),
    [saving, setSaving] = useState(false);
  const editor = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let live = true;
    setView(null);
    setMsg("");
    setDirty(false);
    setDefinitions({});
    Promise.all([
      loadPatternSettings(project),
      api(projectUrl(project, "recommendation-history")),
    ])
      .then(([v, h]) => {
        if (live) {
          setView(v);
          setSelected(v.settings.library.patterns[0]?.id || "");
          setHist(h);
        }
      })
      .catch((e) => live && setMsg(e.message));
    api<{ registry: { definitions: Record<string, ConcernDefinition> } }>(
      projectUrl(project, "registry"),
    )
      .then((v) => live && setDefinitions(v.registry?.definitions || {}))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [project]);
  useEffect(() => {
    editor.current?.scrollTo?.({ top: 0 });
  }, [selected]);

  const s: PatternSettings = view?.settings || {
    threshold: 0.85,
    top_k: 10,
    risk_weight: 0.7,
    history_weight: 0.3,
    library: { patterns: [] },
    overrides: {},
  };
  const ps = s.library.patterns,
    p = ps.find((r: PatternDefinition) => r.id === selected);
  const edit = (v: Partial<PatternSettings>) => {
    if (!view) return;
    setView({ ...view, settings: { ...s, ...v } });
    setDirty(true);
  };
  const patch = (v: Partial<PatternDefinition>) =>
    edit({
      library: {
        ...s.library,
        patterns: ps.map((r: PatternDefinition) =>
          r.id === selected ? { ...r, ...v, version: r.version + 1 } : r,
        ),
      },
    });
  const risk = (r: PatternDefinition) =>
    s.overrides[r.id]?.risk_level || r.risk_level;
  const filtered = ps.filter(
    (r: PatternDefinition) =>
      (!riskFilter || risk(r) === riskFilter) &&
      [
        r.id,
        r.label,
        ...r.concern_keys.map(
          (k: string) => `${definitions[k]?.label || ""} ${k}`,
        ),
      ]
        .join(" ")
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const concernName = (k: string) => definitions[k]?.label || k;
  async function save() {
    if (!view) return;
    setSaving(true);
    try {
      setView(await savePatternSettings(project, view.version, s));
      setDirty(false);
      setMsg("已保存版本。继续运行后生成新结果；旧报告保留原快照。");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setSaving(false);
    }
  }
  function add() {
    const n: PatternDefinition = {
      ...ps[0],
      concern_keys: ps[0]?.concern_keys || ["api.data.completeness"],
      risk_level: "normal",
      risk_reason: "项目新增模式，待审核适用条件",
      enabled: true,
      id: "custom." + Date.now(),
      label: "新模式",
      selector: null,
      preconditions: ["待填写适用前提"],
      trigger_template: "待填写独立失败条件",
      required_evidence: "明确正常规则",
      version: 1,
    };
    edit({ library: { ...s.library, patterns: [...ps, n] } });
    setSelected(n.id);
  }
  return {
    risks,
    feedbacks,
    view,
    setView,
    selected,
    setSelected,
    riskFilter,
    setRiskFilter,
    search,
    setSearch,
    msg,
    setMsg,
    hist,
    setHist,
    text,
    setText,
    definitions,
    setDefinitions,
    dirty,
    setDirty,
    saving,
    setSaving,
    editor,
    s,
    ps,
    p,
    edit,
    patch,
    risk,
    filtered,
    concernName,
    save,
    add,
  };
}
