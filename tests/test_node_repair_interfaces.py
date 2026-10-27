from copy import deepcopy
import pytest
from scene_completion.workflow import Execution
from scene_completion.storage import read_json,write_json
from scene_completion.node_repair import export_repair,submit_repair
from scene_completion.api_documents import explicit_http_interfaces
from scene_completion.http_interfaces import normalize_mapping,clean_path
from scene_completion.validation import validate_result


def document(text):return {'source_id':'s','name':'SR.md','channel':'normal','lines':[{'number':1,'text':text}]}
def mapping(d,path):
 ref=[{'source_id':'s','line_start':1,'line_end':1,'quote':d['lines'][0]['text']}]
 return {'services':[{'name':'MemoryService','interfaces':[{'id':'delete','name':'删除记忆实例','method':'DELETE','address':path,'source_refs':ref}],'source_refs':ref}]}


def test_mermaid_and_plain_http_paths_have_identical_literal_identity():
 path='/ms/v1/memory-instances/{memoryInstanceId}'
 d=document('P->>M: DELETE '+path+'<br/>删除记忆实例')
 declared=explicit_http_interfaces([d]);assert set(declared)=={('DELETE',path)}
 assert next(iter(declared.values()))['quote']==d['lines'][0]['text']
 assert set(explicit_http_interfaces([document('DELETE '+path+' 删除记忆实例')]))==set(declared)
 assert set(explicit_http_interfaces([document('P->>M: DELETE '+path+r'\n删除记忆实例')]))==set(declared)
 bad=mapping(d,path+'<br/>删除记忆实例');fixed=normalize_mapping(bad)
 assert fixed['services'][0]['interfaces'][0]['address']==path and bad['services'][0]['interfaces'][0]['address']!=path
 validate_result('api-map',fixed,{'SR':[d]})
 with pytest.raises(ValueError,match='纯path'):validate_result('api-map',bad,{'SR':[d]})


def test_malformed_placeholder_is_not_repaired_by_inventing_a_brace():
 bad='/ms/v1/memory-instances/{memoryInstanceId）<be/>删除记忆实例'
 assert clean_path(bad) is None
 assert explicit_http_interfaces([document('S->>M: DELETE '+bad)])=={}
 value=mapping(document('DELETE '+bad),bad)
 assert normalize_mapping(value)==value
 with pytest.raises(ValueError):validate_result('api-map',value,{'SR':[document('DELETE '+bad)]})


def test_external_agent_repair_is_input_bound_validated_and_used_without_model(tmp_path):
 root=tmp_path/'run';d=document('abstract interface');calls=[]
 def broken(packet):calls.append(packet['task']);return {'wrong':'invalid'}
 ex=Execution(root,mocks={'api-map':broken});ex.add('api-map','api-map',static={'SR':[d]});out=ex.finish();assert not out['complete']
 package=export_repair(tmp_path,'api-map');package['payload']={'services':[]};package['note']='原文只有抽象说明，没有实际HTTP接口，修正为合法空列表'
 before=deepcopy(package)
 assert submit_repair(tmp_path,'api-map',package,validate_only=True)['saved'] is False
 assert not (root/'external_repairs').exists()
 bad=deepcopy(package);bad['payload']={'wrong':1}
 with pytest.raises(ValueError):submit_repair(tmp_path,'api-map',bad)
 stale=deepcopy(package);stale['binding']['input_hash']='wrong'
 with pytest.raises(ValueError,match='过期'):submit_repair(tmp_path,'api-map',stale)
 assert submit_repair(tmp_path,'api-map',package)['saved']
 count=len(calls)
 ex2=Execution(root,mocks={'api-map':broken});ex2.add('api-map','api-map',static={'SR':[d]});out=ex2.finish()
 assert out['complete'] and len(calls)==count
 assert package==before
 histories=list((root/'external_repairs/history').glob('*.json'));assert len(histories)==1 and read_json(histories[0])['previous_failure']
 # A modified input must not consume the old repair.
 ex3=Execution(root,mocks={'api-map':broken});ex3.add('api-map','api-map',static={'SR':[document('different input')]});assert not ex3.finish()['complete'] and len(calls)>count


def test_failure_does_not_block_independent_nodes(tmp_path):
 d=document('abstract')
 ex=Execution(tmp_path/'run',mocks={'api-map':{'wrong':1},'api-parameters':{'apis':[]}})
 ex.add('bad','api-map',static={'SR':[d]});ex.add('independent','api-parameters',static={'SR':[]})
 assert not ex.finish()['complete']
 state=ex.scheduler.state['tasks'];assert state['independent']['status']=='passed' and state['bad']['status']!='passed'


def test_cli_handoff_exports_validates_and_commits_without_direct_artifact_overwrite(tmp_path,capsys):
 from fastapi.testclient import TestClient
 from scene_completion.workbench import create_app
 from scene_completion.workbench_cli import main
 from tests.test_model_accounts_cli import source,FakeAPI
 c=TestClient(create_app(tmp_path/'data'));rid=c.post('/api/projects',json=source()).json()['id'];project=tmp_path/'data'/rid
 root=project/'run';d=document('only abstract API')
 ex=Execution(root,mocks={'api-map':{'wrong':1}});ex.add('api-map','api-map',static={'SR':[d]});assert not ex.finish()['complete']
 api=FakeAPI(c);file=tmp_path/'repair.json'
 assert main(['repair-export','--project',rid,'--node','api-map','--out',str(file)],client=api)==0;capsys.readouterr()
 pkg=read_json(file);pkg['payload']={'services':[]};pkg['note']='依据原文无实际HTTP声明，修正Schema';write_json(file,pkg)
 assert main(['repair-submit','--project',rid,'--node','api-map','--file',str(file),'--validate-only'],client=api)==0
 assert '"saved": false' in capsys.readouterr().out
 assert main(['repair-submit','--project',rid,'--node','api-map','--file',str(file)],client=api)==0
 assert '"saved": true' in capsys.readouterr().out
 assert not (root/'artifacts/shared/api-map.json').exists()
