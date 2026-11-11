"""Bounded lookup for the scoped CRUD task's evidence index."""

import json

PAGE_BYTES = 1900
MAX_LOOKUP_BYTES = 16 * 1024
INLINE_BYTES = 2048


def size(value):
    return len(json.dumps(value, ensure_ascii=False).encode("utf8"))


def location(ref):
    return {k: ref[k] for k in ("source_id", "line_start", "line_end")}


def lookup(context, evidence_ids, offsets):
    if offsets is None:
        offsets = {}
    if not isinstance(offsets, dict) or set(offsets) - set(evidence_ids):
        raise ValueError("offsets must refer only to requested evidence IDs")
    pages = {}
    for key in evidence_ids:
        ref = context.pool[key]
        quote = ref["quote"]
        start = offsets.get(key, 0)
        if type(start) is not int or not 0 <= start < len(quote):
            raise ValueError("evidence offset must be a valid character position")
        # Reserve space for the generated citation ID and JSON structure.
        base = {
            **location(ref),
            "offset": start,
            "next_offset": len(quote),
            "citation_id": "e" + "0" * 12,
        }
        low, high = start, min(start + PAGE_BYTES, len(quote))
        while low < high:
            end = (low + high + 1) // 2
            if size({**base, "quote": quote[start:end]}) <= PAGE_BYTES:
                low = end
            else:
                high = end - 1
        end = low
        if end == start:
            raise ValueError("evidence metadata exceeds the bounded lookup page")
        fragment = quote[start:end]
        citation = None
        if fragment.strip():
            citation = context.register({**location(ref), "quote": fragment})
            context.crud_read.add(citation)
        pages[key] = {
            **base,
            "quote": fragment,
            "citation_id": citation,
            "next_offset": end if end < len(quote) else None,
        }
    if size(pages) > MAX_LOOKUP_BYTES:
        raise ValueError("evidence lookup exceeds 16 KiB")
    return pages
