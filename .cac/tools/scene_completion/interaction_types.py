"""Participant type is distinct from deployment location and message direction."""
SERVICE_POSITIONS={'内部服务','外部Actor（系统）','内部数据库','外部数据库','内部资源','外部资源','AI模型','UI/前端'}
def location(p):
    pos=p['position']
    if '人类' in pos:return 'human'
    if pos=='系统边界':return 'system_boundary'
    if pos.startswith('外部'):return 'external'
    if pos in {'内部服务','内部数据库','内部资源','UI/前端'}:return 'internal'
    return 'undetermined'

def classify(i,all_messages):
    request=i
    if i['direction']=='return':
        request=next((p for p in all_messages if p['id']==i.get('parent_id') and p['direction']=='request' and p['layer']==i['layer']),None)
        if request is None:return {'kind':'undetermined','caller':i['receiver']['name'],'provider':i['sender']['name'],'caller_location':'undetermined','provider_location':'undetermined'}
    a,b=request['sender'],request['receiver'];al,bl=location(a),location(b)
    is_service=lambda p:p['position'] in SERVICE_POSITIONS or p['position']=='系统边界'
    kind='actor_system' if '人类' in a['position'] and is_service(b) else 'service_service' if is_service(a) and is_service(b) else 'undetermined'
    return {'kind':kind,'caller':a['name'],'provider':b['name'],'caller_location':al,'provider_location':bl}
