import {
  resultGet,
  resultSummary,
  invalidateResults,
} from "../shared/resultRequests";
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
    `results/${encodeURIComponent(caseId)}/editor${revision === "current" ? "?compact=true" : `?revision=${encodeURIComponent(revision)}&compact=true`}`,
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

export async function exportSsdBusinessReport(
  project: string,
  selection: {
    case_ids?: string[];
    record_ids?: string[];
    scopes?: string[];
    anchor_ids?: string[];
  },
) {
  const response = await fetch(projectUrl(project, "ssd-review/report"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(selection),
  });
  if (!response.ok)
    throw new Error((await response.json()).detail || "导出失败");
  return response.blob();
}

export function getReviewSummary(project: string, body: object = {}) {
  return resultSummary(project, "ssd-review/summary", body);
}
