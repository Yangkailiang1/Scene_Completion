"""Task-scoped Deep Agents roles using the existing metered model transport.

Every invocation gets a fresh virtual filesystem containing only its allowed
packet and Skill. No general shell, real project filesystem or cross-role memory.
"""
from pathlib import Path
from typing import Any
from datetime import datetime,timezone
import json
from copy import deepcopy
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

CHECKER_TASKS={'test-additional-concerns','existing-concerns','test-concerns','concern-compare','concern-evaluation','existing-branches','existing-bind','existing-extract','gap-compare','semantic-compare','test-ground-truth','test-supplement','test-additional-truth','test-additional-dedup','test-expanded','missing-report','exception-evaluation','extraction-evaluation'}
def role_for(task):
    if task in {'test-inventory','test-case-align'}:return 'checker'
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
            child=DeepAgentsClient(routed,model_override=self.model_override,transport=self._custom_transport)
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
        if packet.get('node_key'):write_json(self.root/'context_index'/(fingerprint(packet['node_key'])+'.json'),{'path':'model_contexts/'+context_id+'.json'})
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
            from .review_questions import report
            report(self.root.parent,task_key,packet['task'],event_context.get('case'),{'question':pending['text'],'required_answer':pending['detail']['decision'],'basis':pending['detail']['basis']},inputs=original_packet['input'])
            conversations.append(task_key,'question_deferred','历史提问已转为非阻断业务待确认项；这不是业务回答，未知事实仍须保留。',{'question_id':pending['detail']['question_id']})
        session={'task_key':task_key,'conversations':conversations,'count':saved.get('model_calls',0),'repair':packet.get('repair')}
        session_token=_AGENT_SESSION.set(session)
        def question_refs(refs):
            return [deepcopy(indexed.pool[r]) if indexed and isinstance(r,str) and r in indexed.pool else r for r in refs or []]
        def ask_user(question:str,basis:str,decision:str,question_type:str='general_clarification',interaction_id:str='unbound',source_refs:list[str|dict]|None=None)->str:
            from .review_questions import report
            if question_type=='general_clarification' and packet['task']=='normal-rules':question_type='rule_completion'
            q=report(self.root.parent,task_key,packet['task'],event_context.get('case'),{'question':question,'required_answer':decision,'known_facts':basis,'question_type':question_type,'interaction_id':interaction_id,'source_refs':question_refs(source_refs)},inputs=original_packet['input'])
            return '问题已保存为非阻断业务待确认项 '+q['id']+'。继续提交有依据的部分，未知部分写pending，不等待回答，不补造事实；不得仅提交问题而省略产物。'
        ask=StructuredTool.from_function(func=ask_user,name='ask_user',description='记录非阻断业务疑问，返回后继续提交已知结果。问题类型：rule_completion/scenario_classification/binding_confirmation/general_clarification。包含已有依据、待决定事项和精确引用；不暂停节点，不自行猜测。')
        def lookup_evidence(evidence_ids:list[str])->dict:
            if indexed is None:raise ValueError('this task has no indexed evidence')
            return indexed.lookup(evidence_ids)
        lookup=StructuredTool.from_function(func=lookup_evidence,name='lookup_evidence',description='仅按当前任务给定evidence_id补取原文依据，最多8条；不会访问其他任务、G/E/GT结果或本机文件。')

        from .execution_events import emit,phase
        from .scheduler import TaskRejected
        def submit(payload:dict,review_questions:list[dict]|None=None) -> str:
            from .review_questions import report
            from .model_submission import containers,questions
            try:
                containers(payload,packet['output_schema'])
                checked_questions=questions(review_questions)
                for question in checked_questions:
                    report(self.root.parent,task_key,original_packet['task'],event_context.get('case'),{**question,'source_refs':question_refs(question.get('source_refs',[]))},inputs=original_packet['input'])
            except (ValueError,KeyError,TypeError) as e:
                emit('validation_failed',error=str(e),phase='submission_envelope')
                rejection=self.root/'agent_rejections'/(fingerprint([packet['batch_id'],task_key,attempt,payload,review_questions,'submission'])+'.json')
                write_json(rejection,{'task':packet['task'],'node_key':task_key,'input_hash':fingerprint(original_packet['input']),'payload':payload,'review_questions':review_questions,'candidate_format':'model' if indexed else 'public','error':str(e)})
                raise TaskRejected({'error':str(e),'phase':'submission_envelope','rejected_output':str(rejection.relative_to(self.root))}) from e
            if indexed:
                try:payload=indexed.expand(payload)
                except (ValueError,KeyError,TypeError) as e:
                    emit('validation_failed',error=str(e))
                    rejection=self.root/'agent_rejections'/(fingerprint([packet['batch_id'],task_key,attempt,payload,'model-format'])+'.json')
                    write_json(rejection,{'task':packet['task'],'node_key':task_key,'input_hash':fingerprint(original_packet['input']),'payload':payload,'candidate_format':'model','error':str(e)})
                    raise TaskRejected({'error':str(e),'phase':'model_contract','rejected_output':str(rejection.relative_to(self.root))}) from e
            if packet['task']=='api-map':
                from .http_interfaces import normalize_mapping
                payload=normalize_mapping(payload)
            if packet['task']=='fused-ssd':
                from .use_cases import canonical_case_ids
                payload=canonical_case_ids(payload,packet['input'])
            if any(not r['applied'] for r in conversations.list(task_key) if r['kind'] in {'guidance','answer','context_resolution'}):
                emit('guidance_pending',message='新指导尚未进入本次请求，请下一轮模型调用后重新提交')
                return '用户在本次HTTP输出期间补充了指导；结果尚未保存。请在下一轮读取节点指导后提交。'
            if original_packet['task']=='test-supplement' and attempt>=3:
                from .test_supplement import quarantine_invalid_tests
                payload=quarantine_invalid_tests(payload,original_packet['input'])
                if payload.get('pending'):emit('test_candidates_quarantined',count=len(payload['pending']),reason='有界修复后仍不符合异常测试约束；候选保留待确认，不计入GT')
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
          args_schema={'title':'SubmitTaskResult','type':'object','properties':{'payload':packet['output_schema'],'review_questions':{'type':'array','maxItems':30,'items':{'type':'object','properties':{'question':{'type':'string','minLength':1},'required_answer':{'type':'string','minLength':1},'question_type':{'enum':['rule_completion','scenario_classification','binding_confirmation','general_clarification']},'known_facts':{'type':'string'},'interaction_id':{'type':'string'},'source_refs':{'type':'array','items':{'anyOf':[{'type':'string'},{'type':'object'}]}}},'required':['question','required_answer']}}},'required':['payload'],'additionalProperties':False})
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
        agent=create_deep_agent(model=model,middleware=[stop_after_submission],tools=[submit_result,ask,lookup],subagents=[],backend=StateBackend(),
          skills=['/skills/'] if packet['skill_text'].lstrip().startswith('---') else [],system_prompt=role_text+'\n'+packet['instructions']+'\n指定Skill已全文加载：\n'+packet['skill_text']+'\n以上Skill已加载，不需要再次读取。直接根据已给完整材料完成本任务，仅证据确有缺口时使用查阅工具。业务疑问用ask_user记录后继续提交有据的结果；未知内容写pending，不等待回答，不自行猜测。节点指导只对本任务生效，不能扩大任务允许的输入通道。使用submit_result提交；不得自行补造证据或把说明当文档事实。当前所需主要材料及精简索引已随用户消息提供，不反复读取大任务包；其余规则可按给定evidence_id使用lookup_evidence查证。原文行号也可在/input/sources/对应文件查证。限定工具阅读轮次；材料充分后立即提交，不为查找不存在的文件反复搜索。',
          permissions=[FilesystemPermission(paths=['/skills/**','/input/**'],operations=['write'],mode='deny')],name='scene-'+role)
        inputs={'messages':[{'role':'user','content':task_message(packet)}],
            'files':{skill_path:file(packet['skill_text']),'/input/task.json':file(json.dumps(packet,ensure_ascii=False,indent=2)),**{path:file(text) for path,text in task_files(packet).items()}}}
        if self.config.get('reasoning_replay') and saved.get('messages'):
            emit('resume_context_restarted',reason='网关要求的思考上下文仅保留于内存；恢复时使用原任务和已有指导，保留累计调用预算')
        if not self.config.get('reasoning_replay') and saved.get('status') in {'awaiting_answer','transport_wait'} and saved.get('messages'):
            from langchain_core.messages import messages_from_dict,messages_to_dict,ToolMessage
            inputs['messages']=messages_from_dict(saved['messages'])
            last=inputs['messages'][-1]
            if getattr(last,'tool_calls',None):
                for call in last.tool_calls:
                    inputs['messages'].append(ToolMessage(content='节点已恢复。业务疑问可能仅被转为非阻断问题，并不代表用户已经回答；请使用实际已给指导，未知内容仍保留待确认，继续提交已知部分。',tool_call_id=call['id']))
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
            def audit_write(path,value):
                try:write_json(path,value)
                except OSError as io_error:emit('artifact_io_failed',diagnostic=getattr(io_error,'response_diagnostic',{}),original_error_type=error,reason='审计轨迹保存失败；保留原模型/校验错误，不替换为审计写入错误')
            audit_write(self.root/'agent_traces'/(packet['batch_id']+'.json'),trace)
            from uuid import uuid4
            audit_write(self.root/'agent_trace_history'/(packet['batch_id'][:24]+'-'+uuid4().hex[:12]+'.json'),trace)
            from langchain_core.messages import messages_to_dict,convert_to_messages
            history=(result['messages'] if result else convert_to_messages(initial_messages)+captured)
            checkpoint_value={'status':'awaiting_answer' if conversations.pending(task_key) else ('transport_wait' if error=='TaskBlocked' else ('failed' if error else 'complete')), 'messages':messages_to_dict(history),'model_calls':session['count']}
            try:conversations.checkpoint(task_key,checkpoint_id,checkpoint_value)
            except OSError as io_error:emit('artifact_io_failed',diagnostic=getattr(io_error,'response_diagnostic',{}),original_error_type=error,reason='恢复点保存失败，未覆盖原任务错误')
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
    from pydantic import Field
    class MeteredChatModel(BaseChatModel):
        scene_client:Any
        task_stage:str
        request_count:int=0
        reasoning_history:dict=Field(default_factory=dict,exclude=True)
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
            self.request_count+=1
            if session:session['count']=self.request_count
            limit=int(self.scene_client.config.get('agent_max_model_calls',5))
            if session:limit+=min(int(self.scene_client.config.get('agent_max_questions',3)),sum(m['kind'] in {'answer','context_resolution'} for m in session['conversations'].list(session['task_key'])))
            if self.request_count>limit:raise ValueError('task model-call budget exhausted without a validated submission')
            converted=[]
            for m in messages:
                role={'human':'user','ai':'assistant','system':'system','tool':'tool'}[m.type]
                row={'role':role,'content':m.content}
                if m.type=='tool':row['tool_call_id']=m.tool_call_id
                if m.type=='ai' and m.tool_calls:
                    row['tool_calls']=[{'id':t['id'],'type':'function','function':{'name':t['name'],'arguments':json.dumps(t['args'],ensure_ascii=False)}} for t in m.tool_calls]
                if role=='assistant' and self.scene_client.config.get('reasoning_replay') and m.id in self.reasoning_history:row['reasoning_content']=self.reasoning_history[m.id]
                converted.append(row)
            if session:
                guidance=[r for r in session['conversations'].list(session['task_key']) if r['kind'] in {'guidance','answer','context_resolution'} and not r['applied']]
                all_guidance=[r for r in session['conversations'].list(session['task_key']) if r['kind'] in {'guidance','answer','context_resolution'}]
                if all_guidance:converted.append({'role':'user','content':'本节点指导及明确标注的系统依据补充（后者不是用户新决定；仅在任务允许输入和事实边界内采用）：\n'+'\n'.join(r['text'] for r in all_guidance)})
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
                notice='系统组成输入已完整提供，直接分析并submit_result，不需要文件探索或维护待办。每个事实保留最小且充分的原文引用，不复制整章。缺失事实保留未知；业务疑问用ask_user记录后继续提交有据部分。'
                if converted and converted[0]['role']=='system':converted[0]['content']=str(converted[0]['content'])+'\n'+notice
                else:converted.insert(0,{'role':'system','content':notice})
            if self.request_count>=limit:
                body['tools']=[t for t in body.get('tools',[]) if t.get('function',{}).get('name') in {'submit_result','ask_user'}]
                body['tool_choice']='required'
                notice='已到达本任务工具阅读预算。请停止文件探索：提交有据部分；业务疑问用ask_user记录后继续submit_result，未知项明确待确认。'
                if converted and converted[0]['role']=='system':converted[0]['content']=str(converted[0]['content'])+'\n'+notice
                else:converted.insert(0,{'role':'system','content':notice})
            # This gateway streamed the tool name, then buffered the large
            # composition arguments until disconnect. JSON text lets actual
            # result tokens flow; the existing submit tool still validates it.
            text_submission=submission_mode(self.scene_client.config,self.task_stage,self.scene_client.model('agent'))=='json_text'
            if text_submission:
                result_tool=next(t for t in body['tools'] if t['function']['name']=='submit_result')
                output_schema=result_tool['function']['parameters']['properties']['payload']
                notice='本次任务输入与Skill已提供，使用JSON文本传输，不重复读取大文件。直接输出符合以下Schema的根业务JSON，不包payload，不输出解释或Schema本身：'+json.dumps(output_schema,ensure_ascii=False,separators=(',',':'))+'。每个事实只保留最小充分的原文引用。业务疑问不阻断；需要提问时仍提交已知结果，使用 {"result":业务JSON,"review_questions":[{"question_type":"rule_completion或scenario_classification或binding_confirmation或general_clarification","question":"问题","known_facts":"已有依据","required_answer":"需业务决定事项","source_refs":[]}]}。未知内容不能编造，不可只返回问题。程序将完整JSON交给同一提交校验工具；部分文本不会成为产物。'
                if self.request_count<limit and self.task_stage in {'existing-extract','test-ground-truth'}:notice+='若已给材料确有缺口，可输出 {"evidence_request":["当前任务给定的evidence_id"]} 按需查证，最多8条；其后仍须提交完整结果，不得用未知ID或读取其他渠道。'
                converted[0]['content']=str(converted[0]['content'])+'\n'+notice
                for key in ('tools','tool_choice','parallel_tool_calls'):body.pop(key,None)
                body['response_format']={'type':'json_object'}
            if body['stream'] and self.scene_client.config.get('stream_usage',True):body['stream_options']={'include_usage':True}
            if stop:body['stop']=stop
            from .runtime_settings import request_options,output_limit,request_diagnostic
            body=request_options(body,self.scene_client.config,self.task_stage)
            from .context_budget import check
            context_bound=check(body,self.scene_client.config)
            from .execution_events import emit,fields,phase
            from uuid import uuid4
            with fields(model_call_id=uuid4().hex):
                phase('model_wait');emit('request_started',account_id=fingerprint(self.scene_client.api_key)[:12],account=self.scene_client.config.get('account_label','账号-'+fingerprint(self.scene_client.api_key)[:8]),requested_model=body['model'],context_budget=context_bound,input_bytes=len(json.dumps(body,ensure_ascii=False).encode()),max_output_tokens=output_limit(body),request_parameters=request_diagnostic(body),reasoning_display_enabled=self.scene_client.config.get('stream_reasoning',False),connect_timeout_seconds=self.scene_client.config.get('timeout_seconds',120),stream_idle_timeout_seconds=self.scene_client.config.get('stream_idle_timeout_seconds',300),stream_total_timeout_seconds=self.scene_client.config.get('stream_total_timeout_seconds',900))
                try:response=self.scene_client.post('/chat/completions',body)
                except Exception as e:
                    emit('request_failed',requested_model=body['model'],diagnostic=getattr(e,'response_diagnostic',getattr(e,'details',{})))
                    if getattr(e,'status',None) in {'rate_limited','pending'} and session:session['count']-=1
                    raise
                if session:session['conversations'].apply(session['task_key'],[r['id'] for r in guidance])
                emit('request_finished',requested_model=body['model'],provider_model=response.get('model'),usage=response.get('usage'),diagnostic=request_diagnostic(body,response))
            if request_diagnostic(body,response)['thinking_control_status']=='disabled_requested_but_reasoning_returned':
                emit('stream_status',status='thinking_disable_not_observed',message='已向网关请求关闭思考，但仍收到reasoning_content；关闭尚未生效，请核对网关参数或模型能力。')
            if response['choices'][0].get('finish_reason')=='length':
                if output_limit(body)>=max(self.scene_client.config.get('max_tokens',output_limit(body)),self.scene_client.output_limit(self.task_stage)):
                    from .scheduler import TaskBlocked
                    raise TaskBlocked('awaiting_configuration',{'failure_category':'output_truncated',**request_diagnostic(body,response),'configuration_required':True,'reason':'finish_reason=length；思考与正文可能共用输出预算。请用CLI config/diagnose查看并调整max_tokens、思考参数或拆分任务，不发布残缺JSON'})
                error=ValueError('task JSON was truncated; no artifact was published')
                error.response_diagnostic={'failure_category':'output_truncated',**request_diagnostic(body,response)}
                raise error
            message=response['choices'][0]['message'];calls=[]
            def decode_json(text):
                try:return json.loads(text)
                except (json.JSONDecodeError,TypeError) as e:
                    e.response_diagnostic={'failure_category':'invalid_result_json',**request_diagnostic(body,response),'json_line':getattr(e,'lineno',None),'json_column':getattr(e,'colno',None)}
                    emit('response_invalid',diagnostic=e.response_diagnostic)
                    raise
            if text_submission:
                from .http_transport import _content_from_response
                decoded=decode_json(_content_from_response(response))
                if not isinstance(decoded,dict):raise ValueError('task response must be a JSON object')
                if set(decoded)=={'clarification'}:
                    detail=decoded['clarification']
                    if not isinstance(detail,dict) or set(detail)!={'question','basis','decision'} or any(not isinstance(v,str) or not v.strip() for v in detail.values()):raise ValueError('incomplete task clarification')
                    name,args='ask_user',detail
                elif set(decoded)=={'evidence_request'}:
                    if self.request_count>=limit:raise ValueError('evidence lookup budget exhausted')
                    name,args='lookup_evidence',{'evidence_ids':decoded['evidence_request']}
                elif 'result' in decoded and set(decoded)<={'result','review_questions'}:
                    name,args='submit_result',{'payload':decoded['result'],'review_questions':decoded.get('review_questions',[])}
                else:name,args='submit_result',{'payload':decoded}
                emit('structured_text_submission',adapter='json_text',target_tool=name)
                calls.append({'name':name,'args':args,'id':'json-adapter-'+uuid4().hex})
            for call in message.get('tool_calls',[]) or []:
                if text_submission:raise ValueError('provider returned tool calls despite JSON text submission mode')
                calls.append({'name':call['function']['name'],'args':decode_json(call['function']['arguments']),'id':call['id']})
            message_id='scene-response-'+uuid4().hex
            if self.scene_client.config.get('reasoning_replay') and message.get('reasoning_content') is not None:self.reasoning_history[message_id]=message['reasoning_content']
            ai=AIMessage(id=message_id,content=message.get('content') or '',tool_calls=calls,response_metadata={'provider_model':response.get('model'),'usage':response.get('usage',{}),'submission_adapter':'json_text' if text_submission else 'tool_calls'})
            return ChatResult(generations=[ChatGeneration(message=ai)],llm_output={'token_usage':response.get('usage',{})})
    return MeteredChatModel(scene_client=client,task_stage=stage)
