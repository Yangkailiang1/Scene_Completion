import { resultGet, invalidateResults } from "../shared/resultRequests";
import { api, projectUrl } from "../../../shared/api";
import type { ProjectBundle, ProjectScope } from "./types";
export function getProjectResultIndex(project: string) {
  return resultGet(project, "project-results");
}
export function getProjectEditor(
  project: string,
  scope: ProjectScope,
  revision = "current",
) {
  return resultGet(
    project,
    `project-results/${scope}/editor${revision === "current" ? "" : `?revision=${encodeURIComponent(revision)}`}`,
  );
}
export async function saveProjectRevision(
  project: string,
  scope: ProjectScope,
  body: { base_revision: number; bundle: ProjectBundle; reason: string },
) {
  const result = await api(
    projectUrl(project, `project-results/${scope}/revisions`),
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
  invalidateResults(project);
  return result;
}
export async function exportProjectReview(
  project: string,
  selection: {
    scope: ProjectScope;
    anchor_ids?: string[];
    record_ids?: string[];
  },
) {
  const response = await fetch(projectUrl(project, "project-review/export"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(selection),
  });
  if (!response.ok)
    throw new Error((await response.json()).detail || "导出失败");
  return response.blob();
}
export function previewProjectReview(
  project: string,
  scope: ProjectScope,
  content: string,
) {
  return api(projectUrl(project, "project-review/preview"), {
    method: "POST",
    body: JSON.stringify({ scope, content }),
  });
}
export async function applyProjectReview(
  project: string,
  scope: ProjectScope,
  content: string,
) {
  const result = await api(projectUrl(project, "project-review/apply"), {
    method: "POST",
    body: JSON.stringify({ scope, content }),
  });
  invalidateResults(project);
  return result;
}
