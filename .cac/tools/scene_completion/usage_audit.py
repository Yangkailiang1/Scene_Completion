"""Read-only usage accounting. Provider-reported tokens are never inferred from bytes."""
from pathlib import Path
from collections import defaultdict
import json,sqlite3,time,html
from urllib.parse import quote
from .storage import read_json,fingerprint
from .source_documents import documents_in,evidence_refs,normal_projection,read_documents


def context_summary(inputs,full_documents=()):
    whole={d['source_id']:d for d in full_documents};docs=documents_in(inputs);scopes=[]
    for d in docs:
        rows={r['number'] for r in d['lines']};original=whole.get(d['source_id']);mode='scoped'
        if original:
            if rows=={r['number'] for r in original['lines']}:mode='full_document'
            elif rows=={r['number'] for r in normal_projection([original])[0]['lines']}:mode='full_positive_document'
        scopes.append({'source_id':d['source_id'],'name':d['name'],'channel':d['channel'],'lines':len(rows),'whole_lines':len(original['lines']) if original else None,'scope':mode})
    refs=evidence_refs(inputs)
    return {'input_json_bytes':len(json.dumps(inputs,ensure_ascii=False,separators=(',',':')).encode()),'documents':scopes,
      'reference_occurrences':len(refs),'unique_references':len({fingerprint(r) for r in refs}),
      'note':'输入字节和引用次数不是token数；派生产物中的引用不表示再次读取源文全文。'}


def summarize_requests(events,now=None):
    now=now or time.time();calls={};last={}
    for event in events:
        kind=event['kind'];d=event['data'];node=event.get('task_key');key=d.get('model_call_id')
        if kind=='request_started':
            key=key or str(event['id']);last[node]=key
            calls[key]={'id':key,'task_key':node,'role':event.get('role'),'case':event.get('case'),'account_id':d.get('account_id'),'account':d.get('account','历史未标注账号'),'model':d.get('requested_model'),'started_at':event['at'],'input_bytes':d.get('input_bytes'),'output_limit':d.get('max_output_tokens'),'status':'in_flight','usage':None}
        elif kind in {'request_finished','request_failed'}:
            key=key or last.get(node)
            if key not in calls:continue
            row=calls[key];row['finished_at']=event['at'];row['status']='completed' if kind=='request_finished' else 'failed'
            row['usage']=d.get('usage');row['provider_model']=d.get('provider_model');row['diagnostic']=d.get('diagnostic')
            reason=(d.get('diagnostic') or {})
            if reason.get('admission_paused') or reason.get('quota') or reason.get('failure_category')=='budget_exhausted':row['status']='not_sent'
    for row in calls.values():row['seconds']=max(0,(row.get('finished_at') or now)-row['started_at'])
    by_node={}
    for row in calls.values():
        node=row['task_key'];n=by_node.setdefault(node,{'task_key':node,'calls':0,'completed_calls':0,'unknown_usage_calls':0,'in_flight_calls':0,'not_sent_calls':0,'input_tokens':0,'output_tokens':0,'reasoning_tokens':0,'cached_input_tokens':0,'reported_total_tokens':0,'request_seconds':0,'max_request_bytes':0,'models':[],'cost':None,'cost_status':'未核算：接口不返回实际扣费，免费额度/计费单价未提供'})
        n['max_request_bytes']=max(n['max_request_bytes'],row.get('input_bytes') or 0)
        n['calls']+=1;n['in_flight_calls']+=row['status']=='in_flight';n['not_sent_calls']+=row['status']=='not_sent';n['completed_calls']+=row['status']=='completed'
        n['request_seconds']+=row['seconds'] if row['status']!='not_sent' else 0
        if row['model'] not in n['models']:n['models'].append(row['model'])
        u=row['usage']
        if isinstance(u,dict) and type(u.get('total_tokens')) is int:
            n['input_tokens']+=u.get('prompt_tokens',0);n['output_tokens']+=u.get('completion_tokens',0);n['reported_total_tokens']+=u['total_tokens']
            n['reasoning_tokens']+=(u.get('completion_tokens_details') or {}).get('reasoning_tokens',0)
            n['cached_input_tokens']+=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0)
        elif row['status'] not in {'not_sent','in_flight'}:n['unknown_usage_calls']+=1
    return {'requests':list(calls.values()),'tasks':by_node}


