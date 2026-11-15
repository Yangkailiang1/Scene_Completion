import type { Observation, SourceRef } from "../ssd/types";

// Related requirements are context for GT, never the origin of a test observation.
export function relatedRequirementRefs(
  bundle: any,
  record: Observation,
): SourceRef[] {
  const anchor = (bundle.steps || bundle.anchors || []).find(
    (s: any) => s.id === (record.step_id || record.anchor_id),
  );
  const field = anchor?.data?.find((f: any) => f.id === record.field_id);
  const refs = record.requirement_refs?.length
    ? record.requirement_refs
    : [...(field?.source_refs || []), ...(anchor?.source_refs || [])];
  const docs = new Map(
    (bundle.documents || []).map((d: any) => [d.id, d.role]),
  );
  const found = new Map<string, SourceRef>();
  for (const ref of refs) {
    if (
      ["RR", "SR"].includes(String(docs.get(ref.document_id))) ||
      (!docs.size && ref.kind === "origin")
    ) {
      found.set(
        JSON.stringify([ref.document_id, ref.start_line, ref.end_line]),
        ref,
      );
    }
  }
  return [...found.values()];
}
