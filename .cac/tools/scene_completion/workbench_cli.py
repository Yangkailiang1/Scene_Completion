"""Code-agent friendly client of the same local workbench API; JSON/JSONL only."""
import argparse,json,sys,time,urllib.request,urllib.error,urllib.parse,base64,getpass
from pathlib import Path

class API:
    def __init__(self,server):
        p=urllib.parse.urlsplit(server)
        if p.scheme not in ('http','https') or p.username or p.password or p.query or p.fragment or p.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('CLI仅连接本机工作台；请使用http://127.0.0.1:8765')
        self.server=server.rstrip('/')
    def call(self,path,body=None,method=None):
        request=urllib.request.Request(self.server+'/api/'+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=60) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            try:detail=json.loads(e.read()).get('detail','操作失败')
            except (ValueError,AttributeError):detail='操作失败'
            raise ValueError(f'工作台HTTP {e.code}: {detail}') from None
        except urllib.error.URLError:raise ValueError('无法连接本机工作台，请先启动serve.py并保持运行') from None

def output(value):print(json.dumps(value,ensure_ascii=False),flush=True)

def parser():
    p=argparse.ArgumentParser(description='让Code Agent操作同一网页工作台；输出JSON或JSONL，不另建隐藏运行目录。');p.add_argument('--server',default='http://127.0.0.1:8765');sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('projects');create=sub.add_parser('create');create.add_argument('--name',required=True)
    for role in ('rr','sr','test'):create.add_argument('--'+role,action='append',required=role!='test',default=[])
    create.add_argument('--mode',choices=('manual','auto'),default='manual');create.add_argument('--case',action='append',default=[])
    accounts=sub.add_parser('accounts')
    save=sub.add_parser('save-account');save.add_argument('--id');save.add_argument('--name',required=True);save.add_argument('--base-url',required=True);save.add_argument('--model',action='append',required=True);group=save.add_mutually_exclusive_group();group.add_argument('--api-key-env');group.add_argument('--prompt-key',action='store_true',help='终端隐藏输入API Key；密钥不进入命令历史')
    for cmd in ('status','artifacts','run','events','configure','config','diagnose','repair-export','repair-submit','rerun','guide','answer'):
        a=sub.add_parser(cmd);a.add_argument('--project',required=True)
        if cmd=='run':a.add_argument('--wait',action='store_true');a.add_argument('--mode',choices=('manual','auto'));a.add_argument('--timeout',type=float,default=3600);a.add_argument('--poll',type=float,default=2)
        if cmd=='events':a.add_argument('--after',type=int,default=0);a.add_argument('--node');a.add_argument('--limit',type=int,default=200)
        if cmd in ('config','diagnose'):
            a.add_argument('--node');a.add_argument('--task',default='agent');a.add_argument('--limit',type=int,default=20)
        if cmd in ('repair-export','repair-submit'):
            a.add_argument('--node',required=True)
            if cmd=='repair-export':a.add_argument('--out',required=True)
            else:a.add_argument('--file',required=True);a.add_argument('--validate-only',action='store_true')
        if cmd=='rerun':a.add_argument('--node',required=True);a.add_argument('--text',default='按已更新的模型配置重新执行当前节点')
        if cmd=='configure':
            a.add_argument('--account');a.add_argument('--model');a.add_argument('--concurrency',type=int);a.add_argument('--config-file',help='运行参数JSON，不接受凭证或配额账本修改');a.add_argument('--preset',choices=('deepseek-thinking',));a.add_argument('--dry-run',action='store_true')
            for flag,key in [('max-output-tokens','max_tokens'),('max-context-tokens','max_context_tokens'),('connect-timeout','timeout_seconds'),('idle-timeout','stream_idle_timeout_seconds'),('total-timeout','stream_total_timeout_seconds'),('max-model-calls','agent_max_model_calls')]:a.add_argument(*(['--max-output-tokens','--max-tokens','--maxtokens'] if flag=='max-output-tokens' else ['--'+flag]),dest=key,type=int)
            a.add_argument('--thinking',choices=('auto','on','off'));a.add_argument('--thinking-api',choices=('legacy','enable_thinking','omit'));a.add_argument('--reasoning-effort');a.add_argument('--thinking-budget',type=int)
            a.add_argument('--submission-mode',choices=('tool_calls','json_text'));a.add_argument('--max-tokens-parameter',choices=('max_tokens','max_completion_tokens'));a.add_argument('--stage-output',action='append',default=[],metavar='TASK=TOKENS')
            for flag in ('stream','stream-usage','send-reasoning-effort','supports-tool-choice','supports-parallel-tool-calls','reasoning-replay','json-response-format'):a.add_argument('--'+flag,action=argparse.BooleanOptionalAction,default=None)

        if cmd in ('guide','answer'):a.add_argument('--node',required=True);a.add_argument('--text',required=True)
        if cmd=='answer':a.add_argument('--question',required=True)
    return p

