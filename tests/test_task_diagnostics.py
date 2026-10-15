from types import SimpleNamespace
import pytest
from scene_completion.case_dag import Scheduler,Task
from scene_completion.semantic_backend import prepare_packets,read_json,write_json
from scene_completion.task_diagnostics import run
from tests.test_interaction_method_revision import medical_source


@pytest.mark.parametrize('rounds,reopened',[(1,True),(2,False)])
def test_diagnostic_refresh_is_offline_specific_and_cannot_replenish_rounds(tmp_path,monkeypatch,rounds,reopened):
    index,packet,result=medical_source(tmp_path)
    result['component_reviews'][0]['interaction_quote']='not in the source'
    case='Consult-7';case_root=tmp_path/'case';folder=case_root/'batches/participants'
    manifest=prepare_packets(folder,'interaction-participants',[packet['input']],[],{})
    batch=manifest['batches'][0]
    raw={**result,**batch,'model':'fixture','execution_model_evidence':{'requested_model':'fixture'}}
    write_json(folder/'attempts'/(batch['batch_id']+'-attempt.json'),{'result':raw,'validation_error':'old vague error'})
    from scene_completion.interaction_participants import participant_validator
    class Pipeline:
        def __init__(self,args):
            self.scheduler=Scheduler(tmp_path);self.profiler=None
            self.contexts={case:{'root':case_root,'validators':{'participants':participant_validator(index)}}}
        def build(self):self.scheduler.add(Task(case+':participants',case,'participants',version=1))
        def key(self,case,stage):return case+':'+stage
        def progress(self,scheduler):pass
    setup=Pipeline(None);setup.build();record=setup.scheduler.state['tasks'][case+':participants']
    record.update(status='budget_exhausted',rounds=rounds,input_hash=setup.scheduler.input_hash(setup.scheduler.tasks[case+':participants']),
        reason='same failure; no semantic progress',failure={'errors':{batch['batch_id']:'old vague error'}})
    setup.scheduler.save();write_json(tmp_path/'pipeline_arguments.json',{'output_dir':str(tmp_path)})
    monkeypatch.setattr('scene_completion.concern_gap_dag.Pipeline',Pipeline)
    value,code=run(SimpleNamespace(output_dir=str(tmp_path),use_case_id=[case],stage='participants'))
    assert code==0 and value['model_calls']==0 and value['updated_tasks'][0]['reopened']==reopened
    saved=read_json(tmp_path/'case_tasks.json')['tasks'][case+':participants']
    assert saved['rounds']==rounds and saved['status']==('rejected' if reopened else 'budget_exhausted')
    assert 'lab.interaction_quote' in str(saved['failure']['errors'])
