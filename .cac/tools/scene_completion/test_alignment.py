"""Independent test catalogue and source-backed requirement case alignment."""
from copy import deepcopy
from .storage import fingerprint


def register():
    from .contracts import obj,arr,S,STR,REFS,enum,SCHEMAS,INPUT_KEYS,TASKS
    case=obj(id=S,name=S,association=STR,source_refs=REFS)
    test=obj(id=S,case_id=S,name=S,scenario_type=enum('exception','normal','optional','pending'),declared_type=STR,preconditions=STR,trigger=STR,expected_result=STR,test_data=STR,test_steps=STR,source_refs=REFS)
    test['required']=[k for k in test['required'] if k not in {'test_data','test_steps'}]
    SCHEMAS['test-inventory']=obj(cases=arr(case),tests=arr(test),pending=arr(obj(reason=S,source_refs=REFS)))
    SCHEMAS['test-case-align']=obj(matches=arr(obj(test_case_id=S,case_group_id={'type':['string','null']},status=enum('confirmed','pending','unmatched'),basis=S,source_refs=REFS)))
    INPUT_KEYS.update({'test-inventory':{'test-documents'},'test-case-align':{'test-inventory','rr-cases','sr-cases','case-groups'}})
    TASKS.update({'test-inventory':('scene-test-inventory','独立测试用例与场景整理'),'test-case-align':('scene-test-case-align','测试与需求用例对应')})


def known_catalogue(documents):
    from .test_sources import records
    cases={};tests=[]
    for d in documents:
        rows=records([d])
        if not rows and any(r['text'].strip() for r in d['lines']):return None
        for r in rows:
            association=r['关联需求'];cid='test-case-'+fingerprint([d['source_id'],association])[:20]
            refs=[{'source_id':d['source_id'],'line_start':row['number'],'line_end':row['number'],'quote':row['text']} for row in d['lines'] if row['number'] in r.get('context_rows',[])]
            if cid not in cases:cases[cid]={'id':cid,'name':r.get('case_name') or association or d['name'],'association':association,'source_refs':refs or r['source_refs']}
            tests.append({'id':r['id'],'case_id':cid,'name':r['测试名称'],'scenario_type':r['scenario_type'],'declared_type':r.get('declared_type',r['类型']),'preconditions':r['前置条件'],'trigger':r['触发条件'],'expected_result':r['预期结果'],'test_data':r['测试数据'],'test_steps':r['测试步骤'],'source_refs':r['source_refs']})
    return {'cases':list(cases.values()),'tests':tests,'pending':[]}


def exact_alignment(inputs):
    import re
    groups=inputs['case-groups']['groups'];matches=[]
    for case in inputs['test-inventory']['cases']:
        text=case['association'];selected=[g for g in groups if any(re.search(r'(?<![\w-])'+re.escape(cid)+r'(?![\w-])',text) for cid in g['rr_ids']+g['sr_ids'])]
        if len(selected)!=1:return None
        confirmed=selected[0]['status']=='confirmed'
        matches.append({'test_case_id':case['id'],'case_group_id':selected[0]['id'] if confirmed else None,'status':'confirmed' if confirmed else 'pending','basis':'测试原文明示的需求用例编号精确对应' if confirmed else '对应的RR/SR用例组尚未确认','source_refs':case['source_refs']})
    return {'matches':matches}


def as_records(catalogue,documents):
    from .test_sources import HEADERS
    cases={c['id']:c for c in catalogue['cases']};out=[]
    for t in catalogue['tests']:
        r={k:'' for k in HEADERS};first=t['source_refs'][0]
        r.update({'测试ID':t['id'],'测试名称':t['name'],'类型':{'exception':'异常','normal':'正常','optional':'可选','pending':'待确认'}[t['scenario_type']],'前置条件':t['preconditions'],'触发条件':t['trigger'],'预期结果':t['expected_result'],'测试数据':t.get('test_data',''),'测试步骤':t.get('test_steps',''),'关联需求':cases[t['case_id']]['association'],'来源方式':'独立测试整理'})
        r.update(id=t['id'],scenario_type=t['scenario_type'],source_id=first['source_id'],name=next((d['name'] for d in documents if d['source_id']==first['source_id']),'独立测试'),row=first['line_start'],source_refs=t['source_refs'])
        out.append(r)
    return out


def scoped_tests(catalogue,alignment,documents,group):
    owners={m['test_case_id'] for m in alignment['matches'] if m['status']=='confirmed' and m['case_group_id']==group}
    cases=[c for c in catalogue['cases'] if c['id'] in owners];tests=[t for t in catalogue['tests'] if t['case_id'] in owners]
    refs=[r for c in cases for r in c['source_refs']]+[r for t in tests for r in t['source_refs']]
    selected=[]
    for d in documents:
        rows=[r for r in d['lines'] if any(x['source_id']==d['source_id'] and x['line_start']<=r['number']<=x['line_end'] for x in refs)]
        if rows:selected.append({**d,'lines':rows})
    return selected,{'cases':cases,'tests':tests,'pending':catalogue['pending']}


def validate_test_task(task,value,inputs):
    from .source_documents import validate_evidence
    if task=='test-inventory':
        cases={c['id'] for c in value['cases']};ids=set()
        for t in value['tests']:
            if t['id'] in ids or t['case_id'] not in cases or not t['source_refs']:raise ValueError('测试场景编号重复、所属用例未知或缺少原文依据')
            ids.add(t['id']);validate_evidence(t['source_refs'],inputs['test-documents'])
            if t['scenario_type']=='exception':
                import re
                text=' '.join(r['quote'] for r in t['source_refs'])
                if not re.search(r'异常|失败|错误|非法|超时|不可用|不存在|拒绝|越权|负数|超出|缺失|HTTP\s*[45]\d\d|exception|fail|invalid|error|unauthori',text,re.I):raise ValueError('未明示异常类型或失败条件的测试须保持pending，不自行补为异常')
        for c in value['cases']:
            if not c['source_refs']:raise ValueError('测试用例必须有原文依据')
        if len(cases)!=len(value['cases']):raise ValueError('测试用例ID重复')
        from .test_sources import records
        supplied={t['id']:t for t in value['tests']}
        for original in records(inputs['test-documents']):
            if original['id'] not in supplied or supplied[original['id']]['scenario_type']!=original['scenario_type']:raise ValueError('不得丢失测试场景或改变其明示类型')
        if inputs['test-documents'] and not value['tests'] and not value['pending']:raise ValueError('不能静默丢弃未识别的测试Markdown，需整理或列待确认')
    else:
        cases={c['id'] for c in inputs['test-inventory']['cases']};groups={g['id'] for g in inputs['case-groups']['groups'] if g['status']=='confirmed'};seen=set()
        for m in value['matches']:
            if m['test_case_id'] not in cases or m['test_case_id'] in seen:raise ValueError('测试用例对应重复或引用未知ID')
            seen.add(m['test_case_id'])
            if m['status']=='confirmed' and m['case_group_id'] not in groups:raise ValueError('测试只能对应到已确认的RR/SR用例组')
            if m['status']!='confirmed' and m['case_group_id'] is not None:raise ValueError('未确定的测试用例对应不能偷偷进入计分组')
        if seen!=cases:raise ValueError('每个测试用例必须对应或明确列待确认/未匹配，不能丢弃')
