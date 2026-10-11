"""Resolve original shared role and requirement definitions for normal extraction.

Kept separate from checker section assignment so normal context cannot expand C.
Identifiers are exact references, never inferred use-case decomposition units.
"""
import re

from .sources import validate_refs
from .interaction_participants import architecture_context


def model_context_sections(index, sections):
    context = architecture_context(index)
    seen = {(s['document'], s['line_start'], s['line_end']) for s in context}
    for doc in index['documents']:
        lines = doc['text'].splitlines()
        references = set()
        for section in sections:
            if section['document'] != doc['document']:
                continue
            for line in lines[section['line_start']-1:section['line_end']]:
                if re.search(r'关联|对应.*需求|Related\s+(?:requirement|spec)|Requirement\s+reference', line, re.I):
                    references.update(re.findall(r'\b[A-Za-z][A-Za-z0-9_]*(?:[-.:][A-Za-z0-9_]+)+\b', line))
        for number, line in enumerate(lines, 1):
            # Definition rows identify a referenced code in the first cell;
            # mentioning a code in an arbitrary branch is not a definition.
            first = line.strip().strip('|').split('|')[0].strip().strip('`')
            if first not in references or not line.lstrip().startswith('|'):
                continue
            if any(s['document'] == doc['document'] and s['line_start'] <= number <= s['line_end'] for s in sections + context):
                continue
            ref = validate_refs([{'document': doc['document'], 'line_start': number, 'line_end': number}], index)[0]
            key = (doc['document'], number, number)
            if key not in seen:
                seen.add(key)
                context.append({**ref, 'requirement_layer': doc['requirement_layer'],
                    'context_kind': 'referenced_requirement_definition', 'numbered_text': f'{number}: {line}'})
    return context
