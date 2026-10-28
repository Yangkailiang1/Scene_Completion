"""Assemble complete SSE chat output; never accept partial JSON; provider reasoning is an explicit display opt-in."""
import json
import time
import http.client


def read_chat_stream(response, started, timeout, observer=None, *, idle_timeout=None,set_read_timeout=None,capture_reasoning=False,display_reasoning=False,throughput_policy=None,requested_model=None):
    from .throughput import Monitor
    monitor=Monitor(throughput_policy or (lambda:{}),started=started,model=requested_model)
    reasoning=[];reasoning_bytes=0;reasoning_fields=set();delta_fields=set();initial_progress=False
    content=[];tool_calls={};model=None;finish=None;usage=None;done=False;event=[];events=0;size=0;first=None;last=None;last_progress=started;preparing=False
    def consume(lines):
        nonlocal model,finish,usage,done,events,first,size,last,last_progress,preparing,reasoning_bytes,initial_progress
        data='\n'.join(lines)
        if data=='[DONE]':done=True;return
        if not data:return
        row=json.loads(data);events+=1;last=time.perf_counter()
        if first is None:
            first=time.perf_counter()-started
            if observer:observer.emit('stream_first_event',duration_seconds=first)
        if row.get('error'):
            details=row['error'] if isinstance(row['error'],dict) else {}
            code=details.get('code')
            error=RuntimeError('model provider rejected streamed request')
            category={400:'request_invalid',401:'authentication_failed',403:'access_denied',404:'model_unavailable',408:'transport_timeout',429:'rate_limited',504:'transport_timeout'}.get(code,'stream_provider_error')
            error.response_diagnostic={'failure_category':category,**({'http_status':code} if type(code) is int else {}),'configuration_required':code in (400,401,403,404)}
            retry=details.get('retry_after_seconds')
            if type(retry) in (int,float):error.response_diagnostic['retry_after_seconds']=max(0.,min(300.,retry))
            raise error
        model=row.get('model') or model
        usage=row.get('usage') or usage
        from .execution_events import emit
        for choice in row.get('choices',[]) or []:
            if choice.get('index',0)!=0:continue
            delta=choice.get('delta') or {}
            delta_fields.update(k for k in delta if k in {'role','content','tool_calls','reasoning_content','reasoning','reasoning_details'})
            from .provider_reasoning import fragments
            pieces,fields=fragments(delta);reasoning_fields.update(fields)
            for source,piece in pieces:
                reasoning_bytes+=len(piece.encode('utf8'))
                if reasoning_bytes>32*1024*1024:raise ValueError('reasoning exceeds bounded transport buffer')
                if capture_reasoning:reasoning.append(piece)
                if display_reasoning:emit('stream_delta',channel='reasoning',text=piece,source='provider_'+source,not_artifact=True)
            if pieces and not preparing:
                emit('stream_status',status='preparing_answer',message='模型正在准备回复，尚未返回正文。')
                preparing=True
            text=delta.get('content')
            if text:
                if not isinstance(text,str):raise ValueError('stream content must be text')
                size+=len(text.encode('utf8'))
                if size>16*1024*1024:raise ValueError('stream output exceeds bounded response size')
                content.append(text)
                emit('stream_delta',channel='text',text=text)
            for part in delta.get('tool_calls',[]) or []:
                index=part.get('index',0)
                call=tool_calls.setdefault(index,{'id':'','type':'function','function':{'name':'','arguments':''}})
                fun=part.get('function') or {}
                call['id']+=part.get('id') or ''
                call['function']['name']+=fun.get('name') or ''
                call['function']['arguments']+=fun.get('arguments') or ''
                size+=len((fun.get('arguments') or '').encode('utf8'))
                if size>16*1024*1024:raise ValueError('stream output exceeds bounded response size')
                emit('stream_delta',channel='tool_arguments',tool_index=index,tool_name=fun.get('name') or '',text=fun.get('arguments') or '',tool_call_id=part.get('id'))
            finish=choice.get('finish_reason') or finish
        if not initial_progress or last-last_progress>=10:
            emit('stream_progress',elapsed_seconds=round(last-started,2),stream_events=events,output_bytes=size,provider_model=model,reasoning_bytes=reasoning_bytes,reasoning_received=bool(reasoning_bytes),reasoning_display_enabled=display_reasoning,reasoning_fields=sorted(reasoning_fields),delta_fields=sorted(delta_fields))
            initial_progress=True;last_progress=last
    try:
        iterator=iter(response)
        while True:
            if time.perf_counter()-started>timeout:
                err=TimeoutError('stream total deadline exceeded');err.response_diagnostic={'timeout_kind':'total_deadline'};raise err
            monitor.observe(size+reasoning_bytes)
            wait_limit=monitor.read_wait()
            if set_read_timeout:set_read_timeout(max(.001,min(idle_timeout or timeout,timeout-(time.perf_counter()-started),wait_limit if wait_limit is not None else timeout)))
            try:raw=next(iterator)
            except StopIteration:break
            line=raw.decode('utf8').rstrip('\r\n')
            if not line:
                consume(event);event=[]
                if done:break
            elif line.startswith('data:'):event.append(line[5:].lstrip())
            # SSE comments/heartbeats and reasoning text are not model answers.
    except TimeoutError as err:
        now=time.perf_counter()
        monitor.timeout()
        err.response_diagnostic={'failure_category':'transport_timeout','phase':'stream_read','timeout_kind':'total_deadline' if now-started>=timeout else 'idle_read','elapsed_seconds':round(now-started,3),'first_event_seconds':first,'last_event_age_seconds':round(now-last,3) if last else None,'stream_events':events,'partial_content_bytes':size,'provider_model':model,'reasoning_bytes':reasoning_bytes,'reasoning_fields':sorted(reasoning_fields),'delta_fields':sorted(delta_fields),'incomplete_tools':[c['function']['name'] for c in tool_calls.values()],**getattr(err,'response_diagnostic',{})}
        raise
    if event and not done:consume(event)
    if not done or finish is None:
        error=http.client.IncompleteRead(b'',None)
        error.response_diagnostic={'failure_category':'stream_incomplete','phase':'stream_read',
          'elapsed_seconds':round(time.perf_counter()-started,3),'partial_content_bytes':size,'stream_events':events,
          'provider_model':model,'finish_reason':finish,'done_received':done,
          'first_event_seconds':first,'last_event_age_seconds':round(time.perf_counter()-last,3) if last else None,
          'reasoning_bytes':reasoning_bytes,'reasoning_fields':sorted(reasoning_fields),'delta_fields':sorted(delta_fields),'incomplete_tools':[c['function']['name'] for c in tool_calls.values()]}
        raise error
    calls=[tool_calls[i] for i in sorted(tool_calls)]
    for call in calls:
        # Keep completed transport usage; the semantic client rejects a model
        # length ceiling before parsing or publishing partial tool arguments.
        if finish=='length':continue
        if not call['id'] or not call['function']['name']:raise ValueError('incomplete streamed tool identity')
        # Parse arguments in the metered semantic adapter, after usage settlement.
        # A complete HTTP stream can still contain invalid semantic JSON.
    return {'model':model,'choices':[{'message':{'content':''.join(content),**({'reasoning_content':''.join(reasoning)} if capture_reasoning and reasoning else {}),**({'tool_calls':calls} if calls else {})},'finish_reason':finish}],
        'usage':usage,'_scene_completion_metrics':{'stream_events':events,'first_event_seconds':first,'stream_complete':True,'reasoning_bytes':reasoning_bytes,'reasoning_fields':sorted(reasoning_fields),'delta_fields':sorted(delta_fields),'reasoning_display_enabled':display_reasoning,'response_mode':'sse','estimated_generated_tokens':round((size+reasoning_bytes)/4,1),'tokens_per_second_estimate':round((size+reasoning_bytes)/4/max(.001,time.perf_counter()-started),3),'throughput_measurement':'UTF-8 bytes / 4; estimate including reasoning, not billing'}}
