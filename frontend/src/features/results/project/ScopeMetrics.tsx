import { ResultMetricCards } from "../shared/ResultMetricCards";
import { scopeNames, type AnalysisScope } from "./types";
export function ScopeMetrics({
  snapshot,
  historical = false,
}: {
  snapshot: any;
  historical?: boolean;
}) {
  const metrics = snapshot?.metrics || {};
  return (
    <>
      <h3>{historical ? "所选历史版本" : "当前修订"} · 关注点层</h3>
      <ResultMetricCards
        values={snapshot?.metrics_by_level?.concern || metrics}
      />
      <h3>{historical ? "所选历史版本" : "当前修订"} · 场景层</h3>
      <ResultMetricCards
        values={
          snapshot?.metrics_by_level?.scenario || snapshot?.scenario_diagnostic
        }
        scenario
      />
      {snapshot?.original_metrics && (
        <details className="ssd-step-panel">
          <summary>原始机器指标对照</summary>
          <h4>关注点层</h4>
          <ResultMetricCards
            values={
              snapshot.original_metrics_by_level?.concern ||
              snapshot.original_metrics
            }
          />
          <h4>场景层</h4>
          <ResultMetricCards
            values={
              snapshot.original_metrics_by_level?.scenario ||
              snapshot.original_scenario_diagnostic
            }
            scenario
          />
        </details>
      )}
      {snapshot?.completeness && !snapshot.completeness.complete && (
        <p className="management-notice">
          当前范围仍有待确认或未完成比较项；指标只反映已确认集合。
        </p>
      )}
    </>
  );
}
function rate(value: any) {
  return value?.value == null
    ? value?.status || "尚未评测"
    : `${Number(value.value).toFixed(2)}%（${value.numerator}/${value.denominator}）`;
}
export function ScopeMetricsSummary({
  index,
  sourceControl,
  navigation,
}: {
  index: any;
  sourceControl?: React.ReactNode;
  navigation: React.ReactNode;
}) {
  const metrics = index?.metrics;
  return (
    <div className="management-view results-view ssd-results">
      {navigation}
      <div className="results-compact-controls">
        {sourceControl}
        <span className="results-compact-description">
          用例交互＋共用外部服务 · 关注点与场景分别计分
        </span>
      </div>
      <section className="result-metrics ssd-metrics-view">
        <h2>项目分层与汇总指标</h2>
        <p>
          普通交互按用例统计，共用服务按合并单位仅计一次；未完成结果单独标注。
        </p>
        <table>
          <thead>
            <tr>
              <th>分析范围</th>
              <th>计分单位</th>
              <th>漏报率</th>
              <th>生成有效率</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {(["interaction", "shared_services"] as AnalysisScope[]).flatMap(
              (scope) =>
                ["concern", "scenario"].map((level) => {
                  const values = metrics?.by_scope?.[scope];
                  return (
                    <tr key={`${scope}-${level}`}>
                      <td>{scopeNames[scope]}</td>
                      <td>{level === "concern" ? "关注点" : "场景"}</td>
                      <td>
                        {rate(values?.[level]?.missing_exception_miss_rate)}
                      </td>
                      <td>{rate(values?.[level]?.generation_validity)}</td>
                      <td>
                        {values?.available === false || !values
                          ? "尚无结果"
                          : values.complete
                            ? "已完成"
                            : "部分结果"}
                      </td>
                    </tr>
                  );
                }),
            )}
            {["concern", "scenario"].map((level) => (
              <tr key={level}>
                <td>
                  <strong>项目汇总</strong>
                </td>
                <td>{level === "concern" ? "关注点" : "场景"}</td>
                <td>
                  {rate(metrics?.overall?.[level]?.missing_exception_miss_rate)}
                </td>
                <td>{rate(metrics?.overall?.[level]?.generation_validity)}</td>
                <td>{metrics?.complete ? "已完成" : "包含未完成范围"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
