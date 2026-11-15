export function ResultMetricCards({
  values,
  scenario = false,
}: {
  values: any;
  scenario?: boolean;
}) {
  return (
    <div className="ssd-metrics">
      {Object.entries({
        missing_exception_miss_rate: scenario ? "场景漏报率" : "关注点漏报率",
        generation_validity: scenario ? "场景生成有效率" : "关注点生成有效率",
      }).map(([key, label]) => {
        const value =
          values?.[key] ||
          values?.concern?.[key] ||
          values?.concern_level?.[key];
        return (
          <div key={key}>
            <span>{label}</span>
            <strong>
              {value?.value == null
                ? value?.status || "尚未评测"
                : `${Number(value.value).toFixed(2)}%`}
            </strong>
            {value && (
              <small>
                {value.numerator} / {value.denominator}
              </small>
            )}
          </div>
        );
      })}
    </div>
  );
}
