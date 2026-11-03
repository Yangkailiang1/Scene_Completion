/** Project-owned pattern settings; IDs and evidence rules remain server validated. */
export type RiskLevel = "low" | "normal" | "high" | "critical";
export interface PatternDefinition {
  id: string;
  label: string;
  concern_keys: string[];
  preconditions: string[];
  trigger_template: string;
  required_evidence: string;
  risk_level: RiskLevel;
  risk_reason: string;
  selector: string | null;
  enabled: boolean;
  version: number;
  definition_hash?: string;
}
export interface PatternSettings {
  threshold: number;
  top_k: number;
  risk_weight: number;
  history_weight: number;
  library: { version?: string; patterns: PatternDefinition[] };
  overrides: Record<string, { risk_level: RiskLevel; reason: string }>;
}
export interface PatternSettingsView {
  version: string;
  settings: PatternSettings;
  history: { version: string; at: number }[];
}
export interface ConcernDefinition {
  label: string;
  kind: string;
  enabled?: boolean;
}
