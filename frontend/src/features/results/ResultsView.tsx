import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Download,
  FileStack,
  RefreshCw,
} from "lucide-react";
import { fileUrl, projectUrl } from "../../shared/api";
import { RecommendationsView } from "../patterns/PatternManager";
import { QualityDiagnostics } from "../quality/QualityDiagnostics";
import { TestSources } from "../sources/TestSources";
import { ArtifactView } from "./ArtifactView";
import { GlobalResults, ProjectMetrics } from "./GlobalResults";
import {
  AlignmentTable,
  ConcernAlignmentTable,
  MetricsPanel,
} from "./ResultComparison";
import { useResultsViewController } from "./useResultsViewController";
export function ResultsView({
  project,
  liveVersion,
}: {
  project: string;
  liveVersion?: string;
}) {
  const {
    labels,
    show,
    Evidence,
    Scenario,
    controlsCollapsed,
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
    cid,
    setCase,
    detail,
    step,
    setStep,
    mode,
    setMode,
    error,
    reload,
    setReload,
    setArtifact,
    artifactValue,
    zoom,
    setZoom,
    catalog,
    artifact,
    row,
    i,
    defs,
    diagram,
    unresolved,
  } = useResultsViewController({ project, liveVersion });
  const [resultArea, setResultArea] = useState<"case" | "global" | "project">(
    "case",
  );
  const [caseMode, setCaseMode] = useState("steps");
  const caseViews = [
    ["steps", "交互对照"],
    ["metrics", "本用例指标"],
    ["diagrams", "用例图表"],
    ["tests", "测试场景"],
    ["recommendations", "风险推荐"],
    ["quality", "用例诊断"],
  ];
  const projectViews = [
    ["project", "项目总指标"],
    ["metrics", "交互级汇总"],
  ];
  function changeArea(area: "case" | "global" | "project") {
    setResultArea(area);
    setMode(area === "case" ? caseMode : area);
  }
  function chooseMode(next: string) {
    setMode(next);
    if (resultArea === "case") setCaseMode(next);
  }
  return (
    <div className="management-view results-view">
      <div
        className="results-area-nav view-segments"
        role="tablist"
        aria-label="结果统计范围"
      >
        {(
          [
            ["case", "用例结果"],
            ["global", "全局业务分析"],
            ["project", "项目指标"],
          ] as const
        ).map(([area, label]) => (
          <button
            key={area}
            role="tab"
            aria-selected={resultArea === area}
            className={resultArea === area ? "active" : ""}
            onClick={() => changeArea(area)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="results-compact-controls" aria-label="结果快捷控制">
        {resultArea === "case" && (
          <select
            aria-label="结果用例"
            value={cid}
            onChange={(e) => setCase(e.target.value)}
          >
            <option value="" disabled>
              选择用例
            </option>
            {index?.cases.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.id} · {c.name}
              </option>
            ))}
          </select>
        )}
        {resultArea !== "global" && (
          <select
            aria-label="当前范围视图"
            value={mode}
            onChange={(e) => chooseMode(e.target.value)}
          >
            {(resultArea === "case" ? caseViews : projectViews).map(
              ([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ),
            )}
          </select>
        )}
        <span className="results-compact-description">
          {index?.historical
            ? "历史保存报告"
            : index?.complete
              ? "本轮已完成"
              : "本轮部分结果"}
          {" · "}
          {testSet === "business"
            ? "业务审核后GT"
            : testSet === "expanded"
              ? "扩展异常测试场景"
              : "原始异常测试场景"}
        </span>
        <button
          onClick={toggleControls}
          aria-expanded={!controlsCollapsed}
          aria-controls="results-main-controls"
        >
          {controlsCollapsed ? (
            <ChevronDown size={14} />
          ) : (
            <ChevronUp size={14} />
          )}
          {controlsCollapsed ? "展开工具栏" : "收起工具栏"}
        </button>
      </div>
      <div
        id="results-main-controls"
        className="results-toolbar"
        hidden={controlsCollapsed}
      >
        <div
          className="view-segments results-view-tabs"
          role="navigation"
          aria-label="当前范围结果视图"
        >
          {(resultArea === "case"
            ? caseViews
            : resultArea === "project"
              ? projectViews
              : []
          ).map(([key, label]) => (
            <button
              key={key}
              className={mode === key ? "active" : ""}
              onClick={() => chooseMode(key)}
            >
              {label}
            </button>
          ))}
        </div>
        {resultArea !== "global" && (
          <label className="results-truth-picker">
            <span>交互接口范围</span>
            <select
              aria-label="指标接口层级"
              value={evaluationScope}
              onChange={(e) => setEvaluationScope(e.target.value)}
            >
              <option value="SR">仅SR接口及内部交互</option>
              <option value="RR">仅RR接口</option>
              <option value="all">RR＋SR全部</option>
            </select>
          </label>
        )}
        <label className="results-truth-picker">
          <span>评测依据</span>
          <select
            aria-label="结果测试集"
            value={testSet}
            onChange={(e) => setTestSet(e.target.value)}
          >
            <option value="original">原始异常测试场景</option>
            <option value="expanded">扩展异常测试场景</option>
            <option value="business">业务审核后GT（扩展＋人工增补）</option>
          </select>
        </label>
        <small>报告版本：{index?.matching_version || "尚无报告"}</small>
        <button
          className="results-refresh"
          onClick={() => setReload((x) => x + 1)}
        >
          <RefreshCw size={14} />
          刷新
        </button>
      </div>
      {error && (
        <div role="alert" className="management-notice">
          {error}
        </div>
      )}
      {mode === "global" ? (
        <GlobalResults
          project={project}
          testSet={testSet}
          liveVersion={String(liveVersion || "") + ":" + reload}
          artifacts={index?.artifacts || []}
        />
      ) : mode === "project" ? (
        <ProjectMetrics
          scope={evaluationScope}
          project={project}
          testSet={testSet}
          liveVersion={String(liveVersion || "") + ":" + reload}
        />
      ) : mode === "quality" ? (
        <QualityDiagnostics
          project={project}
          caseId={cid}
          testSet={testSet}
          caseLocked
        />
      ) : mode === "recommendations" ? (
        <RecommendationsView project={project} caseId={cid} testSet={testSet} />
      ) : mode === "tests" ? (
        <TestSources project={project} />
      ) : !index ? (
        <p className="management-loading">
          {error ? "目录未能载入，请点击上方刷新重试。" : "正在读取结果目录…"}
        </p>
      ) : !index.cases.length ? (
        <p className="management-loading">用例对应完成后显示结果。</p>
      ) : mode === "metrics" ? (
        <MetricsPanel
          caseId={resultArea === "case" ? cid : undefined}
          liveVersion={String(liveVersion || "") + ":" + reload}
          scope={evaluationScope}
          project={project}
          testSet={testSet}
          onCase={(id) => {
            setResultArea("case");
            setCaseMode("steps");
            setCase(id);
            setMode("steps");
            setOnlyUnmatched(true);
            if (id === cid && detail) {
              const target = detail.interactions.find((x: any) =>
                x.alignment_rows?.some((a: any) => a.status !== "triple"),
              );
              if (target) setStep(target.interaction.id);
            }
          }}
        />
      ) : mode === "diagrams" ? (
        <div className="results-diagrams">
          <div className="results-diagram-controls" hidden={controlsCollapsed}>
            <label className="results-artifact-picker">
              <span>
                <FileStack size={14} aria-hidden="true" />
                当前图表 / 产物
              </span>
              <select
                aria-label="结果图表"
                value={artifact?.key || ""}
                onChange={(e) => setArtifact(e.target.value)}
              >
                {catalog.map((a: any) => (
                  <option key={a.key} value={a.key}>
                    {a.case === "shared" ? "项目共享" : cid} · {a.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="results-file-actions" aria-label="下载当前产物">
              {artifact?.files.map((f: any) => (
                <a
                  key={f.path}
                  aria-label={"下载" + f.name.split(".").pop()?.toUpperCase()}
                  title={"下载 " + f.name}
                  href={fileUrl(project, f.path)}
                  download={f.name}
                >
                  <Download size={14} aria-hidden="true" />
                  {f.name.split(".").pop()?.toUpperCase()}
                </a>
              ))}
            </div>
            {diagram && (
              <label className="results-zoom-picker">
                <span>图形显示</span>
                <select
                  aria-label="图形缩放"
                  value={zoom}
                  onChange={(e) => setZoom(Number(e.target.value))}
                >
                  <option value={1}>适应宽度</option>
                  <option value={2}>放大2倍</option>
                  <option value={4}>放大4倍</option>
                </select>
              </label>
            )}
          </div>
          {diagram ? (
            <div className="results-diagram-canvas">
              <img
                alt={artifact.label}
                src={fileUrl(project, diagram.path)}
                style={{ width: `${zoom * 100}%`, maxWidth: "none" }}
              />
            </div>
          ) : artifactValue ? (
            <div className="results-table">
              <ArtifactView
                key={artifact.key}
                projectId={project}
                artifacts={artifact.files}
                value={artifactValue}
                definitions={defs}
                taskKey={artifact.key}
              />
            </div>
          ) : (
            <p className="management-loading">
              {catalog.length ? "正在读取图表…" : "暂无已保存图表"}
            </p>
          )}
        </div>
      ) : !detail ? (
        <p className="management-loading">正在读取本用例…</p>
      ) : (
        <div className="results-step-body">
          <aside className="results-step-list" aria-label="结果交互步骤">
            {detail.interactions.map((r: any) => {
              const x = r.interaction;
              return (
                <button
                  key={x.id}
                  className={step === x.id ? "active" : ""}
                  onClick={() => {
                    setStep(x.id);
                    setSelectedConcern("");
                  }}
                >
                  <small>
                    步骤{x.sequence} · {x.id} ·{" "}
                    {x.direction === "return" ? "返回" : "请求"}
                  </small>
                  <strong>{x.operation.name}</strong>
                  <span>
                    {x.sender.name} → {x.receiver.name}
                  </span>
                  <small>
                    场景 E {r.channels.E.length} · G {r.channels.G.length} · GT{" "}
                    {r.channels.GT.length}
                    {detail.matching_version && (
                      <> · 关注点 {(r.concern_rows || []).length}</>
                    )}
                  </small>
                </button>
              );
            })}
            {unresolved && (
              <details>
                <summary>尚未绑定到展示交互的异常</summary>
                {Object.entries(detail.unbound).map(([k, v]) => (
                  <p key={k}>
                    {labels[k]}：{(v as any[]).length}条
                  </p>
                ))}
                <pre>{JSON.stringify(detail.unbound, null, 2)}</pre>
              </details>
            )}
          </aside>
          <section className="results-reading">
            {!i ? (
              <p>本用例的交互尚未保存。</p>
            ) : (
              <>
                <div className="results-step-meta">
                  <strong>
                    步骤{i.sequence} · {i.id}
                  </strong>
                  <span>
                    {i.layer} · {i.direction === "return" ? "返回" : "请求"}
                    {i.parent_id ? " · 展开自 " + i.parent_id : ""}
                  </span>
                </div>
                {evaluationScope !== "all" &&
                  row?.metric_in_scope === false && (
                    <p className="result-metric-note">
                      此交互仍可查看；
                      {row.interface_source_layer
                        ? `实际接口属于 ${row.interface_source_layer}`
                        : "接口归属待确认"}
                      ，不进入当前 {evaluationScope} 指标分母。
                    </p>
                  )}
                <div className="interaction-four">
                  <div>
                    <small>发送方</small>
                    <strong>{i.sender.name}</strong>
                    <p>{i.sender.position}</p>
                  </div>
                  <div>
                    <small>操作</small>
                    <strong>{i.operation.name}</strong>
                    {i.operation.sequence?.length > 0 && (
                      <p>操作序列：{i.operation.sequence.join(" → ")}</p>
                    )}
                    {i.operation.optional?.length > 0 && (
                      <p>可选操作：{i.operation.optional.join("、")}</p>
                    )}
                  </div>
                  <div>
                    <small>数据</small>
                    <strong>
                      {i.data.sequence.map((p: any) => p.name).join("、") ||
                        "未明示数据"}
                    </strong>
                    <p>{i.api_id ? "接口 " + i.api_id : "未关联具体接口"}</p>
                  </div>
                  <div>
                    <small>接收方</small>
                    <strong>{i.receiver.name}</strong>
                    <p>{i.receiver.position}</p>
                  </div>
                </div>
                <details className="result-data">
                  <summary>数据属性、交互双方关注点及原文依据</summary>
                  {i.source_views?.length > 1 && (
                    <details>
                      <summary>同一次交互的RR/SR来源（统一计分）</summary>
                      {i.source_views.map((v: any) => (
                        <p key={v.id}>
                          {v.layer} · {v.id} · {v.operation} ·{" "}
                          {v.api_id || "未单独关联API"}
                        </p>
                      ))}
                    </details>
                  )}
                  <p className="muted">
                    {i.associated_api
                      ? `已关联接口 ${i.associated_api} · ${i.direction === "return" ? "成功响应字段" : "请求字段"}`
                      : "接口尚未唯一关联：仅展示SSD明确属性，未知项保持待确认"}
                    {
                      "。失败响应分支请在图表总览的接口参数表中查看；历史指标未因属性展示更新而重算。"
                    }
                  </p>
                  <div className="result-data-scroll">
                    <table>
                      <thead>
                        <tr>
                          {[
                            "数据",
                            "位置",
                            "类型",
                            "必填／可选",
                            "默认值",
                            "约束",
                          ].map((t) => (
                            <th key={t}>{t}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {i.data.sequence.map((p: any, n: number) => (
                          <tr key={n}>
                            <td>{p.name}</td>
                            <td>{p.location}</td>
                            <td>{show(p.data_type)}</td>
                            <td>
                              {p.required === true
                                ? "必填"
                                : p.required === false
                                  ? "可选"
                                  : "待确认"}
                            </td>
                            <td>{show(p.default)}</td>
                            <td>
                              {p.constraints
                                ?.map((c: any) => `${c.kind}：${show(c.value)}`)
                                .join("；") || "未明示"}
                              {(i.parameter_requirement_sources || [])
                                .filter(
                                  (r: any) =>
                                    r.name === p.name &&
                                    r.location === p.location,
                                )
                                .map((r: any) => (
                                  <details key={r.location + r.name}>
                                    <summary>
                                      要求来源（{r.sources.length}）
                                    </summary>
                                    {r.sources.map((s: any, j: number) => (
                                      <div key={j} className="muted">
                                        <strong>{s.origin}</strong> · 类型{" "}
                                        {show(s.data_type)} · 必填{" "}
                                        {show(s.required)} · 默认值{" "}
                                        {show(s.default)}
                                        {(s.source_refs || []).map(
                                          (ref: any, k: number) => (
                                            <blockquote key={k}>
                                              {ref.quote}
                                            </blockquote>
                                          ),
                                        )}
                                      </div>
                                    ))}
                                  </details>
                                ))}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {["sender", "receiver"].map((k) => (
                    <p key={k}>
                      {k === "sender" ? "发送方" : "接收方"}适用关注点：
                      {(i[k].concerns || [])
                        .filter((c: any) => c.status === "applicable")
                        .map(
                          (c: any) =>
                            defs[c.concern_key]?.label || c.concern_key,
                        )
                        .filter(
                          (v: string, n: number, a: string[]) =>
                            a.indexOf(v) === n,
                        )
                        .join("、") || "暂无已确认项"}
                    </p>
                  ))}
                  <Evidence rows={i.source_refs} />
                </details>
                <div className="comparison-layer-toolbar">
                  <div
                    className="view-segments"
                    role="group"
                    aria-label="匹配层级"
                  >
                    <button
                      className={comparisonLayer === "concerns" ? "active" : ""}
                      onClick={() => {
                        setComparisonLayer("concerns");
                        setSelectedConcern("");
                      }}
                    >
                      关注点层
                    </button>
                    <button
                      className={
                        comparisonLayer === "scenarios" ? "active" : ""
                      }
                      onClick={() => setComparisonLayer("scenarios")}
                    >
                      场景层
                    </button>
                  </div>
                  <p>
                    {comparisonLayer === "concerns"
                      ? "先识别关注点，再按统一四要素标识规则匹配"
                      : "一个关注点可有多个独立失败场景；按具体条件匹配与推荐"}
                  </p>
                  {selectedConcern && (
                    <button onClick={() => setSelectedConcern("")}>
                      清除关注点筛选
                    </button>
                  )}
                </div>
                {!detail.matching_version && (
                  <p className="management-notice">
                    当前为历史场景结果，尚无新版独立关注点识别；请继续运行生成新版结果。旧场景不反推为关注点层G。
                  </p>
                )}
                {detail.recognition_outdated && (
                  <p className="management-notice">
                    当前展示的是修订前的冻结结果，尚未按新的字段识别和对象定位规则重验。历史指标保持原值；请勿将此表视为修复后的结果。
                  </p>
                )}
                <label className="alignment-filter">
                  <input
                    type="checkbox"
                    checked={onlyUnmatched}
                    onChange={(e) => setOnlyUnmatched(e.target.checked)}
                  />
                  只看未完整对应／冲突项
                </label>
                {row.recognition_summary?.applicable > 0 &&
                  row.channels.G.length === 0 && (
                    <p className="management-notice">
                      本步骤已有已确认关注点，但尚无生成场景；关注点识别与场景展开分别记录，不将场景缺口显示为未识别。
                    </p>
                  )}
                {comparisonLayer === "concerns" && row.recognition_summary && (
                  <details className="management-notice">
                    <summary>
                      本方法识别状态：已确认{" "}
                      {row.recognition_summary.applicable} 项 ，待确认{" "}
                      {row.recognition_summary.pending.length} 项 ，不适用{" "}
                      {row.recognition_summary.not_applicable} 项 · 点击查看原因
                    </summary>
                    {row.recognition_summary.note && (
                      <p>{row.recognition_summary.note}</p>
                    )}
                    {row.recognition_summary.pending.map(
                      (item: any, n: number) => (
                        <p key={n}>
                          <strong>{item.object}</strong> ·{" "}
                          {defs[item.concern_key]?.label || item.concern_key}：
                          {item.reason}
                        </p>
                      ),
                    )}
                  </details>
                )}
                {comparisonLayer === "concerns" && detail.matching_version ? (
                  <ConcernAlignmentTable
                    rows={row.concern_rows || []}
                    definitions={defs}
                    onlyUnmatched={onlyUnmatched}
                    truthReady={detail.concern_truth_ready}
                    onSelect={(id) => {
                      setSelectedConcern(id);
                      setComparisonLayer("scenarios");
                    }}
                  />
                ) : (
                  <AlignmentTable
                    rows={(row.alignment_rows || []).filter(
                      (r: any) =>
                        !selectedConcern ||
                        Object.values(r.cells).some((values: any) =>
                          values.some((s: any) =>
                            s.concern_binding_ids?.includes(selectedConcern),
                          ),
                        ),
                    )}
                    missing={row.missing_ids}
                    onlyUnmatched={onlyUnmatched}
                    renderCell={(s: any, missing: boolean, channel: string) => (
                      <Scenario
                        s={s}
                        defs={defs}
                        missing={missing}
                        detailUrl={projectUrl(
                          project,
                          "results/" +
                            encodeURIComponent(cid) +
                            "/scenarios/" +
                            channel +
                            "/" +
                            encodeURIComponent(s.id) +
                            "?test_set=" +
                            testSet,
                        )}
                      />
                    )}
                  />
                )}
                <p className="muted">
                  E为原文已有异常的独立逆向归类；GT含独立测试的明示项及框架推导项，仍需审核。显示执行时的关注点版本，未重新匹配或计分。
                </p>
                {detail.matching_version && (
                  <details className="result-data">
                    <summary>
                      不参与确定计分的关注点（
                      {
                        Object.values(detail.concern_excluded || {}).reduce(
                          (n: number, v: any) => n + v.length,
                          0,
                        ) as number
                      }
                      项）
                    </summary>
                    {Object.entries(detail.concern_excluded || {}).map(
                      ([channel, values]) => (
                        <div key={channel}>
                          <strong>{channel}</strong>
                          {(values as any[]).map((v, n) => (
                            <p key={n}>
                              {v.interaction_id} · {v.object} ·{" "}
                              {defs[v.concern_key]?.label || v.concern_key}：
                              {v.reason || v.status_reason}
                            </p>
                          ))}
                        </div>
                      ),
                    )}
                  </details>
                )}
                <details className="result-data">
                  <summary>不参与计分的生成／原文／测试场景</summary>
                  {Object.entries(detail.excluded || {}).flatMap(
                    ([channel, values]) =>
                      (values as any[]).map((v: any, n: number) => (
                        <p key={channel + n}>
                          {channel} · {v.original_id} · {v.scenario_type}：
                          {v.reason}
                        </p>
                      )),
                  )}
                </details>
                <details className="result-data">
                  <summary>本用例已保存的覆盖匹配与指标</summary>
                  <pre>
                    {JSON.stringify(
                      {
                        metric_units: detail.metric_units,
                        concern_metrics: detail.concern_metrics,
                        metrics: detail.metrics,
                        full_matches: detail.full_matches,
                        partial_diagnostics: detail.partial_diagnostics,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
