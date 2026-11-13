export type ScopeUnit = {
  source_id: string;
  trigger: string;
  scope: string;
  global_kind: string | null;
  entity_ids: string[];
  related_cases: string[];
  reason: string;
};

export type ScopeRecord = {
  task_key: string;
  expected_version: string;
  pending_rerun: boolean;
  value: { units: ScopeUnit[] };
};

export type ScopeCatalogue = {
  records: ScopeRecord[];
  entities: { id: string; name: string }[];
  cases: { id: string; name: string }[];
};
