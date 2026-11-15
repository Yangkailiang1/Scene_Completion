import {
  setResultEpoch,
  invalidateResults,
} from "../results/shared/resultRequests";
import { getProjectResultIndex } from "../results/project/api";
import { useEffect, useRef, useState } from "react";
import { api, projectUrl } from "../../shared/api";
import { getSsdResultIndex } from "../results/ssd/api";
import {
  SsdReviewHandoff,
  type SsdReviewApplied,
  type SsdReviewCase,
  type SsdReviewSelection,
} from "./SsdReviewHandoff";
export function ReviewHandoff({
  project,
  reviewOnly = false,
  selection,
  onApplied,
  liveVersion,
}: {
  project: string;
  reviewOnly?: boolean;
  selection?: SsdReviewSelection;
  onApplied?: (result: SsdReviewApplied) => void;
  liveVersion?: string;
}) {
  const activeProject = useRef(project);
  activeProject.current = project;
  const [ssdCases, setSsdCases] = useState<SsdReviewCase[]>([]);
  const [projectScopes, setProjectScopes] = useState<string[]>([]);
  const [probe, setProbe] = useState<
    "loading" | "current" | "legacy" | "error"
  >("loading");
  const [probeProject, setProbeProject] = useState(project);
  const [retry, setRetry] = useState(0);
  const [format, setFormat] = useState<"auto" | "ssd" | "windows">("auto");
  const showSsd =
    (ssdCases.length > 0 || projectScopes.length > 0) && format !== "windows";
  const [status, setStatus] = useState<any>(null),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [document, setDocument] = useState<any>(null),
    [preview, setPreview] = useState<any>(null),
    [impact, setImpact] = useState<any>(null),
    [partial, setPartial] = useState(false);
  const load = () =>
    api(projectUrl(project, "handoff"))
      .then((value) => {
        if (activeProject.current === project) setStatus(value);
      })
      .catch((e) => {
        if (activeProject.current === project) setNotice(e.message);
      });
  useEffect(() => {
    setDocument(null);
    setPreview(null);
    setImpact(null);
    setFormat("auto");
    setSsdCases([]);
    setProjectScopes([]);
  }, [project]);
  useEffect(() => {
    let active = true;
    setResultEpoch(project, liveVersion);
    setProbe((previous) =>
      probeProject === project && previous === "current" ? previous : "loading",
    );
    Promise.allSettled([
      getProjectResultIndex(project),
      getSsdResultIndex(project),
    ]).then(([p, s]) => {
      if (!active) return;
      const scopes =
        p.status === "fulfilled" && p.value?.version === "project-scopes-v1"
          ? (p.value.scopes || [])
              .filter((x: any) => x.available !== false && x.revision != null)
              .map((x: any) => x.id)
          : [];
      const cases =
        s.status === "fulfilled" && s.value?.version === "ssd-case-v1"
          ? [...(s.value.cases || [])].sort(
              (a: SsdReviewCase, b: SsdReviewCase) =>
                a.id.localeCompare(b.id, undefined, { numeric: true }),
            )
          : [];
      setProbeProject(project);
      setProjectScopes(scopes);
      setSsdCases(cases);
      setProbe(
        cases.length || scopes.length
          ? "current"
          : p.status === "rejected" || s.status === "rejected"
            ? "error"
            : "legacy",
      );
    });
    return () => {
      active = false;
    };
  }, [project, liveVersion, retry]);
  useEffect(() => {
    if (probe === "legacy" || format === "windows") load();
  }, [project, probe, format]);
  async function exportPackage() {
    setBusy(true);
    try {
      const r = await fetch(projectUrl(project, "handoff/export"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format: "windows" }),
      });
      if (!r.ok) throw new Error((await r.json()).detail);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = window.document.createElement("a");
      a.href = url;
      a.download = "business-review-windows-x64.zip";
      a.click();
      URL.revokeObjectURL(url);
      setNotice(
        "审核包已导出。包含项目快照，不含模型凭证；请通过业务允许的渠道交付，不上传公开仓库。",
      );
      load();
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function importFile(file: File) {
    try {
      const d = JSON.parse(await file.text());
      setDocument(d);
      setPreview(
        await api(projectUrl(project, "feedback/import"), {
          method: "POST",
          body: JSON.stringify({ feedback: d, dry_run: true }),
        }),
      );
      setImpact(null);
    } catch (e: any) {
      setDocument(null);
      setPreview(null);
      setNotice(e.message);
    }
  }
  async function apply() {
    setBusy(true);
    try {
      const r = await api(projectUrl(project, "feedback/import"), {
        method: "POST",
        body: JSON.stringify({
          feedback: document,
          dry_run: false,
          allow_partial: partial,
        }),
      });
      setPreview(r);
      setImpact(r.impact || null);
      setNotice(
        r.duplicate
          ? "该反馈已导入，无重复应用。"
          : "反馈已保存，未启动模型。请核对下方影响范围后显式重跑。",
      );
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function run() {
    if (!impact) return;
    setBusy(true);
    try {
      await api(projectUrl(project, "rerun-affected"), {
        method: "POST",
        body: JSON.stringify({ plan_id: impact.plan_id }),
      });
      setNotice("已启动定向重跑，可回工作区查看进度。");
      setImpact(null);
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (probeProject !== project || probe === "loading")
    return (
      <p role="status" className="management-loading">
        正在识别审核格式与保存版本…
      </p>
    );
  if (probe === "error" && format !== "windows")
    return (
      <div role="alert">
        审核结果加载失败，未切换历史界面。
        <button onClick={() => setRetry((v) => v + 1)}>重试</button>
      </div>
    );
  return (
    <div className="management-view review-handoff-view">
      <div className="management-filters">
        <h3>审核交接</h3>
        <span>
          {showSsd
            ? "SSD 差异审核 · 预览后应用人工修改"
            : reviewOnly
              ? "业务审核模式 · 不运行模型"
              : "研发端 · 反馈导入后手动重跑"}
        </span>
        <button
          onClick={() => {
            invalidateResults(project);
            setRetry((v) => v + 1);
            if (format === "windows") load();
          }}
        >
          刷新
        </button>
      </div>
      {notice && (
        <p role="status" className="management-notice">
          {notice}
        </p>
      )}
      <div className="handoff-scroll">
        {(ssdCases.length > 0 || projectScopes.length > 0) && (
          <label className="management-filters">
            审核对象与格式
            <select
              aria-label="审核交接格式"
              value={showSsd ? "ssd" : "windows"}
              onChange={(event) =>
                setFormat(event.target.value as "ssd" | "windows")
              }
            >
              <option value="ssd">三层三方差异 · 离线 HTML / JSON</option>
              <option value="windows">
                业务问题与推荐 · Windows 审核包 / 反馈 JSON
              </option>
            </select>
          </label>
        )}
        {showSsd ? (
          <SsdReviewHandoff
            key={project}
            project={project}
            cases={ssdCases}
            selection={selection}
            onApplied={onApplied}
          />
        ) : (
          <>
            <div className="handoff-steps">
              <span>① 已知结果与待确认问题</span>
              <span>② 业务对照原文审核</span>
              <span>③ 交回反馈包</span>
              <span>④ 研发定向重跑</span>
            </div>
            {reviewOnly ? (
              <article>
                <h3>交回业务审核反馈</h3>
                <p>
                  回答和推荐审核均保存在本包。完成后下载反馈文件交回研发，无需返回完整目录；不会发送到外网。
                </p>
                <a
                  className="primary-action"
                  href={projectUrl(project, "feedback/export")}
                >
                  导出业务反馈包
                </a>
              </article>
            ) : (
              <>
                <article>
                  <h3>导出Windows业务审核包</h3>
                  <p>
                    包含Python、网页、原文、正式图表及审核快照。业务无需配置模型；保存回答不会重跑。原始思考流、API
                    Key、账号配置和额度账本不随包分发。
                  </p>
                  <button disabled={busy} onClick={exportPackage}>
                    {busy ? "处理中…" : "导出Windows业务审核包"}
                  </button>
                </article>
                <article>
                  <h3>导入业务反馈</h3>
                  <input
                    aria-label="选择业务反馈包"
                    type="file"
                    accept=".json"
                    onChange={(e) =>
                      e.target.files?.[0] && importFile(e.target.files[0])
                    }
                  />
                  {preview && (
                    <>
                      <p>
                        可应用 {preview.ready_count ?? 0} 项 · 冲突{" "}
                        {preview.conflicts?.length ?? 0} 项
                        {preview.saved ? " · 已保存" : " · 仅预览，尚未保存"}
                      </p>
                      {preview.conflicts?.map((c: any, i: number) => (
                        <p key={i} role="alert">
                          {c.id}：{c.reason}
                        </p>
                      ))}
                      {!!preview.conflicts?.length && (
                        <label>
                          <input
                            type="checkbox"
                            checked={partial}
                            onChange={(e) => setPartial(e.target.checked)}
                          />
                          仅导入无冲突项，保留冲突供后续核查
                        </label>
                      )}
                      <button
                        disabled={
                          busy ||
                          preview.saved ||
                          !!preview.duplicate ||
                          (!partial && !!preview.conflicts?.length)
                        }
                        onClick={apply}
                      >
                        保存有效反馈（不重跑）
                      </button>
                    </>
                  )}
                </article>
                <article>
                  <h3>查看受影响节点</h3>
                  <button
                    onClick={() =>
                      api(projectUrl(project, "impact"))
                        .then(setImpact)
                        .catch((e) => setNotice(e.message))
                    }
                  >
                    预览真实DAG影响范围
                  </button>
                  {impact && (
                    <>
                      <p>
                        来源节点 {impact.roots.length} 个 · 含下游{" "}
                        {impact.affected.length} 个
                      </p>
                      <ul>
                        {impact.nodes.map((n: any) => (
                          <li key={n.id}>
                            {n.label} <small>{n.id}</small>
                          </li>
                        ))}
                      </ul>
                      {impact.conflicts?.map((c: any) => (
                        <p key={c.id}>{c.reason}</p>
                      ))}
                      <button
                        className="primary-action"
                        disabled={
                          busy ||
                          !impact.roots.length ||
                          !!impact.conflicts.length
                        }
                        onClick={run}
                      >
                        按此范围重跑
                      </button>
                    </>
                  )}
                </article>
              </>
            )}
            <details>
              <summary>交接快照与版本记录</summary>
              {status?.snapshots?.map((s: any) => (
                <p key={s.id}>
                  {s.created_at} · {s.id}
                </p>
              ))}
            </details>
          </>
        )}
      </div>
    </div>
  );
}
