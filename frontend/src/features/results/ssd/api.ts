import { api, projectUrl } from "../../../shared/api";
import type { Bundle } from "./types";

export function getSsdResultIndex(project: string) {
  return api(projectUrl(project, "ssd-results"));
}

export function getSsdEditor(
  project: string,
  caseId: string,
  revision = "current",
) {
  return api(
    projectUrl(
      project,
      `results/${encodeURIComponent(caseId)}/editor${revision === "current" ? "" : `?revision=${encodeURIComponent(revision)}`}`,
    ),
  );
}

export function saveSsdRevision(
  project: string,
  caseId: string,
  body: { base_revision: number; bundle: Bundle; reason: string },
) {
  return api(
    projectUrl(project, `results/${encodeURIComponent(caseId)}/revisions`),
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function exportSsdReview(
  project: string,
  selection: { case_ids?: string[]; record_ids?: string[] },
) {
  const response = await fetch(projectUrl(project, "ssd-review/export"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(selection),
  });
  if (!response.ok)
    throw new Error((await response.json()).detail || "导出失败");
  return response.blob();
}

export function previewSsdReview(project: string, content: string) {
  return api(projectUrl(project, "ssd-review/preview"), {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function applySsdReview(
  project: string,
  content: string,
  caseIds: string[],
) {
  return api(projectUrl(project, "ssd-review/apply"), {
    method: "POST",
    body: JSON.stringify({ content, case_ids: caseIds }),
  });
}
