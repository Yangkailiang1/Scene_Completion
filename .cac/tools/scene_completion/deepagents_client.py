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

CHECKER_TASKS={'existing-extract','gap-compare','semantic-compare','test-ground-truth'}
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
        @tool
        def submit_result(payload:dict) -> str:
            """Validate and submit the task JSON. The payload must match output_schema exactly."""
            try:validate_result(packet['task'],payload,packet['input'])
            except ValueError as e:return '校验失败：'+str(e)
            submitted.append(payload);return '已通过校验。结束本任务，不再提交其他结果。'
        model=self.model_override or _transport_model(self,packet['task'])
        role_path=Path(__file__).resolve().parents[2]/'agents'/('scene-'+role+'.md')
        role_text=role_path.read_text(encoding='utf8')
        skill_name=packet['skill'];skill_path='/skills/'+skill_name+'/SKILL.md'
        now=datetime.now(timezone.utc).isoformat()
        file=lambda content:{'content':content.splitlines(),'created_at':now,'modified_at':now}
        # StateBackend has no route to local files; no original E or GT can leak
        # through a modeler tool even when a prompt-injected document requests it.
        agent=create_deep_agent(model=model,tools=[submit_result],subagents=[],backend=StateBackend(),
          skills=['/skills/'],system_prompt=role_text+'\n'+packet['instructions']+'\n先阅读指定Skill，再处理任务。使用submit_result提交；不得自行补造证据或把说明当文档事实。',
          permissions=[FilesystemPermission(paths=['/skills/**','/input/**'],operations=['write'],mode='deny')],name='scene-'+role)
        inputs={'messages':[{'role':'user','content':'执行'+packet['task']+'。完整任务包：\n'+json.dumps(packet,ensure_ascii=False)}],
            'files':{skill_path:file(packet['skill_text']),'/input/task.json':file(json.dumps(packet,ensure_ascii=False,indent=2))}}
        from langsmith import tracing_context
        with tracing_context(enabled=False):
            result=agent.invoke(inputs,config={'recursion_limit':int(self.config.get('agent_recursion_limit',24))})
        trace={'role':role,'task':packet['task'],'batch_id':packet['batch_id'],
               'messages':[m.model_dump(mode='json') for m in result['messages']]}
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
            converted=[]
            for m in messages:
                role={'human':'user','ai':'assistant','system':'system','tool':'tool'}[m.type]
                row={'role':role,'content':m.content}
                if m.type=='tool':row['tool_call_id']=m.tool_call_id
                if m.type=='ai' and m.tool_calls:
                    row['tool_calls']=[{'id':t['id'],'type':'function','function':{'name':t['name'],'arguments':json.dumps(t['args'],ensure_ascii=False)}} for t in m.tool_calls]
                converted.append(row)
            body={'model':self.scene_client.model('agent'),'messages':converted,
              'max_tokens':self.scene_client.output_limit(self.task_stage),**{k:v for k,v in kwargs.items() if k in {'tools','tool_choice','parallel_tool_calls'}}}
            if stop:body['stop']=stop
            if 'extra_body' in self.scene_client.config:body.update(self.scene_client.config['extra_body'])
            limit=self.scene_client.config.get('max_context_tokens')
            if limit and len(json.dumps(body,ensure_ascii=False).encode())+body['max_tokens']>limit:
                raise ValueError('task context exceeds configured budget; split source use cases without truncating evidence')
            response=self.scene_client.post('/chat/completions',body)
            message=response['choices'][0]['message'];calls=[]
            for call in message.get('tool_calls',[]):
                calls.append({'name':call['function']['name'],'args':json.loads(call['function']['arguments']),'id':call['id']})
            ai=AIMessage(content=message.get('content') or '',tool_calls=calls,response_metadata={'provider_model':response.get('model'),'usage':response.get('usage',{})})
            return ChatResult(generations=[ChatGeneration(message=ai)],llm_output={'token_usage':response.get('usage',{})})
    return MeteredChatModel(scene_client=client,task_stage=stage)
