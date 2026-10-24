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
  project: Project;
  job: { status: string; message?: string };
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
