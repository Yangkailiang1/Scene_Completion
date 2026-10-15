"""Assemble complete SSE chat output; never accept partial JSON or store reasoning."""
import json
import time
import http.client


def read_chat_stream(response, started, timeout, observer=None):
    content=[];model=None;finish=None;usage=None;done=False;event=[];events=0;size=0;first=None
    def consume(lines):
        nonlocal model,finish,usage,done,events,first,size
        data='\n'.join(lines)
        if data=='[DONE]':done=True;return
        if not data:return
        row=json.loads(data);events+=1
        if first is None:
            first=time.perf_counter()-started
            if observer:observer.emit('stream_first_event',duration_seconds=first)
        if row.get('error'):raise http.client.IncompleteRead(b'',None)
        model=row.get('model') or model
        usage=row.get('usage') or usage
        for choice in row.get('choices',[]):
            if choice.get('index',0)!=0:continue
            delta=choice.get('delta',{})
            text=delta.get('content')
            if text:
                if not isinstance(text,str):raise ValueError('stream content must be text')
                size+=len(text.encode('utf8'))
                if size>16*1024*1024:raise ValueError('stream output exceeds bounded response size')
                content.append(text)
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
    return {'model':model,'choices':[{'message':{'content':''.join(content)},'finish_reason':finish}],
        'usage':usage,'_scene_completion_metrics':{'stream_events':events,'first_event_seconds':first,'stream_complete':True}}
