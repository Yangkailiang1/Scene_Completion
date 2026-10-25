"""Restore omitted, verbatim error-code citations inside the allowed case slice."""
from copy import deepcopy
import re
from .storage import fingerprint

def complete(value,inputs):
    out=deepcopy(value)
    for b in out['branches']:
        text=' '.join(r['quote'] for r in b['source_refs'])
        codes=set(re.findall(r'\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b',b['description']))
        for code in sorted(codes):
            if code in text:continue
            found=[{'source_id':d['source_id'],'line_start':r['number'],'line_end':r['number'],'quote':r['text']} for d in inputs['existing-documents'] for r in d['lines'] if re.search(r'\b'+re.escape(code)+r'\b',r['text'])]
            branches=[r for r in found if re.search(r'[-*]\s*[Aa]\d+[:：]',r['quote'])]
            selected=branches or found
            if not selected:raise ValueError('原文异常描述中的错误码没有本任务原文支持：'+code)
            b['source_refs']+=selected
        b['source_refs']=list({fingerprint(r):r for r in b['source_refs']}.values())
    return out
