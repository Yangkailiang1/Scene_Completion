from scene_completion.usage_audit import summarize_requests,context_summary,usage_html

def test_usage_counts_failed_attempts_without_adding_reasoning_or_cache_twice():
    def e(i,kind,at,data):return {'id':i,'kind':kind,'at':at,'task_key':'n','data':{'model_call_id':str((i+1)//2),**data}}
    events=[e(1,'request_started',10,{'requested_model':'m'}),e(2,'request_finished',15,{'usage':{'prompt_tokens':80,'completion_tokens':20,'total_tokens':100,'completion_tokens_details':{'reasoning_tokens':12},'prompt_tokens_details':{'cached_tokens':50}}}),e(3,'request_started',20,{'requested_model':'m'}),e(4,'request_failed',23,{'diagnostic':{'failure_category':'stream_incomplete'}}),e(5,'request_started',24,{}),e(6,'request_failed',24.1,{'diagnostic':{'admission_paused':True}})]
    r=summarize_requests(events);n=r['tasks']['n']
    assert n['reported_total_tokens']==100 and n['input_tokens']==80 and n['output_tokens']==20
    assert n['reasoning_tokens']==12 and n['cached_input_tokens']==50
    assert n['unknown_usage_calls']==1 and n['not_sent_calls']==1 and n['request_seconds']==8
    assert n['cost'] is None

def test_context_scope_and_repeated_dependency_quotes_are_distinct():
    d={'source_id':'s','name':'rr.md','channel':'existing','lines':[{'number':1,'text':'# Main'},{'number':2,'text':'normal'}]}
    ref={'source_id':'s','line_start':2,'line_end':2,'quote':'normal'}
    c=context_summary({'RR':[d],'dependency':{'source_refs':[ref,ref]}},[d])
    assert c['documents'][0]['scope']=='full_document' and c['reference_occurrences']==2 and c['unique_references']==1
    assert context_summary({'RR':[{**d,'lines':d['lines'][1:]}]},[d])['documents'][0]['scope']=='scoped'
    h=usage_html({'tasks':{},'totals':{},'notes':['<script>']})
    assert '&lt;script&gt;' in h


def test_in_flight_usage_is_pending_not_a_failed_unknown_charge():
    events=[{'id':1,'kind':'request_started','at':10,'task_key':'slow','data':{'model_call_id':'one','requested_model':'large'}}]
    r=summarize_requests(events,now=20)['tasks']['slow']
    assert r['in_flight_calls']==1 and r['unknown_usage_calls']==0 and r['request_seconds']==10
