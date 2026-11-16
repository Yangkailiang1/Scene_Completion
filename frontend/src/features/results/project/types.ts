import type { Bundle, SourceRef } from "../ssd/types";
export type AnalysisScope =
  | "interaction"
  | "business_chain"
  | "architecture"
  | "shared_services";
export type ProjectScope = Exclude<AnalysisScope, "interaction">;
export const scopeNames: Record<AnalysisScope, string> = {
  interaction: "交互级",
  business_chain: "业务链路",
  architecture: "项目架构",
  shared_services: "共用外部服务",
};
export type Anchor = {
  id: string;
  kind: "dependency" | "external_service";
  source_refs: SourceRef[];
  from_case_id?: string;
  to_case_id?: string;
  relation_type?: "direct" | "cascade";
  condition?: string;
  obligation?: string;
  entity_ids?: string[];
  name?: string;
  description?: string;
  external?: boolean;
  technology?: string;
  api_ids?: string[];
  case_ids?: string[];
  status?: string;
  [key: string]: any;
};
export type ProjectBundle = {
  version: "project-scope-v1";
  scope: { id: ProjectScope; name: string };
  anchors: Anchor[];
  channels: Bundle["channels"];
  documents: Bundle["documents"];
  decisions: Bundle["decisions"];
  pending: Bundle["pending"];
  registry: any;
  cases?: { id: string; name?: string }[];
  [key: string]: any;
};
export function anchorName(anchor?: Anchor) {
  if (!anchor) return "待重新挂载";
  return anchor.kind === "dependency"
    ? `${anchor.from_case_id || "待指定用例"} → ${anchor.to_case_id || "待指定用例"} · ${anchor.relation_type === "cascade" ? "级联" : "直接依赖"}`
    : anchor.name || anchor.id;
}
