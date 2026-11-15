import { resultGet, invalidateResults } from "../shared/resultRequests";
import { api, projectUrl } from "../../../shared/api";
import type { Bundle } from "./types";

export function getSsdResultIndex(project: string) {
  return resultGet(project, "ssd-results");
}

export function getSsdEditor(
  project: string,
  caseId: string,
  revision = "current",
) {
  return resultGet(
    project,
    `results/${encodeURIComponent(caseId)}/editor${revision === "current" ? "" : `?revision=${encodeURIComponent(revision)}`}`,
  );
}

export async function saveSsdRevision(
  project: string,
  caseId: string,
  body: { base_revision: number; bundle: Bundle; reason: string },
) {
  const result = await api(
    projectUrl(project, `results/${encodeURIComponent(caseId)}/revisions`),
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
  invalidateResults(project);
  return result;
}

export async function exportSsdReview(
  project: string,
  selection: {
    case_ids?: string[];
    record_ids?: string[];
    scopes?: string[];
    anchor_ids?: string[];
  },
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

export async function applySsdReview(
  project: string,
  content: string,
  itemIds: string[],
) {
  const result = await api(projectUrl(project, "ssd-review/apply"), {
    method: "POST",
    body: JSON.stringify({ content, item_ids: itemIds }),
  });
  invalidateResults(project);
  return result;
}

export function getReviewSummary(project: string, body: object = {}) {
  return api(projectUrl(project, "ssd-review/summary"), {
    method: "POST",
    body: JSON.stringify(body),
  });
}
