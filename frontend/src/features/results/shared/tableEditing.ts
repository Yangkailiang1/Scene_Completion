import type { Channel, Observation } from "../ssd/types";

export function clearTableCell(
  bundle: any,
  row: any,
  channel: Channel,
  kind: string,
  cascade = false,
) {
  const ids = new Set<string>(
    (row.cells[channel] || []).map((r: Observation) => r.id),
  );
  const data = bundle.channels[channel];
  data[kind] = data[kind].filter((r: Observation) => !ids.has(r.id));
  if (kind === "concerns") {
    data.scenarios = data.scenarios.flatMap((r: Observation) => {
      if (!(r.concern_ids || []).some((id: string) => ids.has(id))) return [r];
      if (cascade) return [];
      return [
        {
          ...r,
          concern_ids: (r.concern_ids || []).filter(
            (id: string) => !ids.has(id),
          ),
          status: "unbound",
          binding_issue: "关注点已清空，请重新挂载",
        },
      ];
    });
  }
  const remaining = new Set(
    [data.concerns, data.scenarios, data.pending]
      .flat()
      .map((r: Observation) => r.id),
  );
  bundle.decisions = bundle.decisions.filter(
    (d: any) =>
      !(
        (d.pair.split("_")[0] === channel && !remaining.has(d.left_id)) ||
        (d.pair.split("_")[1] === channel && !remaining.has(d.right_id))
      ),
  );
}

export function putTableRecord(
  bundle: any,
  channel: Channel,
  kind: string,
  value: Observation,
) {
  if (kind === "scenarios" && !(value.concern_ids || []).length) {
    const binding = (r: Observation) =>
      (r.step_id || r.anchor_id) === (value.step_id || value.anchor_id) &&
      r.target === value.target &&
      r.key === value.key &&
      (r.field_id || null) === (value.field_id || null) &&
      (r.entity_id || null) === (value.entity_id || null);
    let concern = bundle.channels[channel].concerns.find(binding);
    if (!concern) {
      concern = {
        ...value,
        id: "manual-concern-" + value.id,
        label:
          bundle.registry?.definitions?.[value.key || ""]?.label || value.key,
        origin: "manual",
      };
      delete concern.concern_ids;
      bundle.channels[channel].concerns.push(concern);
    }
    value.concern_ids = [concern.id];
  }
  const rows = bundle.channels[channel][kind];
  const pos = rows.findIndex((r: Observation) => r.id === value.id);
  if (pos < 0) rows.push(value);
  else rows[pos] = value;
}

// Grouping is a presentation choice; it never creates matching decisions.
export function groupDisplayRows(rows: any[]) {
  const result = rows.map((r) => ({
    ...r,
    cells: Object.fromEntries(
      Object.entries(r.cells).map(([ch, values]) => [
        ch,
        [...(values as any[])],
      ]),
    ),
  }));
  const byId = new Map(result.map((r) => [r.id, r]));
  const moved: { ch: string; record: any; coverage: any }[] = [];
  for (const row of result)
    for (const ch of ["E", "G", "GT"]) {
      row.cells[ch] = row.cells[ch].filter((record: any) => {
        if (!record.display_row_id || record.display_row_id === row.id)
          return true;
        moved.push({
          ch,
          record,
          coverage: row.coverage_by_record?.[record.id],
        });
        return false;
      });
    }
  for (const { ch, record, coverage } of moved) {
    let row = byId.get(record.display_row_id);
    if (!row) {
      row = {
        id: record.display_row_id,
        step_id: record.step_id,
        anchor_id: record.anchor_id,
        target: record.target,
        field_id: record.field_id,
        entity_id: record.entity_id,
        key: record.key,
        status: "single",
        reason: "人工表格行；匹配关系独立维护",
        cells: { E: [], G: [], GT: [] },
        coverage_by_record: {},
      };
      result.push(row);
      byId.set(row.id, row);
    }
    row.cells[ch].push(record);
    if (coverage)
      row.coverage_by_record = {
        ...row.coverage_by_record,
        [record.id]: coverage,
      };
  }
  return result.filter((r) =>
    Object.values(r.cells).some((v: any) => v.length),
  );
}
