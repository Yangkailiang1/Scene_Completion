import { useState } from "react";
import {
  CheckCircle2,
  FileText,
  FolderOpen,
  RefreshCw,
  UploadCloud,
  Workflow,
} from "lucide-react";
import { api, fileUrl, projectUrl } from "../../shared/api";
import { NodeOutput } from "../execution/NodeOutput";
import { ArtifactView } from "../results/ArtifactView";
import { SuppliedCases, type SuppliedPreview } from "./SuppliedCases";
import { InputBundlePicker } from "./InputBundlePicker";
import { useInputManagerController } from "./useInputManagerController";
export function InputManager({
  project,
  reviewOnly = false,
  onOpenPlan,
}: {
  project: string;
  reviewOnly?: boolean;
  onOpenPlan?: () => void;
}) {
  const [supplied, setSupplied] = useState<SuppliedPreview>();
  const {
    labels,
    statuses,
    data,
    watch,
    detail,
    chosen,
    setChosen,
    editor,
    setEditor,
    message,
    setMessage,
    busy,
    caseId,
    setCaseId,
    cases,
    recovery,
    replace,
    setReplace,
    events,
    bundleOpen,
    setBundleOpen,
    bundleFiles,
    setBundleFiles,
    fileInput,
    folderInput,
    load,
    select,
    action,
    upload,
    artifact,
    coverage,
    setCoverage,
    decide,
  } = useInputManagerController({ project, reviewOnly, onOpenPlan });
  return (
    <div className="input-manager">
      <header>
        <div>
          <h2>
            <UploadCloud size={20} /> 输入与导入
          </h2>
          <p>发现文件 → 识别与转换 → 预览 → 交给对应节点</p>
        </div>
        <div className="input-toolbar-actions">
          <button onClick={onOpenPlan}>
            <Workflow size={16} />
            文件映射与完整依赖图
          </button>
          {!reviewOnly && (
            <>
              <button
                className="input-primary"
                disabled={busy}
                onClick={() => fileInput.current?.click()}
              >
                <UploadCloud size={16} />
                添加文件
              </button>
              <button
                disabled={busy}
                onClick={() => folderInput.current?.click()}
              >
                <FolderOpen size={16} />
                添加文件夹
              </button>
              <button
                onClick={() => {
                  setBundleFiles(undefined);
                  setBundleOpen(true);
                }}
              >
                指定5份路径
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  action(async () => {
                    setSupplied(
                      await api(projectUrl(project, "supplied-cases")),
                    );
                  })
                }
              >
                预检已有 SSD
              </button>
              <input
                ref={fileInput}
                type="file"
                multiple
                hidden
                accept=".md,.markdown,.json,.xlsx"
                onChange={(e) => upload(e.target.files)}
              />
              <input
                ref={folderInput}
                type="file"
                multiple
                hidden
                {...{ webkitdirectory: "" }}
                onChange={(e) => {
                  setBundleFiles(Array.from(e.target.files || []));
                  setBundleOpen(true);
                  e.target.value = "";
                }}
              />
            </>
          )}
          <button onClick={() => load().catch((e) => setMessage(e.message))}>
            <RefreshCw size={15} />
            刷新
          </button>
        </div>
      </header>
      {bundleOpen && (
        <InputBundlePicker
          project={project}
          initialFiles={bundleFiles}
          onClose={() => setBundleOpen(false)}
          onImported={() => {
            load().catch((e) => setMessage(e.message));
            setMessage(
              "已有文件输入已保存；未启动模型，后续按采用范围复用或补齐。",
            );
            onOpenPlan?.();
          }}
        />
      )}
      {message && (
        <p role="status" className="input-message">
          {message}
        </p>
      )}
      {!reviewOnly && supplied && (
        <section className="supplied-cases-panel" aria-label="已有 SSD 校验">
          <SuppliedCases preview={supplied} />
          <button
            disabled={busy || !supplied.accepted.length}
            onClick={() =>
              action(() =>
                api(projectUrl(project, "run"), {
                  method: "POST",
                  body: JSON.stringify({
                    supplied_only: true,
                    case_ids: supplied.accepted,
                  }),
                }),
              )
            }
          >
            仅运行已校验的用例
          </button>
        </section>
      )}
      {!reviewOnly && (
        <details className="input-controls">
          <summary>
            目录监控与运行范围 <span>按需展开设置</span>
          </summary>
          <div className="input-control-grid">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                action(() =>
                  api(projectUrl(project, "input-scan"), {
                    method: "POST",
                    body: JSON.stringify({
                      directory: form.get("directory"),
                      watch: form.get("watch") === "on",
                      expected_revision: watch.revision,
                    }),
                  }),
                );
              }}
            >
              <label>
                监控本机目录
                <input
                  name="directory"
                  key={watch.directory}
                  defaultValue={watch.directory || ""}
                  placeholder="例如 C:\SceneCompletion\input"
                  required
                />
              </label>
              <label>
                <input
                  type="checkbox"
                  name="watch"
                  defaultChecked={watch.watch ?? true}
                />
                自动发现新文件（每5秒检查）
              </label>
              <button disabled={busy}>登记并扫描</button>
            </form>
            <div className="input-run-controls">
              <label>
                运行范围
                <select
                  value={caseId}
                  onChange={(e) => setCaseId(e.target.value)}
                >
                  <option value="">全部用例，按目录顺序</option>
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.id} · {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="input-actions">
                <button
                  disabled={busy || !caseId}
                  onClick={() =>
                    action(() =>
                      api(projectUrl(project, "run"), {
                        method: "POST",
                        body: JSON.stringify({ case_ids: [caseId] }),
                      }),
                    )
                  }
                >
                  仅运行此例
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    action(() =>
                      api(projectUrl(project, "run"), {
                        method: "POST",
                        body: JSON.stringify({
                          case_ids: [],
                          priority_cases: caseId ? [caseId] : [],
                        }),
                      }),
                    )
                  }
                >
                  优先此例，继续其余
                </button>
              </div>
              <small>关闭网页不停止执行；结果按用例实时发布。</small>
            </div>
          </div>
        </details>
      )}
      <div className="input-columns">
        <aside aria-label="导入文件列表">
          <div className="input-list-heading">
            <strong>文件列表</strong>
            <span>{data.items.length}</span>
          </div>
          {data.items.length === 0 ? (
            <div className="input-list-empty">
              <FileText size={26} />
              <strong>还没有文件</strong>
              <p>添加需求文档、测试场景或同事的抽取产物。</p>
              <small>Markdown · JSON · XLSX</small>
            </div>
          ) : (
            data.items.map((r: any) => (
              <button
                key={r.id}
                className={detail?.id === r.id ? "active" : ""}
                onClick={() => select(r.id).catch((e) => setMessage(e.message))}
              >
                <strong>{r.name}</strong>
                <small>
                  {r.purpose || r.role} · {statuses[r.status] || r.status}
                </small>
              </button>
            ))
          )}
        </aside>
        <section className="input-detail">
          {!detail ? (
            <div className="node-empty">
              <FileText size={34} />
              <h3>选择文件，开始查看</h3>
              <p>左侧选择文件后，可查看解析预览、来源依据与采用状态。</p>
            </div>
          ) : (
            <>
              <div className="input-detail-heading">
                <h3>{detail.name}</h3>
                <a
                  href={fileUrl(project, detail.original)}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看原文件
                </a>
                <span>版本 {detail.revision}</span>
              </div>
              {detail.error && <p role="alert">{detail.error}</p>}
              <div className="import-summary-cards">
                <div>
                  <small>识别用途</small>
                  <strong>
                    {detail.purpose ||
                      (
                        {
                          test: "测试场景 / 独立GT",
                          artifact: "结构化分析结果",
                          RR: "RR系统需求",
                          SR: "SR设计需求",
                        } as any
                      )[detail.role] ||
                      "待归类"}
                  </strong>
                  <p>{detail.recognition?.reason}</p>
                </div>
                <div>
                  <small>处理状态</small>
                  <strong>{statuses[detail.status] || detail.status}</strong>
                  <p>来源始终保留为 {detail.name}</p>
                </div>
                <div>
                  <small>采用与追溯</small>
                  <strong>{detail.usage?.length || 0} 个节点已引用</strong>
                  <p>候选不会覆盖正在执行的任务</p>
                </div>
              </div>
              {detail.target_nodes?.length > 0 && (
                <div className="import-targets">
                  <Workflow size={15} />
                  <span>目标节点</span>
                  {detail.target_nodes.map((n: string) => (
                    <code key={n}>{labels[n] || n}</code>
                  ))}
                </div>
              )}
              {detail.colleague_product && (
                <section className="import-readable">
                  <h3>
                    {detail.colleague_product.format === "function_tree"
                      ? "功能树：已声明的实体与属性"
                      : "接口抽取：映射与请求部分"}
                  </h3>
                  <div className="import-type-counts">
                    {Object.entries(detail.colleague_product.counts || {}).map(
                      ([k, v]) => (
                        <span key={k}>
                          {{
                            use_cases: "用例",
                            entities: "实体",
                            scoped_attributes: "按用例保留的属性记录",
                            interface_attributes: "接口属性片段",
                            interfaces: "接口",
                            services: "实现服务",
                            request_fields: "请求字段",
                            success_response_fields: "已提供成功响应字段",
                          }[k] || k}{" "}
                          <b>{String(v)}</b>
                        </span>
                      ),
                    )}
                  </div>
                  <p>
                    {detail.colleague_product.format === "function_tree"
                      ? "保留用例适用范围；CRUD类别仍需结合具体交互识别。接口属性只在同层、同方法、同路径及字段位置唯一时补充，未知方向不会猜成请求或响应。"
                      : "请求部分可复用；文件没有声明的成功／失败响应仍需从允许材料补抽，不能用空响应视作已完成。"}
                  </p>
                  {detail.colleague_product.pending?.length > 0 && (
                    <details>
                      <summary>
                        缺项与待定位 {detail.colleague_product.pending.length}
                      </summary>
                      {detail.colleague_product.pending.map(
                        (p: any, n: number) => (
                          <p key={n}>
                            {p.object}：{p.reason}
                          </p>
                        ),
                      )}
                    </details>
                  )}
                </section>
              )}
              {detail.test_preview && (
                <section className="import-readable">
                  <h3>测试场景预览</h3>
                  <div className="import-type-counts">
                    {Object.entries(detail.test_preview.counts).map(
                      ([k, v]) => (
                        <span key={k}>
                          {
                            (
                              {
                                exception: "异常",
                                normal: "成功",
                                optional: "可选",
                                pending: "待确认",
                              } as any
                            )[k]
                          }{" "}
                          <b>{String(v)}</b>
                        </span>
                      ),
                    )}
                  </div>
                  <p>
                    仅明确异常进入指标；先对齐需求用例与交互，再整理关注点和具体场景。
                  </p>
                  <div className="import-table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>场景ID</th>
                          <th>用例</th>
                          <th>类型</th>
                          <th>场景与条件</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.test_preview.records.map((r: any) => (
                          <tr key={r.id}>
                            <td>{r.id}</td>
                            <td>{r.case_name || r["关联需求"]}</td>
                            <td>{r["类型"]}</td>
                            <td>
                              <strong>{r["测试名称"]}</strong>
                              <p>{r["预期结果"] || r["触发条件"]}</p>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {detail.behavior_product && (
                <section className="import-readable">
                  <h3>{detail.behavior_product.label}</h3>
                  <p>
                    用例：{detail.behavior_product.case_name || "待确认归属"} ·{" "}
                    {detail.behavior_product.layer}层
                  </p>
                  <div className="import-type-counts">
                    {Object.entries(detail.behavior_product.counts || {}).map(
                      ([key, value]) => (
                        <span key={key}>
                          {{
                            interactions: "交互",
                            local_actions: "本地动作",
                            main_scenarios: "主成功场景",
                            exception_branches: "已有异常",
                            retained_scenarios: "保留备选",
                            ordered_references: "时序引用",
                          }[key] || key}{" "}
                          <b>{String(value)}</b>
                        </span>
                      ),
                    )}
                  </div>
                  <p>
                    仅主成功内容用于正向建模；明示异常走E通道，备选不自动计分。本地动作不补造Service调用，目录名称不认定为业务实体。
                  </p>
                  <p>
                    RR交互定义来自ssd.json；SR交互定义来自complete_behavior.json；main_success.json仅提供主成功时序引用，不要求重复包含完整定义。
                  </p>
                  {detail.behavior_upgrade_required && (
                    <p role="alert">
                      此文件使用旧适配版本，请重新导入同一文件后确认采用。旧记录和报告保留。
                    </p>
                  )}
                  <p>
                    {detail.behavior_upgrade_required
                      ? "需要升级适配，请重新导入同一文件；原流程仍可用"
                      : detail.behavior_enabled
                        ? "已采用，下次运行按本用例补充；缺项由原流程补齐"
                        : "待采用，不影响原建模流程"}
                  </p>
                  {!reviewOnly && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        decide(
                          detail.behavior_enabled
                            ? "disable_behavior"
                            : "enable_behavior",
                        )
                      }
                    >
                      {detail.behavior_enabled
                        ? "停用此行为版本"
                        : "采用此行为版本"}
                    </button>
                  )}
                  <details>
                    <summary>内容预览与待补齐项</summary>
                    {detail.behavior_product.pending?.map(
                      (p: any, n: number) => (
                        <p key={n}>
                          {p.object}：{p.reason}
                        </p>
                      ),
                    )}
                    {detail.behavior_resolution?.map((p: any, n: number) => (
                      <p key={"resolution-" + n}>
                        {p.object}：{p.reason}
                      </p>
                    ))}
                    <pre style={{ whiteSpace: "pre-wrap" }}>
                      {detail.behavior_product.kind === "sr_complete"
                        ? JSON.stringify(detail.behavior_product.raw, null, 2)
                        : (
                            detail.behavior_product.scenario_document?.lines ||
                            detail.behavior_product.normal_document?.lines ||
                            []
                          )
                            .map((r: any) => r.text)
                            .join("\n")}
                    </pre>
                  </details>
                </section>
              )}
              {detail.behavior_error && (
                <section className="import-readable">
                  <h3>行为格式待修正</h3>
                  <p role="alert">{detail.behavior_error}</p>
                  <p>未采用，不阻塞原有RR／SR抽取和建模。</p>
                </section>
              )}
              {detail.structure_model && (
                <section className="import-readable">
                  <h3>{detail.structure_model.layer} 结构化需求</h3>
                  <div className="import-type-counts">
                    <span>
                      用例 <b>{detail.structure_model.counts.use_cases}</b>
                    </span>
                    <span>
                      主成功路径{" "}
                      <b>{detail.structure_model.counts.main_success}</b>
                    </span>
                    <span>
                      已有异常 <b>{detail.structure_model.counts.exceptions}</b>
                    </span>
                    <span>
                      其他分支{" "}
                      <b>{detail.structure_model.counts.non_exception}</b>
                    </span>
                  </div>
                  <p>
                    复用用例目录及已有异常分支；用例对应、融合SSD、异常定位与关注点识别仍需执行。追溯到本JSON及其属性位置，不要求未提供的原始文档。
                  </p>
                  <p>
                    {detail.structure_enabled !== false
                      ? "已启用，下次执行采用"
                      : "已停用，保留历史与来源"}
                    ；运行中的任务不被替换。
                  </p>
                  {!reviewOnly && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        decide(
                          detail.structure_enabled !== false
                            ? "disable_structure"
                            : "enable_structure",
                        )
                      }
                    >
                      {detail.structure_enabled !== false
                        ? "停用此结构版本"
                        : "启用此结构版本"}
                    </button>
                  )}
                  <div className="import-table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>用例ID</th>
                          <th>名称</th>
                          <th>已声明参与者</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.structure_model.catalogue.cases.map(
                          (c: any) => (
                            <tr key={c.id}>
                              <td>{c.id}</td>
                              <td>{c.name}</td>
                              <td>
                                {c.actors.join("、") || "未声明，待后续建模"}
                              </td>
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {detail.artifacts?.length ? (
                <>
                  <label>
                    目标产物
                    <select
                      value={chosen}
                      onChange={(e) => {
                        const n = Number(e.target.value);
                        setChosen(n);
                        setEditor(
                          JSON.stringify(detail.artifacts[n].payload, null, 2),
                        );
                      }}
                    >
                      {detail.artifacts.map((a: any, n: number) => (
                        <option key={a.id} value={n}>
                          {labels[a.task]} · {a.case_hint || "项目共享/待绑定"}{" "}
                          · {a.coverage === "complete" ? "完整" : "部分"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    覆盖范围（完整仍须通过节点校验）
                    <select
                      value={coverage}
                      disabled={reviewOnly}
                      onChange={(e) => setCoverage(e.target.value)}
                    >
                      <option value="partial">部分：只补充已声明事实</option>
                      <option value="complete">
                        完整：已覆盖该节点／用例全部范围
                      </option>
                    </select>
                  </label>
                  <p>
                    {statuses[artifact.status] || artifact.status}{" "}
                    {artifact.error && " · " + artifact.error}
                  </p>
                  <section className="import-readable">
                    <h3>已提取信息</h3>
                    <ArtifactView
                      projectId={project}
                      value={artifact.payload}
                      definitions={{}}
                      artifacts={[]}
                    />
                  </section>
                  <details className="import-json-advanced">
                    <summary>高级：编辑标准化JSON</summary>
                    <label>
                      标准化JSON（可编辑，提交仍需校验）
                      <textarea
                        className="input-json"
                        value={editor}
                        readOnly={reviewOnly}
                        onChange={(e) => setEditor(e.target.value)}
                        spellCheck={false}
                      />
                    </label>
                  </details>
                  {!reviewOnly && (
                    <div className="input-actions">
                      <label>
                        <input
                          type="checkbox"
                          checked={replace}
                          onChange={(e) => setReplace(e.target.checked)}
                        />
                        确认替换已有成功产物
                      </label>
                      <button disabled={busy} onClick={() => decide("accept")}>
                        确认本产物
                      </button>
                      <button disabled={busy} onClick={() => decide("reject")}>
                        拒绝
                      </button>
                    </div>
                  )}
                </>
              ) : !detail.structure_model &&
                !detail.behavior_product &&
                !detail.behavior_error ? (
                <>
                  <p>
                    {statuses[detail.status] || detail.status}
                    。未知格式可重试转换；RR/SR/测试来源需明确确认用途。
                  </p>
                  {!reviewOnly && (
                    <div className="input-actions">
                      {["RR", "SR", "test"].map((role) => (
                        <button
                          key={role}
                          disabled={busy}
                          onClick={() =>
                            action(async () => {
                              await api(
                                projectUrl(project, "imports/" + detail.id),
                                {
                                  method: "PUT",
                                  body: JSON.stringify({
                                    action: "accept_source",
                                    role,
                                    replace,
                                    expected_revision: detail.revision,
                                  }),
                                },
                              );
                              await select(detail.id);
                            })
                          }
                        >
                          登记为{role}
                        </button>
                      ))}
                      <label>
                        <input
                          type="checkbox"
                          checked={replace}
                          onChange={(e) => setReplace(e.target.checked)}
                        />
                        替换同名来源
                      </label>
                      <button
                        disabled={busy}
                        onClick={() => decide("retry_conversion")}
                      >
                        重试格式转换
                      </button>
                    </div>
                  )}
                </>
              ) : null}
              <details>
                <summary>格式转换实时输出</summary>
                <div className="input-conversion-log">
                  <NodeOutput
                    events={events}
                    loading={false}
                    active={detail.status === "needs_conversion"}
                  />
                </div>
              </details>
              <details>
                <summary>版本与转换记录</summary>
                <p>
                  已采用节点：
                  {detail.usage?.map((u: any) => u.node).join("、") ||
                    (detail.source_registered
                      ? "已登记为当前来源；等待对应节点执行"
                      : "尚未采用")}
                </p>
                <pre>{JSON.stringify(detail.history, null, 2)}</pre>
              </details>
            </>
          )}
          {detail && (
            <details className="input-adoption">
              <summary>采用状态与原始来源</summary>
              <h3>{statuses[detail.status] || detail.status}</h3>
              <p>
                {detail.role === "test"
                  ? "该文件进入测试场景通道。用例对应、交互定位和GT评估由相应节点完成。"
                  : "校验通过后，完整结果跳过抽取；部分结果仅补缺项。"}
              </p>
              <h4>实际引用节点</h4>
              {detail.usage?.length ? (
                detail.usage.map((u: any) => (
                  <p key={u.node}>
                    <CheckCircle2 size={14} />
                    {u.node}
                  </p>
                ))
              ) : (
                <p>
                  {detail.source_registered
                    ? "已登记为当前来源，执行后显示具体节点引用。"
                    : "尚未采用，运行前可先预览确认。"}
                </p>
              )}
              <a
                href={fileUrl(project, detail.original)}
                target="_blank"
                rel="noreferrer"
              >
                原始文件 ↗
              </a>
              <small>文件版本 {detail.revision}</small>
            </details>
          )}
        </section>
      </div>
      {recovery && (
        <details className="input-recovery">
          <summary>
            自动恢复策略与记录 · 默认每节点最多2次、每轮20次额外调用
          </summary>
          <p>
            恢复只修复本节点结果或使用预设参数；程序错误保留故障包，未知业务保留待确认。
          </p>
          {!reviewOnly && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                action(() =>
                  api(projectUrl(project, "recovery"), {
                    method: "PUT",
                    body: JSON.stringify({
                      expected_revision: recovery.revision,
                      settings: {
                        ...recovery.settings,
                        enabled: f.get("enabled") === "on",
                        max_output_tokens: f.get("ceiling")
                          ? Number(f.get("ceiling"))
                          : null,
                      },
                    }),
                  }),
                );
              }}
            >
              <label>
                <input
                  name="enabled"
                  type="checkbox"
                  defaultChecked={recovery.settings.enabled}
                />
                启用有界恢复
              </label>
              <label>
                允许恢复时使用的输出上限（留空则不自动调大）
                <input
                  name="ceiling"
                  type="number"
                  min="256"
                  defaultValue={recovery.settings.max_output_tokens || ""}
                />
              </label>
              <button disabled={busy}>保存策略</button>
            </form>
          )}
          <pre>{JSON.stringify(recovery.ledger, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
