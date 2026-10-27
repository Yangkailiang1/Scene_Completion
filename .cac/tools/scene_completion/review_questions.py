"""Non-blocking, task-bound business questions and versioned answers.

Business answers are not execution commands. Confirmed normal rules are new
evidence owned by their originating channel, never a rewrite of the documents.
"""
from pathlib import Path
from copy import deepcopy
import time
from threading import RLock
from functools import wraps
from .storage import read_json, write_json, fingerprint

VERSION = 'business-review-v1'
_LOCK=RLock()
def locked(fn):
    @wraps(fn)
    def call(*args,**kwargs):
        with _LOCK:return fn(*args,**kwargs)
    return call
TYPES = {
    'rule_completion': {'label': '补充正常校验规则', 'choices': {'provide_rule': '补充规则', 'not_required': '不要求此校验', 'needs_info': '仍待补充'}},
    'scenario_classification': {'label': '异常候选判定', 'choices': {'anomaly': '是异常', 'not_anomaly': '不是异常', 'needs_info': '仍待确认'}},
    'binding_confirmation': {'label': '确认用例、交互或对象归属', 'choices': {'confirm': '确认当前对应', 'correct': '修正对应关系', 'needs_info': '仍待确认'}},
    'general_clarification': {'label': '补充业务说明', 'choices': {'answered': '已回答', 'needs_info': '仍待补充'}},
}


def load(project, name, default):
    path = Path(project) / name
    return read_json(path) if path.exists() else deepcopy(default)


def channel_for(stage):
    if stage.startswith('test-'): return 'test_gt'
    if stage.startswith('existing-'): return 'existing_e'
    return 'positive'


@locked
def report(project, node, stage, case, question, *, inputs=None):
    if not isinstance(question, dict): raise ValueError('业务问题必须为对象')
    kind = question.get('question_type', 'general_clarification')
    if kind not in TYPES: raise ValueError('未知业务问题类型')
    text = question.get('question') or question.get('text')
    missing = question.get('required_answer') or question.get('decision')
    if not isinstance(text, str) or not text.strip() or len(text) > 6000 or not isinstance(missing, str) or not missing.strip():
        raise ValueError('问题须说明不确定内容和需要业务决定的事项')
    refs = question.get('source_refs', [])
    if not isinstance(refs,list) or len(refs)>100:raise ValueError('问题引用必须是有界列表')
    if any(not isinstance(r,dict) or set(r)!={'source_id','line_start','line_end','quote'} or type(r['line_start']) is not int or type(r['line_end']) is not int or not isinstance(r['source_id'],str) or not r['source_id'] or not isinstance(r['quote'],str) or not r['quote'].strip() or not 1<=r['line_start']<=r['line_end'] for r in refs):raise ValueError('问题必须使用当前任务提供的精确引用，不能创造行号或ID')
    if inputs is not None and refs:
        from .source_documents import documents_in, evidence_refs, validate_evidence
        allowed = {fingerprint(r) for r in evidence_refs(inputs)}
        for ref in refs:
            if fingerprint(ref) not in allowed: validate_evidence(ref, documents_in(inputs))
    identity = fingerprint([node, fingerprint(inputs) if inputs is not None else None, kind, text, refs])[:24]
    row = {'id': identity, 'case': case or 'shared', 'interaction_id': question.get('interaction_id') or 'unbound',
           'object': question.get('object'), 'concern_key': question.get('concern_key'), 'reason': text.strip(),
           'required_answer': missing.strip(), 'known_facts': str(question.get('known_facts') or question.get('basis') or ''),
           'source_refs': refs, 'origins': [node], 'source_channel': channel_for(stage), 'queue': 'business',
           'question_type': kind, 'nonblocking': True, 'created_at': time.time(), 'input_hash': fingerprint(inputs) if inputs is not None else None}
    saved = load(project, 'business_questions.json', {'version': VERSION, 'items': {}})
    if identity not in saved['items']:
        saved['items'][identity] = row
        write_json(Path(project) / 'business_questions.json', saved)
        from .execution_events import EventStore
        EventStore(Path(project) / 'run').append('business_question_recorded', task_key=node, question_id=identity, question_type=kind, nonblocking=True)
    return saved['items'][identity]


def bindings(project, origins, state=None):
    state = state if state is not None else load(project, 'run/workflow_tasks.json', {'tasks': {}})['tasks']
    return {key: {k: state.get(key, {}).get(k) for k in ('identity', 'output_hash', 'stage', 'case')} for key in origins}


