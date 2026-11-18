export type Channel = "E" | "G" | "GT";
export type SourceRef = {
  document_id: string;
  start_line: number;
  end_line: number;
  quote: string;
  kind?: string;
  json_pointer?: string;
  origin?: string;
};
export type SourceDocument = {
  id: string;
  name: string;
  role: string;
  content: string;
  hash?: string;
};
export type Party = {
  id: string;
  name: string;
  type: string;
  technology?: string;
  external?: boolean;
};
export type Field = {
  id: string;
  name: string;
  location: string;
  type?: string;
  required?: boolean | null;
  command_id?: string;
  call_step_id?: string;
  validation_step_ids?: string[];
  response_step_ids?: string[];
  rule_texts?: string[];
  constraints: { kind: string; value: any; source_refs?: SourceRef[] }[];
  source_refs: SourceRef[];
};
export type Step = {
  id: string;
  order: number;
  kind: string;
  layer: string;
  direction: string;
  sender: Party;
  receiver: Party;
  operation: {
    name: string;
    kinds: string[];
    kinds_source?: string;
    command_id?: string;
    http_method?: string;
    http_path?: string;
    reason?: string;
  };
  data: Field[];
  api_id: string | null;
  entity_ids: string[];
  source_refs: SourceRef[];
  parent_id?: string | null;
  [key: string]: any;
};
export type Observation = {
  id: string;
  step_id?: string;
  target?: string;
  key?: string;
  label?: string;
  field_id?: string | null;
  entity_id?: string | null;
  attribute?: string | null;
  condition: string;
  expected?: string;
  concern_ids?: string[];
  status: string;
  source_refs: SourceRef[];
  rule_id?: string;
  [key: string]: any;
};
export type Decision = {
  id: string;
  level: string;
  pair: string;
  left_id: string;
  right_id: string;
  status: string;
  reason: string;
  origin: string;
};
export type Bundle = {
  version: string;
  case: { id: string; name: string };
  steps: Step[];
  channels: Record<
    Channel,
    {
      concerns: Observation[];
      scenarios: Observation[];
      pending: Observation[];
    }
  >;
  documents: SourceDocument[];
  analysis_profile?: string;
  command_bindings?: Record<
    string,
    {
      primary_step_id: string;
      occurrences: string[];
      validation_step_ids?: string[];
      response_step_ids?: string[];
    }
  >;
  field_anchors?: {
    units: { step_id: string; entity: string; attribute: string }[];
  };
  entities?: {
    id: string;
    attributes: {
      name: string;
      type?: string;
      tags?: string[];
      constraints: Field["constraints"];
      source_refs?: SourceRef[];
    }[];
  }[];
  source_classifications?: Partial<
    Record<
      "E" | "GT",
      {
        record_id: string;
        kind: string;
        condition: string;
        reason: string;
        source_refs: SourceRef[];
      }[]
    >
  >;
  decisions: Decision[];
  pending: Observation[];
  [key: string]: any;
};
export const channelLabels = { E: "原文抽取", G: "方法生成", GT: "测试逆向" };
export const targetLabels: Record<string, string> = {
  sender: "发送方",
  data: "数据",
  receiver: "接收方",
};
export const uid = (prefix: string) =>
  `${prefix}-${globalThis.crypto?.randomUUID?.() || Date.now().toString(36) + Math.random().toString(36).slice(2)}`;
export const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value));
