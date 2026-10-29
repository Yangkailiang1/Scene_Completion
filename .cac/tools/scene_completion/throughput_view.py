"""A whitelist-only telemetry series; never returns prompt, arguments or thinking text."""
import json,csv,io
from .execution_events import EventStore
KINDS={'request_started','request_finished','request_failed','throughput_sample','stream_progress','stream_first_event','model_degraded','model_switched','model_switch_skipped','rate_limit_wait'}
FIELDS={'model_call_id','requested_model','provider_model','account_id','elapsed_seconds','window_seconds','tokens_per_second_estimate','output_bytes','reasoning_bytes','reasoning_characters','content_bytes','tool_argument_bytes','failure_category','retry_after_seconds','reason','measurement','enabled','estimated_generated_tokens','last_output_age_seconds','threshold','previous_model','retry_at','model'}

def series(project,after=0,limit=2000,model=None,node=None,since=None):
 store=EventStore(project/'run');query='SELECT id,payload FROM events WHERE id>? AND kind IN ('+','.join('?' for k in KINDS)+')';args=[after,*sorted(KINDS)]
 if since is not None:
  import math
  if not math.isfinite(since) or since<0:raise ValueError('无效吞吐时间范围')
  query+=' AND at>=?';args.append(since)
 if node:query+=' AND task_key=?';args.append(node)
 query+=' ORDER BY id LIMIT ?';args.append(min(10000,max(1,limit)))
 with store.connect() as db:rows=db.execute(query,args).fetchall()
 points=[];cursor=after
 for eid,raw in rows:
  event=json.loads(raw);cursor=eid;data=event['data'];clean={k:v for k,v in data.items() if k in FIELDS and type(v) in (str,int,float,bool,type(None))}
  diagnostic=data.get('diagnostic') or {}
  for k in ('failure_category','http_status','retry_after_seconds'):
   if k in diagnostic:clean[k]=diagnostic[k]
  if model and clean.get('requested_model') not in (None,model):continue
  points.append({'id':eid,'at':event['at'],'kind':event['kind'],'node':event.get('task_key'),'role':event.get('role'),**clean})
 return {'points':points,'cursor':cursor,'has_more':len(rows)>=min(10000,max(1,limit)),'measurement':'实时Token为UTF-8字节/4估算，不是账单Token；网关不公开的内容不可测量'}

def csv_export(value):
 out=io.StringIO();fields=['id','at','kind','node','role',*sorted(FIELDS)];writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(value['points']);return '\ufeff'+out.getvalue()
