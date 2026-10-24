from copy import deepcopy
from scene_completion.comparison_batches import compare_in_batches
from scene_completion.contracts import packet
from scene_completion.exception_comparison import compare_report
from tests.test_workflow import scenario

class Client:
    base_url='http://offline/v1'
    def __init__(self):self.calls=[]
    def model(self,kind):return 'test'
    def agent(self,p):
        self.calls.append(p['input'])
        return {'decisions':[{'left_id':a['id'],'right_id':b['id'],'status':'full' if a['cause']==b['cause'] else 'unmatched','reason':'fixture semantic decision'} for a in p['input']['left'] for b in p['input']['right']]}

def test_partitioned_comparison_keeps_exhaustive_decisions_and_reuses_valid_parts(tmp_path):
    a,b=scenario('a'),scenario('b');b['interaction_id']='second'
    x,y=deepcopy(a),deepcopy(b);x['id']='x';y['id']='y'
    p=packet('gap-compare',{'left':[a,b],'right':[x,y],'purpose':'G_E'});p['node_key']='case:gap-compare'
    client=Client();v=compare_in_batches(p,client,tmp_path)
    assert len(client.calls)==2 and all(len(r['left'])==len(r['right'])==1 for r in client.calls)
    assert len(v['decisions'])==4 and not v['missing']
    assert sum(d['status']=='unmatched' for d in v['decisions'])==2
    again=compare_in_batches(p,client,tmp_path)
    assert len(client.calls)==2 and again['decisions']==v['decisions']

def test_large_interaction_matrix_is_bounded_per_model_request(tmp_path):
    left=[scenario('l'+str(n)) for n in range(17)];right=[scenario('r'+str(n)) for n in range(10)]
    p=packet('semantic-compare',{'left':left,'right':right,'purpose':'GT_G'});p['node_key']='case:GT_G'
    c=Client();v=compare_in_batches(p,c,tmp_path)
    assert len(v['decisions'])==170 and len(c.calls)==6
    assert all(len(x['left'])*len(x['right'])<=64 for x in c.calls)
