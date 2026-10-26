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

def test_old_rule_run_upgrades_to_new_project_without_overwriting_history(tmp_path):
    from scene_completion.workbench import Workbench
    from scene_completion.storage import read_json,write_json
    w=Workbench(tmp_path);meta=w.create({'name':'old','sources':{'RR':[{'name':'rr.md','content':'RR'}],'SR':[{'name':'sr.md','content':'SR'}]}})
    old=w.run_dir(meta['id']);meta.pop('ruleset_version');write_json(old/'project.json',meta)
    write_json(old/'run/run_manifest.json',{'protocol':'scene-workflow-v3','complete':True})
    upgraded=w.upgrade(meta['id'])
    assert upgraded!=meta['id'] and read_json(old/'run/run_manifest.json')['complete']
    assert read_json(w.run_dir(upgraded)/'project.json')['previous_project_id']==meta['id']
    assert w.upgrade(upgraded)==upgraded

def test_accounts_with_same_model_have_independent_usage_filters(tmp_path):
    store=EventStore(tmp_path)
    for i,account in enumerate(('account-one','account-two')):
        store.append('request_started',task_key='task',role='modeler',case='C',model_call_id=str(i),requested_model='same-model',account=account,account_id=str(i))
        store.append('request_finished',task_key='task',model_call_id=str(i),usage={'prompt_tokens':80,'completion_tokens':20,'total_tokens':100})
    assert indexed_usage(tmp_path)['totals']['reported_total_tokens']==200
    one=indexed_usage(tmp_path,account='account-one',view='tasks')
    assert one['totals']['reported_total_tokens']==100 and one['items'][0]['accounts']==['account-one']

def test_historical_task_keeps_stage_when_absent_from_current_graph(tmp_path):
    from scene_completion.storage import write_json
    store=EventStore(tmp_path);add(store,'one',task='C:existing-extract--part-old')
    write_json(tmp_path/'workflow_tasks.json',{'tasks':{'C:existing-extract--part-old':{'stage':'existing-extract','case':'C','status':'passed'}}})
    write_json(tmp_path/'workflow_graph.json',{'nodes':[]})
    report=indexed_usage(tmp_path)
    assert report['groups']['stage'][0]['name']=='existing-extract'
    assert report['groups']['stage'][0]['input_tokens']==80


def test_rankings_cover_all_filtered_nodes_before_pagination_and_keep_time_units(tmp_path,monkeypatch):
    import time
    clock=[1000.];monkeypatch.setattr(time,'time',lambda:clock[0])
    store=EventStore(tmp_path)
    for n in range(7):
        key='task-'+str(n)
        store.append('request_started',task_key=key,role='modeler',case='C',model_call_id=key,requested_model='m',account='A')
        clock[0]+=80 if n==0 else 5
        store.append('request_finished',task_key=key,model_call_id=key,usage={'prompt_tokens':100+n*100,'completion_tokens':20,'total_tokens':120+n*100})
    report=indexed_usage(tmp_path,view='tasks',offset=6,limit=1,sort='seconds')
    assert report['count']==7 and report['task_count']==7
    assert report['rankings']['tokens'][0]['task_key']=='task-6'
    slow=report['rankings']['seconds'][0]
    assert slow['task_key']=='task-0' and slow['request_seconds']==80 and slow['max_request_seconds']==80
    assert len(report['rankings']['tokens'])==5
    assert indexed_usage(tmp_path,task_key='task-3')['rankings']['tokens'][0]['task_key']=='task-3'
    assert not indexed_usage(tmp_path,account='B')['rankings']['tokens']
    import pytest
    with pytest.raises(ValueError):indexed_usage(tmp_path,sort='unsupported')


def test_usage_search_accepts_human_node_labels_and_requests_can_sort_by_tokens(tmp_path):
    from scene_completion.storage import write_json
    store=EventStore(tmp_path);add(store,'one',task='a',tokens=100);add(store,'two',task='b',tokens=300)
    write_json(tmp_path/'workflow_graph.json',{'nodes':[{'id':'a','label':'查询记忆库的规则','stage':'normal-rules','role':'modeler','case':'C'}]})
    assert indexed_usage(tmp_path,search='记忆库')['totals']['reported_total_tokens']==100
    assert indexed_usage(tmp_path,view='requests',sort='tokens')['items'][0]['task_key']=='b'
