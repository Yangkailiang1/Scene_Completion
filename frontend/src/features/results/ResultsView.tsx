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
  const [sharedMode, setSharedMode] = useState(
    props.requestedScope === "shared_services",
  );
  const [legacyScope, setLegacyScope] = useState<
    "business_chain" | "architecture"
  >("business_chain");
  const [modern, setModern] = useState<any>(null),
    [projectIndex, setProjectIndex] = useState<any>(null);
  const [probedProject, setProbedProject] = useState<string | null>(null),
    [source, setSource] = useState("ssd");
  const [scope, setScope] = useState<AnalysisScope | "metrics">("interaction");
  const [dirty, setDirty] = useState(false),
    [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [jump, setJump] = useState<{ caseId: string; stepId?: string } | null>(
    null,
  );
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
    setScope("interaction");
    setSharedMode(props.requestedScope === "shared_services");
    setJump(null);
    setNotice("");
  }, [props.project]);
  useEffect(() => {
    if (props.requestedScope && !dirty) {
      setScope("interaction");
      setSharedMode(props.requestedScope === "shared_services");
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
  const hasCurrent =
    hasSsd || available.length > 0 || !!projectData?.legacy_scopes?.length;
  const activeScope = scope === "metrics" ? "metrics" : "interaction";
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
            if (event.target.value === "legacy") {
              setScope("interaction");
              if (!projectData?.legacy_scopes?.includes(legacyScope))
                setLegacyScope(projectData.legacy_scopes[0]);
            }
            setNotice("");
          }}
        >
          <option value="ssd">当前结果与修订</option>
          <option value="saved">历史工作流 / Code Agent 报告（只读）</option>
          {!!projectData?.legacy_scopes?.length && (
            <option value="legacy">历史业务链路／架构结果（只读）</option>
          )}
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
      {(["interaction", "metrics"] as const).map((area) => (
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
  if (source === "legacy")
    return (
      <ProjectScopeResultsView
        key={props.project + legacyScope}
        {...props}
        scope={legacyScope}
        forceReadonly
        navigation={
          <>
            {navigation}
            <label>
              历史范围
              <select
                aria-label="历史项目范围"
                value={legacyScope}
                onChange={(e) => setLegacyScope(e.target.value as any)}
              >
                {(projectData?.legacy_scopes || []).map((s: any) => (
                  <option key={s} value={s}>
                    {scopeNames[s as AnalysisScope]}
                  </option>
                ))}
              </select>
            </label>
          </>
        }
        sourceControl={resultSourceControl}
      />
    );
  const interactionNav = (
    <>
      {navigation}
      <div
        className="results-subnav view-segments"
        role="group"
        aria-label="交互结果分类"
      >
        <button
          aria-pressed={!sharedMode}
          onClick={() => {
            if (dirty) {
              setNotice("请先保存或放弃草稿。");
              return;
            }
            setSharedMode(false);
          }}
        >
          用例交互
        </button>
        <button
          aria-pressed={sharedMode}
          onClick={() => {
            if (dirty) {
              setNotice("请先保存或放弃草稿。");
              return;
            }
            setSharedMode(true);
          }}
        >
          共用外部服务
        </button>
      </div>
    </>
  );
  if (sharedMode || (!hasSsd && available.length))
    return (
      <ProjectScopeResultsView
        key={`${props.project}:shared_services`}
        {...props}
        scope="shared_services"
        navigation={interactionNav}
        sourceControl={resultSourceControl}
        onNavigateCase={(caseId, stepId) => {
          if (dirty) {
            setNotice("请先保存或放弃草稿。");
            return;
          }
          setSharedMode(false);
          setJump({ caseId, stepId });
        }}
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
      scopeNavigation={interactionNav}
      requestedCaseId={jump?.caseId || props.requestedCaseId}
      requestedStepId={jump?.stepId || props.requestedStepId}
    />
  ) : (
    <div className="management-view results-view">
      {navigation}
      <div className="results-compact-controls">{resultSourceControl}</div>
      <p className="management-loading">当前尚无交互级结果。</p>
    </div>
  );
}
