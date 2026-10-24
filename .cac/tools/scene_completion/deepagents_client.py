"""Task-scoped Deep Agents roles using the existing metered model transport.

Every invocation gets a fresh virtual filesystem containing only its allowed
packet and Skill. No general shell, real project filesystem or cross-role memory.
"""
from pathlib import Path
from typing import Any
from datetime import datetime,timezone
import json
from .model_client import SemanticClient
from .storage import write_json,fingerprint
from contextvars import ContextVar
_AGENT_SESSION=ContextVar('scene_agent_session',default=None)

def submission_mode(config,task,model):
    default='json_text' if task=='components' or model=='ecnu-plus' else 'tool_calls'
    selected=config.get('component_submission_mode') if task=='components' else None
    selected=selected or config.get('submission_mode',default)
    if selected not in {'json_text','tool_calls'}:raise ValueError('submission_mode must be json_text or tool_calls')
    return selected

def compact_input(value):
    """Lossless numbered document presentation; do not repeat schema in the prompt."""
    if isinstance(value,dict):
        if {'source_id','channel','lines'}<=value.keys():
            return {k:value[k] for k in ('source_id','name','channel')}|{'numbered_text':'\n'.join(('['+r['evidence_id']+'] ' if r.get('evidence_id') else '')+str(r['number'])+' | '+r['text'] for r in value['lines'])}
        return {k:compact_input(v) for k,v in value.items()}
    if isinstance(value,list):return [compact_input(v) for v in value]
    return value

def task_message(packet):
    view={k:packet[k] for k in ('task','case_ids','repair','tool_rule_coverage','tool_rule_instruction') if k in packet}
    view['input']=compact_input(packet['input'])
    return '执行本任务。文档以原始行号 | 原文呈现；输出Schema已提供在submit_result工具，不能把Schema当结果。\n'+json.dumps(view,ensure_ascii=False,separators=(',',':'))

def task_files(packet):
    from .source_documents import documents_in
    files={}
    for doc in documents_in(packet['input']):
        path='/input/sources/'+fingerprint(doc['source_id'])[:16]+'.txt'
        files[path]='source_id='+doc['source_id']+'\n'+'\n'.join(str(line['number'])+' | '+line['text'] for line in doc['lines'])
    return files

CHECKER_TASKS={'existing-branches','existing-bind','existing-extract','gap-compare','semantic-compare','test-ground-truth','missing-report','exception-evaluation','extraction-evaluation'}
def role_for(task):
    if task=='gap-recommend':return 'recommender'
    return 'checker' if task in CHECKER_TASKS else 'modeler'

