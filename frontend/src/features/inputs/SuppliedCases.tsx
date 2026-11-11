export type SuppliedPreview = {
  accepted: string[];
  sr_interface_count?: number;
  sr_api_pending?: string[];
  cases: {
    file_id: string;
    file: string;
    name: string;
    case_id: string | null;
    target: string | null;
    status: "ready" | "excluded" | "outside_scope";
    reason: string;
    existing_exceptions?: number;
    existing_pending?: { file: string; scenario_id: string; reason: string }[];
  }[];
};

export function SuppliedCases({ preview }: { preview: SuppliedPreview }) {
  if (!preview.cases.length) return <p>暂无可预检的融合 SSD 文件。</p>;
  return (
    <div className="input-bundle-table">
      <table>
        <caption>
          {preview.accepted.length} 个用例通过融合 SSD 校验
          {preview.sr_interface_count !== undefined &&
            ` · ${preview.sr_interface_count} 个功能树 SR 接口已绑定`}
        </caption>
        <thead>
          <tr>
            <th>用例与来源文件</th>
            <th>目标节点</th>
            <th>校验结果</th>
          </tr>
        </thead>
        <tbody>
          {preview.cases.map((item) => (
            <tr key={item.file_id}>
              <td>
                <strong>{item.name}</strong>
                <br />
                <small>{item.file}</small>
              </td>
              <td>{item.target ?? "待对应"}</td>
              <td>
                {item.status === "ready" ? "可运行" : "未纳入"} · {item.reason}
                {item.existing_exceptions !== undefined && (
                  <div>SR 原文异常已对应 {item.existing_exceptions} 条</div>
                )}
                {!!item.existing_pending?.length && (
                  <details>
                    <summary>
                      SR 原文异常待确认 {item.existing_pending.length} 条
                    </summary>
                    <ul>
                      {item.existing_pending.map((entry) => (
                        <li key={entry.file + ":" + entry.scenario_id}>
                          {entry.scenario_id} · {entry.reason}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!!preview.sr_api_pending?.length && (
        <details>
          <summary>SR 接口及字段待补项</summary>
          <ul>
            {preview.sr_api_pending.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
