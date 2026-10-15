from scene_completion.semantic_backend import prepare_packets,run_agent_packets,read_json
from scene_completion.sources import fingerprint


def test_fresh_generation_uses_the_same_format_view_as_cache_and_keeps_raw(tmp_path):
    prepare_packets(tmp_path,'gap-generation',[{'mounts':[{'mount_id':'m1'}]}],[],{'items':[]})
    class Client:
        config={'max_concurrency':1,'semantic_max_attempts':1}
        calls=0
        def model(self,kind):return 'configured-candidate'
        def agent(self,packet):
            self.calls+=1
            return {'m1':[{'name':'actual condition'}],
                'execution_model_evidence':{'requested_model':self.model('agent'),'thinking':False,'reasoning_effort':None}}
    client=Client()
    def validate(packet,result):
        assert result['items']==[{'mount_id':'m1','scenarios':[{'name':'actual condition'}]}]
        return result['items']
    assert run_agent_packets(tmp_path,client,validate)['complete']
    raw=read_json(next((tmp_path/'results').glob('*.json')))
    assert 'items' not in raw and raw['m1']==[{'name':'actual condition'}]
    assert run_agent_packets(tmp_path,client,validate)['batches'][0]['status']=='cached'
    assert client.calls==1


def test_gap_failure_budget_and_immutable_diagnostic_are_retained(tmp_path):
    prepare_packets(tmp_path,'gap-unit-test',[{'value':1}],[],{'items':[]})
    class Client:
        config={'max_concurrency':1,'semantic_max_attempts':1}
        calls=0
        def model(self,kind):return 'ecnu-max'
        def agent(self,p):
            self.calls+=1
            return {'model':'ecnu-max','execution_model_evidence':{'requested_model':'ecnu-max'},'items':[1]}
    def reject(packet,result):raise ValueError('source citation does not belong to this interaction')
    client=Client();state=run_agent_packets(tmp_path,client,reject)
    assert not state['complete'] and client.calls==1
    attempts=list((tmp_path/'attempts').glob('*.json'))
    assert len(attempts)==1
    saved=read_json(attempts[0]);assert saved['result']['items']==[1]
    assert 'source citation' in saved['validation_error']


def test_gap_success_is_reused_but_changed_input_is_not(tmp_path):
    class Client:
        config={'max_concurrency':1,'semantic_max_attempts':1,'allowed_cached_models':['ecnu-max']}
        calls=0
        def model(self,kind):return 'ecnu-max'
        def agent(self,p):
            self.calls+=1
            return {'model':'ecnu-max','execution_model_evidence':{'requested_model':'ecnu-max','thinking':False,'reasoning_effort':None},'items':[p['input']['value']]}
    def validate(packet,result):assert result['items']==[packet['input']['value']];return result['items']
    prepare_packets(tmp_path,'gap-unit-test',[{'value':1}],[],{'items':[]})
    c=Client();assert run_agent_packets(tmp_path,c,validate)['complete']
    assert run_agent_packets(tmp_path,c,validate)['batches'][0]['status']=='cached'
    assert c.calls==1
    prepare_packets(tmp_path,'gap-unit-test',[{'value':2}],[],{'items':[]})
    assert run_agent_packets(tmp_path,c,validate)['complete'] and c.calls==2


def test_explicit_historical_effort_authorization_reuses_ecnu_without_relabeling(tmp_path):
    prepare_packets(tmp_path,'gap-unit-test',[{}],[],{'items':[]})
    class Client:
        config={'max_concurrency':1,'semantic_max_attempts':1,'thinking':True,'reasoning_effort':'high','allowed_cached_models':['ecnu-max']}
        calls=0
        def model(self,kind):return 'ecnu-max'
        def agent(self,p):
            self.calls+=1
            return {'model':'ecnu-max','execution_model_evidence':{'requested_model':'ecnu-max','thinking':True,'reasoning_effort':self.config['reasoning_effort']},'items':[]}
    c=Client();validate=lambda p,r:r['items']
    assert run_agent_packets(tmp_path,c,validate)['complete']
    c.config={**c.config,'reasoning_effort':'low','allowed_cached_reasoning_efforts':['high','low']}
    assert run_agent_packets(tmp_path,c,validate)['batches'][0]['status']=='cached' and c.calls==1
    result=read_json(next((tmp_path/'results').glob('*.json')))
    assert result['execution_model_evidence']['reasoning_effort']=='high'