class DeepAgentsClient(SemanticClient):
    def __init__(self,config,*,model_override=None,transport=None):
        super().__init__(config,transport)
        self.model_override=model_override
        self.root=Path(config.get('run_root','runs/deepagents'))
    def agent(self,packet):
        from .model_routing import routed_config
        routed=routed_config(self.config,packet['task'],role_for(packet['task']))
        if routed is not None:
            child=DeepAgentsClient(routed,model_override=self.model_override,transport=self.transport)
            if getattr(self,'shared_call_gate',None):
                original=child.post
                child.post=lambda *a,**k:self.shared_call_gate.call(original,*a,**k)
            return child.agent(packet)
        original_packet=packet
        from .indexed_context import EvidenceContext
        indexed=EvidenceContext(packet) if self.config.get('indexed_context',False) else None
        if indexed:packet=indexed.packet
        # Persist the actual model-facing, credential-free packet for inspection.
        context_id=fingerprint({'task':packet['task'],'input':packet['input'],'schema':packet['output_schema']})
        write_json(self.root/'model_contexts'/(context_id+'.json'),{'task':packet['task'],'node_key':packet.get('node_key'),'input':packet['input'],'output_schema':packet['output_schema'],'context_version': 'indexed-evidence-v1' if indexed else 'raw'})
        from deepagents import create_deep_agent
        from deepagents.backends import StateBackend
        from deepagents.middleware.filesystem import FilesystemPermission
        from .validation import validate_result
        role=role_for(packet['task'])
        if role=='recommender':return {'enabled':False,'status':'未启用'}
        from langchain_core.tools import StructuredTool
        submitted=[]
        from .execution_events import context
        from .node_conversations import Conversations
        _,event_context=context();task_key=event_context.get('task_key',packet['task'])
        conversations=Conversations(self.root)
        attempt=event_context.get('attempt',1)
        mode=submission_mode(self.config,packet['task'],self.model('agent'))
        checkpoint_parts=[packet['task'],packet['input'],packet['output_schema'],packet.get('skill_text'),packet.get('instructions'),attempt,fingerprint(self.config),self.model('agent'),self.base_url]
        if packet['task']=='components' or mode=='json_text':checkpoint_parts.append(mode)
        checkpoint_id=fingerprint(checkpoint_parts)
        saved=conversations.checkpoint(task_key,checkpoint_id) or {}
        pending=conversations.pending(task_key)
        if pending:
            from .scheduler import TaskBlocked
            raise TaskBlocked('awaiting_answer',{'question':pending})
        session={'task_key':task_key,'conversations':conversations,'count':saved.get('model_calls',0),'repair':packet.get('repair')}
        session_token=_AGENT_SESSION.set(session)
        def ask_user(question:str,basis:str,decision:str)->str:
            from .scheduler import TaskBlocked
            if sum(m['kind']=='question' for m in conversations.list(task_key))>=int(self.config.get('agent_max_questions',3)):
                raise TaskRejected({'error':'本节点业务澄清预算已用完，请审核任务输入后重做','phase':'clarification'})
            q=conversations.question(task_key,question,basis,decision)
            emit('question_asked',question=q)
            raise TaskBlocked('awaiting_answer',{'question':q})
        ask=StructuredTool.from_function(func=ask_user,name='ask_user',description='仅在缺少会影响结果的业务决定时提问。包含问题、已有依据、待决定事项。暂停当前节点，其他任务继续。')
        from .execution_events import emit,phase
        from .scheduler import TaskRejected
        def submit(payload:dict) -> str:
            if indexed:
                try:payload=indexed.expand(payload)
                except (ValueError,KeyError,TypeError) as e:
                    emit('validation_failed',error=str(e))
                    rejection=self.root/'agent_rejections'/(fingerprint([packet['batch_id'],task_key,attempt,payload,'model-format'])+'.json')
                    write_json(rejection,{'task':packet['task'],'node_key':task_key,'input_hash':fingerprint(original_packet['input']),'payload':payload,'candidate_format':'model','error':str(e)})
                    raise TaskRejected({'error':str(e),'phase':'model_contract','rejected_output':str(rejection.relative_to(self.root))}) from e
            if packet['task']=='fused-ssd':
                from .use_cases import canonical_case_ids
                payload=canonical_case_ids(payload,packet['input'])
            if any(not r['applied'] for r in conversations.list(task_key) if r['kind'] in {'guidance','answer'}):
                emit('guidance_pending',message='新指导尚未进入本次请求，请下一轮模型调用后重新提交')
                return '用户在本次HTTP输出期间补充了指导；结果尚未保存。请在下一轮读取节点指导后提交。'
            phase('validating')
            try:validate_result(original_packet['task'],payload,original_packet['input'])
            except ValueError as e:
                emit('validation_failed',error=str(e))
                rejection=self.root/'agent_rejections'/(fingerprint([packet['batch_id'],task_key,attempt,payload])+'.json')
                write_json(rejection,{'task':packet['task'],'node_key':task_key,'input_hash':fingerprint(original_packet['input']),'payload':payload,'error':str(e)})
                raise TaskRejected({'error':str(e),'phase':'validation','rejected_output':str(rejection.relative_to(self.root)),'instruction':'由任务执行器使用剩余修复预算定向修复'}) from e
            submitted.append(payload);emit('result_validated')
            return '结果已通过校验，任务完成。'
        submit_result=StructuredTool.from_function(func=submit,name='submit_result',
          description='提交本任务结构化产物。payload必须是已填充的业务结果，不能是Schema定义。',
          args_schema={'title':'SubmitTaskResult','type':'object','properties':{'payload':packet['output_schema']},'required':['payload'],'additionalProperties':False})
        from langchain.agents.middleware import wrap_model_call
        from langchain_core.messages import AIMessage
        @wrap_model_call
        def stop_after_submission(request,handler):
            if submitted:return AIMessage(content='任务结果已验证并保存。',response_metadata={'scene_status':'validated_tool_result'})
            return handler(request)
        model=self.model_override or _transport_model(self,packet['task'])
        role_path=Path(__file__).resolve().parents[2]/'agents'/('scene-'+role+'.md')
        role_text=role_path.read_text(encoding='utf8')
        skill_name=packet['skill'];skill_path='/skills/'+skill_name+'/SKILL.md'
        now=datetime.now(timezone.utc).isoformat()
        file=lambda content:{'content':content.splitlines(),'created_at':now,'modified_at':now}
        # StateBackend has no route to local files; no original E or GT can leak
        # through a modeler tool even when a prompt-injected document requests it.
        agent=create_deep_agent(model=model,middleware=[stop_after_submission],tools=[submit_result,ask],subagents=[],backend=StateBackend(),
          skills=['/skills/'] if packet['skill_text'].lstrip().startswith('---') else [],system_prompt=role_text+'\n'+packet['instructions']+'\n指定Skill已全文加载：\n'+packet['skill_text']+'\n以上Skill已加载，不需要再次读取。直接根据已给完整材料完成本任务，仅证据确有缺口时使用查阅工具。不确定且阻断时调用ask_user，不能自行猜测。节点指导只对本任务生效，不能扩大任务允许的输入通道。使用submit_result提交；不得自行补造证据或把说明当文档事实。完整input已经随用户消息提供，不需要反复读取大任务包。原文行号可在/input/sources/对应文件查证。限定工具阅读轮次；材料充分后立即提交，不为查找不存在的文件反复搜索。',
          permissions=[FilesystemPermission(paths=['/skills/**','/input/**'],operations=['write'],mode='deny')],name='scene-'+role)
        inputs={'messages':[{'role':'user','content':task_message(packet)}],
            'files':{skill_path:file(packet['skill_text']),'/input/task.json':file(json.dumps(packet,ensure_ascii=False,indent=2)),**{path:file(text) for path,text in task_files(packet).items()}}}
        if saved.get('status') in {'awaiting_answer','transport_wait'} and saved.get('messages'):
            from langchain_core.messages import messages_from_dict,messages_to_dict,ToolMessage
            inputs['messages']=messages_from_dict(saved['messages'])
            last=inputs['messages'][-1]
            if getattr(last,'tool_calls',None):
                for call in last.tool_calls:
                    inputs['messages'].append(ToolMessage(content='用户已回答；请读取下次模型请求附带的节点指导并继续。',tool_call_id=call['id']))
        initial_messages=inputs['messages'][:]
        from langsmith import tracing_context
        from langchain_core.callbacks import BaseCallbackHandler
        captured=[];tool_names={}
        class Observer(BaseCallbackHandler):
            def on_tool_start(self,serialized,input_str,*,run_id,**kwargs):
                name=serialized.get('name','tool');tool_names[str(run_id)]=name
                emit('tool_started',tool=name,arguments=input_str)
            def on_tool_end(self,output,*,run_id,**kwargs):
                emit('tool_finished',tool=tool_names.get(str(run_id),'tool'),result=str(output)[:16000])
                if hasattr(output,'model_dump'):captured.append(output)
            def on_tool_error(self,error,*,run_id,**kwargs):
                emit('tool_failed',tool=tool_names.get(str(run_id),'tool'),error_type=type(error).__name__,error=str(error))
            def on_llm_end(self,response,**kwargs):
                for generation in response.generations:
                    for g in generation:
                        if hasattr(g,'message'):captured.append(g.message)
        result=None;error=None
        try:
            with tracing_context(enabled=False):
                result=agent.invoke(inputs,config={'recursion_limit':int(self.config.get('agent_recursion_limit',24)),'callbacks':[Observer()]})
        except Exception as e:
            error=type(e).__name__;emit('agent_failed',error_type=error,error=str(e));raise
        finally:
            trace={'role':role,'task':packet['task'],'batch_id':packet['batch_id'],'status':'failed' if error else 'complete','error_type':error,
               'messages':[m.model_dump(mode='json') for m in (result['messages'] if result else captured)]}
            write_json(self.root/'agent_traces'/(packet['batch_id']+'.json'),trace)
            from uuid import uuid4
            write_json(self.root/'agent_trace_history'/(packet['batch_id']+'-'+uuid4().hex+'.json'),trace)
            from langchain_core.messages import messages_to_dict,convert_to_messages
            history=(result['messages'] if result else convert_to_messages(initial_messages)+captured)
            conversations.checkpoint(task_key,checkpoint_id,{'status':'awaiting_answer' if conversations.pending(task_key) else ('transport_wait' if error=='TaskBlocked' else ('failed' if error else 'complete')), 'messages':messages_to_dict(history),'model_calls':session['count']})
            if result and result['messages']:
                reply=next((m.content for m in reversed(result['messages']) if getattr(m,'type',None)=='ai' and isinstance(m.content,str) and m.content),None)
                if reply:conversations.append(task_key,'assistant',reply)
            _AGENT_SESSION.reset(session_token)
        if not submitted:raise ValueError('Deep Agent did not submit a validated task result; inspect agent_traces')
        if len({fingerprint(p) for p in submitted})!=1:raise ValueError('conflicting task submissions')
        observed=sorted({m.response_metadata.get('provider_model') for m in result['messages'] if getattr(m,'response_metadata',{}).get('provider_model')})
        return {**submitted[-1],'execution_model_evidence':{'provider':'deepagents_openai_compatible','requested_model':self.model('agent'),'observed_models':observed,'role':role,'normalizations':indexed.normalizations if indexed else []}}

