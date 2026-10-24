from scene_completion.api_documents import index_interfaces
from scene_completion.validation import validate_result
from scene_completion.contracts import PROTOCOL
import pytest

def test_index_uses_every_mapped_interface_and_exact_paths():
    lines=['# APIs','## API-1 List','GET /items','query page','## API-2 Detail','GET /items/{id}','path id']
    doc={'source_id':'s','name':'sr.md','channel':'normal','lines':[{'number':n,'text':v} for n,v in enumerate(lines,1)]}
    def api(id,name,address,n):return {'id':id,'name':name,'address':address,'method':'GET','source_refs':[{'source_id':'s','line_start':n,'line_end':n,'quote':lines[n-1]}]}
    mapping={'services':[{'name':'Service','interfaces':[api('API-1','List','/items',3),api('API-2','Detail','/items/{id}',6)],'source_refs':[{'source_id':'s','line_start':1,'line_end':1,'quote':'# APIs'}]}]}
    inputs={'SR':[doc],'api-map':mapping};result=index_interfaces(inputs)
    assert [a['id'] for a in result['apis']]==['API-1','API-2']
    spans=result['apis'][0]['source_ranges'];assert any(r['start']==2 and r['end']==4 for r in spans)
    assert not any(r['start']>=5 for r in spans)
    validate_result('api-index',result,inputs)


def test_parameter_task_preserves_known_interface_address():
    inputs={'SR':[],'interface':{'id':'a','address':'/items'}}
    p={'apis':[{'id':'a','name':'List','address':None,'parameters':[],'source_refs':[{'source_id':'s','line_start':1,'line_end':1,'quote':'list'}]}]}
    inputs['interface']['source_refs']=p['apis'][0]['source_refs']
    with pytest.raises(ValueError,match='地址'):validate_result('api-parameters',p,inputs)
