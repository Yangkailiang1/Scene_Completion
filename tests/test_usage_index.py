from scene_completion.execution_events import EventStore
from scene_completion.usage_index import indexed_usage,usage_csv

def add(store,key,model='m',task='a',tokens=100):
    store.append('request_started',task_key=task,role='modeler',case='C',model_call_id=key,requested_model=model)
    store.append('request_finished',task_key=task,model_call_id=key,usage={'prompt_tokens':tokens-20,'completion_tokens':20,'total_tokens':tokens,'completion_tokens_details':{'reasoning_tokens':10}})

def test_incremental_usage_has_no_duplicate_charges_and_does_not_scan_contexts(tmp_path,monkeypatch):
    store=EventStore(tmp_path);add(store,'one');store.append('stream_delta',text='large model stream ignored')
    a=indexed_usage(tmp_path);b=indexed_usage(tmp_path)
    assert a['totals']==b['totals'] and a['totals']['reported_total_tokens']==100
    add(store,'two',model='n');c=indexed_usage(tmp_path,view='tasks',model='n')
    assert c['totals']['reported_total_tokens']==100 and c['items'][0]['reported_total_tokens']==100
    assert indexed_usage(tmp_path)['totals']['reported_total_tokens']==200
    assert not a['items'] and len(str(a))<4000
    requests=indexed_usage(tmp_path,view='requests',offset=1,limit=1)
    assert requests['count']==2 and len(requests['items'])==1
    assert 'task_key' in usage_csv(indexed_usage(tmp_path,view='export'))

def test_unknown_usage_and_estimates_stay_separate_from_actual_cost(tmp_path):
    store=EventStore(tmp_path);add(store,'one')
    store.append('request_started',task_key='b',model_call_id='two',requested_model='m')
    store.append('request_failed',task_key='b',model_call_id='two',diagnostic={'failure_category':'transport_timeout'})
    v=indexed_usage(tmp_path,prices={'m':{'input':1,'output':2}})
    assert v['totals']['actual_cost'] is None and v['totals']['estimated_cost']==.00012
    assert v['totals']['unknown_usage_calls']==1 and v['totals']['reported_total_tokens']==100
