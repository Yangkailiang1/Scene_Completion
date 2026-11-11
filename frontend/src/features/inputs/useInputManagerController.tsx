import { useEffect, useRef, useState } from "react";
import { api, projectUrl } from "../../shared/api";
const labels: Record<string, string> = {
  components: "系统组成",
  "api-map": "API映射",
  "api-parameters": "API参数",
  "rr-ssd": "RR SSD",
  "sr-ssd": "SR SSD",
  "fused-ssd": "融合SSD",
  "object-operations": "对象操作",
  "business-entities": "业务实体属性与约束",
};
const statuses: Record<string, string> = {
  candidate: "完整候选，待节点校验",
  accepted: "已确认",
  active: "已采用",
  needs_confirmation: "部分或结构待确认",
  needs_conversion: "等待格式转换",
  conversion_failed: "转换失败",
  converted: "转换完成",
  source_pending: "待确认原始材料",
  source_active: "已登记原始材料",
  unclassified: "待归类",
  rejected: "已拒绝",
};
export function useInputManagerController({
  project,
}: {
  project: string;
  reviewOnly?: boolean;
  onOpenPlan?: () => void;
}) {
  const [data, setData] = useState<any>({ items: [] }),
    [watch, setWatch] = useState<any>({}),
    [detail, setDetail] = useState<any>(null),
    [chosen, setChosen] = useState(0),
    [editor, setEditor] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [caseId, setCaseId] = useState(""),
    [cases, setCases] = useState<any[]>([]),
    [recovery, setRecovery] = useState<any>(null),
    [replace, setReplace] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const [bundleOpen, setBundleOpen] = useState(false);
  const [bundleFiles, setBundleFiles] = useState<File[] | undefined>();
  const selectedFile = useRef<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!detail?.id) {
      setEvents([]);
      return;
    }
    let live = true;
    const loadEvents = () =>
      api(
        projectUrl(
          project,
          "events/history?task_key=" +
            encodeURIComponent("imports:" + detail.id) +
            "&limit=1000",
        ),
      )
        .then((v) => live && setEvents(v.events || []))
        .catch(() => {});
    loadEvents();
    const timer = setInterval(loadEvents, 2000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [project, detail?.id]);
  const load = async () => {
    const [a, b, c, d] = await Promise.all([
      api(projectUrl(project, "imports")),
      api(projectUrl(project, "input-scan")),
      api(projectUrl(project, "results")),
      api(projectUrl(project, "recovery")),
    ]);
    setData(a);
    setWatch(b);
    setCases(c.cases || []);
    setRecovery(d);
    if (selectedFile.current) {
      const id = selectedFile.current;
      const row = await api(
        projectUrl(project, "imports?item=" + encodeURIComponent(id)),
      );
      // Refresh live bindings/status only. The editor is an independent unsaved draft.
      if (selectedFile.current === id) setDetail(row);
    }
  };
  useEffect(() => {
    setDetail(null);
    selectedFile.current = null;
    load().catch((e) => setMessage(e.message));
    const id = setInterval(() => load().catch(() => {}), 5000);
    return () => clearInterval(id);
  }, [project]);
  const select = async (id: string) => {
    selectedFile.current = id;
    const row = await api(
      projectUrl(project, "imports?item=" + encodeURIComponent(id)),
    );
    if (selectedFile.current !== id) return;
    setDetail(row);
    setChosen(0);
    setReplace(false);
    setEditor(JSON.stringify(row.artifacts?.[0]?.payload || {}, null, 2));
  };
  const action = async (
    fn: () => Promise<any>,
    success = "已保存；运行中变更保留为候选，下一安全执行轮接入。",
  ) => {
    setBusy(true);
    setMessage("");
    try {
      await fn();
      await load();
      setMessage(success);
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };
  const upload = async (files: FileList | null) =>
    action(async () => {
      const rows = await Promise.all(
        Array.from(files || []).map(async (f) => ({
          name: f.name,
          relative_path: f.webkitRelativePath || f.name,
          content_base64: await new Promise<string>((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(String(r.result).split(",")[1]);
            r.onerror = reject;
            r.readAsDataURL(f);
          }),
        })),
      );
      return api(projectUrl(project, "imports"), {
        method: "POST",
        body: JSON.stringify({ files: rows }),
      });
    });
  const artifact = detail?.artifacts?.[chosen];
  const [coverage, setCoverage] = useState("partial");
  useEffect(
    () => setCoverage(artifact?.coverage || "partial"),
    [detail?.id, chosen, artifact?.coverage],
  );
  const decide = (decision: string) =>
    action(async () => {
      await api(projectUrl(project, "imports/" + detail.id), {
        method: "PUT",
        body: JSON.stringify({
          action: decision,
          expected_revision: detail.revision,
          artifact_id: artifact?.id,
          coverage: artifact ? coverage : undefined,
          payload: artifact ? JSON.parse(editor) : undefined,
          case_id: caseId || undefined,
          replace,
        }),
      });
      await select(detail.id);
    });
  return {
    labels,
    statuses,
    data,
    setData,
    watch,
    setWatch,
    detail,
    setDetail,
    chosen,
    setChosen,
    editor,
    setEditor,
    message,
    setMessage,
    busy,
    setBusy,
    caseId,
    setCaseId,
    cases,
    setCases,
    recovery,
    setRecovery,
    replace,
    setReplace,
    events,
    setEvents,
    bundleOpen,
    setBundleOpen,
    bundleFiles,
    setBundleFiles,
    selectedFile,
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
  };
}
