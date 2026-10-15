"""Literal evidence selection and bounded diagnosis-format repair helpers."""
from .sources import fingerprint


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,list):
        for item in value:yield from strings(item)
    elif isinstance(value,dict):
        for key,item in value.items():
            if key not in ('skill','extraction_skills','execution_versions','instructions'):
                yield from strings(item)


def quote_catalog(allowed, limit=40):
    result=[];seen=set()
    for text in strings(allowed):
        for line in text.splitlines():
            quote=line.strip()[:200]
            if len(quote)<4 or quote in seen:continue
            seen.add(quote);result.append({'id':'DQ-'+fingerprint(quote)[:12],'quote':quote})
            if len(result)>=limit:return result
    return result


def validate(packet,result):
    if result.get('action') not in ('repair','recheck','confirm') or not result.get('reason'):
        raise ValueError('diagnosis requires a permitted action and concrete reason')
    allowed=list(strings(packet['input']['allowed_inputs']))
    quotes=result.get('evidence_quotes',[])
    if not isinstance(quotes,list):raise ValueError('diagnosis evidence_quotes must be a list')
    quotes=list(quotes)
    catalog={r['id']:r['quote'] for r in packet['input'].get('evidence_catalog',[])}
    refs=result.get('evidence_refs',[])
    if not isinstance(refs,list) or any(not isinstance(ref,str) or ref not in catalog for ref in refs):
        raise ValueError('diagnosis evidence_refs must select supplied literal quote IDs')
    quotes.extend(catalog[ref] for ref in refs)
    # Match original string leaves, not Python repr(dict), which escapes
    # newlines and quotation marks and rejected otherwise literal evidence.
    if any(not isinstance(q,str) or not q or not any(q in text for text in allowed) for q in quotes):
        raise ValueError('diagnosis must quote supplied evidence')
    if result['action']=='recheck' and not quotes:
        raise ValueError('checker misjudgment requires independent original-source evidence')
    if not isinstance(result.get('targets'),list):raise ValueError('diagnosis must explicitly identify repair targets')
    return [{'action':result['action'],'reason':result['reason'],'targets':result['targets'],
        'evidence_quotes':list(dict.fromkeys(quotes))}]
