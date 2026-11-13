import { useEffect, useState } from "react";
import { api, fileUrl } from "../../../shared/api";
import { getSavedCaseResult, getSavedResultIndex } from "./api";
const labels: Record<string, string> = {
  E: "需求文档已有 E",
  G: "本方法生成 G",
  GT: "独立测试真值 GT",
};
const sourceLabels: Record<string, string> = {
  explicit: "原文明示",
  framework_inferred: "框架推导",
};
function show(value: any): string {
  return value == null
    ? "待确认"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
}
function Evidence({ rows }: { rows: any[] }) {
  return rows?.length ? (
    <details className="result-evidence">
      <summary>原文依据（{rows.length}处）</summary>
      {rows.map((r, i) => (
        <blockquote key={i}>
          <small>
            {r.source_id} · 第{r.line_start}–{r.line_end}行
          </small>
          <p>{r.quote}</p>
        </blockquote>
      ))}
    </details>
  ) : null;
}
function Scenario({
  s,
  defs,
  missing,
  detailUrl,
}: {
  detailUrl: string;
  s: any;
  defs: any;
  missing: boolean;
}) {
  const [full, setFull] = useState<any>(null),
    [loading, setLoading] = useState(false),
    [failure, setFailure] = useState("");
  const detail = full || s;
  async function open(e: React.SyntheticEvent<HTMLDetailsElement>) {
    if (!e.currentTarget.open || !s.lazy_detail || full || loading) return;
    setLoading(true);
    try {
      setFull(await api(detailUrl));
    } catch (e: any) {
      setFailure(e.message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <article className="result-scenario">
      <header>
        <strong>
          {["input_parameters", "authentication", "authorization"].includes(
            s.coverage_kind,
          )
            ? (
                {
                  input_parameters: "输入数据",
                  authentication: "身份认证",
                  authorization: "访问授权",
                } as Record<string, string>
              )[s.coverage_kind] + "（宽泛分支）"
            : defs[s.concern_key]?.label || s.concern_key}
        </strong>
        {missing && <span className="result-missing">文档未覆盖</span>}
      </header>
      <p>
        {s.coverage_description ||
          s.steps?.trigger ||
          s.conditions?.join("；") ||
          s.cause}
      </p>
      <small>
        {s.field || s.object} ·{" "}
        {sourceLabels[s.source_status] || s.source_status}
        {s.source_scenario_id?.startsWith("SUP-") || s.id?.startsWith("SUP-")
          ? " · 独立机器补充测试（自动GT）"
          : ""}
        {s.executable === false ? " · 条件级，尚不可直接执行" : ""}
      </small>
      {s.pattern_id && (
        <small className="scenario-pattern-badge">
          模式 {s.pattern_id} · C={s.confidence?.score} · {s.risk?.level}风险 ·
          关联关注点 {s.concern_origins?.length || 1}项
        </small>
      )}
      <details onToggle={open}>
        <summary>异常步骤与归类依据</summary>
        {loading && <p>正在读取证据…</p>}
        {failure && <p role="alert">{failure}</p>}
        {["input_parameters", "authentication", "authorization"].includes(
          s.coverage_kind,
        ) && (
          <p>
            原记录分类：{defs[detail.concern_key]?.label || detail.concern_key}
            ；本行按原文宽泛分支覆盖展示，未改写原始分类或评分。
          </p>
        )}
        <p>失败原因：{detail.cause}</p>
        <p>
          正常上下文：{detail.steps?.normal_context?.join("；") || "未提供"}
        </p>
        <p>触发条件：{detail.conditions?.join("；") || "未提供"}</p>
        <p>
          原文明示后续：
          {detail.steps?.documented_follow_up
            ?.map((r: any) => (typeof r === "string" ? r : r.action))
            .join("；") || "未明示，不补造"}
        </p>
        <p>{detail.derivation}</p>
        {detail.quality_notes?.map((n: string, index: number) => (
          <p className="quality-note" key={index}>
            {n}
          </p>
        ))}
        <small>
          异常ID：{detail.id}
          {detail.original_branch_id
            ? " · 原分支：" + detail.original_branch_id
            : ""}
        </small>
        <Evidence rows={detail.source_refs} />
      </details>
    </article>
  );
}
export function useSavedResultsController({
  project,
  liveVersion,
}: {
  project: string;
  liveVersion?: string;
}) {
  const [controlsCollapsed, setControlsCollapsed] = useState(
    () => localStorage.getItem("scene-result-controls-collapsed") !== "false",
  );
  const toggleControls = () =>
    setControlsCollapsed((old) => {
      localStorage.setItem("scene-result-controls-collapsed", String(!old));
      return !old;
    });
  const [onlyUnmatched, setOnlyUnmatched] = useState(false);
  const [comparisonLayer, setComparisonLayer] = useState("concerns");
  const [selectedConcern, setSelectedConcern] = useState("");
  const [importId, setImportId] = useState("");
  const [imports, setImports] = useState<
    {
      id: string;
      case: { id: string; name: string };
      scope: string;
      imported_at: string;
    }[]
  >([]);
  const importQuery = importId
    ? "&import_id=" + encodeURIComponent(importId)
    : "";
  const [testSet, setTestSet] = useState("expanded");
  const [evaluationScope, setEvaluationScope] = useState("SR");
  const [index, setIndex] = useState<any>(null),
    [cid, setCase] = useState(""),
    [detail, setDetail] = useState<any>(null),
    [step, setStep] = useState(""),
    [mode, setMode] = useState("steps"),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0);
  const [artifactKey, setArtifact] = useState(""),
    [artifactValue, setArtifactValue] = useState<any>(null),
    [zoom, setZoom] = useState(1);
  useEffect(() => {
    setImportId("");
    setImports([]);
  }, [project]);
  useEffect(() => {
    let live = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    setIndex(null);
    setError("");
    getSavedResultIndex(project, false, importQuery, {
      signal: controller.signal,
    })
      .then((r) => {
        if (live) {
          setIndex(r);
          setImports(r.case_result_imports || []);
          if (r.supplement_tests === false) setTestSet("original");
          if (r.supplement_tests === false && !index) setTestSet("original");
          setCase((c) =>
            r.cases.some((x: any) => x.id === c) ? c : r.cases[0]?.id || "",
          );
        }
      })
      .catch(
        (e) =>
          live &&
          setError(
            e.name === "AbortError"
              ? "结果目录读取超时，请点击刷新重试。"
              : e.message,
          ),
      )
      .finally(() => clearTimeout(timeout));
    return () => {
      live = false;
      clearTimeout(timeout);
      controller.abort();
    };
  }, [project, reload, liveVersion, importQuery]);
  useEffect(() => {
    if (!cid || (mode !== "steps" && !(importId && mode === "recommendations")))
      return;
    let live = true;
    setDetail(null);
    getSavedCaseResult(
      project,
      cid,
      importId ? "original" : testSet,
      evaluationScope,
      importQuery,
    )
      .then((r) => {
        if (live) {
          setDetail(r);
          const target = onlyUnmatched
            ? r.interactions.find((x: any) =>
                x.alignment_rows?.some((a: any) => a.status !== "triple"),
              )
            : null;
          setStep(
            (previous) =>
              target?.interaction.id ||
              (r.interactions.some((x: any) => x.interaction.id === previous)
                ? previous
                : r.interactions[0]?.interaction.id || ""),
          );
        }
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [
    project,
    cid,
    reload,
    testSet,
    evaluationScope,
    liveVersion,
    mode,
    importId,
    importQuery,
  ]);
  useEffect(() => {
    if (importId || !["diagrams", "global"].includes(mode)) return;
    const controller = new AbortController();
    getSavedResultIndex(project, true, "", {
      signal: controller.signal,
    })
      .then((r) =>
        setIndex((old: any) => (old ? { ...old, artifacts: r.artifacts } : r)),
      )
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [project, mode, reload, liveVersion, importId]);
  const catalog =
    index?.artifacts.filter(
      (a: any) => a.case === "shared" || a.case === cid,
    ) || [];
  const artifact =
    catalog.find((a: any) => a.key === artifactKey) || catalog[0];
  useEffect(() => {
    if (mode !== "diagrams" || !artifact) return;
    let live = true;
    setArtifactValue(null);
    setZoom(1);
    const json = artifact.files.find((f: any) => f.name.endsWith(".json"));
    if (json)
      api(fileUrl(project, json.path))
        .then((v) => live && setArtifactValue(v.payload || v))
        .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [project, mode, artifact?.key, reload]);
  const row = detail?.interactions.find((r: any) => r.interaction.id === step),
    i = row?.interaction,
    defs = detail?.definitions || {};
  const diagram = artifact?.files.find((f: any) => f.name.endsWith(".svg"));
  const unresolved =
    detail && Object.values(detail.unbound).some((a: any) => a.length);
  return {
    importId,
    setImportId,
    imports,
    importQuery,
    labels,
    sourceLabels,
    show,
    Evidence,
    Scenario,
    controlsCollapsed,
    setControlsCollapsed,
    toggleControls,
    onlyUnmatched,
    setOnlyUnmatched,
    comparisonLayer,
    setComparisonLayer,
    selectedConcern,
    setSelectedConcern,
    testSet,
    setTestSet,
    evaluationScope,
    setEvaluationScope,
    index,
    setIndex,
    cid,
    setCase,
    detail,
    setDetail,
    step,
    setStep,
    mode,
    setMode,
    error,
    setError,
    reload,
    setReload,
    artifactKey,
    setArtifact,
    artifactValue,
    setArtifactValue,
    zoom,
    setZoom,
    catalog,
    artifact,
    row,
    i,
    defs,
    diagram,
    unresolved,
  };
}
