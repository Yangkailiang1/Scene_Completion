export type SuppliedPreview = {
  accepted: string[];
  cases: {
    file_id: string;
    file: string;
    name: string;
    case_id: string | null;
    target: string | null;
    status: "ready" | "excluded" | "outside_scope";
    reason: string;
  }[];
};

export function SuppliedCases({ preview }: { preview: SuppliedPreview }) {
  if (!preview.cases.length) return <p>暂无可预检的融合 SSD 文件。</p>;
  return (
    <div className="input-bundle-table">
      <table>
        <caption>{preview.accepted.length} 个用例通过融合 SSD 校验</caption>
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
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
