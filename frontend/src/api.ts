import type { Artifact } from "./types";
export function primaryJsonArtifact(artifacts: Artifact[]) {
  return artifacts.find(
    (a) =>
      a.name.endsWith(".json") &&
      !a.name.endsWith(".metadata.json") &&
      !a.name.endsWith(".layout.json"),
  );
}
export async function api<T = any>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!r.ok) {
    let error = `请求失败（${r.status}）`;
    let preview: any;
    try {
      const b = await r.json();
      error = typeof b.detail === "string" ? b.detail : error;
      preview = b.import_preview;
    } catch {}
    throw Object.assign(new Error(error), { importPreview: preview });
  }
  return r.json();
}
export function projectUrl(id: string, suffix = "") {
  return `/api/projects/${id}${suffix ? "/" + suffix : ""}`;
}
export function fileUrl(id: string, path: string) {
  return projectUrl(id, "file?path=" + encodeURIComponent(path));
}