def test_gap_retry_recomputes_feedback_without_changing_failed_evidence(tmp_path):
    prepare_packets(tmp_path,'gap-unit-test',[{}],[],{'items':[]})
    class Client:
        config={'max_concurrency':1,'semantic_max_attempts':1}
        calls=[]
        def model(self,kind):return 'ecnu-max'
        def agent(self,p):
            self.calls.append(p)
            return {'model':'ecnu-max','execution_model_evidence':{'requested_model':'ecnu-max'},'items':[]}
    message='old diagnostic'
    def reject(p,r):raise ValueError(message)
    c=Client();assert not run_agent_packets(tmp_path,c,reject)['complete']
    saved=read_json(next((tmp_path/'attempts').glob('*.json')))
    message='new precise source diagnostic'
    assert not run_agent_packets(tmp_path,c,reject)['complete']
    assert 'new precise' in c.calls[-1]['validation_feedback']
    assert saved['validation_error']=='old diagnostic'


def test_comparison_format_hint_is_recorded_without_rewriting_packet_or_decision(tmp_path):
    manifest=prepare_packets(tmp_path,'gap-ambiguity-EG',[{}],[],{'pairs':[]})
    path=tmp_path/'packets'/(manifest['batches'][0]['batch_id']+'.json')
    original=path.read_bytes()
    class Client:
        config={'max_concurrency':1,'semantic_max_attempts':1}
        calls=0
        def model(self,kind):return 'ecnu-max'
        def agent(self,p):
            self.calls+=1
            hint=p['validation_format_hint']
            assert hint['accepted_pair_requirements']['condition_evidence'][0]['reason']
            return {'execution_model_evidence':{'requested_model':'ecnu-max','thinking':False,'reasoning_effort':None},
                    'pairs':[{'status':'unmatched','reason':'different cause'}]}
    c=Client();validate=lambda p,r:r['pairs']
    assert run_agent_packets(tmp_path,c,validate)['complete']
    raw=read_json(next((tmp_path/'results').glob('*.json')))
    from scene_completion.concern_gap_comparison import format_hint
    assert raw['execution_model_evidence']['format_hint_hash']==fingerprint(format_hint())
    assert raw['pairs']==[{'status':'unmatched','reason':'different cause'}]
    assert path.read_bytes()==original
    assert run_agent_packets(tmp_path,c,validate)['batches'][0]['status']=='cached'
    assert c.calls==1


def test_strengthened_cache_guard_retains_old_execution_and_requires_new_judgment(tmp_path):
    prepare_packets(tmp_path,'gap-unit-test',[{}],[],{'items':[]})
    class Client:
        config={'max_concurrency':1,'semantic_max_attempts':1}
        calls=0
        def model(self,kind):return 'ecnu-max'
        def agent(self,p):
            self.calls+=1
            return {'execution_model_evidence':{'requested_model':'ecnu-max','thinking':False,'reasoning_effort':None},
                    'items':[self.calls]}
    c=Client();accepted=1
    def validate(p,r):
        if r['items']!=[accepted]:raise ValueError('actual semantic contradiction')
        return r['items']
    assert run_agent_packets(tmp_path,c,validate)['complete']
    accepted=2
    assert run_agent_packets(tmp_path,c,validate)['complete']
    old=read_json(next((tmp_path/'attempts').glob('*-cache-*.json')))
    assert old['result']['items']==[1] and old['cached_result_revalidation'] is True
    assert 'actual semantic contradiction' in old['validation_error']
    assert c.calls==2
