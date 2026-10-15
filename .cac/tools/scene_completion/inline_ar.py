"""Index explicitly labelled AR material embedded in SR without changing line numbers."""
import copy
import re
from .sources import fingerprint


def from_sr(index):
    documents=[]
    for original in index['documents']:
        if original.get('requirement_layer')!='SR':continue
        roots=[c for c in original['chapters'] if re.search(
            r'^(?:\[\s*)?AR(?:\b|需求|设计)|^架构需求|^Architecture\s+(?:requirements?|design)\b',c['title'],re.I)]
        if not roots:continue
        doc=copy.deepcopy(original)
        doc['chapters']=[c for c in doc['chapters'] if any(r['line_start']<=c['line_start']<=c['line_end']<=r['line_end'] for r in roots)]
        lines=doc['text'].splitlines()
        # Blank rather than remove unrelated SR text, so citations remain at
        # their original file/line/chapter. This is a trace-only source view.
        doc['text']='\n'.join(line if any(r['line_start']<=n<=r['line_end'] for r in roots) else '' for n,line in enumerate(lines,1))
        doc.update(requirement_layer='AR',material_requirement_layer='SR',embedded_ar=True,
            original_content_hash=original['content_hash'],content_hash=fingerprint(doc['text']))
        documents.append(doc)
    return {'schema_version':index.get('schema_version','three-agent-v1'),'documents':documents}
