"""Literal HTTP declarations in prose, tables and Mermaid; preserve source text."""
import re

METHOD=re.compile(r'\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+',re.I)
BREAK=re.compile(r'<\s*br\s*/?\s*>|&lt;\s*br\s*/?\s*&gt;|\\n',re.I)


def clean_path(value):
    text=BREAK.split(str(value),maxsplit=1)[0].strip().strip('`"\'')
    if text.startswith('http://') or text.startswith('https://'):
        from urllib.parse import urlsplit
        text=urlsplit(text).path
    # Stop at presentation boundaries, never synthesize missing braces.
    path=re.split(r'[\s`"\'，。；,;|()（）<>]',text,maxsplit=1)[0].split('?',1)[0]
    if not path.startswith('/') or not path or path.count('{')!=path.count('}'):return None
    return path


def declarations(text):
    out=[]
    for match in METHOD.finditer(text):
        if re.search(r'不是|不要|禁止',text[max(0,match.start()-12):match.start()]):continue
        path=clean_path(text[match.end():])
        if path:out.append((match[1].upper(),path))
    return out


def normalize_mapping(value):
    from copy import deepcopy
    out=deepcopy(value)
    for service in out.get('services',[]):
        for api in service.get('interfaces',[]):
            address=api.get('address')
            if not address:continue
            pure=clean_path(address)
            refs=api.get('source_refs',[])
            # Only presentation cleanup supported by this interface's own quote.
            if pure and pure!=address and any((not api.get('method') or (api['method'].upper(),pure) in declarations(r['quote'])) and pure in r['quote'] for r in refs):api['address']=pure
    return out
