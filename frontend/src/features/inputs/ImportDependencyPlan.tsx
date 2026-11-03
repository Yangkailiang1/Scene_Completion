import { ExternalLink, FileText, Workflow, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, fileUrl, projectUrl } from "../../shared/api";
import type { Graph } from "../../shared/types";
import { phaseLabels } from "../../shared/utils";
import { ExecutionFlow } from "../execution/ExecutionFlow";

export function ImportDependencyPlan({
  project,
  onClose,
}: {
  project: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<(Graph & { files: any[] }) | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [file, setFile] = useState("");
  useEffect(() => {
    let live = true;
    api(projectUrl(project, "import-plan"))
      .then((v) => {
        if (live) setData(v);
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [project]);
  const node = data?.nodes.find((n) => n.id === selected);
  const relevant =
    data?.nodes.filter(
      (n) => !file || n.input_bindings?.some((b) => b.file_id === file),
    ) || [];
  return (
    <div className="import-plan-overlay">
      <section
        role="dialog"
        aria-modal="true"
        aria-label="文件映射与完整依赖图"
        className="import-plan-dialog"
      >
        <header>
          <div>
            <h2>
              <Workflow size={20} />
              文件映射与完整依赖图
            </h2>
            <p>
              导入计划预览，不是执行进度。节点对应真实工作流定义；用例对应、接口新增和依赖分片将在运行时继续校验、展开。
            </p>
          </div>
          <button aria-label="关闭文件映射图" onClick={onClose}>
            <X size={20} />
          </button>
        </header>
        {error && <p role="alert">{error}</p>}
        {!data && !error ? (
          <p className="plan-loading">正在读取导入依赖计划…</p>
        ) : (
          data && (
            <>
              <div className="import-plan-legend">
                {[
                  ["reuse", "可复用／跳过LLM抽取"],
                  ["partial", "部分补齐"],
                  ["basis", "提供依据"],
                  ["execute", "仍需执行"],
                  ["pending", "待确认采用"],
                  ["tool", "工具整理"],
                ].map(([key, label]) => (
                  <span className={"import-mode " + key} key={key}>
                    {label} {data.summary?.[key] || 0}
                  </span>
                ))}
                <small>
                  复用不是删除节点；运行后仍校验并展示实际采用记录。
                </small>
              </div>
              <div className="import-plan-body">
                <aside className="import-plan-files">
                  <h3>输入文件 → 目标节点</h3>
                  <select
                    aria-label="映射文件范围"
                    value={file}
                    onChange={(e) => {
                      setFile(e.target.value);
                      setSelected(null);
                    }}
                  >
                    <option value="">全部输入文件</option>
                    {data.files.map((f) => (
                      <option value={f.file_id} key={f.file_id}>
                        {f.purpose} · {f.name}
                      </option>
                    ))}
                  </select>
                  <small>
                    {relevant.length} 个节点；点击查看来源、复用或补齐原因。
                  </small>
                  <div className="import-plan-node-list">
                    {relevant.map((n) => (
                      <button
                        key={n.id}
                        onClick={() => setSelected(n.id)}
                        className={selected === n.id ? "selected" : ""}
                      >
                        <strong>{n.label}</strong>
                        <small>
                          {n.case === "shared" ? "项目共享" : n.case}
                        </small>
                        <span className={"import-mode " + n.import_mode}>
                          {n.import_label}
                        </span>
                      </button>
                    ))}
                  </div>
                </aside>
                <div className="import-plan-canvas">
                  <ExecutionFlow
                    graph={data}
                    selected={selected}
                    onSelect={setSelected}
                  />
                </div>
                <aside className="import-plan-detail">
                  {node ? (
                    <>
                      <h3>{node.label}</h3>
                      <code>{node.target_key || "运行时动态展开"}</code>
                      <span className={"import-mode " + node.import_mode}>
                        {node.import_label}
                      </span>
                      {node.execution_status && (
                        <p>
                          已有执行记录：
                          {phaseLabels[node.execution_status] ||
                            node.execution_status}{" "}
                          · {node.execution_provenance}
                          {node.actual_import_reuse
                            ? "；已从当前输入复用，跳过对应LLM抽取"
                            : "；不表示本次输入已校验采用"}
                        </p>
                      )}
                      <h4>来源与处理方式</h4>
                      {node.input_bindings?.length ? (
                        node.input_bindings.map((b, i) => (
                          <div
                            className="plan-binding"
                            key={b.file_id + String(i)}
                          >
                            <strong>
                              <FileText size={14} />
                              {b.purpose}
                            </strong>
                            <p>
                              {b.name} · 版本 {b.revision}
                            </p>
                            <p>{b.explanation}</p>
                            <a
                              href={fileUrl(project, b.original)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              查看来源文件 <ExternalLink size={12} />
                            </a>
                          </div>
                        ))
                      ) : (
                        <p>没有可替代本任务的输入结果，按上游依赖继续执行。</p>
                      )}
                      <h4>直接上游</h4>
                      {node.deps.length ? (
                        node.deps.map((id) => (
                          <button
                            className="plan-upstream"
                            key={id}
                            onClick={() => setSelected(id)}
                          >
                            {data.nodes.find((n) => n.id === id)?.label || id}
                          </button>
                        ))
                      ) : (
                        <p>无上游任务</p>
                      )}
                      <h4>目标产物</h4>
                      {node.expected_files.map((f) => (
                        <code className="plan-file" key={f}>
                          {f}
                        </code>
                      ))}
                      <p>尚未运行，不表示已经生成这些文件。</p>
                    </>
                  ) : (
                    <div className="plan-detail-empty">
                      <Workflow size={30} />
                      <h3>选择一个节点</h3>
                      <p>
                        可从左侧文件映射列表或依赖图进入，查看由哪个输入提供结果、哪些LLM抽取可跳过，以及还需要补齐什么。
                      </p>
                    </div>
                  )}
                </aside>
              </div>
            </>
          )
        )}
      </section>
    </div>
  );
}
