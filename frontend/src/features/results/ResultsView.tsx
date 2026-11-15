import { setResultEpoch } from "./shared/resultRequests";
import { useCallback, useEffect, useState } from "react";
import { getSsdResultIndex } from "./ssd/api";
import { SsdResultsView } from "./ssd/SsdResultsView";
import { SavedResultsView } from "./saved/SavedResultsView";
import type { SsdReviewSelection } from "../review/SsdReviewHandoff";
import { getProjectResultIndex } from "./project/api";
import { ProjectScopeResultsView } from "./project/ProjectScopeResultsView";
import { ScopeMetricsSummary } from "./project/ScopeMetrics";
import { scopeNames, type AnalysisScope } from "./project/types";
export function ResultsView(props: {
  project: string;
  liveVersion?: string;
  requestedCaseId?: string;
  requestedStepId?: string;
  requestedScope?: AnalysisScope;
  requestedAnchorId?: string;
  onReviewRequest?: (selection: SsdReviewSelection) => void;
  onSelectionChange?: (selection: SsdReviewSelection) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const [modern, setModern] = useState<any>(null),
    [projectIndex, setProjectIndex] = useState<any>(null);
  const [probedProject, setProbedProject] = useState<string | null>(null),
    [source, setSource] = useState("ssd");
  const [scope, setScope] = useState<AnalysisScope | "metrics">(
    props.requestedScope || "interaction",
  );
  const [dirty, setDirty] = useState(false),
    [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [loadError, setLoadError] = useState("");
  const onDirtyChange = useCallback(
    (value: boolean) => {
      setDirty(value);
      props.onDirtyChange?.(value);
    },
    [props.onDirtyChange],
  );
  useEffect(() => {
    setSource("ssd");
    setScope(props.requestedScope || "interaction");
    setNotice("");
  }, [props.project]);
  useEffect(() => {
    if (props.requestedScope && !dirty) {
      setScope(props.requestedScope);
      setSource("ssd");
    }
  }, [props.requestedScope, props.requestedAnchorId]);
  useEffect(() => {
    if (dirty) return;
    let live = true;
    let foundCurrent = false;
    const failures: string[] = [];
    setLoadError("");
    setResultEpoch(props.project, props.liveVersion);
    let settled = 0;
    const ready = () => {
      if (live && ++settled === 2) {
        if (!foundCurrent && failures.length)
          setLoadError("结果加载失败，请重试；未切换到历史报告。");
        setProbedProject(props.project);
      }
    };
    getSsdResultIndex(props.project)
      .then((value) => {
        if (!live) return;
        const current = value?.version === "ssd-case-v1" && value.cases?.length;
        setModern(current ? { project: props.project, index: value } : null);
        if (current) {
          foundCurrent = true;
          setProbedProject(props.project);
        }
      })
      .catch((e) => {
        failures.push(String(e));
      })
      .finally(ready);
    getProjectResultIndex(props.project)
      .then((value) => {
        if (!live) return;
        const current = value?.version === "project-scopes-v1";
        setProjectIndex(
          current ? { project: props.project, index: value } : null,
        );
        if (
          current &&
          scope !== "interaction" &&
          value.scopes?.some(
            (s: any) => s.available !== false && s.revision != null,
          )
        ) {
          foundCurrent = true;
          setProbedProject(props.project);
        }
      })
      .catch((e) => {
        failures.push(String(e));
      })
      .finally(ready);
    return () => {
      live = false;
    };
  }, [props.project, props.liveVersion, revision, dirty]);
  if (probedProject !== props.project)
    return <p role="status">正在加载结果来源…</p>;
  if (loadError)
    return (
      <p role="alert">
        {loadError}
        <button onClick={() => setRevision((v) => v + 1)}>重试</button>
      </p>
    );
  const hasSsd = modern?.project === props.project;
  const projectData =
    projectIndex?.project === props.project ? projectIndex.index : null;
  const available = (projectData?.scopes || []).filter(
    (item: any) =>
      item.available !== false && (item.revision != null || item.anchor_count),
  );
  const hasCurrent = hasSsd || available.length > 0;
  const activeScope =
    scope === "interaction" && !hasSsd && available.length
      ? available[0].id
      : scope;
  const resultSourceControl = hasCurrent ? (
    <>
      <label>
        结果视图
        <select
          aria-label="结果视图来源"
          value={source}
          onChange={(event) => {
            if (dirty) {
              setNotice("当前修改尚未保存，请先保存或放弃修改再切换结果来源。");
              return;
            }
            setSource(event.target.value);
            setNotice("");
          }}
        >
          <option value="ssd">当前结果与修订</option>
          <option value="saved">历史工作流 / Code Agent 报告（只读）</option>
        </select>
      </label>
      {notice && <span role="status">{notice}</span>}
    </>
  ) : undefined;
  if (!hasCurrent || source === "saved")
    return (
      <SavedResultsView {...props} resultSourceControl={resultSourceControl} />
    );
  const navigation = (
    <div
      className="results-area-nav view-segments"
      role="tablist"
      aria-label="结果统计范围"
    >
      {(
        ["interaction", "business_chain", "architecture", "metrics"] as const
      ).map((area) => (
        <button
          key={area}
          role="tab"
          aria-selected={activeScope === area}
          className={activeScope === area ? "active" : ""}
          onClick={() => {
            if (dirty) {
              setNotice("当前修改尚未保存，请先保存或放弃修改再切换分析范围。");
              return;
            }
            setScope(area);
            setNotice("");
          }}
        >
          {area === "metrics" ? "项目指标" : scopeNames[area]}
        </button>
      ))}
    </div>
  );
  if (activeScope === "metrics")
    return (
      <ScopeMetricsSummary
        index={
          projectData || {
            metrics: {
              by_scope: {
                interaction: {
                  ...modern?.index.metrics_by_level,
                  available: hasSsd,
                  complete: modern?.index.complete,
                },
              },
            },
          }
        }
        sourceControl={resultSourceControl}
        navigation={navigation}
      />
    );
  if (activeScope === "business_chain" || activeScope === "architecture")
    return (
      <ProjectScopeResultsView
        key={`${props.project}:${activeScope}`}
        {...props}
        scope={activeScope}
        navigation={navigation}
        sourceControl={resultSourceControl}
        onDirtyChange={onDirtyChange}
        onUpdated={() => setRevision((value) => value + 1)}
      />
    );
  return hasSsd ? (
    <SsdResultsView
      key={props.project}
      {...props}
      initialIndex={modern.index}
      onDirtyChange={onDirtyChange}
      resultSourceControl={resultSourceControl}
      scopeNavigation={navigation}
    />
  ) : (
    <div className="management-view results-view">
      {navigation}
      <div className="results-compact-controls">{resultSourceControl}</div>
      <p className="management-loading">当前尚无交互级结果。</p>
    </div>
  );
}