def main(argv=None,client=None):
    args=parser().parse_args(argv);api=client or API(args.server)
    if args.command=='projects':output(api.call('projects'));return 0
    if args.command=='accounts':output(api.call('model-accounts'));return 0
    if args.command=='save-account':
        accounts=api.call('model-accounts');body={'expected_revision':accounts['revision'],'name':args.name,'base_url':args.base_url,'models':args.model}
        if args.id:body['id']=args.id
        if args.api_key_env:body['api_key_env']=args.api_key_env
        if args.prompt_key:body['api_key']=getpass.getpass('API Key（隐藏输入）: ')
        output(api.call('model-accounts',body,'PUT'));return 0
    if args.command=='create':
        sources={}
        for role in ('rr','sr','test'):
            sources['test' if role=='test' else role.upper()]=[]
            for name in getattr(args,role):
                file=Path(name);row={'name':file.name}
                if file.suffix.lower()=='.xlsx' and role=='test':row['content_base64']=base64.b64encode(file.read_bytes()).decode()
                else:row['content']=file.read_text(encoding='utf-8-sig')
                sources['test' if role=='test' else role.upper()].append(row)
        output(api.call('projects',{'name':args.name,'sources':sources,'review_mode':args.mode,'case_ids':args.case}));return 0
    rid=args.project
    if len(rid)!=32 or any(c not in '0123456789abcdef' for c in rid):raise ValueError('项目ID必须是工作台返回的32位ID')
    path='projects/'+rid
    if args.command=='repair-export':
        value=api.call(path+'/node-repair?'+urllib.parse.urlencode({'task_key':args.node}));target=Path(args.out);target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');output({'saved_to':str(target),'task_key':args.node,'note':'包含本节点业务材料，保留本地，不提交Git'});return 0
    if args.command=='repair-submit':
        value=json.loads(Path(args.file).read_text(encoding='utf-8-sig'));output(api.call(path+'/node-repair',{'task_key':args.node,'repair':value,'validate_only':args.validate_only}));return 0
    if args.command in ('config','diagnose'):
        query=urllib.parse.urlencode({**({'task_key':args.node} if args.node else {'task':args.task}),**({'limit':args.limit} if args.command=='diagnose' else {})})
        output(api.call(path+('/diagnostics' if args.command=='diagnose' else '/config')+'?'+query));return 0
    if args.command=='rerun':output(api.call(path+'/rerun-node',{'task_key':args.node,'text':args.text}));return 0
    if args.command=='configure':
        from .runtime_settings import KEYS,validate_options,PRESETS
        body=json.loads(Path(args.config_file).read_text(encoding='utf-8-sig')) if args.config_file else {}
        if not isinstance(body,dict) or set(body)-KEYS:raise ValueError('配置文件只接受运行参数；凭证用save-account，配额账本保持不变')
        if args.preset:body={**PRESETS[args.preset],**body};body['preset']=args.preset
        for arg,key in [('account','model_account_id'),('model','agent_model'),('concurrency','max_concurrency')]+[(k,k) for k in KEYS if k not in {'thinking','stage_max_tokens','extra_body','stage_extra_body','task_models','role_models','model_profiles'}]:
            v=getattr(args,arg,None)
            if v is not None:body[key]=v
        if args.thinking:body['thinking']={'auto':None,'on':True,'off':False}[args.thinking]
        if args.reasoning_effort is not None:body['send_reasoning_effort']=args.reasoning_effort!='omit';body['reasoning_effort']=args.reasoning_effort if args.reasoning_effort!='omit' else 'high'
        if args.stage_output:
            rules=dict(body.get('stage_max_tokens',{}))
            for item in args.stage_output:
                k,sep,v=item.partition('=')
                if not sep or not k or not v.isdecimal():raise ValueError('--stage-output格式为TASK=TOKENS')
                rules[k]=int(v)
            body['stage_max_tokens']=rules
        if not body:output(api.call(path+'/config'));return 0
        if args.dry_run:
            current=api.call(path+'/config')['settings'];merged={**current,**{k:v for k,v in body.items() if k!='preset'}}
            validate_options(merged);output({'dry_run':True,'changes':body,'notes':['仅校验参数，不保存、不调用模型；完整账号/路由及真实请求预算由服务端保存/执行时再次校验。']});return 0
        output(api.call(path+'/config',body,'PUT'));return 0

    if args.command=='guide':output(api.call(path+'/conversation',{'task_key':args.node,'text':args.text}));return 0
    if args.command=='answer':output(api.call(path+'/answer',{'task_key':args.node,'question_id':args.question,'text':args.text}));return 0
    if args.command=='events':
        query=urllib.parse.urlencode({'after':args.after,'limit':args.limit,**({'task_key':args.node} if args.node else {})});output(api.call(path+'/events/history?'+query));return 0
    if args.command=='status':output(api.call(path+'/execution-status'));return 0
    if args.command=='artifacts':output({'project':rid,'artifacts':api.call(path)['artifacts'],'catalog':api.call(path+'/results')});return 0
    if args.command=='run':
        if args.timeout<=0 or not .2<=args.poll<=60:raise ValueError('timeout需为正数，poll范围0.2至60秒')
        if args.mode:api.call(path+'/mode',{'review_mode':args.mode},'PUT')
        # Begin at current cursor, not a replay of every historical token.
        current=api.call(path+'/execution-status');cursor=current['event_cursor']
        value=api.call(path+'/run',{});output({'kind':'started',**value});prior=rid;rid=value['project_id'];path='projects/'+rid
        if rid!=prior:cursor=0
        if not args.wait:return 0
        deadline=time.monotonic()+args.timeout;previous=None
        while True:
            events=api.call(path+'/events/history?'+urllib.parse.urlencode({'after':cursor,'limit':200}))['events']
            for event in events:cursor=max(cursor,event['id']);output({'kind':'execution_event','project':rid,'event_cursor':cursor,'event':event})
            value=api.call(path+'/execution-status');signature=json.dumps(value,sort_keys=True)
            if signature!=previous:output({'kind':'status',**value});previous=signature
            if value['job']['status']!='running':
                output({'kind':'finished',**value,'web_url':api.server if hasattr(api,'server') else args.server});return 0 if value['complete'] else 2
            if time.monotonic()>=deadline:output({'kind':'detached','project':rid,'reason':'CLI等待超时；服务端运行继续，可在网页查看或再次status/events'});return 3
            time.sleep(args.poll)
    raise ValueError('unsupported command')

def entry():
    try:return main()
    except (ValueError,OSError) as e:output({'error':str(e)});return 2
