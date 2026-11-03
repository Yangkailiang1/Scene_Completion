export type Role = "modeler" | "checker" | "recommender";
export interface Project {
  protocol?: string;
  id: string;
  name: string;
  review_mode: "manual" | "auto";
  case_ids?: string[];
  sources: Record<string, { path: string; name: string }[]>;
  created_at: number;
}
export interface GraphNode {
  target_key?: string | null;
  execution_task_key?: string;
  execution_status?: string;
  execution_provenance?: string;
  actual_import_reuse?: boolean;
  import_mode?: string;
  import_label?: string;
  input_bindings?: {
    file_id: string;
    name: string;
    purpose: string;
    original: string;
    revision: number;
    mode: string;
    explanation: string;
  }[];
  provenance?: string;
  import_sources?: { name: string; file_id: string; revision: number }[];
  recovery_calls?: number;
  planned?: boolean;
  input_summary?: string;
  artifacts?: { name: string; path: string; status: string }[];
  retry_at?: number | null;
  retry_count?: number | null;
  question?: any;
  guidance_revision?: number;
  id: string;
  stage: string;
  case: string;
  role: Role;
  label: string;
  status: string;
  phase: string;
  deps: string[];
  expected_files: string[];
  blocked_by: string[];
  failure: any;
  attempt: number;
  elapsed_seconds: number | null;
  last_event_at: number | null;
}
export interface Graph {
  preview_only?: boolean;
  summary?: Record<string, number>;
  nodes: GraphNode[];
  edges: { id: string; source: string; target: string }[];
  definition_available: boolean;
  case_expansion_pending: boolean;
  roles: {
    id: Role;
    label: string;
    completed: number;
    known: number;
    disabled: boolean;
  }[];
}
export interface Artifact {
  path: string;
  name: string;
  bytes: number;
  task_key?: string;
}
export interface Snapshot {
  review_only?: boolean;
  review_summary?: { unresolved: number; counts: Record<string, number> };
  project: Project;
  job: {
    status: string;
    message?: string;
    reason?: string;
    control_state?: string;
  };
  manifest: any;
  tasks: { tasks: Record<string, any>; events: any[] };
  reviews: any[];
  artifacts: Artifact[];
  config: Record<string, any>;
}
export interface ExecutionEvent {
  id: number;
  kind: string;
  at: number;
  task_key: string | null;
  role: Role | null;
  case: string | null;
  attempt: number | null;
  data: Record<string, any>;
}
export interface Review {
  key: string;
  task: string;
  input_hash: string;
  payload: any;
  inputs: any;
  status: string;
  revision: number;
  comment?: string;
}
