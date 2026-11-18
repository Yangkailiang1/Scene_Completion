import type { Observation, SourceDocument, SourceRef } from "../ssd/types";

const roleLabels: Record<string, string> = {
  RR: "RR 需求",
  SR: "SR 设计",
  test: "测试逆向",
  intermediate: "结构化抽取",
  artifact: "导入原文件",
  colleague_artifact: "抽取产物",
  colleague_structure: "结构化投影",
  colleague_behavior: "行为目录",
};

// Reviewers pick from the case snapshot only: saving rejects documents that
// differ from the pinned originals, so an outside file could never jump to a line.
export function documentChoices(documents: SourceDocument[] = []) {
  const found = documents
    .filter((d) => typeof d.content === "string")
    .map((d) => {
      const lines = d.content.split("\n").map((text, n) => ({
        number: n + 1,
        text,
      }));
      const suffix = /\.(md|markdown)$/i.test(d.name) ? "" : "（源码按行）";
      return {
        id: d.id,
        name: d.name,
        role: d.role,
        roleLabel: roleLabels[d.role] || d.role || "原文",
        label: `[${roleLabels[d.role] || d.role || "原文"}] ${d.name} · ${lines.length} 行${suffix}`,
        lines,
      };
    });
  return found;
}

export function documentLines(
  documents: SourceDocument[] = [],
  id: string,
): { number: number; text: string }[] {
  return documentChoices(documents).find((d) => d.id === id)?.lines || [];
}

// An empty range is not evidence: the record has no traceable origin yet.
export function hasTraceableSource(record: Observation) {
  return (record.source_refs || []).some(
    (r) => r.document_id && r.start_line >= 1,
  );
}

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
