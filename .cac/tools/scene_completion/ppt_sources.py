"""Independent source channels. Positive projections retain original line numbers."""
from copy import deepcopy
from pathlib import Path
import re
from .sources import fingerprint

# Section-level exclusion, including numbered use-case sections in existing specs.
EXCEPTION = re.compile(r'异常|扩展路径|失败路径|失败分支|错误处理|错误码|异常处理|异常码|HTTP\s*[45]\d\d|exception|alternative\s+flow|error\s+(?:handling|responses?)', re.I)
SECTION = re.compile(r'^\s*(?:#{1,6}\s+|\d+[.、]\s*|\*\*\d+[.、]\s*)')


def read_documents(paths, channel):
    docs=[]
    for path in paths:
        p=Path(path)
        if p.suffix.lower() not in {'.md','.markdown'}: raise ValueError('ppt-task-v1 sources must be Markdown')
        text=p.read_text(encoding='utf-8')
        lines=text.splitlines()
        docs.append({'source_id':fingerprint(str(p.resolve()))[:20], 'name':p.name,
                     'channel':channel,'lines':[{'number':i,'text':s} for i,s in enumerate(lines,1)]})
    if len({d['source_id'] for d in docs})!=len(docs): raise ValueError('duplicate document')
    return docs


def normal_projection(documents):
    result=[]
    for doc in documents:
        projected=[]; blocked=False; blocked_heading=None
        for row in doc['lines']:
            text=row['text']
            is_section=bool(SECTION.match(text))
            heading=re.match(r'^\s*(#{1,6})\s+',text)
            level=len(heading[1]) if heading else None
            if EXCEPTION.search(text):
                blocked=True; blocked_heading=level
            elif blocked and is_section:
                # A numbered item inside an exception block is NOT a new normal section.
                if (blocked_heading is None and level is not None) or (level is not None and blocked_heading is not None and level<=blocked_heading):
                    blocked=False; blocked_heading=None
            if not blocked and not EXCEPTION.search(text): projected.append(deepcopy(row))
        result.append({**doc,'channel':'normal','lines':projected})
    return result


def validate_evidence(value, documents):
    allowed={d['source_id']:{r['number']:r['text'] for r in d['lines']} for d in documents}
    def visit(node):
        if isinstance(node,dict):
            if set(node)=={'source_id','line_start','line_end','quote'}:
                rows=allowed.get(node['source_id'],{})
                start,end=node['line_start'],node['line_end']
                if end<start or end-start>100 or any(i not in rows for i in range(start,end+1)):
                    raise ValueError('evidence outside allowed source channel')
                text='\n'.join(rows[i] for i in range(start,end+1))
                if node['quote'] not in text: raise ValueError('evidence quote differs from source')
            else:
                for v in node.values():visit(v)
        elif isinstance(node,list):
            for v in node:visit(v)
    visit(value)


def documents_in(value):
    docs={}
    def visit(v):
        if isinstance(v,dict):
            if {'source_id','channel','lines'}<=v.keys():docs[v['source_id']]=v
            else:
                for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value)
    return list(docs.values())


def evidence_refs(value):
    refs=[]
    def visit(v):
        if isinstance(v,dict):
            if set(v)=={'source_id','line_start','line_end','quote'}: refs.append(v)
            else:
                for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value)
    return refs
