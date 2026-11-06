import { useEffect, useState } from "react";
import { ScopeReview } from "./ScopeReview";
import { api, fileUrl, projectUrl } from "../../shared/api";

const names: Record<string, string> = {
  missing_omission: "关注点层缺失漏报率 ↓",
  generation_effectiveness: "关注点层生成有效率 ↑",
  recommendation_adoption: "场景层推荐采纳率 ↑",
  recommendation_false_positive: "场景层推荐误报率 ↓",
  baseline_adoption: "推荐前 M 命中率 ↑",
  baseline_false_positive: "推荐前 M 误报率 ↓",
};
function display(rate: any) {
  return rate?.value == null
    ? rate?.status || "未评测"
    : `${rate.value.toFixed(2)}%（${rate.numerator}/${rate.denominator}）`;
}
function Metrics({ values }: { values: Record<string, any> }) {
  return (
    <div className="v5-metric-grid">
      {Object.entries(names).map(([key, name]) => (
        <article className="v5-metric-card" key={key}>
          <small>{name}</small>
          <strong>{display(values?.[key])}</strong>
          {values?.[key]?.partial && <small>部分范围；尚非完整项目指标</small>}
        </article>
      ))}
    </div>
  );
}
function useData(
  project: string,
  path: string,
  testSet: string,
  liveVersion?: string,
  scope?: string,
) {
  const [value, setValue] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setValue(null);
    api(
      projectUrl(
        project,
        `results/${path}?test_set=${encodeURIComponent(testSet)}${scope ? "&scope=" + scope : ""}`,
      ),
    )
      .then((data) => {
        if (live) setValue(data);
      })
      .catch((reason) => {
        if (live) setError(String(reason?.message || reason));
      });
    return () => {
      live = false;
    };
  }, [project, path, testSet, liveVersion, scope]);
  return { value, error };
}
export function ProjectMetrics({
  project,
  testSet,
  liveVersion,
  scope,
}: {
  project: string;
  testSet: string;
  liveVersion?: string;
  scope?: string;
}) {
  const { value, error } = useData(
    project,
    "project-metrics",
    testSet,
    liveVersion,
    scope,
  );
  if (error) return <p role="alert">{error}</p>;
  if (!value) return <p>正在读取项目指标…</p>;
  return (
    <section className="v5-global-view">
      <h2>项目总指标</h2>
      <p>
        {value.unit_note}。
        {value.global_excluded_reason || "全局级真值使用独立原始异常测试。"}
      </p>
      <Metrics values={value.metrics} />
      <div className="v5-scope-summary">
        <div>
          <h3>交互级 · {value.interaction.case_count} 个用例</h3>
          <p>{value.interaction.status}</p>
          <Metrics
            values={{
              missing_omission:
                value.interaction.metrics.missing_exception_miss_rate,
              generation_effectiveness:
                value.interaction.metrics.generation_validity,
              recommendation_adoption:
                value.interaction.metrics.recommendation_adoption,
              recommendation_false_positive:
                value.interaction.metrics.recommendation_false_positive,
              baseline_adoption: value.interaction.metrics.baseline_adoption,
              baseline_false_positive:
                value.interaction.metrics.baseline_false_positive,
            }}
          />
        </div>
        <div>
          <h3>全局业务依赖级</h3>
          <p>{value.global.status}</p>
          <Metrics values={value.global.metrics} />
        </div>
      </div>
    </section>
  );
}
export function GlobalResults({
  project,
  testSet,
  liveVersion,
  artifacts,
}: {
  project: string;
  testSet: string;
  liveVersion?: string;
  artifacts: any[];
}) {
  const { value, error } = useData(project, "global", testSet, liveVersion);
  const diagram = artifacts
    .find((a) => a.stage === "business-dependencies")
    ?.files.find((f: any) => f.name.endsWith(".svg"));
  if (error) return <p role="alert">{error}</p>;
  if (!value) return <p>正在读取全局依赖…</p>;
  return (
    <section className="v5-global-view">
      <h2>全局业务分析</h2>
      <p>
        项目级独立计分；跨用例依赖按关系计一次，幂等性按用例、业务实体和C/U/D操作计一次。
        {value.truth_note}。当前状态：
        {value.status}。
      </p>
      {diagram && (
        <details>
          <summary>查看用例与业务实体依赖图</summary>
          <img
            className="v5-dependency-svg"
            src={fileUrl(project, diagram.path)}
            alt="用例与业务实体依赖图"
          />
        </details>
      )}
      <Metrics values={value.metrics} />
      {value.pending?.length > 0 && (
        <p>待确认：{value.pending.length} 项；未纳入确定集合。</p>
      )}
      <ScopeReview project={project} />
      <h3>关注点层 E / G / GT</h3>
      <div className="alignment-scroll">
        <table className="alignment-table">
          <thead>
            <tr>
              <th>依赖／对象／关注点</th>
              <th>需求已有 E</th>
              <th>生成 G</th>
              <th>测试 GT</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {value.concerns.map((row: any, index: number) => (
              <tr key={index}>
                <td>
                  {row.anchor.business_operation_id
                    ? (() => {
                        const op = value.business_operations?.find(
                          (o: any) => o.id === row.anchor.business_operation_id,
                        );
                        return op
                          ? `${op.case_id} · ${op.entity_name} · ${op.operation}`
                          : row.anchor.business_operation_id;
                      })()
                    : row.anchor.dependency_id}
                  <br />
                  {row.anchor.object}
                  <br />
                  <strong>{row.anchor.concern_key}</strong>
                </td>
                {(["E", "G", "GT"] as const).map((channel) => (
                  <td key={channel}>
                    {(() => {
                      const item = value.records?.[row.cells[channel]];
                      return item ? (
                        <>
                          <strong>{item.concern_key}</strong>
                          <p>
                            {item.concrete_rule || item.cause || item.object}
                          </p>
                          {item.conditions?.join("；")}
                          <details>
                            <summary>识别依据与定位</summary>
                            {item.reason}
                            <pre>
                              {JSON.stringify(item.source_refs, null, 2)}
                            </pre>
                          </details>
                        </>
                      ) : (
                        row.cells[channel] || "未识别到对应项"
                      );
                    })()}
                  </td>
                ))}
                <td>{row.missing ? "文档缺失" : "已覆盖／仅单方"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>具体异常场景层 E / G / GT</h3>
      <div className="alignment-scroll">
        <table className="alignment-table">
          <thead>
            <tr>
              <th>依赖／对象／独立失败条件</th>
              <th>需求已有 E</th>
              <th>生成 G</th>
              <th>测试 GT</th>
              <th>推荐</th>
            </tr>
          </thead>
          <tbody>
            {value.scenarios.map((row: any, index: number) => (
              <tr key={index}>
                <td>
                  {row.anchor.business_operation_id
                    ? (() => {
                        const op = value.business_operations?.find(
                          (o: any) => o.id === row.anchor.business_operation_id,
                        );
                        return op
                          ? `${op.case_id} · ${op.entity_name} · ${op.operation}`
                          : row.anchor.business_operation_id;
                      })()
                    : row.anchor.dependency_id}
                  <br />
                  {row.anchor.object}
                  <br />
                  <strong>{row.anchor.cause}</strong>
                  <br />
                  {row.anchor.conditions.join("；")}
                  <br />
                  <small>{row.anchor.concern_keys.join("、")}</small>
                </td>
                {(["E", "G", "GT"] as const).map((channel) => (
                  <td key={channel}>
                    {(() => {
                      const item = value.records?.[row.cells[channel]];
                      return item ? (
                        <>
                          <strong>{item.concern_key}</strong>
                          <p>
                            {item.concrete_rule || item.cause || item.object}
                          </p>
                          {item.conditions?.join("；")}
                          <details>
                            <summary>识别依据与定位</summary>
                            {item.reason}
                            <pre>
                              {JSON.stringify(item.source_refs, null, 2)}
                            </pre>
                          </details>
                        </>
                      ) : (
                        row.cells[channel] || "未识别到对应项"
                      );
                    })()}
                  </td>
                ))}
                <td>
                  {value.recommendations.find(
                    (r: any) => r.scenario_id === row.cells.G,
                  )?.selected
                    ? "已推荐"
                    : row.missing
                      ? "缺失，未入选"
                      : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
