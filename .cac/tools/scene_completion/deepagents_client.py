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

def task_files(packet):
    from .source_documents import documents_in
    files={}
    for doc in documents_in(packet['input']):
        path='/input/sources/'+fingerprint(doc['source_id'])[:16]+'.txt'
        files[path]='source_id='+doc['source_id']+'\n'+'\n'.join(str(line['number'])+' | '+line['text'] for line in doc['lines'])
    return files

CHECKER_TASKS={'existing-extract','gap-compare','semantic-compare','test-ground-truth','missing-report','exception-evaluation','extraction-evaluation'}
def role_for(task):
    if task=='gap-recommend':return 'recommender'
    return 'checker' if task in CHECKER_TASKS else 'modeler'

class DeepAgentsClient(SemanticClient):
    def __init__(self,config,*,model_override=None,transport=None):
        super().__init__(config,transport)
        self.model_override=model_override
        self.root=Path(config.get('run_root','runs/deepagents'))
    def agent(self,packet):
        from deepagents import create_deep_agent
        from deepagents.backends import StateBackend
        from deepagents.middleware.filesystem import FilesystemPermission
        from langchain_core.tools import tool
        from .validation import validate_result
        role=role_for(packet['task'])
        if role=='recommender':return {'enabled':False,'status':'未启用'}
        submitted=[]
        from langchain_core.tools import StructuredTool
        from .execution_events import emit,phase
        from .scheduler import TaskRejected
        def submit(payload:dict) -> str:
            phase('validating')
            try:validate_result(packet['task'],payload,packet['input'])
            except ValueError as e:
                emit('validation_failed',error=str(e))
                raise TaskRejected({'error':str(e),'phase':'validation','instruction':'由任务执行器使用剩余修复预算定向修复'}) from e
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
        agent=create_deep_agent(model=model,middleware=[stop_after_submission],tools=[submit_result],subagents=[],backend=StateBackend(),
          skills=['/skills/'],system_prompt=role_text+'\n'+packet['instructions']+'\n先阅读指定Skill，再处理任务。使用submit_result提交；不得自行补造证据或把说明当文档事实。完整input已经随用户消息提供，不需要反复读取大任务包。原文行号可在/input/sources/对应文件查证。限定工具阅读轮次；材料充分后立即提交，不为查找不存在的文件反复搜索。',
          permissions=[FilesystemPermission(paths=['/skills/**','/input/**'],operations=['write'],mode='deny')],name='scene-'+role)
        inputs={'messages':[{'role':'user','content':'执行'+packet['task']+'。完整任务包：\n'+json.dumps(packet,ensure_ascii=False)}],
            'files':{skill_path:file(packet['skill_text']),'/input/task.json':file(json.dumps(packet,ensure_ascii=False,indent=2)),**{path:file(text) for path,text in task_files(packet).items()}}}
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
        if not submitted:raise ValueError('Deep Agent did not submit a validated task result; inspect agent_traces')
        if len({fingerprint(p) for p in submitted})!=1:raise ValueError('conflicting task submissions')
        observed=sorted({m.response_metadata.get('provider_model') for m in result['messages'] if getattr(m,'response_metadata',{}).get('provider_model')})
        return {**submitted[-1],'execution_model_evidence':{'provider':'deepagents_openai_compatible','requested_model':self.model('agent'),'observed_models':observed,'role':role}}

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
            self.request_count+=1
            limit=int(self.scene_client.config.get('agent_max_model_calls',5))
            if self.request_count>limit:raise ValueError('task model-call budget exhausted without a validated submission')
            converted=[]
            for m in messages:
                role={'human':'user','ai':'assistant','system':'system','tool':'tool'}[m.type]
                row={'role':role,'content':m.content}
                if m.type=='tool':row['tool_call_id']=m.tool_call_id
                if m.type=='ai' and m.tool_calls:
                    row['tool_calls']=[{'id':t['id'],'type':'function','function':{'name':t['name'],'arguments':json.dumps(t['args'],ensure_ascii=False)}} for t in m.tool_calls]
                converted.append(row)
            body={'model':self.scene_client.model('agent'),'messages':converted,
              'max_tokens':self.scene_client.output_limit(self.task_stage),'stream':self.scene_client.config.get('stream',True),**{k:v for k,v in kwargs.items() if k in {'tools','tool_choice','parallel_tool_calls'}}}
            if self.request_count>=limit:
                body['tool_choice']={'type':'function','function':{'name':'submit_result'}}
                notice='已到达本任务工具阅读预算。请立即根据现有允许材料调用submit_result提交产物；未知项明确待确认，不再探索文件。'
                if converted and converted[0]['role']=='system':converted[0]['content']=str(converted[0]['content'])+'\n'+notice
                else:converted.insert(0,{'role':'system','content':notice})
            if body['stream'] and self.scene_client.config.get('stream_usage',True):body['stream_options']={'include_usage':True}
            if stop:body['stop']=stop
            if 'extra_body' in self.scene_client.config:body.update(self.scene_client.config['extra_body'])
            limit=self.scene_client.config.get('max_context_tokens')
            if limit and len(json.dumps(body,ensure_ascii=False).encode())+body['max_tokens']>limit:
                raise ValueError('task context exceeds configured budget; split source use cases without truncating evidence')
            from .execution_events import emit,fields,phase
            from uuid import uuid4
            with fields(model_call_id=uuid4().hex):
                phase('model_wait');emit('request_started',requested_model=body['model'])
                response=self.scene_client.post('/chat/completions',body)
                emit('request_finished',requested_model=body['model'],provider_model=response.get('model'),usage=response.get('usage'))
            message=response['choices'][0]['message'];calls=[]
            for call in message.get('tool_calls',[]) or []:
                calls.append({'name':call['function']['name'],'args':json.loads(call['function']['arguments']),'id':call['id']})
            ai=AIMessage(content=message.get('content') or '',tool_calls=calls,response_metadata={'provider_model':response.get('model'),'usage':response.get('usage',{})})
            return ChatResult(generations=[ChatGeneration(message=ai)],llm_output={'token_usage':response.get('usage',{})})
    return MeteredChatModel(scene_client=client,task_stage=stage)