def decorate(project, rows):
    out = {r['id']: deepcopy(r) for r in rows}
    state = load(project, 'run/workflow_tasks.json', {'tasks': {}})['tasks']
    questions = load(project, 'business_questions.json', {'items': {}})['items']
    for q in questions.values():
        if all(k in state for k in q['origins']):
            stale=False
            for origin in q['origins']:
                record=state[origin];file=Path(project)/'run'/str(record.get('output_file',''))
                if record.get('status')=='passed' and file.is_file():
                    actual=read_json(file).get('metadata',{}).get('input_hash')
                    if actual and q.get('input_hash') and actual!=q['input_hash']:stale=True
            if not stale:out[q['id']] = deepcopy(q)
    # A resolved question remains auditable after a new output no longer asks it.
    for iid, decision in load(project,'pending_decisions.json',{'items':{}})['items'].items():
        if iid not in out and decision.get('item_snapshot'):
            out[iid]={**deepcopy(decision['item_snapshot']),'historical':True}
    for item in out.values():
        stages = {state.get(k, {}).get('stage') for k in item['origins']}
        kind = item.get('question_type')
        # Only explicit ownership/context diagnostics move to engineering review.
        # This is presentation routing, never an anomaly/concern classification.
        reason=str(item.get('reason',''))
        ownership=(reason.startswith('规则归属核查：') or '请在对应实际服务交互核对' in reason or ('fused-ssd' in reason.lower() and any(x in reason for x in ('唯一接收方','未出现在','不属于','无可绑定','不落在'))))
        if not kind and ownership:
            kind='binding_confirmation';item['queue']='structure';item['engineering_review']=True
            item['required_answer']='请先由研发核对SSD与原文的实际执行对象；业务可补充真实对应关系，不需要将结构矛盾判成异常。'
        if not kind:
            if 'normal-rules' in stages and not str(item['reason']).startswith('规则归属核查：'): kind = 'rule_completion'
            elif stages & {'existing-bind', 'test-case-align', 'fused-ssd', 'enriched-view'} or str(item['reason']).startswith('规则归属核查：'): kind = 'binding_confirmation'
            elif item.get('category') in {'异常场景', '异常归类'}: kind = 'scenario_classification'
            else: kind = 'general_clarification'
        if kind not in TYPES:kind='general_clarification'
        item['question_type'] = kind
        item['answer_spec'] = TYPES[kind]
        item['origin_bindings'] = bindings(project, item['origins'],state)
        item['required_answer'] = item.get('required_answer') or ({'rule_completion': '请补充实际校验条件及执行位置，或明确不要求此校验。', 'binding_confirmation': '请确认或修正对应对象／步骤；模型结构错误可交回研发核查。'}.get(kind, '请说明业务决定及依据。'))
    return list(out.values())


@locked
def answer(project, item, body, *, dry_run=False):
    if item.get('technical'): raise ValueError('技术执行错误请由研发修复，不能直接确认为业务异常')
    if body.get('expected_origin_bindings') is not None and body['expected_origin_bindings']!=bindings(project,item['origins']):raise ValueError('来源产物已变化，请刷新问题后再回答')
    saved = load(project, 'pending_decisions.json', {'revision': 0, 'items': {}, 'history': []})
    previous = saved['items'].get(item['id'], {})
    if body.get('revision') != previous.get('revision', 0): raise ValueError('回答已变化，请刷新')
    actor = str(body.get('reviewer') or '').strip()
    if not actor: raise ValueError('请填写审核人')
    choice = body.get('choice')
    if choice not in TYPES[item['question_type']]['choices'] and choice != 'withdraw': raise ValueError('回答与问题类型不符')
    text = str(body.get('answer') or body.get('note') or '').strip()
    if len(text) > 8000: raise ValueError('回答最多8000字符')
    if choice not in {'needs_info', 'withdraw'} and not text: raise ValueError('请填写实际规则或判断依据')
    concern = body.get('concern_key')
    if choice == 'anomaly':
        from .project_review import project_registry
        definition = project_registry(project)['definitions'].get(concern, {})
        if definition.get('kind') != 'check' or not definition.get('enabled', True): raise ValueError('请选择启用的具体关注点')
    row = {'item_id': item['id'], 'revision': previous.get('revision', 0)+1, 'choice': 'unresolved' if choice=='withdraw' else choice,
           'action': choice, 'question_type': item['question_type'], 'answer': text, 'note': text, 'concern_key': concern,
           'reviewer': actor, 'via': body.get('via', 'web'), 'at': time.time(), 'origins': item['origins'],
           'origin_bindings': bindings(project, item['origins']), 'item_snapshot': {k: v for k,v in item.items() if k!='decision'},
           'requires_recompute': choice not in {'needs_info', 'withdraw'}, 'version': VERSION}
    if dry_run: return {'valid': True, 'saved': False, 'answer': row}
    saved['items'][item['id']] = row; saved['history'].append(row); saved['revision'] += 1
    write_json(Path(project) / 'pending_decisions.json', saved)
    from .execution_events import EventStore
    EventStore(Path(project) / 'run').append('business_answer_saved', item_id=item['id'], revision=row['revision'], reviewer=actor, recompute_started=False)
    return row


