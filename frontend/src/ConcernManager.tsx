import { useEffect, useState } from "react";
import { ConcernTree } from "./ConcernTree";
import { api, projectUrl, fileUrl } from "./api";
const layers: Record<string, string> = {
  human: "人类Actor",
  base: "Service基础层",
  shared: "输入／输出数据",
  functional: "五类功能层",
  technology: "技术扩展层",
  relation: "Service之间",
};
const groups: Record<string, Record<string, string>> = {
  human: { human: "身份与权限" },
  base: { service_base: "服务基础" },
  shared: { api_data: "数据关注点" },
  functional: {
    display_interaction: "展示交互型",
    query_retrieval: "查询检索型",
    resource_mutation: "资源变更型",
    analysis_generation: "分析生成型",
    release_activation: "发布生效型",
  },
  technology: { database: "数据库", llm: "LLM" },
  relation: { service_relation: "服务关系" },
};
const operations: Record<string, string> = {
  read: "查询",
  display: "展示",
  create: "创建",
  update: "修改",
  delete: "删除",
  process: "分析／生成",
  publish: "发布",
  external_call: "外部调用",
};
const guards: Record<string, string> = {
  business: "明确业务规则",
  authentication: "身份认证条件",
  authorization: "权限／可见范围",
  resource_lookup: "资源查询条件",
  timing: "明确时间条件",
  device: "设备适配要求",
  idempotency: "幂等要求",
  persistence: "持久化要求",
  concurrency: "并发要求",
  release: "发布前置条件",
  recovery: "恢复要求",
  reference: "关联完整性",
  unique: "唯一约束",
  resource_limit: "资源限制",
  grounding: "事实依据",
  instruction: "指令要求",
  context: "上下文要求",
  prompt_security: "提示词安全",
  stability: "稳定性要求",
  relation: "服务关系约束",
  result: "结果约束",
};
export function ConcernManager({
  project,
  onUpdated,
}: {
  project: string;
  onUpdated?: () => void;
}) {
  const [view, setView] = useState<any>(null),
    [selected, setSelected] = useState(""),
    [form, setForm] = useState<any>(null),
    [query, setQuery] = useState(""),
    [layer, setLayer] = useState(""),
    [showDeleted, setShowDeleted] = useState(false),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  function load(version = "") {
    api(
      projectUrl(project, "registry" + (version ? "?version=" + version : "")),
    )
      .then((d) => {
        setView(d);
        setForm(null);
        setSelected("");
      })
      .catch((e) => setNotice(e.message));
  }
  useEffect(() => {
    load();
  }, [project]);
  function pick(key: string, d: any) {
    setSelected(key);
    setForm({
      ...d,
      parents: [...d.parents],
      operation_kinds: [...d.operation_kinds],
    });
    setNotice("");
  }
  function add() {
    setSelected("");
    setForm({
      key: "custom." + Date.now().toString(36),
      label: "",
      description: "",
      layer: "functional",
      group: "query_retrieval",
      parents: [],
      kind: "check",
      guard: "business",
      failure_family: null,
      operation_kinds: ["read"],
      technology: null,
      enabled: true,
      custom: true,
    });
  }
  async function save(value: any = form, registry: any = null) {
    setBusy(true);
    try {
      const r = registry || {
        ...view.registry,
        definitions: {
          ...view.registry.definitions,
          [value.key]: {
            ...value,
            failure_family: value.failure_family || value.key,
          },
        },
      };
      const d = await api(projectUrl(project, "registry"), {
        method: "PUT",
        body: JSON.stringify({
          expected_hash: view.current_hash,
          registry: r,
          note: registry
            ? "恢复历史版本为新版本"
            : "编辑关注点：" + value.label,
        }),
      });
      setView(d);
      if (value) {
        setForm({ ...value });
        setSelected(value.key);
      }
      setNotice("已发布项目新版本。已有报告不变；下一次分析使用新定义。");
      onUpdated?.();
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }
  const defs = view?.registry.definitions || {},
    readOnly = view?.read_only;
  return (
    <div className="management-view concern-manager">
      {notice && (
        <div role="status" className="management-notice">
          {notice}
        </div>
      )}
      <div className="management-filters">
        <button className="primary-action" disabled={readOnly} onClick={add}>
          ＋ 新增关注点
        </button>
        <input
          aria-label="搜索关注点"
          placeholder="搜索名称、定义或ID"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          aria-label="关注点层级筛选"
          value={layer}
          onChange={(e) => setLayer(e.target.value)}
        >
          <option value="">全部层级</option>
          {Object.entries(layers).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={showDeleted}
            onChange={(e) => setShowDeleted(e.target.checked)}
          />
          显示已停用项
        </label>
        <select
          aria-label="关注点版本"
          value={readOnly ? view.registry.hash : ""}
          onChange={(e) => load(e.target.value)}
        >
          <option value="">当前版本 {view?.revision ?? 0}</option>
          {view?.versions?.map((v: any) => (
            <option key={v.revision + "-" + v.hash} value={v.hash}>
              版本{v.revision} · {new Date(v.at * 1000).toLocaleString()}
            </option>
          ))}
        </select>
      </div>
      {readOnly && (
        <div className="management-notice">
          正在查看历史只读版本。
          <button onClick={() => load()}>返回当前版本</button>
          <button disabled={busy} onClick={() => save(null, view.registry)}>
            恢复为新版本
          </button>
          {view.reports?.map((r: any) => (
            <a key={r.path} href={fileUrl(project, r.path)} download>
              下载该版本报告
            </a>
          ))}
        </div>
      )}
      {!view ? (
        <p className="management-loading">正在读取项目定义…</p>
      ) : (
        <div className="management-body">
          <aside className="management-list" aria-label="关注点列表">
            <ConcernTree
              project={project}
              selected={selected}
              query={query}
              pick={pick}
              paths={view.presentation?.paths || {}}
              definitions={Object.entries(defs).filter(
                ([, d]: any) =>
                  (showDeleted || d.enabled !== false) &&
                  (!layer || d.layer === layer),
              )}
            />
          </aside>
          <section className="management-detail">
            {form ? (
              <>
                <div className="detail-kicker">
                  {selected ? "编辑定义" : "新增定义"}
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    save();
                  }}
                >
                  <fieldset disabled={readOnly || busy}>
                    <label>
                      稳定ID
                      <input
                        aria-label="关注点ID"
                        value={form.key}
                        disabled={!!selected}
                        onChange={(e) =>
                          setForm({ ...form, key: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      名称
                      <input
                        aria-label="关注点名称"
                        required
                        value={form.label}
                        onChange={(e) =>
                          setForm({ ...form, label: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      定义与判断边界
                      <textarea
                        aria-label="关注点定义"
                        required
                        rows={5}
                        value={form.description}
                        onChange={(e) =>
                          setForm({ ...form, description: e.target.value })
                        }
                        placeholder="说明检查什么、不包含什么，以及适用条件"
                      />
                    </label>
                    <div className="form-columns">
                      <label>
                        层级
                        <select
                          aria-label="关注点层级"
                          disabled={!!selected}
                          value={form.layer}
                          onChange={(e) => {
                            const l = e.target.value,
                              g = Object.keys(groups[l])[0];
                            setForm({
                              ...form,
                              layer: l,
                              group: g,
                              technology: l === "technology" ? g : null,
                              ...(!selected
                                ? {
                                    key: (
                                      {
                                        human: "human.custom_",
                                        relation: "service_relation.custom_",
                                        shared: "api.data.custom_",
                                      } as Record<string, string>
                                    )[l]
                                      ? (
                                          {
                                            human: "human.custom_",
                                            relation:
                                              "service_relation.custom_",
                                            shared: "api.data.custom_",
                                          } as Record<string, string>
                                        )[l] + Date.now().toString(36)
                                      : "custom." + Date.now().toString(36),
                                  }
                                : {}),
                            });
                          }}
                        >
                          {Object.entries(layers).map(([k, v]) => (
                            <option key={k} value={k}>
                              {v}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        分类
                        <select
                          aria-label="关注点功能分类"
                          value={form.group}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              group: e.target.value,
                              technology:
                                form.layer === "technology"
                                  ? e.target.value
                                  : null,
                            })
                          }
                        >
                          {Object.entries(groups[form.layer]).map(([k, v]) => (
                            <option key={k} value={k}>
                              {v}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="form-columns">
                      <label>
                        项目类型
                        <select
                          aria-label="关注点项目类型"
                          value={form.kind}
                          onChange={(e) =>
                            setForm({ ...form, kind: e.target.value })
                          }
                        >
                          <option value="check">具体检查项</option>
                          <option value="family">分类／父节点</option>
                        </select>
                      </label>
                      <label>
                        适用依据
                        <select
                          aria-label="关注点适用依据"
                          value={form.guard || ""}
                          onChange={(e) =>
                            setForm({ ...form, guard: e.target.value || null })
                          }
                        >
                          <option value="">
                            不限定类别（仍须正常规则依据）
                          </option>
                          {Object.entries(guards).map(([k, v]) => (
                            <option key={k} value={k}>
                              {v}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <h4>适用操作（不选表示不限操作）</h4>
                    <div className="checkbox-grid">
                      {Object.entries(operations).map(([k, v]) => (
                        <label key={k}>
                          <input
                            type="checkbox"
                            checked={form.operation_kinds.includes(k)}
                            onChange={(e) =>
                              setForm({
                                ...form,
                                operation_kinds: e.target.checked
                                  ? [...form.operation_kinds, k]
                                  : form.operation_kinds.filter(
                                      (x: string) => x !== k,
                                    ),
                              })
                            }
                          />
                          {v}
                        </label>
                      ))}
                    </div>
                    <details>
                      <summary>继承的父关注点（{form.parents.length}）</summary>
                      <div className="checkbox-grid parent-choices">
                        {Object.entries(defs)
                          .filter(
                            ([k, d]: any) =>
                              k !== form.key && d.enabled !== false,
                          )
                          .map(([k, d]: any) => (
                            <label key={k}>
                              <input
                                type="checkbox"
                                checked={form.parents.includes(k)}
                                onChange={(e) =>
                                  setForm({
                                    ...form,
                                    parents: e.target.checked
                                      ? [...form.parents, k]
                                      : form.parents.filter(
                                          (x: string) => x !== k,
                                        ),
                                  })
                                }
                              />
                              {d.label}
                              <small>{k}</small>
                            </label>
                          ))}
                      </div>
                    </details>
                    <div className="decision-actions">
                      <button className="primary-action" type="submit">
                        {busy ? "保存中…" : "保存为新版本"}
                      </button>
                      {selected && (
                        <button
                          type="button"
                          className="danger-action"
                          onClick={() =>
                            save({ ...form, enabled: form.enabled === false })
                          }
                        >
                          {form.enabled === false ? "恢复关注点" : "删除关注点"}
                        </button>
                      )}
                    </div>
                    <p className="muted">
                      删除会从当前使用范围停用，历史定义保留。跨对象层级调整请新建关注点并停用旧项。存在启用子项时，需先调整继承关系。
                    </p>
                  </fieldset>
                </form>
              </>
            ) : (
              <div className="management-empty">
                选择左侧关注点查看层级和定义，或新增一项。
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