def project_usage(root,include_context=False):
    root=Path(root);events=[];dbfile=root/'execution_events.sqlite3'
    if dbfile.exists():
        with sqlite3.connect('file:'+str(dbfile)+'?mode=ro',uri=True) as db:
            for seq,raw in db.execute("SELECT id,payload FROM events WHERE kind IN ('request_started','request_finished','request_failed') ORDER BY id"):
                events.append({**json.loads(raw),'id':seq})
    report=summarize_requests(events)
    graph=read_json(root/'workflow_graph.json') if (root/'workflow_graph.json').exists() else {'nodes':[]}
    states=read_json(root/'workflow_tasks.json').get('tasks',{}) if (root/'workflow_tasks.json').exists() else {}
    from .execution_graph import LABELS
    for node in graph['nodes']:
        key=node['id'];r=report['tasks'].setdefault(key,{'task_key':key,'calls':0,'completed_calls':0,'unknown_usage_calls':0,'in_flight_calls':0,'not_sent_calls':0,'input_tokens':0,'output_tokens':0,'reasoning_tokens':0,'cached_input_tokens':0,'reported_total_tokens':0,'request_seconds':0,'max_request_bytes':0,'models':[],'cost':None,'cost_status':'无模型调用记录'})
        r.update(label=node.get('label') or LABELS.get(node['stage'],node['stage']),stage=node['stage'],case=node['case'],status=states.get(key,{}).get('status','pending'))
    if include_context:
        full=[];meta=root.parent/'project.json'
        if meta.exists():
            for role,docs in read_json(meta).get('sources',{}).items():full+=read_documents([root.parent/d['path'] for d in docs], 'test' if role=='test' else 'existing')
        contexts={}
        for file in sorted((root/'packets').glob('*.json'),key=lambda f:f.stat().st_mtime):
            q=read_json(file);key=q.get('node_key')
            if key:contexts[key]=context_summary(q['input'],full)
        for key,value in contexts.items():
            if key in report['tasks']:report['tasks'][key]['context']=value
        for file in sorted((root/'model_contexts').glob('*.json'),key=lambda f:f.stat().st_mtime):
            q=read_json(file);key=q.get('node_key')
            if key in report['tasks']:report['tasks'][key]['model_context']=context_summary(q['input'],full)
    values=list(report['tasks'].values())
    report.update(generated_at=time.time(),totals={k:sum(t.get(k,0) for t in values) for k in ('calls','not_sent_calls','completed_calls','unknown_usage_calls','in_flight_calls','input_tokens','output_tokens','reasoning_tokens','reported_total_tokens','request_seconds')},
      notes=['包含此项目全部历史尝试和修复；复用外部验证结果不记为本项目新调用。','输出token通常已经包含思考token，不再次相加；缓存输入是输入的子集。','请求累计耗时包括失败/重试，多个任务并行时不能当项目墙钟时间。','无usage的断流/失败不记为0；保守额度预留与实际报告token分开。'])
    return report


def usage_html(report):
    esc=lambda s:html.escape(str(s));rows=[]
    for key,t in report['tasks'].items():
        scopes='；'.join(d['name']+': '+d['scope']+' '+str(d['lines'])+'/'+str(d['whole_lines'] or '?')+'行' for d in t.get('model_context',t.get('context',{})).get('documents',[])) or '无模型原文任务包（工具任务或尚未准备）'
        rows.append('<tr><td><a target="_blank" href="context?task_key='+quote(key,safe='')+'">'+esc(key)+'</a></td>'+''.join('<td>'+esc(v)+'</td>' for v in [t.get('label',key),t.get('status','历史任务'),', '.join(t['models']),t['calls']-t['not_sent_calls'],t['not_sent_calls'],t['input_tokens'],t['output_tokens'],t['reasoning_tokens'],t['reported_total_tokens'],t['unknown_usage_calls'],t.get('in_flight_calls',0),round(t['request_seconds'],1),scopes,round(t.get('context',{}).get('input_json_bytes',0)/1024,1),round(t.get('model_context',{}).get('input_json_bytes',0)/1024,1),round(t.get('max_request_bytes',0)/1024,1)] )+'</tr>')
    heads=['任务ID','业务任务','当前状态','请求模型','已发起请求','未发出/暂停','输入token','输出token','其中思考token','已报告总token','用量未知请求','进行中请求','累计请求秒','当前原文范围','原始业务包KB（非token）','模型侧精简上下文KB（非token）','最大请求KB（含Schema）']
    return '<!doctype html><html lang="zh"><meta charset="utf-8"><title>用量与上下文审计</title><style>body{font:14px system-ui;margin:24px;color:#18324b}table{border-collapse:collapse;width:100%}th,td{border:1px solid #d9e2ec;padding:8px;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#eaf2fa}input{padding:10px;width:420px;margin:12px 0}tr:nth-child(even){background:#f8fafc}</style><h1>任务token、耗时与上下文审计</h1><p>'+esc(json.dumps(report['totals'],ensure_ascii=False))+'</p><ul>'+''.join('<li>'+esc(n)+'</li>' for n in report['notes'])+'</ul><p><a href="?format=json">下载JSON</a></p><input id="q" placeholder="搜索用例、模型、任务或状态"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table><script>const q=document.querySelector("#q");q.oninput=e=>document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase()));q.value=decodeURIComponent(location.hash.slice(1));q.dispatchEvent(new Event("input"))</script></html>'
