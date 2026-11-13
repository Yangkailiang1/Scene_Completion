export function RecommendationComparison({ data }: { data: any }) {
  if (!data?.baseline)
    return <p className="muted">推荐前后场景指标尚未评测，不按0处理。</p>;
  const rate = (r: any) =>
    r?.value == null
      ? r?.status || "未评测"
      : `${r.value.toFixed(2)}%（${r.numerator}/${r.denominator}）`;
  return (
    <section aria-label="推荐前后场景指标" className="alignment-scroll">
      <h3>场景层：推荐前后对照</h3>
      <p>
        同一选定GT版本；推荐前使用全部缺失场景M，推荐后使用算法筛选的Q。误报率分母为GT，可能超过100%。
      </p>
      <table className="alignment-table">
        <thead>
          <tr>
            <th>阶段</th>
            <th>场景数</th>
            <th>命中GT</th>
            <th>GT采纳率 ↑</th>
            <th>误报率 ↓</th>
          </tr>
        </thead>
        <tbody>
          {[data.baseline, data.recommended].filter(Boolean).map((v: any) => (
            <tr key={v.set}>
              <td>
                {v.label || "推荐后：算法筛选场景"}（{v.set}）
              </td>
              <td>{v.candidate_count ?? "未评测"}</td>
              <td>{v.matched ?? "未评测"}</td>
              <td>
                {v.metrics
                  ? rate(v.metrics.recommendation_adoption)
                  : v.status || "未评测"}
              </td>
              <td>
                {v.metrics
                  ? rate(v.metrics.recommendation_false_positive)
                  : v.status || "未评测"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
