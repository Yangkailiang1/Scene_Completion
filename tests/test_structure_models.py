import json
from copy import deepcopy
import pytest
from scene_completion.structure_models import compile_model,catalogue,existing_branches,imported_sources
from scene_completion.source_documents import normal_projection,read_documents,validate_evidence
from scene_completion.use_cases import select_documents
from scene_completion.validation import validate_result
from scene_completion.artifact_imports import receive,snapshot,decide
from scene_completion.workflow import Execution,build_pipeline
from scene_completion.storage import read_json


def model(layer='RR'):
    entities=[{'entity_id':'actor','entity_type':'actor','canonical_name':'开发者'},
              {'entity_id':'sys','entity_type':'system','canonical_name':'平台'}]
    relations=[]
    for n in (1,2):
        cid=f'{layer}-UC-{n}'
        entities.append({'entity_id':cid,'entity_type':'use_case','canonical_name':'用例'+str(n),'use_case_id':'UC-'+str(n),'actors':['actor'] if layer=='RR' else []})
        for kind in ('main_success','exception','alternative'):
            sid=f'{layer}-scene-{n}-{kind}'
            entities.append({'entity_id':sid,'entity_type':'scenario','scenario_kind':kind,
                             'steps':[f'{kind} {n} 开发者向平台查询'], 'expected_result':kind+' result',
                             'evidence':[{'source_id':'ABSENT-SPEC','quote':'DO_NOT_LEAK_EVIDENCE_ANSWER','locator':'L999-L1000'}]})
            relations.append({'source_entity_id':sid,'target_entity_id':cid,'relation_type':'associated_with_usecase'})
    return {'schema_version':'3','scope':{'model_level':layer},'entities':entities,'relations':relations,
            'source_inputs':[{'source_id':'BASE','secret':'DO_NOT_LEAK_BASELINE'}],
            'review_items':[{'question':'DO_NOT_LEAK_BASELINE_REVIEW'}]}


@pytest.mark.parametrize('minified',[False,True])
@pytest.mark.parametrize('layer',['RR','SR'])
def test_literal_conversion_channels_and_case_slices(layer,minified):
    text=json.dumps(model(layer),ensure_ascii=False,indent=None if minified else 2)
    converted=compile_model(text,'structure_model.json');doc=converted['document'];normal=normal_projection([doc])
    c=catalogue(normal,layer);b=existing_branches([doc])
    assert len(c['cases'])==2 and len(b['branches'])==2
    assert len(converted['retained'])==2
    validate_result('use-case-extract',c,{'documents':normal,'layer':layer})
    validate_result('existing-branches',b,{'existing-documents':[doc]})
    safe=str(normal)
    for excluded in ('exception result','alternative result','DO_NOT_LEAK','ABSENT-SPEC'):
        assert excluded not in safe
    sliced=select_documents([doc],[c['cases'][0]],c['cases'])
    assert len(existing_branches(sliced)['branches'])==1
    assert existing_branches(sliced)['branches'][0]['case_hint']=='UC-1'
    assert '用例2' not in str(sliced)
    assert 'COLLEAGUE_EXCEPTION' not in str(normal_projection(sliced))
    assert all('json_pointer' in location for location in converted['locations'])
    validate_evidence(c,normal);validate_evidence(b,[doc])


def test_broken_ownership_and_duplicate_cases_fail_loudly():
    raw=model();raw['relations'].pop()
    with pytest.raises(ValueError,match='缺少用例关联'):compile_model(json.dumps(raw),'x.json')
    raw=model();raw['entities'][6]['use_case_id']='UC-1'
    with pytest.raises(ValueError,match='重复use_case_id'):compile_model(json.dumps(raw),'x.json')


def test_upload_selection_disable_and_multiple_versions(tmp_path):
    data=json.dumps(model(),ensure_ascii=False)
    receive(tmp_path,[{'name':'structure_model.json','content':data}]);rows=snapshot(tmp_path)
    assert rows[0]['status']=='converted' and rows[0]['target_nodes']==['rr-use-cases','<用例>:existing-branches']
    assert imported_sources(rows)['RR']['channel']=='existing'
    duplicate=deepcopy(rows[0]);duplicate['id']='another'
    with pytest.raises(ValueError,match='多个版本'):imported_sources(rows+[duplicate])
    decide(tmp_path,rows[0]['id'],{'expected_revision':0,'action':'disable_structure'})
    assert imported_sources(snapshot(tmp_path))=={}


