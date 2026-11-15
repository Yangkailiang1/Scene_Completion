"""Presentation rows preserve manual grouping without creating coverage decisions."""

from copy import deepcopy


def display_rows(bundle, comparison):
    result = deepcopy(comparison)
    for kind in ("concerns", "scenarios"):
        rows = result[kind]
        by_id = {row["id"]: row for row in rows}
        coverage = {k: v for row in rows for k, v in row.get("coverage_by_record", {}).items()}
        manual = []
        for channel in ("E", "G", "GT"):
            for record in bundle["channels"][channel][kind]:
                if record.get("display_row_id"):
                    manual.append((channel, record))
        for channel, record in manual:
            for row in rows:
                row["cells"][channel] = [
                    r for r in row["cells"][channel] if r["id"] != record["id"]
                ]
        for channel, record in manual:
            identity = record["display_row_id"]
            if identity not in by_id:
                row = {
                    "id": identity,
                    **{
                        k: record.get(k)
                        for k in ("step_id", "anchor_id", "target", "key", "field_id", "entity_id")
                    },
                    "cells": {c: [] for c in ("E", "G", "GT")},
                    "status": "single",
                    "reason": "人工表格行；覆盖由独立匹配判断",
                }
                by_id[identity] = row
                rows.append(row)
            by_id[identity]["cells"][channel].append(deepcopy(record))
            if record["id"] in coverage:
                by_id[identity].setdefault("coverage_by_record", {})[record["id"]] = coverage[
                    record["id"]
                ]
        result[kind] = [row for row in rows if any(row["cells"].values())]
    return result
