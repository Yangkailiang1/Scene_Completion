import { api, projectUrl } from "../../shared/api";
import type { PatternSettings, PatternSettingsView } from "./types";

export function loadPatternSettings(project: string, version?: string) {
  return api<PatternSettingsView>(
    projectUrl(
      project,
      "patterns" + (version ? "?version=" + encodeURIComponent(version) : ""),
    ),
  );
}

export function savePatternSettings(
  project: string,
  version: string,
  settings: PatternSettings,
) {
  return api<PatternSettingsView>(projectUrl(project, "patterns"), {
    method: "PUT",
    body: JSON.stringify({ expected_version: version, settings }),
  });
}
