import { FolderOpen, X } from "lucide-react";
import { Button } from "../../components/ui/button";
import { ModelSettings } from "../../features/models/ModelSettings";
import { sourceFile } from "../../features/sources/TestSources";
import { api } from "../../shared/api";
import type { Project } from "../../shared/types";
import type { AppController } from "../types";
export function ProjectDialog({
  setDialog,
  dialog,
  setNewCreating,
  setNewTestError,
  setNewTestPreview,
  loadProjects,
  openProject,
  setBundleCreate,
  newTestRequest,
  current,
  setNewTestLoading,
  newTestError,
  newTestLoading,
  newTestPreview,
  newCreating,
  snapshot,
  refresh,
  setNotice,
}: Pick<
  AppController,
  | "setDialog"
  | "dialog"
  | "setNewCreating"
  | "setNewTestError"
  | "filter"
  | "setNewTestPreview"
  | "loadProjects"
  | "openProject"
  | "setBundleCreate"
  | "newTestRequest"
  | "current"
  | "setNewTestLoading"
  | "newTestError"
  | "newTestLoading"
  | "newTestPreview"
  | "value"
  | "newCreating"
  | "project"
  | "snapshot"
  | "refresh"
  | "setNotice"
>) {
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && setDialog(null)}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={dialog === "new" ? "新建项目" : "模型配置"}
      >
        <button
          className="modal-close"
          onClick={() => setDialog(null)}
          aria-label="关闭对话框"
        >
          <X size={18} />
        </button>
        {dialog === "new" ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = e.currentTarget;
              const form = new FormData(f);
              (async () => {
                setNewCreating(true);
                setNewTestError("");
                const sources: Record<string, any[]> = {};
                for (const role of ["RR", "SR", "AR", "test"])
                  sources[role] = await Promise.all(
                    (form.getAll(role) as File[])
                      .filter((v) => v.name)
                      .map(sourceFile),
                  );
                const checked = await api("/api/test-sources/preview", {
                  method: "POST",
                  body: JSON.stringify({ sources: sources.test }),
                });
                setNewTestPreview(checked);
                if (!checked.valid) {
                  setNewTestError(
                    "请先修正下面列出的测试导入问题，文件仍保留在当前表单。",
                  );
                  return;
                }
                const p = await api<Project>("/api/projects", {
                  method: "POST",
                  body: JSON.stringify({
                    name: form.get("name"),
                    review_mode: form.get("review_mode"),
                    evaluation_scope: "SR",
                    case_ids: String(form.get("case_ids") || "")
                      .split(/[,，\s]+/)
                      .filter(Boolean),
                    sources,
                  }),
                });
                await loadProjects();
                openProject(p.id);
                setDialog(null);
              })()
                .catch((err: any) => {
                  if (err.importPreview) setNewTestPreview(err.importPreview);
                  setNewTestError(err.message);
                })
                .finally(() => setNewCreating(false));
            }}
          >
            <span className="eyebrow">NEW PROJECT</span>
            <h2>新建审核项目</h2>
            <p>文档与模型结果保存在本地，逐节点检查有据可循。</p>
            <button
              type="button"
              onClick={() => {
                setDialog(null);
                setBundleCreate(true);
              }}
            >
              <FolderOpen size={16} /> 从五类JSON文件夹／绝对路径新建
            </button>
            <label>
              项目名称
              <input name="name" required placeholder="例如：商城需求审核" />
            </label>
            {[
              ["RR", "RR 系统需求文档"],
              ["SR", "SR 功能设计文档"],
              ["AR", "AR 分配需求文档（可选）"],
              ["test", "测试文档（可选）"],
            ].map(([name, label]) => (
              <label key={name}>
                {label}
                <input
                  type="file"
                  name={name}
                  accept={
                    name === "test"
                      ? ".md,.markdown,.json,.xlsx"
                      : ".md,.markdown,.json"
                  }
                  multiple
                  required={name === "RR" || name === "SR"}
                  onChange={
                    name === "test"
                      ? async (e) => {
                          const request = ++newTestRequest.current;
                          setNewTestPreview(null);
                          setNewTestError("");
                          setNewTestLoading(true);
                          try {
                            const sources = await Promise.all(
                              Array.from(e.target.files || []).map(sourceFile),
                            );
                            const result = await api(
                              "/api/test-sources/preview",
                              {
                                method: "POST",
                                body: JSON.stringify({ sources }),
                              },
                            );
                            if (request === newTestRequest.current)
                              setNewTestPreview(result);
                          } catch (err: any) {
                            if (request === newTestRequest.current)
                              setNewTestError(err.message);
                          } finally {
                            if (request === newTestRequest.current)
                              setNewTestLoading(false);
                          }
                        }
                      : undefined
                  }
                />
              </label>
            ))}
            {newTestError && <p role="alert">{newTestError}</p>}
            {newTestLoading && <p role="status">正在检查测试文件…</p>}
            {newTestPreview && (
              <section
                className="test-import-preview"
                aria-label="测试导入预览"
              >
                <p>
                  测试导入预览：异常 {newTestPreview.counts?.exception || 0} /
                  正常 {newTestPreview.counts?.normal || 0} / 可选{" "}
                  {newTestPreview.counts?.optional || 0} / 待确认{" "}
                  {newTestPreview.counts?.pending || 0}。
                </p>
                {!!newTestPreview.semantic_index_required?.length && (
                  <p>
                    以下文件将在运行时独立整理测试用例与场景，并与RR/SR用例对齐：
                    {newTestPreview.semantic_index_required.join("、")}
                    。当前尚未计入上述结构化预览数量。
                  </p>
                )}
                {!!newTestPreview.issues?.length && (
                  <details open={!newTestPreview.valid}>
                    <summary>
                      {newTestPreview.valid
                        ? "不参与计分的待确认提示"
                        : "需要修正的导入问题"}
                      （{newTestPreview.issues.length}项）
                    </summary>
                    <ul>
                      {newTestPreview.issues.map((x: any, n: number) => (
                        <li key={n}>
                          {x.source} 第{x.row}行 {x.id}：{x.reason}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </section>
            )}
            <div className="form-grid">
              <label>
                执行模式
                <select name="review_mode">
                  <option value="manual">中间产物手动确认</option>
                  <option value="auto">自动运行完整流程</option>
                </select>
              </label>
              <label>
                用例范围（可选）
                <input name="case_ids" placeholder="留空分析所有用例" />
              </label>
            </div>
            <Button
              className="mt-5 w-full"
              type="submit"
              disabled={
                newTestLoading || newCreating || newTestPreview?.valid === false
              }
            >
              {newCreating ? "正在创建…" : "创建项目"}
            </Button>
          </form>
        ) : (
          <ModelSettings
            project={current!}
            config={snapshot?.config || {}}
            onSaved={() => {
              setDialog(null);
              refresh();
              setNotice("模型配置已保存。");
            }}
          />
        )}
      </div>
    </div>
  );
}
