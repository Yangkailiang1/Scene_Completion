import { useEffect, useState } from "react";
import { api, projectUrl, fileUrl } from "./api";
const titles: Record<string, string> = {
  triple: "三方完整对应",
  pair: "两方对应",
  single: "单方独有",
  conflict: "两两匹配冲突",
};
export function AlignmentTable({
  rows,
  missing,
  renderCell,
  onlyUnmatched,
}: {
  rows: any[];
  missing: string[];
  renderCell: (s: any, missing: boolean, channel: string) => React.ReactNode;
  onlyUnmatched: boolean;
}) {
  const shown = rows.filter((r) => !onlyUnmatched || r.status !== "triple");
  return (
    <div className="alignment-scroll">
      <table className="alignment-table">
        <thead>
          <tr>
            {[
              "具体异常／触发条件",
              "需求文档已有 E",
              "本方法生成 G",
              "独立测试真值 GT",
              "对应状态与依据",
            ].map((x) => (
              <th key={x}>{x}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.id} className={"alignment-" + r.status}>
              <td>
                <strong>{r.anchor.field || r.anchor.object}</strong>
                <p>
                  {r.anchor.steps?.trigger ||
                    r.anchor.conditions?.join("；") ||
                    r.anchor.cause}
                </p>
              </td>
              {["E", "G", "GT"].map((k) => (
                <td key={k}>
                  {r.cells[k].length ? (
                    r.cells[k].map((s: any) => (
                      <div key={s.id}>
                        {r.shared_e_ids?.includes(s.id) && (
                          <small className="shared-branch">
                            共用原分支 · 仅计一次
                          </small>
                        )}
                        {renderCell(s, k === "G" && missing.includes(s.id), k)}
                      </div>
                    ))
                  ) : (
                    <span className="alignment-empty">
                      无已保存的完整对应项
                    </span>
                  )}
                </td>
              ))}
              <td>
                <strong>{titles[r.status]}</strong>
                {r.diagnostics
                  ?.filter((d: string) => d !== "GT未验证")
                  .map((d: string) => (
                    <p key={d}>{d}</p>
                  ))}
                {r.cells.G.length > 0 && !r.cells.GT.length && (
                  <p>未被现有GT验证，不直接判错</p>
                )}
                {!r.cells.G.length && r.cells.GT.length > 0 && (
                  <p>GT未被G完整命中</p>
                )}
                <details>
                  <summary>查看匹配判据</summary>
                  {r.matching?.map((m: any, n: number) => (
                    <p key={n}>
                      <b>
                        {m.purpose} · {m.status}
                        {m.candidate_only ? " · 候选诊断，不算对应" : ""}
                      </b>
                      <br />
                      {m.reason}
                    </p>
                  ))}
                </details>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!shown.length && <p className="muted">当前筛选下没有待核查的对应行。</p>}
    </div>
  );
}
const names: Record<string, string> = {
  missing_exception_miss_rate: "缺失异常漏报率 ↓",
  generation_validity: "生成有效率 ↑",
};
function Rate({ value }: { value: any }) {
  return (
    <>
      {value?.value == null
        ? value?.status || "未评测"
        : `${value.value.toFixed(2)}%`}
      <small>
        {value?.denominator != null
          ? `（${value.numerator}/${value.denominator}）`
          : ""}
      </small>
    </>
  );
}
export function MetricsPanel({
  project,
  testSet = "expanded",
  onCase,
}: {
  project: string;
  testSet?: string;
  onCase: (id: string) => void;
}) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setData(null);
    api(
      projectUrl(
        project,
        "results/metrics" +
          (testSet === "original" ? "?test_set=original" : ""),
      ),
    )
      .then((v) => live && setData(v))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [project, testSet]);
  if (error) return <p role="alert">{error}</p>;
  if (!data)
    return <p className="management-loading">正在读取已保存的评测计数…</p>;
  return (
    <section className="result-metrics">
      {data.test_source_changed && (
        <p className="management-notice">
          测试源已切换，尚未重算。当前数值是上次保存报告，不能当作新测试版本的指标。请继续运行。
        </p>
      )}
      <p>
        {testSet === "expanded"
          ? "扩展异常测试集（机器补充自动计分）"
          : "原始异常测试集"}
        ；只计类型为异常的记录。集合扩充导致的变化不代表生成模型质量提升。
      </p>
      <p className="muted">
        全部用例合并 · 已评测{" "}
        {data.cases.filter((c: any) => c.status.startsWith("已评测")).length}/
        {data.cases.length}
        {!data.complete ? " · 本轮尚未完成，中间计数不作为最终指标" : ""}
      </p>
      <div className="metric-cards">
        {Object.keys(names).map((k) => (
          <article key={k}>
            <h3>{names[k]}</h3>
            <strong>
              <Rate value={data.metrics[k]} />
            </strong>
            <p>
              {k === "missing_exception_miss_rate"
                ? "漏掉的GT缺失项 ÷ 全部GT缺失项；越低越好"
                : "与GT完整匹配的生成项 ÷ 全部生成项；越高越好"}
            </p>
          </article>
        ))}
      </div>
      <p className="muted">
        合并分子／分母，不取百分比平均。{data.truth_source}
        ；未匹配GT不等于已经证实生成错误。推荐器：{data.recommendation}。
      </p>
      {data.diagnostic_counts?.G > 0 && (
        <p className="muted">
          计分集合规模：G={data.diagnostic_counts.G}，GT=
          {data.diagnostic_counts.GT}
          。一一匹配下，当前GT规模支持的生成有效率理论上限为{" "}
          {data.diagnostic_counts.one_to_one_ceiling.toFixed(2)}
          %；这不是质量结论，需结合测试覆盖范围判断。
        </p>
      )}
      {data.cases.some((c: any) => c.truth_pending > 0) && (
        <p className="management-notice">
          GT仍有{" "}
          {data.cases.reduce(
            (n: number, c: any) => n + (c.truth_pending || 0),
            0,
          )}{" "}
          项待确认，尚未计入分母；当前指标针对已解析的GT，不代表所有测试异常已完成对齐。
        </p>
      )}
      <details>
        <summary>公式及版本</summary>
        <p>漏报率＝(1−|M∩(GT−E)|/|GT−E|)×100%；生成有效率＝|G∩GT|/|G|×100%。</p>
        <p>
          G：生成异常；E：文档已有异常；GT：测试真值；M：G中未被E覆盖的异常。交集使用已保存的完整语义对应；空分母不适用。
        </p>
        <p>
          执行版本：{data.execution_id} · 规则版本：{data.ruleset_version} ·
          关注点版本：{data.registry_hash}
        </p>
      </details>
      <table>
        <thead>
          <tr>
            {["用例", "漏报率 ↓", "生成有效率 ↑", "G / E / GT / M", "状态"].map(
              (x) => (
                <th key={x}>{x}</th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {data.cases.map((c: any) => (
            <tr key={c.id}>
              <td>
                <button onClick={() => onCase(c.id)}>
                  {c.id} · {c.name}
                </button>
              </td>
              <td>
                <button onClick={() => onCase(c.id)}>
                  <Rate value={c.metrics.missing_exception_miss_rate} />
                </button>
              </td>
              <td>
                <button onClick={() => onCase(c.id)}>
                  <Rate value={c.metrics.generation_validity} />
                </button>
              </td>
              <td>
                {["G", "E", "GT", "M"].map((k) => c.counts[k]).join(" / ")}
              </td>
              <td>{c.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!!data.history.length && (
        <details>
          <summary>历史报告（{data.history.length}）</summary>
          {data.history.map((r: any) => (
            <p key={r.path}>
              <a href={fileUrl(project, r.path)} download>
                {r.name}
              </a>
              {r.metrics && (
                <span>
                  {" "}
                  · 漏报率{" "}
                  <Rate value={r.metrics.missing_exception_miss_rate} /> ·
                  生成有效率 <Rate value={r.metrics.generation_validity} />
                </span>
              )}
            </p>
          ))}
        </details>
      )}
      {!!data.audit_files?.length && (
        <details>
          <summary>下载逐条质量复核与修订对照</summary>
          {data.audit_files.map((r: any) => (
            <p key={r.path}>
              <a href={fileUrl(project, r.path)} download>
                {r.name}
              </a>
              <small> · {(r.bytes / 1024).toFixed(0)} KB，按需下载</small>
            </p>
          ))}
        </details>
      )}
    </section>
  );
}
