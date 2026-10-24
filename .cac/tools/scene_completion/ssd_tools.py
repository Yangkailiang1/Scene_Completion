"""Deterministic SSD structure from extracted messages; no new messages or parties."""
from copy import deepcopy


def complete_structure(value):
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