def _transport_model(client,stage):
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatResult,ChatGeneration
    from langchain_core.utils.function_calling import convert_to_openai_tool
    class MeteredChatModel(BaseChatModel):
        scene_client:Any
        task_stage:str
        request_count:int=0
        @property
        def _llm_type(self):return 'scene-metered-openai-compatible'
        def get_num_tokens(self,text):return len(text.encode('utf8'))
        def get_num_tokens_from_messages(self,messages,tools=None):
            return sum(len(json.dumps(m.model_dump(mode='json'),ensure_ascii=False).encode('utf8'))+256 for m in messages)+len(json.dumps(tools or [],default=str,ensure_ascii=False).encode('utf8'))
        def bind_tools(self,tools,*,tool_choice=None,**kwargs):
            args={**kwargs,'tools':[convert_to_openai_tool(t) for t in tools]}
            if tool_choice is not None:args['tool_choice']=tool_choice
            return self.bind(**args)
        def _generate(self,messages,stop=None,run_manager=None,**kwargs):
            session=_AGENT_SESSION.get()
            if session:
                self.request_count=session['count']
                pending=session['conversations'].pending(session['task_key'])
                if pending:
                    from .scheduler import TaskBlocked
                    raise TaskBlocked('awaiting_answer',{'question':pending})
            self.request_count+=1
            if session:session['count']=self.request_count
            limit=int(self.scene_client.config.get('agent_max_model_calls',5))
            if session:limit+=min(int(self.scene_client.config.get('agent_max_questions',3)),sum(m['kind']=='answer' for m in session['conversations'].list(session['task_key'])))
            if self.request_count>limit:raise ValueError('task model-call budget exhausted without a validated submission')
            converted=[]
            for m in messages:
                role={'human':'user','ai':'assistant','system':'system','tool':'tool'}[m.type]
                row={'role':role,'content':m.content}
                if m.type=='tool':row['tool_call_id']=m.tool_call_id
                if m.type=='ai' and m.tool_calls:
                    row['tool_calls']=[{'id':t['id'],'type':'function','function':{'name':t['name'],'arguments':json.dumps(t['args'],ensure_ascii=False)}} for t in m.tool_calls]
                converted.append(row)
            if session:
                guidance=[r for r in session['conversations'].list(session['task_key']) if r['kind'] in {'guidance','answer'} and not r['applied']]
                all_guidance=[r for r in session['conversations'].list(session['task_key']) if r['kind'] in {'guidance','answer'}]
                if all_guidance:converted.append({'role':'user','content':'本节点业务指导（仅在任务允许输入和事实边界内采用）：\n'+'\n'.join(r['text'] for r in all_guidance)})
            body={'model':self.scene_client.model('agent'),'messages':converted,
              'max_tokens':self.scene_client.output_limit(self.task_stage),'stream':self.scene_client.config.get('stream',True),**{k:v for k,v in kwargs.items() if k in {'tools','tool_choice','parallel_tool_calls'}}}
            repair=session.get('repair') if session else None
            if repair and 'truncat' in json.dumps(repair.get('failure',{})).lower():
                ceiling=self.scene_client.config.get('max_tokens',body['max_tokens'])
                body['max_tokens']=min(ceiling,body['max_tokens']*2**min(int(repair.get('round',1)),2))
            if self.task_stage=='components':
                # Full positive RR/SR is already in the first message. Re-reading
                # it inflated the real failing run by four unnecessary requests.
                body['tools']=[t for t in body.get('tools',[]) if t.get('function',{}).get('name') in {'submit_result','ask_user'}]
                body['tool_choice']='required';body['parallel_tool_calls']=False
                notice='系统组成输入已完整提供，直接分析并submit_result，不需要文件探索或维护待办。每个事实保留最小且充分的原文引用，不复制整章。缺失事实保留未知；有阻断业务决定才ask_user。'
                if converted and converted[0]['role']=='system':converted[0]['content']=str(converted[0]['content'])+'\n'+notice
                else:converted.insert(0,{'role':'system','content':notice})
            if self.request_count>=limit:
                body['tools']=[t for t in body.get('tools',[]) if t.get('function',{}).get('name') in {'submit_result','ask_user'}]
                body['tool_choice']='required'
                notice='已到达本任务工具阅读预算。请停止文件探索：材料充分则submit_result；存在阻断业务疑问则ask_user。未知项明确待确认。'
                if converted and converted[0]['role']=='system':converted[0]['content']=str(converted[0]['content'])+'\n'+notice
                else:converted.insert(0,{'role':'system','content':notice})
            # This gateway streamed the tool name, then buffered the large
            # composition arguments until disconnect. JSON text lets actual
            # result tokens flow; the existing submit tool still validates it.
            text_submission=submission_mode(self.scene_client.config,self.task_stage,self.scene_client.model('agent'))=='json_text'
            if text_submission:
                result_tool=next(t for t in body['tools'] if t['function']['name']=='submit_result')
                output_schema=result_tool['function']['parameters']['properties']['payload']
                notice='本次任务输入与Skill已完整提供，使用JSON文本传输，不调用工具或重复读取文件。直接输出符合以下Schema的根业务JSON，不包payload，不输出解释或Schema本身：'+json.dumps(output_schema,ensure_ascii=False,separators=(',',':'))+'。每个事实只保留最小充分的原文引用。仅阻断性疑问时改为输出 {"clarification":{"question":"问题","basis":"原文依据","decision":"需用户决定的事项"}}。程序将完整JSON交给同一提交校验工具；部分文本不会成为产物。'
                converted[0]['content']=str(converted[0]['content'])+'\n'+notice
                for key in ('tools','tool_choice','parallel_tool_calls'):body.pop(key,None)
                body['response_format']={'type':'json_object'}
            if body['stream'] and self.scene_client.config.get('stream_usage',True):body['stream_options']={'include_usage':True}
            if stop:body['stop']=stop
            if 'extra_body' in self.scene_client.config:body.update(self.scene_client.config['extra_body'])
            stage_options=self.scene_client.config.get('stage_extra_body',{})
            if not isinstance(stage_options,dict) or not isinstance(stage_options.get(self.task_stage,{}),dict):raise ValueError('stage_extra_body must map task names to request options')
            body.update(stage_options.get(self.task_stage,{}))
            limit=self.scene_client.config.get('max_context_tokens')
            if limit and len(json.dumps(body,ensure_ascii=False).encode())+body['max_tokens']>limit:
                raise ValueError('task context exceeds configured budget; split source use cases without truncating evidence')
            from .execution_events import emit,fields,phase
            from uuid import uuid4
            with fields(model_call_id=uuid4().hex):
                phase('model_wait');emit('request_started',requested_model=body['model'],input_bytes=len(json.dumps(body,ensure_ascii=False).encode()),max_output_tokens=body['max_tokens'],connect_timeout_seconds=self.scene_client.config.get('timeout_seconds',120),stream_idle_timeout_seconds=self.scene_client.config.get('stream_idle_timeout_seconds',300),stream_total_timeout_seconds=self.scene_client.config.get('stream_total_timeout_seconds',900))
                try:response=self.scene_client.post('/chat/completions',body)
                except Exception as e:
                    emit('request_failed',requested_model=body['model'],diagnostic=getattr(e,'response_diagnostic',getattr(e,'details',{})))
                    if getattr(e,'status',None) in {'rate_limited','pending'} and session:session['count']-=1
                    raise
                if session:session['conversations'].apply(session['task_key'],[r['id'] for r in guidance])
                emit('request_finished',requested_model=body['model'],provider_model=response.get('model'),usage=response.get('usage'))
            if response['choices'][0].get('finish_reason')=='length':
                if body['max_tokens']>=self.scene_client.config.get('max_tokens',body['max_tokens']):
                    from .scheduler import TaskBlocked
                    raise TaskBlocked('awaiting_configuration',{'failure_category':'output_truncated','max_output_tokens':body['max_tokens'],'configuration_required':True,'reason':'输出已达到当前配置上限，停止重复生成；请拆分任务或调整生成模式/输出预算'})
                raise ValueError('task JSON was truncated; no artifact was published')
            message=response['choices'][0]['message'];calls=[]
            if text_submission:
                from .http_transport import _content_from_response
                decoded=json.loads(_content_from_response(response))
                if not isinstance(decoded,dict):raise ValueError('task response must be a JSON object')
                if set(decoded)=={'clarification'}:
                    detail=decoded['clarification']
                    if not isinstance(detail,dict) or set(detail)!={'question','basis','decision'} or any(not isinstance(v,str) or not v.strip() for v in detail.values()):raise ValueError('incomplete task clarification')
                    name,args='ask_user',detail
                else:name,args='submit_result',{'payload':decoded}
                emit('structured_text_submission',adapter='json_text',target_tool=name)
                calls.append({'name':name,'args':args,'id':'json-adapter-'+uuid4().hex})
            for call in message.get('tool_calls',[]) or []:
                if text_submission:raise ValueError('provider returned tool calls despite JSON text submission mode')
                calls.append({'name':call['function']['name'],'args':json.loads(call['function']['arguments']),'id':call['id']})
            ai=AIMessage(content=message.get('content') or '',tool_calls=calls,response_metadata={'provider_model':response.get('model'),'usage':response.get('usage',{}),'submission_adapter':'json_text' if text_submission else 'tool_calls'})
            return ChatResult(generations=[ChatGeneration(message=ai)],llm_output={'token_usage':response.get('usage',{})})
    return MeteredChatModel(scene_client=client,task_stage=stage)