def test_direct_json_source_and_execution_skip_model_calls(tmp_path,monkeypatch):
    p=tmp_path/'rr.json';p.write_text(json.dumps(model()),encoding='utf8')
    docs=read_documents([p],'existing');n=normal_projection(docs)
    ex=Execution(tmp_path/'run',mocks={})
    def forbidden(*args,**kwargs):raise AssertionError('structured extraction must not call LLM')
    monkeypatch.setattr(ex,'semantic',forbidden)
    ex.add('rr-use-cases','use-case-extract',static={'documents':n,'layer':'RR'})
    ex.add('UC-1:existing-branches','existing-branches',static={'existing-documents':select_documents(docs,[catalogue(n,'RR')['cases'][0]],catalogue(n,'RR')['cases'])})
    ex.scheduler.run()
    for key in ('rr-use-cases','UC-1:existing-branches'):
        row=ex.scheduler.state['tasks'][key]
        assert row['status']=='passed',row
        output=read_json(ex.root/row['output_file'])
        assert output['metadata']['execution']['provider']=='colleague_structure'


def test_pipeline_uses_uploaded_sources_only_in_their_layer(tmp_path):
    receive(tmp_path,[{'name':'structure_model.json','content':json.dumps(model('RR'))}])
    ex=Execution(tmp_path/'run',mocks={})
    rr=[{'source_id':'old','name':'old.md','channel':'existing','lines':[{'number':1,'text':'OLD_RR'}]}]
    sr=[{'source_id':'sr','name':'sr.md','channel':'existing','lines':[{'number':1,'text':'STILL_SR'}]}]
    build_pipeline(ex,rr,sr,[])
    # Only execute the source-index and catalogue branch of the real DAG.
    keep={'source-index','rr-catalogue-context','rr-use-cases'}
    ex.scheduler.tasks={k:v for k,v in ex.scheduler.tasks.items() if k in keep}
    ex.scheduler.run()
    assert ex.scheduler.state['tasks']['rr-use-cases']['status']=='passed'
    output=read_json(ex.root/ex.scheduler.state['tasks']['rr-use-cases']['output_file'])
    assert len(output['payload']['cases'])==2
    assert ex.scheduler.state['tasks']['rr-use-cases']['provenance']=='同事产物导入'
    assert ex.scheduler.state['tasks']['rr-use-cases']['import_sources'][0]['name']=='structure_model.json'
    assert len(read_json(tmp_path/'imports/usage.json'))==1


def test_upload_layer_check_and_original_file_trace(tmp_path):
    from scene_completion.test_sources import decode_source
    from scene_completion.review_handoff import source_view
    from scene_completion.storage import write_json
    raw=json.dumps(model('RR'),ensure_ascii=False)
    assert decode_source({'name':'rr.json','content':raw},'RR')[1]=='.json'
    with pytest.raises(ValueError,match='model_level'):decode_source({'name':'rr.json','content':raw},'SR')
    receive(tmp_path,[{'name':'rr.json','content':raw}])
    write_json(tmp_path/'project.json',{'id':'p','sources':{'RR':[],'SR':[],'test':[]}})
    converted=snapshot(tmp_path)[0]['structure_model']
    ref=converted['catalogue']['cases'][0]['source_refs'][0]
    shown=source_view(tmp_path,ref['source_id'],ref['line_start'],ref['line_end'])
    assert shown['document_format']=='markdown'
    assert shown['derived_from'].startswith('import-raw-')
    assert shown['original_path'].endswith('/original/rr.json')
    assert any(x['line']==ref['line_start'] and x['json_pointer'].startswith('/entities/') for x in shown['json_locations'])


def test_ordinary_markdown_cannot_spoof_structured_provenance():
    converted=compile_model(json.dumps(model()),'x.json')
    fake={**converted['document'],'source_id':'ordinary-markdown'}
    assert catalogue([fake],'RR') is None
    assert existing_branches([fake]) is None


def test_positive_use_case_named_exception_replay_is_not_an_exception_branch():
    value=model('SR');value['entities'][2]['canonical_name']='重放异常事件'
    value['entities'][3]['steps']=['异常事件先隔离，再由授权任务重放']
    converted=compile_model(json.dumps(value,ensure_ascii=False),'sr.json')
    normal=normal_projection([converted['document']])
    assert len(catalogue(normal,'SR')['cases'])==2
    assert '异常事件先隔离' in str(normal) and 'exception result' not in str(normal)
    assert normal_projection(normal)==normal
