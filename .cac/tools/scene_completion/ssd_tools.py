"""Deterministic SSD structure from extracted messages; no new messages or parties."""
from copy import deepcopy
import re


def validate_explicit_resources(rows):
    """Reject a named table that contradicts a unique literal table reference.

    A multi-table operation or a physical database with another name cannot
    resolve to a unique table here; leave that semantic decision to the model.
    """
    for row in rows:
        if row['direction']!='request' or '数据库' not in row['receiver']['position']:continue
        actual=re.fullmatch(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*表',row['receiver']['name'])
        if not actual:continue
        text=' '.join(r['quote'] for r in row['operation'].get('source_refs',[]))
        names=set(re.findall(r'(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)\s*表',text))
        if len(names)==1 and actual[1] not in names:
            expected=next(iter(names))+'表'
            raise ValueError('message '+row['id']+' names '+row['receiver']['name']+' but its operation evidence explicitly names '+expected+'; select the evidenced resource identity and preserve the corresponding reverse return endpoints, without inventing a resource')


def complete_structure(value,normalizations=None):
    out=deepcopy(value);rows=out['interactions'];by_id={i['id']:i for i in rows}
    for layer in ('RR','SR'):
        opened=[]
        for i in (r for r in rows if r['layer']==layer):
            if i['direction']=='request':
                parents=[by_id[k] for k in opened if by_id[k]['receiver']['name']==i['sender']['name']]
                if len(parents)==1:i['parent_id']=parents[0]['id']
                elif len(parents)>1:
                    out.setdefault('pending',[]).append({'interaction_id':i['id'],'reason':'多个未结束调用都可能是本请求的调用上下文，未猜测父调用','source_refs':i['source_refs']})
                opened.append(i['id'])
            elif i.get('parent_id') in opened:opened.remove(i['parent_id'])
    claims={}
    for link in out.get('rr_sr_links',[]):
        if link['status']=='confirmed':
            for sid in link['sr_ids']:claims.setdefault(sid,[]).append(link)
    for sid,links in claims.items():
        if len(links)<2 or sid not in by_id:continue
        message=by_id[sid]
        exact=[link for link in links if link['rr_id'] in by_id and
          by_id[link['rr_id']]['direction']==message['direction'] and
          all(by_id[link['rr_id']][role]['name']==message[role]['name'] for role in ('sender','receiver'))]
        # A root request may encompass downstream returns, but a separately
        # modeled identical RR return owns its exact SR return. Multiple exact
        # matches (e.g. reusable templates) remain unresolved for review.
        if len(exact)!=1:continue
        owner=exact[0]
        for link in links:
            if link is owner:continue
            link['sr_ids']=[k for k in link['sr_ids'] if k!=sid]
            if not link['sr_ids']:
                link['status']='pending'
                out.setdefault('pending',[]).append({'interaction_id':link['rr_id'],'reason':'展开消息归属于唯一同向同端点交互；本条RR展开尚缺依据','source_refs':link.get('source_refs',[])})
        if normalizations is not None:normalizations.append({'message_id':sid,'field':'refinements','action':'unique same-direction same-endpoint RR message owns this SR message','rr_message_id':owner['rr_id']})
    direct={sid:link['rr_id'] for link in out.get('rr_sr_links',[]) if link['status']=='confirmed' for sid in link['sr_ids']}
    children={}
    for i in rows:
        if i.get('parent_id'):children.setdefault(i['parent_id'],[]).append(i['id'])
    order={i['id']:n for n,i in enumerate(rows)}
    for link in out.get('rr_sr_links',[]):
        rr=by_id.get(link['rr_id'])
        if link['status']!='confirmed' or not rr or rr['direction']!='request':continue
        reached=set(link['sr_ids']);todo=list(reached)
        while todo:
            for sid in children.get(todo.pop(),[]):
                if sid in reached or (sid in direct and direct[sid]!=link['rr_id']):continue
                if by_id[sid]['layer']!='SR':continue
                reached.add(sid);todo.append(sid)
        link['sr_ids']=sorted(reached,key=lambda sid:order[sid])
    return out
