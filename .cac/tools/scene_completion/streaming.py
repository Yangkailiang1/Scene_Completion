"""Assemble complete SSE chat output; never accept partial JSON or store reasoning."""
import json
import time
import http.client


def read_chat_stream(response, started, timeout, observer=None):
    content=[];tool_calls={};model=None;finish=None;usage=None;done=False;event=[];events=0;size=0;first=None
    def consume(lines):
        nonlocal model,finish,usage,done,events,first,size
        data='\n'.join(lines)
        if data=='[DONE]':done=True;return
        if not data:return
        row=json.loads(data);events+=1
        if first is None:
            first=time.perf_counter()-started
            if observer:observer.emit('stream_first_event',duration_seconds=first)
        if row.get('error'):
            details=row['error'] if isinstance(row['error'],dict) else {}
            code=details.get('code')
            error=RuntimeError('model provider rejected streamed request')
            error.response_diagnostic={'failure_category':'request_invalid' if code==400 else 'stream_provider_error',**({'http_status':code} if type(code) is int else {}),'configuration_required':code in (400,401,403,404)}
            raise error
        model=row.get('model') or model
        usage=row.get('usage') or usage
        from .execution_events import emit
        for choice in row.get('choices',[]) or []:
            if choice.get('index',0)!=0:continue
            delta=choice.get('delta') or {}
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
    for raw in response:
        if time.perf_counter()-started>timeout:raise TimeoutError('stream deadline exceeded')
        line=raw.decode('utf8').rstrip('\r\n')
        if not line:
            consume(event);event=[]
            if done:break
        elif line.startswith('data:'):event.append(line[5:].lstrip())
        # SSE comments/heartbeats and reasoning text are not model answers.
    if event and not done:consume(event)
    if not done or finish is None:
        error=http.client.IncompleteRead(b'',None)
        error.response_diagnostic={'failure_category':'stream_incomplete','partial_content_bytes':size,'stream_events':events}
        raise error
    if finish=='length':raise ValueError('model output was truncated before a complete task submission; review stage output budget')
    calls=[tool_calls[i] for i in sorted(tool_calls)]
    for call in calls:
        if not call['id'] or not call['function']['name']:raise ValueError('incomplete streamed tool identity')
        try:json.loads(call['function']['arguments'])
        except json.JSONDecodeError as e:raise ValueError('completed tool stream contains invalid JSON arguments') from e
    return {'model':model,'choices':[{'message':{'content':''.join(content),**({'tool_calls':calls} if calls else {})},'finish_reason':finish}],
        'usage':usage,'_scene_completion_metrics':{'stream_events':events,'first_event_seconds':first,'stream_complete':True}}
