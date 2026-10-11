"""Resolve literal table aliases from cited physical-resource evidence.

Never infer that equally named resources in different databases/documents share
identity. Qualified table tokens and internal/external origin remain distinct.
"""
import re

from .interaction_batches import cited_text


def physical_identity(node, index):
    name = node['name']
    if node['kind'] not in {'internal_database', 'external_database'}:
        return name, None
    match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*(?:表|table)?', name, re.I)
    if not match:
        return name, None
    token = match[1]
    text = cited_text(node['source_refs'], index)
    literal_table = re.search(r'(?<![A-Za-z0-9_.])' + re.escape(token) + r'\s*(?:表|\btable\b)(?![A-Za-z0-9_])', text, re.I)
    if not literal_table:
        return name, None
    documents = sorted({r['document'] for r in node['source_refs']})
    if '.' not in token:
        assigned = '\n'.join(d['text'] for d in index['documents'] if d['document'] in documents)
        qualified = re.findall(r'(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_.]*\.' + re.escape(token) + r')\s*(?:表|\btable\b)', assigned, re.I)
        if qualified:
            # Do not guess which physical database an unqualified alias denotes.
            return name, None
    return token, {'table_identifier': token, 'documents': documents,
        'origin': 'internal' if node['kind'] == 'internal_database' else 'external',
        'evidence_quote': literal_table.group(0)}