def impact(project):
    saved = load(project, 'pending_decisions.json', {'items': {}})
    applied = load(project, 'review_applied.json', {'items': {}})
    nodes = load(project, 'run/workflow_graph.json', {'nodes': []})['nodes']
    graph = {n['id']: n for n in nodes}; roots=set(); revisions={}; conflicts=[]
    for iid, row in saved['items'].items():
        # Withdrawing an already applied answer must also remove its evidence.
        if row.get('choice') == 'needs_info' or row.get('revision') == applied['items'].get(iid): continue
        if not row.get('version') or (row.get('choice')=='unresolved' and iid not in applied['items']): continue
        if not all(k in graph for k in row['origins']): conflicts.append({'id': iid, 'reason': '来源节点不在当前执行图'});continue
        roots.update(row['origins']); revisions[iid]=row['revision']
    affected=set(roots)
    while True:
        more={k for k,n in graph.items() if set(n.get('deps', [])) & affected}
        if more<=affected: break
        affected |= more
    identity=fingerprint({'revisions': revisions, 'bindings': bindings(project, sorted(affected))})
    return {'plan_id': identity, 'roots': sorted(roots), 'affected': sorted(affected), 'answer_revisions': revisions,
            'conflicts': conflicts, 'nodes': [{'id':k,'label':graph[k].get('label',k),'stage':graph[k].get('stage')} for k in sorted(affected)], 'llm_called': False}


def apply_answers(project, expected_plan):
    plan=impact(project)
    if expected_plan!=plan['plan_id']: raise ValueError('影响范围已变化，请重新预览')
    if plan['conflicts']: raise ValueError('存在反馈冲突，请先处理')
    # Preserve exact prior reports and affected outputs before recomputation.
    import shutil
    root=Path(project)/'run';archive=root/'report_versions'/('business-review-'+plan['plan_id'][:20])
    archive.mkdir(parents=True,exist_ok=True)
    for name in ('run_manifest.json','workflow_tasks.json','workflow_graph.json','missing_report.json','missing_report.md'):
        if (root/name).is_file():shutil.copy2(root/name,archive/name)
    records=load(project,'run/workflow_tasks.json',{'tasks':{}})['tasks']
    for key in plan['affected']:
        name=records.get(key,{}).get('output_file')
        if name and (root/name).is_file():
            source=(root/name).resolve()
            if not source.is_relative_to(root.resolve()):raise ValueError('无效历史产物路径')
            dest=archive/'outputs'/(fingerprint(key)+'.json');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    write_json(archive/'review_impact.json',plan)
    previous=load(project, 'review_applied.json', {'items': {}, 'history': []})
    previous['items'].update(plan['answer_revisions'])
    previous['history'].append({'plan_id':plan['plan_id'],'at':time.time(),'affected':plan['affected']})
    write_json(Path(project)/'review_applied.json',previous)
    from .node_conversations import Conversations
    store=Conversations(Path(project)/'run')
    for key in plan['roots']:
        store.append(key, 'guidance', '请使用本节点最新业务确认材料重新核对，其他来源和通道边界保持不变。', {'business_review_plan':plan['plan_id']})
        store.invalidate(key)
    return plan


def materials(project, node):
    """Only explicitly applied answers, scoped to the exact originating node."""
    saved=load(project,'pending_decisions.json',{'items':{}})['items'];applied=load(project,'review_applied.json',{'items':{}})['items'];docs=[]
    for iid,rev in applied.items():
        r=saved.get(iid,{})
        if r.get('revision')!=rev or node not in r.get('origins',[]) or r.get('choice') in {'unresolved','needs_info'}: continue
        snap=r['item_snapshot'];channel=snap['source_channel']
        # Human recommendation adoption is never routed as positive evidence.
        text=f"问题：{snap['reason']}\n业务回答（{r['choice']}）：{r['answer']}\n审核人：{r['reviewer']}；版本：{rev}"
        docs.append({'source_id':'business-'+fingerprint([iid,rev])[:20], 'name':'业务确认 '+iid,
                     'channel':{'positive':'normal','existing_e':'existing','test_gt':'test'}[channel], 'review_channel':channel, 'review_item_id':iid, 'review_revision':rev,
                     'lines':[{'number':n,'text':s} for n,s in enumerate(text.splitlines(),1)]})
    return docs
