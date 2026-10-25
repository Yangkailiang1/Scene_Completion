import { useEffect, useState } from "react";
import { api, projectUrl } from "./api";
export async function sourceFile(file: File) {
  if (!file.name.toLowerCase().endsWith(".xlsx"))
    return { name: file.name, content: await file.text() };
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 8192)
    binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return { name: file.name, content_base64: btoa(binary) };
}
export function TestSources({ project }: { project: string }) {
  const [supplement, setSupplement] = useState<any>(null);
  async function loadSupplement(cid?: string) {
    try {
      setSupplement(
        await api(
          projectUrl(
            project,
            "test-sources/supplement" +
              (cid ? "?case=" + encodeURIComponent(cid) : ""),
          ),
        ),
      );
    } catch (e: any) {
      setError(e.message);
    }
  }
  const [data, setData] = useState<any>(null),
    [preview, setPreview] = useState<any>(null),
    [sources, setSources] = useState<any[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = () =>
    api(projectUrl(project, "test-sources"))
      .then(setData)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, [project]);
  async function save(version?: string) {
    setBusy(true);
    setError("");
    try {
      setData(
        await api(projectUrl(project, "test-sources"), {
          method: "PUT",
          body: JSON.stringify({
            expected_version: data.version,
            ...(version ? { version } : { sources }),
          }),
        }),
      );
      setPreview(null);
      setSources([]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="test-sources-panel">
      <h3>测试集与Excel导入</h3>
      <p>
        只有类型为“异常”的记录进入指标。正常、可选及待确认保留查看。扩展测试集自动计分，机器补充与原始测试分别追溯。
      </p>
      <a href="/api/test-sources/template" download>
        下载商城14用例Excel示例
      </a>
      <details
        onToggle={(e) => {
          if (e.currentTarget.open && !supplement) loadSupplement();
        }}
      >
        <summary>按用例查看独立机器补充的异常测试</summary>
        <p>仅依据正向交互和契约补充，自动GT，不表示测试已经执行。</p>
        {supplement && (
          <>
            <select
              aria-label="补充测试用例"
              value={supplement.case || ""}
              onChange={(e) => loadSupplement(e.target.value)}
            >
              <option value="">选择用例</option>
              {supplement.cases.map((c: any) => (
                <option key={c.id} value={c.id}>
                  {c.id} · {c.name}
                </option>
              ))}
            </select>
            {supplement.case && (
              <p>
                产物状态：
                {supplement.status === "passed" ? "已保存" : supplement.status}
                ；{supplement.tests.length} 条测试
              </p>
            )}
            {supplement.pending?.length>0 && <details><summary>未计入GT的补充待确认项 {supplement.pending.length}</summary>{supplement.pending.map((p:any,n:number)=><p key={n}>{p.interaction_id}：{p.reason}</p>)}</details>}
            <div className="alignment-scroll">
              <table>
                <thead>
                  <tr>
                    <th>交互／关注点</th>
                    <th>前置条件</th>
                    <th>触发／测试数据</th>
                    <th>测试步骤</th>
                    <th>预期结果</th>
                  </tr>
                </thead>
                <tbody>
                  {supplement.tests.map((t: any, n: number) => (
                    <tr key={n}>
                      <td>
                        {t.interaction_id}
                        <br />
                        {t.concern_key}
                        <br />
                        {t.executable ? "可执行" : "条件级，具体标准待确认"}
                      </td>
                      <td>{t.preconditions.join("；")}</td>
                      <td>
                        {t.trigger}
                        <br />
                        {t.test_data}
                      </td>
                      <td>
                        {t.steps.map((s: string, k: number) => (
                          <p key={k}>
                            {k + 1}. {s}
                          </p>
                        ))}
                      </td>
                      <td>{t.expected_result}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </details>
      <label>
        导入新版本（Markdown / XLSX）
        <input
          aria-label="上传测试文件"
          type="file"
          multiple
          accept=".md,.markdown,.xlsx"
          onChange={async (e) => {
            setError("");
            try {
              const values = await Promise.all(
                Array.from(e.target.files || []).map(sourceFile),
              );
              setSources(values);
              setPreview(
                await api("/api/test-sources/preview", {
                  method: "POST",
                  body: JSON.stringify({ sources: values }),
                }),
              );
            } catch (err: any) {
              setError(err.message);
            }
          }}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      {preview && (
        <>
          <h4>导入预览</h4>
          <p>
            异常 {preview.counts.exception} / 正常 {preview.counts.normal} /
            可选 {preview.counts.optional} / 待确认 {preview.counts.pending}
          </p>
          {preview.issues.map((x: any, i: number) => (
            <p key={i}>
              {x.source} 第{x.row}行 {x.id}：{x.reason}
            </p>
          ))}
          <button disabled={!preview.valid || busy} onClick={() => save()}>
            保存为当前测试版本
          </button>
        </>
      )}
      {data && (
        <>
          <p>当前版本：{data.version}。切换后需继续运行评测，历史报告保留。</p>
          <label>
            历史测试版本
            <select
              aria-label="测试集版本"
              value={data.version}
              disabled={busy}
              onChange={(e) => save(e.target.value)}
            >
              {data.versions.map((v: any) => (
                <option key={v.id} value={v.id}>
                  {v.id}
                </option>
              ))}
            </select>
          </label>
          <p>
            异常 {data.preview.counts.exception} / 正常{" "}
            {data.preview.counts.normal} / 可选 {data.preview.counts.optional} /
            待确认 {data.preview.counts.pending}
          </p>
          <div className="alignment-scroll">
            <table>
              <thead>
                <tr>
                  <th>测试ID</th>
                  <th>类型</th>
                  <th>测试名称</th>
                  <th>触发条件</th>
                  <th>来源</th>
                </tr>
              </thead>
              <tbody>
                {data.preview.records.map((r: any) => (
                  <tr key={r.source_id + ":" + r.row}>
                    <td>{r.id}</td>
                    <td>{r["类型"] || "待确认"}</td>
                    <td>{r["测试名称"]}</td>
                    <td>{r["触发条件"]}</td>
                    <td>
                      {r.name} · 行{r.row}
                      {r.source_location && (
                        <details>
                          <summary>单元格位置</summary>
                          <p>
                            {Object.entries(r.source_location.cells)
                              .map(([k, v]) => k + "：" + v)
                              .join("；")}
                          </p>
                        </details>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
