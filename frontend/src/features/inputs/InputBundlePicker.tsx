import { CheckCircle2, FolderSearch, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, projectUrl } from "../../shared/api";

import { SuppliedCases } from "./SuppliedCases";

const roles = [
  ["RR", "RR结构模型"],
  ["SR", "SR结构模型"],
  ["function_tree", "功能树"],
  ["api_extraction", "接口抽取"],
  ["test", "测试逆向场景"],
];
export function InputBundlePicker({
  project,
  initialFiles,
  onClose,
  onImported,
}: {
  project: string;
  initialFiles?: File[];
  onClose: () => void;
  onImported: (value?: any) => void;
}) {
  const [mode, setMode] = useState("upload");
  const [directory, setDirectory] = useState("");
  const [paths, setPaths] = useState<Record<string, string>>({});
  const [selection, setSelection] = useState<any>(null);
  const [preview, setPreview] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [adopt, setAdopt] = useState(false);
  const [replace, setReplace] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState<File[]>(
    initialFiles || [],
  );
  const inspect = async (body: any) => {
    setBusy(true);
    setError("");
    setPreview(null);
    try {
      const result = await api("/api/input-bundles/preview", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSelection(body);
      setPreview(result);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    if (mode !== "upload" || !uploadedFiles.length) return;
    let live = true;
    setBusy(true);
    Promise.all(
      uploadedFiles
        .filter((f) => f.name.toLowerCase().endsWith(".json"))
        .map(async (f) => ({
          name: f.name,
          relative_path: f.webkitRelativePath || f.name,
          content: await f.text(),
        })),
    )
      .then((files) => {
        if (live) return inspect({ files });
      })
      .catch((e) => {
        if (live) {
          setError(e.message);
          setBusy(false);
        }
      });
    return () => {
      live = false;
    };
  }, [uploadedFiles, mode]);
  const apply = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api(
        project
          ? projectUrl(project, "input-bundles")
          : "/api/projects/from-input-bundle",
        {
          method: "POST",
          body: JSON.stringify({
            ...selection,
            expected_hash: preview.preview_hash,
            adopt_partial: adopt,
            replace,
            ...(!project
              ? {
                  name: projectName,
                  evaluation_scope: "SR",
                  review_mode: "manual",
                }
              : {}),
          }),
        },
      );
      onImported(result);
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="input-bundle-overlay">
      <section
        className="input-bundle-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="五类输入识别与导入"
      >
        <header>
          <div>
            <h2>
              <FolderSearch size={19} /> 五类输入识别与导入
            </h2>
            <p>
              按JSON内容识别用途，不执行文件内的Skill指令。确认前不导入、不调用模型。
            </p>
          </div>
          <button aria-label="关闭导入预览" onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        <div className="input-bundle-body">
          {!project && (
            <label>
              新项目名称
              <input
                aria-label="五文件新项目名称"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="例如：记忆平台需求审核"
              />
            </label>
          )}
          <div className="input-bundle-modes">
            {[
              ["upload", "上传文件／文件夹"],
              ["directory", "本机文件夹"],
              ["paths", "分别指定绝对路径"],
            ].map(([id, label]) => (
              <button
                key={id}
                className={mode === id ? "selected" : ""}
                onClick={() => {
                  setMode(id);
                  setPreview(null);
                }}
              >
                {label}
              </button>
            ))}
          </div>
          {mode === "directory" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                inspect({ directory });
              }}
            >
              <label>
                服务所在电脑的输入目录
                <input
                  aria-label="五类输入文件夹路径"
                  value={directory}
                  onChange={(e) => {
                    setDirectory(e.target.value);
                    setPreview(null);
                  }}
                  placeholder="C:\项目\输入文件 或 /Users/.../输入文件"
                  required
                />
              </label>
              <button disabled={busy}>识别文件夹</button>
            </form>
          )}
          {mode === "paths" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                inspect({
                  paths: Object.fromEntries(
                    Object.entries(paths).filter(([, v]) => v.trim()),
                  ),
                });
              }}
            >
              <div className="input-bundle-paths">
                {roles.map(([id, label]) => (
                  <label key={id}>
                    {label}
                    <input
                      aria-label={label + "绝对路径"}
                      value={paths[id] || ""}
                      onChange={(e) => {
                        setPaths({ ...paths, [id]: e.target.value });
                        setPreview(null);
                      }}
                      placeholder="文件的绝对路径"
                    />
                  </label>
                ))}
              </div>
              <button disabled={busy || !Object.values(paths).some(Boolean)}>
                识别指定文件
              </button>
            </form>
          )}
          {mode === "upload" && (
            <div className="input-bundle-upload">
              <label>
                选择JSON文件（五类输入及可选行为文件，支持多选）
                <input
                  type="file"
                  accept=".json"
                  multiple
                  aria-label="选择五份JSON文件"
                  onChange={(e) => {
                    setPreview(null);
                    setUploadedFiles(Array.from(e.target.files || []));
                  }}
                />
              </label>
              <label>
                或选择整个输入文件夹
                <input
                  type="file"
                  multiple
                  {...({ webkitdirectory: "", directory: "" } as any)}
                  aria-label="选择输入文件夹"
                  onChange={(e) => {
                    setPreview(null);
                    setUploadedFiles(Array.from(e.target.files || []));
                  }}
                />
              </label>
              <p>
                选择后自动识别用途和目标节点。RR、SR可以同名，按JSON内的层级区分；不要求重新上传原始Markdown。有效的行为模型进入融合
                SSD 预检。
              </p>
            </div>
          )}
          {busy && <p role="status">正在处理输入文件…</p>}
          {error && (
            <p role="alert" className="input-bundle-error">
              {error}
            </p>
          )}
          {preview && (
            <>
              <div className="input-bundle-summary">
                <CheckCircle2 size={16} />
                {preview.files.length} 份文件已识别 · 模型调用 0 次
              </div>
              {!!preview.supplied_cases?.cases.length && (
                <SuppliedCases preview={preview.supplied_cases} />
              )}
              <div className="input-bundle-table">
                <table>
                  <thead>
                    <tr>
                      <th>用途</th>
                      <th>来源文件</th>
                      <th>对应节点／提供的依据</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.files.map((f: any) => (
                      <tr key={f.role + ":" + f.path}>
                        <td>{f.label}</td>
                        <td>
                          <strong>{f.name}</strong>
                          <small>{f.path}</small>
                          {f.case_name && <small>用例：{f.case_name}</small>}
                          {f.error && (
                            <small role="alert">格式待修正：{f.error}</small>
                          )}
                        </td>
                        <td>
                          {f.target_nodes.map((n: string) => (
                            <code key={n}>{n}</code>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {preview.missing.length > 0 && (
                <p>
                  尚未提供：{preview.missing.join("、")}
                  。现有项目可以仅导入已识别部分。
                </p>
              )}
              {preview.issues.map((i: any, n: number) => (
                <p key={n} role="alert">
                  {i.role}：{i.reason}
                </p>
              ))}
              <p>
                仅运行已校验用例时，SR
                接口及字段约束来自功能树。缺少方向、位置或响应定义时会列出待补项。
              </p>
              <label className="input-bundle-checkbox">
                <input
                  type="checkbox"
                  checked={adopt}
                  onChange={(e) => setAdopt(e.target.checked)}
                />
                采用可校验的字段、属性和行为文件
              </label>
              <label className="input-bundle-checkbox">
                <input
                  type="checkbox"
                  checked={replace}
                  onChange={(e) => setReplace(e.target.checked)}
                />
                允许替换相关已有成功产物（旧版本保留）
              </label>
              {preview.ignored.length > 0 && (
                <details>
                  <summary>未采用的文件／副本 {preview.ignored.length}</summary>
                  {preview.ignored.map((f: any, n: number) => (
                    <p key={n}>
                      {f.name}：{f.reason}
                    </p>
                  ))}
                </details>
              )}
            </>
          )}
        </div>
        <footer>
          <span>保存后不自动运行模型。</span>
          <button onClick={onClose}>取消</button>
          <button
            className="input-primary"
            disabled={
              busy ||
              !preview?.valid ||
              !preview.files.length ||
              (!project &&
                (!projectName.trim() ||
                  (!(adopt && preview.supplied_cases?.accepted?.length) &&
                    preview.missing.some(
                      (k: string) => k === "RR" || k === "SR",
                    ))))
            }
            onClick={apply}
          >
            确认导入
          </button>
        </footer>
      </section>
    </div>
  );
}
