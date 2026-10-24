import { Component, useEffect, useState, type ReactNode } from "react";
import { ChevronDown, Download, FileCode2, FileText } from "lucide-react";
import { fileUrl } from "./api";
import { display } from "./utils";
import type { Artifact } from "./types";
import { api, projectUrl } from "./api";
class PreviewBoundary extends Component<
  { children: ReactNode; value: any },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidUpdate(previous: Readonly<{ children: ReactNode; value: any }>) {
    if (
      this.state.failed &&
      JSON.stringify(previous.value) !== JSON.stringify(this.props.value)
    )
      this.setState({ failed: false });
  }
  render() {
    return this.state.failed ? (
      <div role="alert" className="p-5 text-sm">
        <p>此产物暂时无法渲染表格，完整数据和文件仍可查看。</p>
        <pre className="json-preview">
          {JSON.stringify(this.props.value, null, 2)}
        </pre>
      </div>
    ) : (
      this.props.children
    );
  }
}
const ruleLabels: Record<string, string> = {
  completeness: "完整性",
  type: "类型",
  format: "格式",
  length: "长度",
  size: "大小",
  range: "范围",
  enum: "枚举",
  legality: "合法性",
  minimum: "最小值",
  maximum: "最大值",
};
function Cell({ field, value }: { field: string; value: any }) {
  if (field === "required")
    return (
      <>{value === true ? "必填" : value === false ? "可选" : display(value)}</>
    );
  if (field === "constraints" && Array.isArray(value))
    return value.length ? (
      <ul className="readable-rules">
        {value.map((r: any, i: number) => (
          <li key={i}>
            {ruleLabels[r.kind] || r.kind}：
            {r.status === "pending"
              ? "待确认具体约束"
              : Array.isArray(r.value)
                ? r.value.join("、")
                : display(r.value)}
          </li>
        ))}
      </ul>
    ) : (
      <>未明确约束</>
    );
  if (field === "source_ranges" && Array.isArray(value))
    return (
      <>
        {value
          .map((r: any) => `${r.source_id} · ${r.start}–${r.end}行`)
          .join("\n")}
      </>
    );
  if (field === "source_refs" && Array.isArray(value))
    return (
      <details className="cell-details">
        <summary>{value.length}处原文依据</summary>
        {value.map((r: any, i: number) => (
          <p key={i}>
            {r.source_id} · {r.line_start}–{r.line_end}行<br />
            {r.quote}
          </p>
        ))}
      </details>
    );
  if (Array.isArray(value) && value.every((r) => typeof r !== "object"))
    return <>{value.join("、") || "—"}</>;
  if (value && typeof value === "object") {
    if (value.name) return <>{value.name}</>;
    return (
      <details className="cell-details">
        <summary>查看结构化内容</summary>
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </details>
    );
  }
  return <>{display(value)}</>;
}
function Table({
  rows,
  columns,
}: {
  rows?: any[];
  columns: [string, string][];
}) {
  if (!Array.isArray(rows))
    return (
      <p role="alert" className="p-5 text-sm">
        此结果缺少表格字段，请查看完整结构化结果。
      </p>
    );
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
                <td key={k}>
                  <Cell field={k} value={r[k]} />
                </td>
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
function CatalogTable({
  rows,
  selectedApis,
}: {
  rows: any[];
  selectedApis: string[];
}) {
  const [search, setSearch] = useState("");
  const [all, setAll] = useState(false);
  const visible = rows.filter(
    (r) =>
      (all || !selectedApis.length || selectedApis.includes(r.api_id)) &&
      (!search ||
        [r.service, r.api_name, r.address, r.name].some((v) =>
          String(v || "")
            .toLowerCase()
            .includes(search.toLowerCase()),
        )),
  );
  const groups = new Map<string, any[]>();
  visible.forEach((r) => {
    const key = JSON.stringify([r.service, r.api_id, r.method, r.address]);
    groups.set(key, [...(groups.get(key) || []), r]);
  });
  return (
    <div className="catalog-reader">
      <div className="catalog-search">
        <input
          aria-label="搜索接口或参数"
          placeholder="搜索服务、接口、地址或参数…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {selectedApis.length > 0 && (
          <button onClick={() => setAll((v) => !v)}>
            {all ? "只看当前接口" : "查看全部接口"}
          </button>
        )}
        <span>{groups.size}个接口</span>
      </div>
      {Array.from(groups, ([key, entries]) => {
        const a = entries[0];
        return (
          <section key={key} className="api-reader-card">
            <header>
              <div>
                <span>{a.service || "服务归属待确认"}</span>
                <h3>
                  {a.api_name} <small>{a.api_id}</small>
                </h3>
                <code>
                  {[a.method, a.address || "地址待确认"]
                    .filter(Boolean)
                    .join(" ")}
                </code>
              </div>
              <p>
                {a.mapping_status} · {a.parameter_status}
              </p>
            </header>
            <Table
              rows={entries}
              columns={[
                ["direction", "方向"],
                ["location", "位置"],
                ["name", "参数"],
                ["data_type", "数据类型"],
                ["required", "可选／必填"],
                ["default", "默认值"],
                ["constraints", "约束条件"],
              ]}
            />
          </section>
        );
      })}
      {!groups.size && (
        <p className="p-5 text-sm">
          暂无匹配接口；尚未提取的结果不会显示为无参数。
        </p>
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
  else if (value.branches)
    body = (
      <Table
        rows={value.branches}
        columns={[
          ["id", "原分支"],
          ["case_hint", "用例提示"],
          ["description", "原文异常"],
          ["operation_hint", "操作"],
          ["source_refs", "原文依据"],
        ]}
      />
    );
  else if (value.bindings)
    body = (
      <Table
        rows={value.bindings}
        columns={[
          ["branch_id", "原分支"],
          ["interaction_id", "具体交互"],
          ["status", "绑定状态"],
          ["basis", "绑定依据"],
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
            coverage: missing.has(s.id) ? "缺失，待审核" : "已有覆盖",
            original_coverage: (value.full_matches || [])
              .filter((p: any) => p.checker_scenario_id === s.id)
              .map((p: any) => {
                const e = value.E.find(
                  (e: any) => e.id === p.generated_scenario_id,
                );
                return `${e?.original_branch_id || e?.id}：${e?.coverage_kind === "input_parameters" ? "同交互输入参数分支覆盖" : "具体异常对应"}`;
              })
              .join("；"),
            label: definitions[s.concern_key]?.label || s.concern_key,
          }))}
          columns={[
            ["object", "对象"],
            ["operation", "操作"],
            ["label", "关注点"],
            ["cause", "异常原因"],
            ["conditions", "触发条件"],
            ["interaction_id", "具体交互"],
            ["coverage", "覆盖状态"],
            ["original_coverage", "原分支与覆盖依据"],
          ]}
        />
        <h3 className="section-label">原文已有异常 E及逆向细化</h3>
        {value.original_branches && (
          <Table
            rows={value.original_branches}
            columns={[
              ["id", "原分支"],
              ["description", "原文描述"],
              ["source_refs", "依据"],
            ]}
          />
        )}
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
        rows={value.scenarios.map((s: any) => ({
          ...s,
          label: definitions[s.concern_key]?.label || s.concern_key,
        }))}
        columns={[
          ["interaction_id", "交互"],
          ["object", "对象"],
          ["cause", "具体原因"],
          ["conditions", "必要条件"],
          ["label", "关注点"],
          ["original_branch_id", "原分支"],
          ["coverage_kind", "覆盖范围"],
          ["source_status", "明示／推导"],
          ["derivation", "细化依据"],
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
  else if (
    Array.isArray(value.apis) &&
    value.apis.some((a: any) => "source_ranges" in a)
  )
    body = (
      <>
        <h3 className="section-label">接口目录（内部拆分依据）</h3>
        <p className="px-5 pb-4 text-sm text-slate-500">
          此节点只定位接口及原文章节。参数由后续接口任务提取，完成后汇入接口总表。
        </p>
        <Table
          rows={value.apis}
          columns={[
            ["id", "接口标识"],
            ["name", "接口名称"],
            ["source_ranges", "原文范围"],
            ["source_refs", "原文依据"],
          ]}
        />
      </>
    );
  else if (value.apis)
    body = (
      <>
        {value.apis.length === 0 && (
          <p className="p-5 text-sm text-slate-500">当前接口集合为空。</p>
        )}
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
  taskKey,
}: {
  projectId: string;
  artifacts: Artifact[];
  value: any;
  definitions: Record<string, any>;
  taskKey?: string;
}) {
  const [diagram, setDiagram] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<any>(null);
  const [catalogError, setCatalogError] = useState("");
  const [showCatalog, setShowCatalog] = useState(false);
  const isApi =
    !!taskKey &&
    (taskKey === "api-map" ||
      taskKey === "api-index" ||
      taskKey.startsWith("api-parameters"));
  useEffect(() => {
    setShowCatalog(isApi && taskKey !== "api-index");
    setCatalog(null);
    setCatalogError("");
    if (!isApi) return;
    let active = true;
    const load = () =>
      api(projectUrl(projectId, "api-catalog"))
        .then((v) => {
          if (active) {
            setCatalog(v);
            setCatalogError("");
          }
        })
        .catch((e) => {
          if (active) setCatalogError(String(e));
        });
    load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [projectId, taskKey, isApi]);
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
      {isApi && (
        <div className="flex gap-4 p-4 text-sm">
          <button className="text-primary" onClick={() => setShowCatalog(true)}>
            接口总表（服务、接口与参数）
          </button>
          <button
            className="text-primary"
            onClick={() => setShowCatalog(false)}
          >
            本节点产物
          </button>
        </div>
      )}
      {isApi && showCatalog ? (
        <>
          <h3 className="section-label">API 接口总表</h3>
          {catalogError && (
            <p role="alert" className="p-5 text-sm">
              总表暂时加载失败：{catalogError}。可切换查看本节点产物。
            </p>
          )}
          {!catalog && !catalogError && (
            <p className="p-5 text-sm">正在读取已保存的接口结果…</p>
          )}
          {catalog && (
            <>
              <p className="px-5 pb-4 text-sm text-slate-500">
                {catalog.complete
                  ? "已完成：归属与参数均通过审核。"
                  : "中间结果：包含待审核或尚未完成的接口；未提取的参数不表示无参数。"}
              </p>
              {catalog.identity_pending > 0 && (
                <p className="px-5 pb-4 text-sm text-amber-700">
                  {catalog.identity_pending}
                  项接口身份或服务归属待确认，已分别保留，未按名称猜测合并。
                </p>
              )}
              <PreviewBoundary
                key={projectId + taskKey + "catalog"}
                value={catalog}
              >
                <CatalogTable
                  rows={catalog.rows}
                  selectedApis={
                    taskKey?.startsWith("api-parameters-part-")
                      ? (value?.apis || []).map((a: any) => a.id)
                      : []
                  }
                />
              </PreviewBoundary>
              <div className="flex gap-4 p-5 text-sm text-primary">
                {["json", "md"].map((format) => (
                  <a
                    key={format}
                    href={projectUrl(projectId, "api-catalog?format=" + format)}
                    download={"api-catalog." + format}
                  >
                    下载总表 {format.toUpperCase()}
                  </a>
                ))}
              </div>
            </>
          )}
        </>
      ) : (
        <PreviewBoundary key={projectId + taskKey + "node"} value={value}>
          <PayloadView value={value} definitions={definitions} />
        </PreviewBoundary>
      )}
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
