import { useState } from "react";
import { ChevronDown, Download, FileCode2, FileText } from "lucide-react";
import { fileUrl } from "./api";
import { display } from "./utils";
import type { Artifact } from "./types";
function Table({
  rows,
  columns,
}: {
  rows: any[];
  columns: [string, string][];
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map(([k, label]) => (
              <th key={k}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map(([k]) => (
                <td key={k}>{display(r[k])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <p className="p-5 text-xs text-slate-400">当前结果为空集合</p>
      )}
    </div>
  );
}
export function PayloadView({
  value,
  definitions,
}: {
  value: any;
  definitions: Record<string, any>;
}) {
  if (!value)
    return <p className="p-6 text-sm text-slate-400">等待该节点生成产物。</p>;
  let body;
  if (value.components)
    body = (
      <Table
        rows={value.components}
        columns={[
          ["name", "名称"],
          ["composition_type", "系统组成"],
        ]}
      />
    );
  else if (value.cases)
    body = (
      <Table
        rows={value.cases}
        columns={[
          ["id", "用例编号"],
          ["name", "名称"],
          ["goal", "业务目标"],
          ["layer", "层级"],
        ]}
      />
    );
  else if (value.groups)
    body = (
      <Table
        rows={value.groups}
        columns={[
          ["id", "对应组"],
          ["rr_ids", "RR用例"],
          ["sr_ids", "SR用例"],
          ["status", "状态"],
          ["reason", "对应依据"],
        ]}
      />
    );
  else if (value.interactions)
    body = (
      <Table
        rows={value.interactions.map((i: any) => ({
          ...i,
          sender_name: i.sender.name,
          operation_name: i.operation.name,
          data_names: i.data.sequence.map((p: any) => p.name).join("、"),
          receiver_name: i.receiver.name,
        }))}
        columns={[
          ["layer", "层级"],
          ["sequence", "顺序"],
          ["sender_name", "发送方"],
          ["operation_name", "操作"],
          ["data_names", "数据"],
          ["receiver_name", "接收方"],
        ]}
      />
    );
  else if (value.objects)
    body = (
      <Table
        rows={value.objects.map((o: any) => ({
          ...o,
          operations: o.supported_operations
            .map((op: any) => op.name)
            .join("、"),
        }))}
        columns={[
          ["name", "名称"],
          ["operations", "支持操作"],
        ]}
      />
    );
  else if (value.matches)
    body = (
      <Table
        rows={value.matches.map((m: any) => ({
          ...m,
          label: definitions[m.concern_key]?.label || m.concern_key,
        }))}
        columns={[
          ["interaction_id", "交互"],
          ["object", "对象 / 字段"],
          ["label", "关注点"],
          ["status", "适用状态"],
          ["concrete_rule", "正常规则"],
        ]}
      />
    );
  else if (value.G && value.E && value.M) {
    const missing = new Set(value.M.map((s: any) => s.id));
    body = (
      <>
        <h3 className="section-label">可识别异常与原文覆盖</h3>
        <Table
          rows={value.G.map((s: any) => ({
            ...s,
            coverage: missing.has(s.id) ? "缺失，待审核" : "已有完整对应",
            label: definitions[s.concern_key]?.label || s.concern_key,
          }))}
          columns={[
            ["object", "对象"],
            ["operation", "操作"],
            ["label", "关注点"],
            ["cause", "异常原因"],
            ["conditions", "触发条件"],
            ["coverage", "已有覆盖"],
          ]}
        />
        <h3 className="section-label">原文已有异常 E</h3>
        <Table
          rows={value.E}
          columns={[
            ["object", "对象"],
            ["cause", "原因"],
            ["conditions", "条件"],
          ]}
        />
      </>
    );
  } else if (value.scenarios)
    body = (
      <Table
        rows={value.scenarios}
        columns={[
          ["interaction_id", "交互"],
          ["object", "对象"],
          ["cause", "具体原因"],
          ["conditions", "必要条件"],
        ]}
      />
    );
  else if (value.services)
    body = (
      <Table
        rows={value.services.map((s: any) => ({
          name: s.name,
          interfaces: s.interfaces
            .map((i: any) =>
              [i.id, i.method, i.address].filter(Boolean).join(" "),
            )
            .join("\n"),
        }))}
        columns={[
          ["name", "服务名称"],
          ["interfaces", "对应接口列表"],
        ]}
      />
    );
  else if (value.apis)
    body = (
      <>
        {value.apis.map((a: any) => (
          <section key={a.id}>
            <h3 className="section-label">
              {a.name} · {a.address || "地址待确认"}
            </h3>
            <Table
              rows={a.parameters}
              columns={[
                ["name", "参数"],
                ["location", "位置"],
                ["data_type", "数据类型"],
                ["required", "必填"],
                ["default", "默认值"],
                ["constraints", "约束"],
              ]}
            />
          </section>
        ))}
      </>
    );
  else
    body = <pre className="json-preview">{JSON.stringify(value, null, 2)}</pre>;
  return (
    <>
      {body}
      <details className="full-json">
        <summary>
          完整结构化结果 <ChevronDown size={12} />
        </summary>
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </details>
    </>
  );
}
export function ArtifactView({
  projectId,
  artifacts,
  value,
  definitions,
}: {
  projectId: string;
  artifacts: Artifact[];
  value: any;
  definitions: Record<string, any>;
}) {
  const [diagram, setDiagram] = useState<string | null>(null);
  const images = artifacts.filter((a) => a.name.endsWith(".svg"));
  const selected = images.find((a) => a.path === diagram) || images[0];
  return (
    <div className="artifact-content">
      {selected && (
        <div className="diagram-view">
          {images.length > 1 && (
            <select
              value={selected.path}
              onChange={(e) => setDiagram(e.target.value)}
            >
              {images.map((a) => (
                <option key={a.path} value={a.path}>
                  {a.name}
                </option>
              ))}
            </select>
          )}
          <iframe
            sandbox=""
            src={fileUrl(projectId, selected.path)}
            title={selected.name}
          />
        </div>
      )}
      <PayloadView value={value} definitions={definitions} />
      <div className="artifact-files">
        <h3 className="section-label">已保存文件</h3>
        {artifacts.map((a) => (
          <a key={a.path} href={fileUrl(projectId, a.path)} download={a.name}>
            {a.name.endsWith(".json") ? (
              <FileCode2 size={15} />
            ) : (
              <FileText size={15} />
            )}
            <span>
              {a.name}
              <small>{(a.bytes / 1024).toFixed(1)} KB</small>
            </span>
            <Download size={13} />
          </a>
        ))}
        {!artifacts.length && (
          <p className="text-xs text-slate-400">
            节点校验和保存完成后列出可下载文件。
          </p>
        )}
      </div>
    </div>
  );
}
