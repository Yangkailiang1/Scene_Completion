import { api, projectUrl } from "../../../shared/api";
import type { ScopeCatalogue, ScopeRecord } from "./types";

export function getSavedResultIndex(
  project: string,
  includeArtifacts: boolean,
  importQuery = "",
  init: RequestInit = {},
) {
  return api(
    projectUrl(
      project,
      `results?include_artifacts=${includeArtifacts}${importQuery}`,
    ),
    init,
  );
}

export function getSavedCaseResult(
  project: string,
  caseId: string,
  testSet: string,
  scope: string,
  importQuery: string,
) {
  return api(
    projectUrl(
      project,
      `results/${encodeURIComponent(caseId)}?test_set=${encodeURIComponent(testSet)}&scope=${scope}${importQuery}`,
    ),
  );
}

export function savedMetricsPath(
  caseId: string | undefined,
  testSet: string,
  scope: string,
  importId: string,
) {
  return (
    `results/${caseId ? encodeURIComponent(caseId) + "/" : ""}metrics?test_set=${encodeURIComponent(testSet)}&scope=${scope}` +
    (importId ? "&import_id=" + encodeURIComponent(importId) : "")
  );
}

export function getSavedAggregate(
  project: string,
  path: string,
  testSet: string,
  scope?: string,
) {
  return api(
    projectUrl(
      project,
      `results/${path}?test_set=${encodeURIComponent(testSet)}${scope ? "&scope=" + scope : ""}`,
    ),
  );
}

export function getScopeCatalogue(project: string) {
  return api<ScopeCatalogue>(projectUrl(project, "analysis-scopes"));
}

export function saveScopeRecord(project: string, record: ScopeRecord) {
  return api(projectUrl(project, "analysis-scopes"), {
    method: "PUT",
    body: JSON.stringify({
      task_key: record.task_key,
      expected_version: record.expected_version,
      units: record.value.units,
    }),
  });
}
