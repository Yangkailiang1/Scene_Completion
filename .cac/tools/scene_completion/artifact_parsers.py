"""Literal Markdown/Mermaid structure; no semantic facts or code execution."""
import re
from .http_interfaces import declarations


def mermaid_sequences(text):
    diagrams=[]
    for block in re.finditer(r'```mermaid[^\n]*\n([\s\S]*?)```',text,re.I):
        if not re.search(r'^\s*sequenceDiagram\s*$',block[1],re.M):continue
        offset=text[:block.start(1)].count('\n')
        participants={};messages=[]
        for line,raw in enumerate(block[1].splitlines(),offset+1):
            declaration=re.match(r'\s*(participant|actor)\s+([A-Za-z_][\w.-]*)(?:\s+as\s+(.+))?\s*$',raw)
            if declaration:
                participants[declaration[2]]={'id':declaration[2],'name':declaration[3] or declaration[2],'human':declaration[1]=='actor','line':line}
            message=re.match(r'\s*([A-Za-z_][\w.-]*)\s*(-{1,2}>>?|--?x|--?\))\s*([A-Za-z_][\w.-]*)\s*:\s*(.+)',raw)
            if message:
                label=message[4]
                messages.append({'sender':message[1],'receiver':message[3],'arrow':message[2],'label':label,'line':line,'http':[{'method':method,'path':path} for method,path in declarations(label)]})
        diagrams.append({'participants':list(participants.values()),'messages':messages})
    return diagrams
